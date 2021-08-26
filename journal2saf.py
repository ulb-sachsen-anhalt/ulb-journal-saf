#!/usr/bin/env python3

import re
import logging
import argparse
import requests
import warnings
import pycountry
from urllib.parse import quote_plus
from pathlib import Path
from configparser import ConfigParser

warnings.filterwarnings('ignore', message='Unverified HTTPS request')

__all__ = ['JournalPoll', 'ExportSAF']


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)-5s %(name)s %(message)s')
logger = logging.getLogger(__file__)

CP = ConfigParser()
CP.read("conf/config.ini")


class Journal():
    """This class is going to store single journal objects"""

    def __init__(self, data):
        super().__init__()
        # https://public.bibliothek.uni-halle.de/hercynia/api/v1/contexts/6
        self.url_path = data['urlPath']
        self.submissions = []
        self.publications = []
        self.galleys = []


class Submission:
    """This class is going to store submission objects"""

    def __init__(self, data, parent):
        self._href = data['_href']
        self.parent = parent
        self.data = data
        self.publications = []


class Publication:
    """This class is going to store publication objects"""

    def __init__(self, data, parent):
        self._href = data['_href']
        self.parent = parent
        self.data = data
        self.galleys = []


class Galley:
    """This class is going to store single galley objects"""

    def __init__(self, data, parent):
        # https://publicdev.bibliothek.uni-halle.de/hercynia/api/v1/submissions
        self.parent = parent
        self.href = data['file']['_href']
        self.url = data['file']['url']
        self.approved = data['isApproved']


class JournalPoll():
    """This class is going to requests the journal server
       and even creating/collecting instances
       of submissions and publication objects
    """

    def __init__(self):
        self.journals = []
        self.load_config()

    def load_config(self) -> None:
        g = CP['general']
        self.endpoint_contexts = g['endpoint_contexts']
        self.endpoint_submissions = g['endpoint_submissions']
        self.journal_server = f"{g['journal_server']}/"
        self.token = f"?apiToken={g['api_token']}"

    def _server_request(self, query) -> dict:
        # no need to verify, 'cause we trust the server
        result = requests.get(query, verify=False)
        result_dct = result.json()
        if 'error' in result_dct.keys():
            raise ValueError(result_dct)
        return result_dct

    def server_contexts(self) -> str:
        rest_call = ''.join([
            self.journal_server,
            self.endpoint_contexts,
            self.token])
        logger.info(
            f"build contexts REST call:"
            f"{rest_call[:-len(self.token)+10]}XXX")
        return rest_call

    def server_submissions(self, jounal_name) -> str:
        rest_call = ''.join([
            self.journal_server,
            jounal_name,
            self.endpoint_submissions,
            self.token])
        logger.debug(
            "build submissions REST call: "
            f"{rest_call[:-len(self.token)+10]}XXX")
        return rest_call

    def request_contexts(self) -> None:
        query_contexts = self.server_contexts()
        self.journals_dict = self._server_request(query_contexts)

    def extract_jounales(self, max=-1) -> None:
        data = self.journals_dict
        if 'items' in data.keys():
            logger.info(f"{len(data['items'])} journals found")
            for data in data['items'][:max]:
                journal_obj = Journal(data)
                self.journals.append(journal_obj)

    def request_submissions(self) -> None:
        for journal in self.journals:
            journal_name = journal.url_path
            s = self.server_submissions(journal_name)
            result = self._server_request(s)
            logger.info(
                f"request {len(result['items'])} "
                f"submissions for '{journal_name}'")
            for submission in result['items']:
                subm_obj = Submission(submission, self)
                journal.submissions.append(subm_obj)

    def extract_publications(self) -> None:
        for journal in self.journals:
            journal_name = journal.url_path
            logger.info(
                f"extract {len(journal.submissions)} "
                f"submission items for '{journal_name}'")
            for subm in journal.submissions:
                for publ in subm.data['publications']:
                    status = publ.get('status')
                    locale = publ.get('locale')
                    if status != 3:
                        logger.info(
                            f"status {status} (unveröffentlicht)"
                            f" {publ.get('fullTitle')[locale]} ")
                        continue
                    logger.debug(
                        f"status {status} for {locale}"
                        f" {publ.get('fullTitle')[locale]} ")
                    publ_obj = Publication(publ, self)
                    journal.publications.append(publ_obj)

    def extract_galleys(self) -> None:
        s = p = g = 0
        for j, journal in enumerate(self.journals, start=1):
            for s, subm in enumerate(journal.submissions, start=1):
                for p, publ in enumerate(subm.data['publications'], start=1):
                    for g, galley in enumerate(publ['galleys'], start=1):
                        galley_obj = Galley(galley, self)
                        journal.galleys.append(galley_obj)
        logger.info(
            f"proccess {j} journals, {s} submissions, "
            f"{p} publications {g} galleys")


