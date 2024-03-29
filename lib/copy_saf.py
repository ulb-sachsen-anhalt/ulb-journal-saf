#!/usr/bin/env python3

import logging
import paramiko
from pathlib import Path
from paramiko.client import SSHClient, AutoAddPolicy


logger = logging.getLogger('journals-logging-handler')


class CopySAF:
    """Copy SAF-zip files to dspace server via scp"""

    def __init__(self, configparser, report) -> None:
        self.load_config(configparser)
        self.client = None
        self.report = report

    def load_config(self, configparser) -> None:
        s = configparser['scp']
        ds = configparser['dspace']
        e = configparser['export']
        self.export_path = e['export_path']
        # scp needed
        self.server = s['server']
        self.user = s['user']
        self.key_filename = s['key_filename']

        self.server_source = ds['server_zipsource']

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
            self.report.add('ERROR', err)
            return None
        self.client = client
        return client

    def get_files(self) -> list:
        export_path = Path(self.export_path)
        saf_files = []
        if export_path.exists():
            export = Path(self.export_path).glob('*.zip')
            for zip in export:
                zipfile = zip.absolute()
                saf_files.append(zipfile)
        return saf_files

    def transferobserver(self, transferred, total):
        if transferred == total:
            print(f'  transfer done (total: {total >> 20} Mb)')
        self.observer_count += 1
        if self.observer_count % 100 == 0:
            print('.', end="")

    def copy_files(self, files: list) -> None:
        if len(files) == 0:
            logger.info('no SAF files found to copy')
            return
        client = self.get_client()
        if client is not None:
            with client.open_sftp() as ftp_client:
                self.observer_count = 0
                for file_ in files:
                    logger.info(f'transfer file {file_}')
                    logger.info(f"target: '{self.server_source}/{file_.name}")
                    self.report.add('transfer files', file_.name)
                    ftp_client.put(
                        file_, f'{self.server_source}/{file_.name}',
                        callback=self.transferobserver)
                    done = file_.with_suffix(file_.suffix + '.done')
                    file_.rename(done)
                    logger.info(f'rename file {file_.name} to {done.name}')
            client.close()

    def copy(self) -> dict:
        saf_files = self.get_files()
        self.copy_files(saf_files)
