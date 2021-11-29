#!/usr/bin/env python3

import logging
import paramiko
from paramiko.client import SSHClient

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)-5s %(name)s %(message)s')

logger = logging.getLogger(__file__.split('/')[-1])


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
        try:
            client.connect(
                self.server,
                username=self.user,
                key_filename=self.key_filename)
        except Exception as err:
            logger.error(err)
            return None
        self.client = client
        return client

    def retrieve_files(self) -> None:
        client = self.get_client()
        if client is not None:
            with client.open_sftp() as ftp_client:
                # logger.info(f'transfer file {file_}')
                # logger.info(f"target: '{self.server_source}/{file_.name}")
                export_path = self.export_path
                doifiles = ftp_client.listdir(self.doi_path)
                if not doifiles:
                    logger.info("no new doi files")
                for doifile in doifiles:
                    ftp_client.get(
                        f"{self.doi_path}/{doifile}", f"{export_path}/{doifile}")
                    logger.info(f"got file --> {doifile}")    
            client.close()
            logger.info('copy done...')

    def copy(self) -> dict:
        saf_files = self.get_files()
        self.copy_files(saf_files)
