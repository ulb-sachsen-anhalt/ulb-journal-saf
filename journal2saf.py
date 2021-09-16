#!/usr/bin/env python3

import re
import logging
import argparse
import shutil
import mimetypes
import warnings

import paramiko
import requests
import pycountry

from pathlib import Path
from configparser import ConfigParser
from paramiko.client import SSHClient

warnings.filterwarnings(
    'ignore', message='Unverified HTTPS request')

###############################################################
STATUS_PUBLISHED = 3
CONFIG = "conf/config.ini"
###############################################################

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)-5s %(name)s %(message)s')

logger = logging.getLogger(__file__.split('/')[-1])

CP = ConfigParser()
CP.read(CONFIG)

__all__ = ['Publisher', 'Issue', 'DataPoll', 'ExportSAF']


class Publisher():
    """This class stores single Publisher object"""

    def __init__(self, data) -> None:
        self._data = data
        self.name = data['name']
        self.url_path = data['urlPath']
        self.url = data['url']
        self.description = data['description']
        self.journal_id = data['id']
        self.issues = []

    def __getattr__(self, name: str) -> any:
        if name in self._data:
            return self._data[name]
        else:
            return self.__getattribute__(name)


class Issue():
    """This class stores single issue objects"""

    def __init__(self, data, parent) -> None:
        self._data = data
        self.parent = parent   # journal object
        self.date_published = data['datePublished']
        for article in data['articles']:
            self.locale = article['locale']
        for section in data['sections']:
            self.section = section
        self.publications = data['articles'][0]['publications']
        self.publication = self.publications[0]
        self.galleys = data['articles'][0]['publications'][0]['galleys']
        self.galley = self.galleys[0] if self.galleys else []

    def __getattr__(self, name: str) -> any:
        if name in self._data:
            return self._data[name]
        else:
            return self.__getattribute__(name)


class DataPoll():
    """This class is going to requests the omp/ojs server
       and even creating/collecting instances
       of issues and publication objects
    """

    def __init__(self) -> None:
        self.publishers = []
        self.load_config()

    def load_config(self) -> None:
        g = CP['general']
        self.endpoint_contexts = g['endpoint_contexts']
        self.endpoint_issues = g['endpoint_issues']
        self.journal_server = f"{g['journal_server']}/"
        self.token = f"apiToken={g['api_token']}"

    def _server_request(self, query) -> dict:
        if '?' in query:
            query += f'&{self.token}'
        else:
            query += f'?{self.token}'

        # no need to verify, 'cause we trust the server
        result = requests.get(query, verify=False)

        result_dct = result.json()
        if 'error' in result_dct.keys():
            logger.error(
                f"server request failed due to: {result_dct}")
            raise ValueError(result_dct)
        return result_dct

    def rest_call_context(self, journal_name=None, id_=None) -> str:
        """call *one* or *all* context(s) from server"""

        context = journal_name if journal_name else '_'
        id_ = f'/{id_}' if id_ else ''
        rest_call = ''.join([
            self.journal_server,
            context, self.endpoint_contexts, id_])
        logger.info(
            f"build contexts REST call: {rest_call}")
        return rest_call

    def rest_call_issues(self, jounal_url, issue_id=None) -> str:
        """call one or all issue(s) from journal"""

        issue_id = f'/{issue_id}' if issue_id else ''
        rest_call = ''.join([
            jounal_url, self.endpoint_issues, issue_id])
        logger.debug(
            "build issues REST call: {rest_call}")
        return rest_call

    def _request_publishers(self) -> None:
        query_publishers = self.rest_call_context()
        self.publishers_item_dict = self._server_request(query_publishers)

    def serialise_data(self, start=0, end=-1) -> None:
        publishers = self.publishers_item_dict
        if 'items' in publishers.keys():
            logger.info(f"{len(publishers['items'])} publishers found")
            for data in publishers['items'][start:end]:
                publisher = Publisher(data)
                self.publishers.append(publisher)

    def _request_contexts(self) -> None:
        for publisher in self.publishers:
            id_ = publisher.journal_id
            name = publisher.url_path
            query_context = self.rest_call_context(publisher.url_path, id_)
            context_dict = self._server_request(query_context)
            logger.info(f'got {len(context_dict)} keys/values for {name}')
            publisher._data.update(context_dict)

    def _request_issues(self) -> None:
        for publisher in self.publishers:
            query_issues = self.rest_call_issues(publisher.url)
            logger.info(f'request all issues for {publisher.url_path}:'
                        f' {query_issues}')
            issues_dict = self._server_request(query_issues)
            logger.info(f'receive {issues_dict.get("itemsMax", 0)} issues')
            for issue in issues_dict['items']:
                issue_data = issue
                issue_query = self.rest_call_issues(
                    publisher.url, issue['id'])
                issue_data.update(self._server_request(issue_query))
                if len(issue_data['articles']) > 0:
                    issue_ob = Issue(issue_data, publisher)
                    publisher.issues.append(issue_ob)


