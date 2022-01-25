#!/usr/bin/env python3

import logging
import paramiko
import warnings
from pathlib import Path
from paramiko.client import SSHClient, AutoAddPolicy

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)-5s %(name)s %(message)s')

logger = logging.getLogger(__file__.split('/')[-1])

warnings.filterwarnings(
    'ignore', message='Unverified HTTPS request')


class RetrieveDOI:
    """Retrieve DOI containing files form dspace server"""

    def __init__(self, configparser) -> None:
        self.load_config(configparser)
        self.client = None

    def load_config(self, configparser) -> None:
        s = configparser['scp']
        ds = configparser['dspace']
        e = configparser['export']
        self.doi_path = ds['server_doifiles']
        self.export_path = e['export_path']
        # scp needed
        self.server = s['server']
        self.user = s['user']
        self.key_filename = s['key_filename']

    def get_client(self) -> SSHClient:
        try:
            transport = self.client.get_transport()
            transport.send_ignore()
            return self.client
        except (AttributeError, EOFError):
            # connection is closed, reconnect
            logger.info(f'connect ssh {self.server}')
        client = paramiko.SSHClient()
        client.load_system_host_keys()
        client.set_missing_host_key_policy(AutoAddPolicy())
        try:
            client.connect(
                self.server,
                username=self.user,
                key_filename=self.key_filename)
        except Exception as err:
            logger.error(err)
            logger.info(f"is sshd running on {self.server}?")
            return None
        self.client = client
        return client

    def determine_done(self) -> list:
        files = list(Path(self.export_path).iterdir())
        donelist = []
        for f in files:
            if f.name.endswith('doi'):
                donelist.append(f.name)
            if f.name.endswith('doi.done'):
                donelist.append(f.name[:-5])
        return donelist

    def retrieve_files(self, already_processed=[]) -> None:
        client = self.get_client()
        count_done = 0
        count = 0
        if client is not None:
            with client.open_sftp() as ftp_client:
                export_path = self.export_path
                try:
                    doifiles = ftp_client.listdir(self.doi_path)
                except FileNotFoundError as err:
                    logger.error(f'{self.doi_path} not found remote, {err}')
                    exit()
                if not doifiles:
                    logger.info("no new DOI files")
                for doifile in doifiles:
                    if doifile in already_processed:
                        count_done += 1
                        continue
                    count += 1
                    ftp_client.get(
                        f"{self.doi_path}/{doifile}",
                        f"{export_path}/{doifile}"
                        )
                    logger.info(f"got file --> {doifile}")
            if count_done > 0:
                logger.info(f"{count_done} DOI files already processed")
            client.close()
            logger.info(f'{count} DOI files copied')

    def copy(self) -> dict:
        saf_files = self.get_files()
        self.copy_files(saf_files)
