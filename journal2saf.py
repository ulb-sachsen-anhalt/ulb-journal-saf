#!/usr/bin/env python3

import logging
import requests
import warnings

from configparser import ConfigParser


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

    def extract_jounales(self) -> None:
        data = self.journals_dict
        if 'items' in data.keys():
            logging.info(f"{len(data['items'])} journals found")
            for data in data['items']:
                journal_obj = Journal(data)
                self.journals.append(journal_obj)

    def pull_submissions(self) -> None:
        for journal in self.journals[:-1]:
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
        for j, journal in enumerate(self.journals, start=1):
            for s, subm in enumerate(journal.submissions, start=1):
                for p, publ in enumerate(subm.data['publications'], start=1):
                    for g, galley in enumerate(publ['galleys'], start=1):
                        galley_obj = Galley(galley, self)
                        journal.galleys.append(galley_obj)
        logging.info(
            f"proccess {j} journals, {s} submissions, "
            f"{p} publications {g} galleys")


def main():
    jp = JournalPoll()
    jp.pull_contexts()
    jp.extract_jounales()
    jp.pull_submissions()
    jp.extract_publications()
    jp.extract_galleys()


if __name__ == "__main__":
    main()
