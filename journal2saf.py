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
CONFIGURATION = "conf/config.ini"


class Config:
    """just a config loader"""

    def __init__(self):
        self.init()
        self.load_config()

    def init(self, config=CONFIGURATION) -> None:
        logging.info(f"read configuration from: {config}")
        CP.read(config)
        self.config = CP

    def load_config(self) -> None:
        g = CP['general']
        self.api_token = g['api_token']
        self.endpoint_contexts = g['endpoint_contexts']
        self.endpoint_submissions = g['endpoint_submissions']
        self.journal_server = g['journal_server']
        if not self.journal_server.endswith('/'):
            self.journal_server += '/'
        self.protokoll = g['protokoll']
        self.api_query_key = '?apiToken='


class Journal(Config):
    """This class is going to store single journal objects"""

    def __init__(self, data):
        super().__init__()
        # https://public.bibliothek.uni-halle.de/hercynia/api/v1/contexts/6
        self.url_path = data['urlPath']
        self.submissions = []

    def server_submissions(self, jounal_name) -> str:
        rest_call = ''.join([
            self.protokoll,
            self.journal_server,
            jounal_name,
            self.endpoint_submissions,
            self.api_query_key,
            self.api_token])
        logging.info(
            "build submissions REST call: "
            f"{rest_call[:-len(self.api_token)]}XXX")
        return rest_call


class Submission:
    """This class is going to store submission objects"""

    def __init__(self, data, parent):
        self._href = data['_href']
        self.parent = parent
        self.publications = []

    def extract_submission(self, submission) -> None:
        for publ in submission['publications']:
            for galley_data in publ['galleys']:
                galley = Galley(galley_data, self)
                if galley.approved is True:
                    print('.', end="")
                    # print(publ['_href'], galley.href, galley.approved)


class Galley:
    """This class is going to store single galley objects"""

    def __init__(self, data, parent):
        # https://publicdev.bibliothek.uni-halle.de/hercynia/api/v1/submissions
        self.parent = parent
        self.href = data['file']['_href']
        self.approved = data['isApproved']


class JournalPoll(Config):
    """This class is doing to requests the journal server
       and even creating/collecting instances
       of submissions and publication objects
    """

    def __init__(self):
        self.init()
        self.journals = []
        super().__init__()

    def _server_request(self, query) -> dict:
        # no need to verify, 'cause we trust the server
        result = requests.get(query, verify=False)
        result_dct = result.json()
        return result_dct

    def server_contexts(self) -> str:
        rest_call = ''.join([
            self.protokoll,
            self.journal_server,
            self.endpoint_contexts,
            self.api_query_key,
            self.api_token])
        logging.info(
            f"build contexts REST call: {rest_call[:-len(self.api_token)]}XXX")
        return rest_call

    def pull_contexts(self) -> None:
        query_contexts = self.server_contexts()
        self.journals_dict = self._server_request(query_contexts)

    def pull_jounales(self) -> None:
        data = self.journals_dict
        if 'items' in data.keys():
            logging.info(f"{len(data['items'])} journals found")
            for data in data['items']:
                journal_obj = Journal(data)
                self.journals.append(journal_obj)

    def pull_submissions(self) -> None:
        for journal in self.journals[:2]:
            journal_name = journal.url_path
            s = journal.server_submissions(journal_name)
            result = self._server_request(s)
            logging.info(
                f"proccess {result['itemsMax']} "
                f"submissions for '{journal_name}'")
            for submission in result['items']:
                subm_obj = Submission(submission, self)
                subm_obj.extract_submission(submission)
                journal.submissions.append(subm_obj)

    def pull_galleys(self) -> None:
        pass


def main():
    Config()
    jp = JournalPoll()
    jp.pull_contexts()
    jp.pull_jounales()
    jp.pull_submissions()
    jp.pull_galleys()


    # print(journals)
    # print(json_obj.text)


if __name__ == "__main__":
    main()
