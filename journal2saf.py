#!/usr/bin/env python3

import re
import logging
import argparse
import shutil
import mimetypes
import requests
import warnings
import pycountry
from pathlib import Path
from configparser import ConfigParser

warnings.filterwarnings('ignore', message='Unverified HTTPS request')

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

__all__ = ['Journal', 'Issue', 'JournalPoll', 'ExportSAF']


class Journal():
    """This class stores single journal objects"""

    def __init__(self, data):
        self._data = data
        self.name = data['name']
        self.url_path = data['urlPath']
        self.url = data['url']
        self.description = data['description']
        self.issues = []

    def get(self, attribute):
        if attribute in self._data:
            return self._data[attribute]
        else:
            logger.warning(f"{attribute} not in journal")


class Issue():
    """This class stores single issue objects"""

    def __init__(self, data, parent):
        self.parent = parent   # journal object
        self.issue_id = data['id']
        self.date_published = data['datePublished']
        for article in data['articles']:
            self.locale = article['locale']
        self.volume = data['volume']
        self.number = data['number']
        self.year = data['year']
        for section in data['sections']:
            self.section = section
        self.publications = data['articles'][0]['publications']

    def get(self, attribute):
        if attribute in self._data:
            return self._data[attribute]
        else:
            logger.warning(f"{attribute} not in issue")


class JournalPoll():
    """This class is going to requests the journal server
       and even creating/collecting instances
       of issues and publication objects
    """

    def __init__(self):
        self.journals = []
        self.load_config()

    def load_config(self) -> None:
        g = CP['general']
        self.endpoint_contexts = g['endpoint_contexts']
        self.endpoint_issues = g['endpoint_issues']
        self.journal_server = f"{g['journal_server']}/"
        self.token = f"apiToken={g['api_token']}"

    def _server_request(self, query) -> dict:
        # no need to verify, 'cause we trust the server
        if '?' in query:
            query += f'&{self.token}'
        else:
            query += f'?{self.token}'
        result = requests.get(query, verify=False)
        result_dct = result.json()
        if 'error' in result_dct.keys():
            logger.error(
                f"server request failed due to: {result_dct}")
            raise ValueError(result_dct)
        return result_dct

    def rest_call_contexts(self) -> str:
        rest_call = ''.join([
            self.journal_server,
            self.endpoint_contexts])
        logger.info(
            f"build contexts REST call: {rest_call}")
        return rest_call

    def rest_call_issues(self, jounal_name, issue_id=None) -> str:
        """call one or all issues from journal"""
        issue_id = f'/{issue_id}' if issue_id else ''
        rest_call = ''.join([
            self.journal_server,
            jounal_name,
            self.endpoint_issues,
            issue_id])
        logger.debug(
            "build issues REST call: {rest_call}")
        return rest_call

    def _request_contexts(self) -> None:
        query_contexts = self.rest_call_contexts()
        self.journals_dict = self._server_request(query_contexts)

    def _request_issues(self) -> None:
        for journal in self.journals:
            query_issues = self.rest_call_issues(journal.url_path)
            logger.info(f'request all issues: {query_issues}')
            issues = self._server_request(query_issues)
            for issue in issues['items']:
                issue_data = issue
                issue_query = self.rest_call_issues(
                    journal.url_path, issue['id'])
                issue_data.update(self._server_request(issue_query))
                if len(issue_data['articles']) > 0:
                    issue_ob = Issue(issue_data, journal)
                    journal.issues.append(issue_ob)

    def serialise_journals(self, start=0, end=-1) -> None:
        journales = self.journals_dict
        if 'items' in journales.keys():
            logger.info(f"{len(journales['items'])} journals found")
            for data in journales['items'][start:end]:
                journal_obj = Journal(data)
                self.journals.append(journal_obj)