class ExportSAF:
    """Export given data to Simple Archive Format"""

    def __init__(self, journals):
        self.journals = journals
        self.load_config()

    def load_config(self) -> None:
        e = CP['export']
        g = CP['general']
        self.export_path = e['export_path']
        self.collection = e['collection']
        self.token = f"&apiToken={g['api_token']}"

    @staticmethod
    def write_xml_file(work_dir, dblcore, name, schema='') -> None:
        work_dir.mkdir(parents=True, exist_ok=True)
        pth = work_dir / name
        dcline = '  <dcvalue element="{}" qualifier="{}"{}>{}</dcvalue>'
        dcvalues = [dcline.format(*tpl) for tpl in dblcore]
        if schema != '':
            schema = f' schema="{schema}"'

        with open(pth, 'w') as fh:
            fh.write('<?xml version="1.0" encoding="UTF-8"?>\n')
            fh.write(f'<dublin_core{schema}>\n')
            fh.write('\n'.join(dcvalues))
            fh.write('\n</dublin_core>')

    @staticmethod
    def write_contens_file(work_dir, file_list) -> None:
        pth = work_dir / 'contens'
        with open(pth, 'w') as fh:
            fh.writelines("{}\n".format(line) for line in file_list)

    @staticmethod
    def write_collections_file(work_dir, collection) -> None:
        outfile = 'collections'
        pth = work_dir / outfile
        with open(pth, 'w') as fh:
            fh.write(collection)

    @staticmethod
    def locale2isolang(local_code) -> str:
        locale = local_code[0:2]
        lang = pycountry.languages.get(alpha_2=locale)
        isolang = lang.bibliographic if hasattr(lang, 'bibliographic')\
            else lang.alpha_3
        return isolang

    def create_meta_file(self, folder, data) -> None:
        dcl = []
        for locale, title in data['title'].items():
            lang = self.locale2isolang(locale)
            if title:
                dcl.append(
                    ('title', 'none', f' language="{lang}"', title), )
                dcl.append(
                    ('title', 'alternative', f' language="{lang}"', title),
                )

        authors = data.get('authorsString')
        dcl.append(('contributor', 'author', '', authors), )

        date_ = data.get('datePublished')
        dcl.append(('date', 'issued', '', date_), )
        isolang = self.locale2isolang(data.get('locale'))
        dcl.append(('language', 'iso', '', isolang), )
        galleys = data.get('galleys')

        for galley in galleys:
            file_ = galley.get('file')
            for locale, desc in file_.get('description').items():
                lang = self.locale2isolang(locale)
                if desc:
                    dcl.append(
                        ('description', 'abstract',
                         f' language="{lang}"', desc), )
                    dcl.append(
                        ('description', 'abstract',
                         f' language="{lang}"', desc),
                    )
            dcl.append(('type', 'none', '', file_.get('mimetype')), )
        self.write_xml_file(folder, dcl, 'dublin_core.xml')

    @staticmethod
    def get_filename_from_cd(cd):
        """
        Get filename from content-disposition
        """
        if not cd:
            return None
        fname = re.findall('filename=(.+)', cd)
        if len(fname) == 0:
            return None
        return fname[0]

    def download_galley(self, work_dir, data):
        galleys = data.get('galleys')
        for galley in galleys:
            filedata = galley.get('file')
            url_published = data.get('urlPublished')
            submission_file_id = galley.get('submissionFileId')
            galley_id = galley.get('id')

            url = url_published.replace('view', 'download')
            url1 = url.replace('version', str(galley_id))
            url = f"{url1.rsplit('/', 1)[0]}/{submission_file_id}"

    
            locale = galley.get('locale', None)

            print(work_dir, filedata.get('name')[locale])
            filename = (filedata.get('name')[locale]).replace(' ', '')
            pth = work_dir / filename
            r = requests.get(url, verify=False)
            print(url)

            with open(pth, 'wb') as fh:
                for chunk in r.iter_content(chunk_size=16*1024):
                    # print(chunk)
                    fh.write(chunk)

    def export(self) -> None:
        for journal in self.journals:
            j_name = journal.url_path
            for num, submission in enumerate(journal.submissions, start=1):
                status = submission.data['status']
                if status != 3:  # 3 --> published
                    continue
                publ = submission.data['publications']
                # logger.debug(f"write journal folder '{j_name}'")
                assert len(publ) == 1
                publ = publ[0]

                item_folder = Path(self.export_path)\
                    .joinpath(j_name, f'item_{num:03}')

                self.create_meta_file(item_folder, publ)
                schema = 'local'
                self.write_xml_file(item_folder, [
                    ('title', 'none', '', 'Hans im mähriſchen Glück'),
                    ('date', 'issued', '', '1982')], f'metadata_{schema}.xml',
                    schema="local")
                self.write_contens_file(item_folder, ['1', '2', 'n'])
                self.write_collections_file(item_folder, self.collection)
                self.download_galley(item_folder, publ)

            # shutil.make_archive(saf_dir, zip, saf_dir)


def main():
    jp = JournalPoll()
    jp.request_contexts()
    jp.extract_jounales(1)
    jp.request_submissions()
    jp.extract_publications()
    jp.extract_galleys()

    saf = ExportSAF(jp.journals)
    saf.export()


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
