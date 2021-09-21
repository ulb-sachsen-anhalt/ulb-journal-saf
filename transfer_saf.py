#!/usr/bin/env python3

import logging
import paramiko
from pathlib import Path
from paramiko.client import SSHClient

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)-5s %(name)s %(message)s')

logger = logging.getLogger(__file__.split('/')[-1])


class TransferSAF:
    """Transfer SAF-zip files to dspace server"""

    def __init__(self, configparser) -> None:
        self.load_config(configparser)
        self.client = None

    def load_config(self, configparser) -> None:
        s = configparser['scp']
        d = configparser['docker']
        ds = configparser['dspace']
        e = configparser['export']
        self.dry_run = configparser['general'].getboolean('dry-run')
        self.export_path = e['export_path']
        self.doi_prefix = e['doi_prefix']
        self.server = s['server']
        self.user = s['user']
        self.key_filename = s['key_filename']
        self.docker_user = d['user']
        self.docker_container = d['container']
        self.docker_dspace = ds['docker_dspace']
        self.eperson = ds['eperson']
        self.docker_mapfile = ds['docker_mapfile']
        self.docker_source = ds['docker_zipsource']
        self.server_source = ds['server_zipsource']
        self.extra = ds['extra']

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

    def get_files(self) -> list:
        export_path = Path(self.export_path)
        zip_files = []
        if export_path.exists():
            for zip in export_path.iterdir():
                zipfile = zip.absolute()
                zip_files.append(zipfile)
        return zip_files

    def transferobserver(self, transferred, total):
        if transferred == total:
            print(f'  transfer done (total: {total >> 20} Mb)')
        self.observer_count += 1
        if self.observer_count % 100 == 0:
            print('.', end="")

    def transfer_files(self, files) -> None:
        if len(files) == 0:
            logger.info('no files found to transfer')
            return
        client = self.get_client()
        with client.open_sftp() as ftp_client:
            self.observer_count = 0

            for file_ in files:
                logger.info(f'transfer file {file_}')
                logger.info(f"target: '{self.server_source}/{file_.name}")
                ftp_client.put(
                    file_, f'{self.server_source}/{file_.name}',
                    callback=self.transferobserver)
        client.close()
        logger.info('transfer done...')

    def run_command(self, command) -> list:
        client = self.get_client()
        logger.info(f"\n{'-' * 100}\n{command}\n{'-' * 100}")
        lines = []
        stin, stdout, stderr = client.exec_command(command)
        for line in stderr.read().splitlines()[:1]:
            logger.error(f"ERROR: {line}")
            lines.append(f"ERROR: {line}")
        for line in stdout.read().splitlines():
            logger.info(line)
            lines.append(line)
        return lines

    def delete_mapfile(self, mapfile):
        logger.info(f"delete mapfile {mapfile}")
        cmd = (
            f"docker exec --user {self.docker_user} {self.docker_container} "
            f"rm {self.docker_mapfile}{mapfile}")
        self.run_command(cmd)

    def import_saf(self, zipfile) -> str:
        logging.info("start SAF import to dspace")
        state = 'success'
        cmd = (
            f"docker exec --user {self.docker_user} {self.docker_container} "
            f"{self.docker_dspace} import --add "
            #  " --test "
            f"--eperson {self.eperson} "
            f"--source {self.docker_source} "
            f"--zip {zipfile} "
            f"--mapfile {self.docker_mapfile}{zipfile}.map "
            f"{self.extra}")
        response = self.run_command(cmd)
        for line in response:
            logger.debug(line)
            if 'ERROR' in str(line) and state == 'success':
                logging.warning(f'import {zipfile} failed: {line}')
                state = f'fail: {line}'  # store first ERROR occu.
        return state

    def get_handle(self, mapfile) -> str:
        cmd = (
            f"docker exec --user {self.docker_user} {self.docker_container} "
            f"cat {self.docker_mapfile}{mapfile}")
        result = self.run_command(cmd)
        handle = ''
        for rline in result:
            handle = rline.split()[-1].decode()
        logger.info(f'handle -------> {handle}')
        return handle

    def get_doi(self, handle) -> str:
        cmd = (
            f"docker exec --user {self.docker_user} {self.docker_container} "
            f"{self.docker_dspace} doi-organiser "
            f"--list | grep {handle}")
        result = self.run_command(cmd)
        dioprefix = self.doi_prefix
        for rline in result:
            dioprefix += rline.split()[0].decode()
        return dioprefix

    def delete_import(self, mapfile) -> None:
        cmd = (f"docker exec --user {self.docker_user} dspace-test_dspace_1 "
               f"{self.docker_dspace} import --delete "
               f"--eperson {self.eperson} "
               f"--mapfile {self.docker_mapfile}{mapfile} "
               "-disable_inheritance")
        self.run_command(cmd)
        logger.info(f'delete item with handel in {mapfile} done...')

    def transfer(self) -> dict:
        zip_files = self.get_files()
        dry_run = self.dry_run
        self.transfer_files(zip_files)
        zip_files_names = [f.name for f in zip_files]
        result = {}
        for zipfile in zip_files_names:
            logger.info(f'****start import proccess for {zipfile}****')
            action = {}
            mapfile = f"{zipfile}.map"
            logger.info(f"delete old mapfile {mapfile}")
            self.delete_mapfile(mapfile)
            logger.info(f"import {zipfile}")
            state = self.import_saf(zipfile)
            action['import'] = state
            if 'fail' in state:
                logger.warning(f'import {zipfile} failed, try next one...')
                result[zipfile] = action
                continue
            handle = self.get_handle(mapfile)
            action['handle'] = handle
            doi = self.get_doi(handle)
            logger.info(f"DOI: {doi}")
            action['doi'] = doi
            if dry_run:
                self.delete_import(mapfile)
            result[zipfile] = action
        return result
