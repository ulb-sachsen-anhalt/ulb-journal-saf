#!/usr/bin/env python3

import os
import shutil
import logging
import requests
import warnings

from configparser import ConfigParser
from lxml import etree as ET

warnings.filterwarnings('ignore', message='Unverified HTTPS request')

__all__ = ['JournalPoll']

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)-5s %(name)s %(message)s')

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
        logging.info(
            f"build contexts REST call:"
            f"{rest_call[:-len(self.token)+10]}XXX")
        return rest_call

    def server_submissions(self, jounal_name) -> str:
        rest_call = ''.join([
            self.journal_server,
            jounal_name,
            self.endpoint_submissions,
            self.token])
        logging.debug(
            "build submissions REST call: "
            f"{rest_call[:-len(self.token)+10]}XXX")
        return rest_call

    def pull_contexts(self) -> None:
        query_contexts = self.server_contexts()
        self.journals_dict = self._server_request(query_contexts)

    def extract_jounales(self, max=-1) -> None:
        data = self.journals_dict
        if 'items' in data.keys():
            logging.info(f"{len(data['items'])} journals found")
            for data in data['items'][:max]:
                journal_obj = Journal(data)
                self.journals.append(journal_obj)

    def pull_submissions(self) -> None:
        for journal in self.journals:
            journal_name = journal.url_path
            s = self.server_submissions(journal_name)
            result = self._server_request(s)
            logging.info(
                f"proccess {result['itemsMax']} "
                f"submissions for '{journal_name}'")
            for submission in result['items']:
                subm_obj = Submission(submission, self)
                journal.submissions.append(subm_obj)

    def extract_publications(self) -> None:
        for journal in self.journals:
            journal_name = journal.url_path
            logging.info(
                f"proccess {len(journal.submissions)} "
                f"submissions for '{journal_name}'")
            for subm in journal.submissions:
                for publ in subm.data['publications']:
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
        logging.info(
            f"proccess {j} journals, {s} submissions, "
            f"{p} publications {g} galleys")


class ExportSAF:
    """Export given data to Simple Archive Format"""

    def __init__(self, journals):
        self.journals = journals
        self.load_config()

    def load_config(self) -> None:
        e = CP['export']
        self.export_path = e['export_path']
        self.collection = e['collection']

    def _handle_dublin_core_dummy(self, work_dir):
        dc_dummy_path = os.path.join(work_dir, "dublin_core.xml")
        dublin_core = ET.Element('dublin_core')
        el_title = ET.Element('dcvalue')
        el_title.set('element', 'title')
        el_title.set('qualifier', 'none')
        el_title.text = 'DUMMY'
        el_date = ET.Element('dcvalue')
        el_date.set('element', 'date')
        el_date.set('qualifier', 'issued')
        el_date.text = '1982'
        dublin_core.append(el_title)
        dublin_core.append(el_date)
        self.write_xml_file(dublin_core, dc_dummy_path)

    def write_xml_file(self, xml_root, outfile):
        """ writes xml root pretty printed to outfile """

        root = ET.ElementTree(xml_root)

        xml_string = ET.tostring(root, pretty_print=True, encoding='UTF-8')
        pretty_parser = ET.XMLParser(
            resolve_entities=False, strip_cdata=False, remove_blank_text=True)
        xml_root_new = ET.fromstring(xml_string, pretty_parser)
        xml_formatted = ET.tostring(
            xml_root_new, pretty_print=True, encoding='UTF-8').decode('UTF-8')

        dst_dir = os.path.dirname(outfile)
        if not os.path.exists(dst_dir):
            os.makedirs(dst_dir)

        with open(outfile, 'w') as dc_file:
            dc_file.write('<?xml version="1.0" encoding="UTF-8"?>' '\n')
            dc_file.write(xml_formatted)

    def _handle_contens_file(self, work_dir):
        outfile = 'contens'
        dummy_path = os.path.join(work_dir, outfile)
        with open(dummy_path, 'w') as dc_file:
            dc_file.write('1234.pdf')

    def _handle_metadata_file(self, work_dir):
        outfile = 'metadata_local.xml'
        dummy_path = os.path.join(work_dir, outfile)
        with open(dummy_path, 'w') as dc_file:
            dc_file.write('<?xml version="1.0" encoding="UTF-8"?>' '\n')
            dc_file.write('<dublin_core schema="local">')
            dc_file.write('</dublin_core>')

    def _handle_collections_file(self, work_dir):
        outfile = 'collections'
        dummy_path = os.path.join(work_dir, outfile)
        with open(dummy_path, 'w') as dc_file:
            dc_file.write(self.collection)

    def export(self):
        for journal in self.journals:
            j_name = journal.url_path
            logging.info(f"write journal folder '{j_name}'")
            saf_dir = os.path.join(self.export_path, j_name)
            os.makedirs(saf_dir, exist_ok=True)
            row_number = 1
            item_folder = os.path.join(saf_dir, f'item_{row_number:03}')
            os.makedirs(item_folder, exist_ok=True)
            self._handle_dublin_core_dummy(item_folder)
            self._handle_contens_file(item_folder)
            self._handle_metadata_file(item_folder)
            self._handle_collections_file(item_folder)

            # shutil.make_archive(saf_dir, zip, saf_dir)


def main():
    jp = JournalPoll()
    jp.pull_contexts()
    jp.extract_jounales(1)
    jp.pull_submissions()
    jp.extract_publications()
    jp.extract_galleys()

    saf = ExportSAF(jp.journals)
    saf.export()


if __name__ == "__main__":
    main()