class ExportSAF:
    """Export given data to -Simple Archive Format-"""

    def __init__(self, journals) -> None:
        # self.journals = journals
        self.contexts = journals
        self.load_config()

    def load_config(self) -> None:
        e = CP['export']
        g = CP['general']
        self.meta = CP['meta']
        self.export_path = e['export_path']
        self.collection = e['collection']
        self.token = f"&apiToken={g['api_token']}"
        self.journal_server = g['journal_server']
        self.type = g['type']
        self.dc_identifier_external_prefix = 'ojs'  # TODO: use config

    @staticmethod
    def write_xml_file(work_dir, dblcore, schema) -> None:
        name = 'dublin_core.xml' if schema == 'dc'\
                else f'metadata_{schema}.xml'
        work_dir.mkdir(parents=True, exist_ok=True)
        pth = work_dir / name
        logger.info(f"write {name}")
        dcline = '  <dcvalue element="{1}" qualifier="{2}"{3}>{0}</dcvalue>'
        dcvalues = [dcline.format(*tpl) for tpl in dblcore]
        schema = f' schema="{schema}"' if schema != 'dc' else ''

        with open(pth, 'w', encoding='utf-8') as fh:
            fh.write('<?xml version="1.0" encoding="UTF-8"?>\n')
            fh.write(f'<dublin_core{schema}>\n')
            fh.write('\n'.join(dcvalues))
            fh.write('\n</dublin_core>')

    @staticmethod
    def locale2isolang(local_code) -> str:
        locale = local_code[0:2]
        lang = pycountry.languages.get(alpha_2=locale)
        isolang = lang.bibliographic if hasattr(lang, 'bibliographic')\
            else lang.alpha_3
        return isolang

    @staticmethod
    def write_contents_file(work_dir, file_list) -> None:
        filename = 'contents'
        pth = work_dir / filename
        with open(pth, 'w') as fh:
            fh.writelines("{}\n".format(line) for line in file_list)

    @staticmethod
    def write_collections_file(work_dir, collection) -> None:
        filename = 'collections'
        pth = work_dir / filename
        with open(pth, 'w') as fh:
            fh.write(collection)

    def write_meta_file(self, item_folder, issue) -> None:
        context = issue.parent
        locale = issue.locale
        language = self.locale2isolang(locale)
        pagestart = issue.publication['pages']
        pageend = issue.publication['pages']
        schema_dict = {}
        # ext_prefix = self.dc_identifier_external_prefix

        for k, v in self.meta.items():
            meta_tpl = k.split('.')
            schema = meta_tpl.pop(0)
            while len(meta_tpl) < 3:
                meta_tpl.append('', )

            if v.startswith('"') and v.endswith('"'):
                # fixed value
                value = v[1:-1]
            else:
                value = eval(v)
                if isinstance(value, str) and\
                        (value.count('<') > 0 or value.count('>')):
                    value = f'<![CDATA[{value}]]>'

            if value:
                schema_dict.setdefault(
                    schema, []).append((value, *meta_tpl), )

        for schema, dcl in schema_dict.items():
            self.write_xml_file(item_folder, dcl, schema)

    @staticmethod
    def get_filename_from_cd(cd) -> str:
        """Get filename from content-disposition"""
        if not cd:
            return None
        fname = re.findall('filename=(.+)', cd)
        if len(fname) == 0:
            return None
        return fname[0]

    def download_galley(self, journal, work_dir, issue) -> list:
        publications = issue.publications
        publication = publications[0]
        journal_url = journal.url
        galleys = publication['galleys']

        filenames = []
        for galley in galleys:
            galley_id = galley['id']
            mime_type = galley['file']['mimetype']
            submission_id = galley['file']['submissionId']
            extension = mimetypes.guess_extension(mime_type)
            submission_file_id = galley['submissionFileId']
            url = "{}/article/download/{}/{}/{}".format(
                journal_url, submission_id, galley_id, submission_file_id)
            response = requests.get(url, verify=False)
            status_code = response.status_code
            if status_code != 200:
                logger.error(f'error download file code:{status_code} {url}')
                continue
            filename = '{}_{}_{}{}'.format(
                journal.url_path, submission_id, submission_file_id, extension)

            export_path = work_dir / filename

            with open(export_path, 'wb') as fh:
                for chunk in response.iter_content(chunk_size=16*1024):
                    fh.write(chunk)
                logger.info(
                    f'download file at {url} '
                    f'size: {Path(export_path).stat().st_size >> 20} Mb')
                filenames.append(filename)
        return filenames

    def export(self) -> None:
        for context in self.contexts:
            journal_name = context.url_path
            for num, issue in enumerate(context.issues):

                item_folder = Path(self.export_path)\
                    .joinpath(journal_name, f'item_{num:03d}',
                              f'issue_{issue.id}')

                self.write_meta_file(item_folder, issue)
                self.write_collections_file(item_folder, self.collection)

                # write contents file
                filenames = self.download_galley(
                    context, item_folder, issue)
                self.write_contents_file(item_folder, filenames)

    def write_zips(self) -> None:
        export_pth = Path(self.export_path)
        journals = [d for d in export_pth.iterdir() if d.is_dir()]
        size_abs = 0
        for journal in journals:
            items = [i for i in journal.iterdir() if i.is_dir()]
            for item in items:
                logger.info(f'zip folder at {item}')
                name = f'{journal.name}_{item.name}'
                zipfile = shutil.make_archive(
                    export_pth / name, 'zip', item)
                zipsize = Path(zipfile).stat().st_size
                size_abs += zipsize
                logger.info(f'write zip file {name}.zip '
                            f'with {zipsize >> 20} Mb')
                if Path(zipfile).is_file():
                    shutil.rmtree(item)
            shutil.rmtree(journal)
        logger.info(f'finally wrote {size_abs >> 20} Mb, done...')


class TransferSAF:
    """Transfer SAF-zip files to dspace server"""

    def __init__(self) -> None:
        self.load_config()
        self.client = None

    def load_config(self) -> None:
        s = CP['scp']
        d = CP['docker']
        ds = CP['dspace']
        e = CP['export']
        self.dry_run = CP['general'].getboolean('dry-run')
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
                logging.warning(f'import {zipfile} fail: {line}')
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


def main() -> None:
    dp = DataPoll()
    dp._request_publishers()
    dp.serialise_data(2, 3)
    dp._request_issues()
    dp._request_contexts()

    saf = ExportSAF(dp.publishers)
    saf.export()
    saf.write_zips()

    transfer = TransferSAF()
    result = transfer.transfer()
    for k, v in result.items():
        logger.info(f"{k}: {v}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=("Request Journalserver(OJS/OMP)"
                     " and build SAF's of all published Submissions"))
    parser.add_argument(
        "-v", "--verbose", help="increase output verbosity",
        action="store_true")
    args = parser.parse_args()
    if args.verbose:
        logger.setLevel(level=logging.DEBUG)

    main()