class ExportSAF:
    """Export given data to -Simple Archive Format-"""

    def __init__(self, journals):
        self.journals = journals
        self.load_config()

    def load_config(self) -> None:
        e = CP['export']
        g = CP['general']
        m = CP['meta']
        self.export_path = e['export_path']
        self.collection = e['collection']
        self.token = f"&apiToken={g['api_token']}"
        self.journal_server = g['journal_server']
        self.type = g['type']
        self.dc_identifier_external_prefix = m['dc-identifier-external-prefix']
        self.dc_rights_uri = m['dc-rights-uri']

    @staticmethod
    def write_xml_file(work_dir, dblcore, name, schema=None) -> None:
        work_dir.mkdir(parents=True, exist_ok=True)
        pth = work_dir / name
        dcline = '  <dcvalue element="{}" qualifier="{}"{}>{}</dcvalue>'
        dcvalues = [dcline.format(*tpl) for tpl in dblcore]
        schema = f' schema="{schema}"' if schema else ''

        with open(pth, 'w') as fh:
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

    def write_local_file(self, item_folder, issue) -> None:
        schema = 'local'
        locale = issue.locale
        publication = issue.publications[0]
        dcl = []

        # Pagestart, Pageend
        try:
            start, end = publication['pages'].split('-')
            dcl.extend([
                ('bibliographicCitation', 'pagestart', '', start),
                ('bibliographicCitation', 'pageend', '', end)]
            )
        except ValueError:
            logger.info(f"'pages' property for {item_folder} missing")

        # Volume
        dcl.append(('bibliographicCitation', 'volume', '', issue.volume), )

        # Number
        dcl.append(('bibliographicCitation', 'number', '', issue.number), )

        # Journaltitle
        jtitle = issue.parent.name[locale]
        dcl.append(('bibliographicCitation', 'journaltitle', '', jtitle), )

        dcl.append(('openaccess', 'none', '', 'true'), )
        self.write_xml_file(
            item_folder, dcl,
            f'metadata_{schema}.xml',
            schema=schema)

    def create_dc_file(self, item_folder, issue) -> None:
        filename = 'dublin_core.xml'

        publication = issue.publications[0]
        locale = issue.locale
        lang = self.locale2isolang(publication.get('locale'))
        dcl = []
        ext_prefix = self.dc_identifier_external_prefix
        i_id = issue.issue_id

        # External
        dcl.append(('identifier', 'external', '', f'{ext_prefix}{i_id}'), )

        # Description
        descr = issue.parent.description[locale]
        dcl.append((
            'description', 'abstract', '', f'<![CDATA[{descr}]]>'), )

        # Title
        for locale_, title in publication['fullTitle'].items():
            if title:
                lng = self.locale2isolang(locale)
                if locale_ == locale:
                    dcl.append(
                        ('title', 'none', f' language="{lng}"', title))
                else:
                    dcl.append(
                        ('title', 'translated', f' language="{lng}"', title))

        # Date issued
        dcl.append(('date', 'issued', '', issue.year), )

        # Date available
        date_ = publication['datePublished']
        dcl.append(('date', 'available', '', date_), )

        # Author
        authors = publication['authorsString']
        authors_short = publication['authorsStringShort']
        all_authors = authors if len(authors) else authors_short
        if len(all_authors):
            for author in all_authors.split(','):
                dcl.append(('contributor', 'author', '', author.strip()), )

        # language
        dcl.append(('language', 'iso', '', lang), )

        # Type
        dc_type = issue.section['title']
        for k, type_ in dc_type.items():
            if type_:
                dcl.append(('type', 'none', '', type_.lower()), )
                break

        # Abstract / copy right uri
        galleys = publication['galleys']
        for galley in galleys:
            for locale, desc in galley['file']['description'].items():
                lang = self.locale2isolang(locale)
                if desc:
                    dcl.append(
                        ('description', 'abstract',
                         f' language="{lang}"', desc), )
            copyright = galley['file']['copyrightOwner']

            if not copyright:
                copyright = self.dc_rights_uri

            dcl.append(('rights', 'uri', '', copyright), )

        self.write_xml_file(item_folder, dcl, filename)

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
        for journal in self.journals:
            journal_name = journal.url_path
            for num, issue in enumerate(journal.issues):

                item_folder = Path(self.export_path)\
                    .joinpath(journal_name, f'item_{num:03d}',
                              f'issue_{issue.issue_id}')

                self.create_dc_file(item_folder, issue)

                # write schema files
                schemas = ['local', ]
                for schema in schemas:
                    method = f'write_{schema}_file'
                    try:
                        getattr(self, method)(item_folder, issue)
                    except AttributeError as err:
                        logger.error(
                            f'method for schema "{method}" not found {err}')
                        raise NotImplementedError(err)

                # write collections file
                self.write_collections_file(item_folder, self.collection)

                # write contents file
                filenames = self.download_galley(
                    journal, item_folder, issue)
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
                #if Path(zipfile).is_file():
                #    shutil.rmtree(item)
            #shutil.rmtree(journal)
        logger.info(f'finally wrote {size_abs >> 20} Mb, done...')


def main() -> None:
    jp = JournalPoll()
    jp._request_contexts()
    jp.serialise_journals(2, 3)
    jp._request_issues()

    saf = ExportSAF(jp.journals)
    saf.export()
    saf.write_zips()


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
