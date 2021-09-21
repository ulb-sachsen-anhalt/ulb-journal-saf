#!/usr/bin/env python3

import logging
import argparse
import warnings
import requests
from pprint import pprint
from datetime import datetime
from configparser import ConfigParser

from export_saf import ExportSAF
from transfer_saf import TransferSAF

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
# preserving capital letters with monkey patch
CP.optionxform = lambda option: option
CP.read(CONFIG)

__all__ = ['Publisher', 'Issue', 'DataPoll']


class Publisher():
    """This class stores single Publisher object"""

    def __init__(self, data) -> None:
        self._data = data
        self.name = data['name']
        self.url_path = data['urlPath']
        self.url = data['url']
        self.publisher_id = data['id']
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
            id_ = publisher.id
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


def main() -> None:
    start = datetime.now()
    dp = DataPoll()
    dp._request_publishers()
    dp.serialise_data(3, 3)
    dp._request_issues()
    dp._request_contexts()

    saf = ExportSAF(dp.publishers, CP)
    saf.export()
    saf.write_zips()

    transfer = TransferSAF(CP)
    result = transfer.transfer()
    end = datetime.now()
    pprint(result)
    logger.info(f"time elapsed: {str(end-start).split('.')[0]}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=("Request Journalserver(OJS/OMP)"
                     " and build SAF's of all published Submissions"))
    parser.add_argument(
        "-v", "--verbose", help="increase output verbosity",
        action="store_true")
    parser.add_argument(
        "-c", required=False,
        default=CONFIG,
        help="path to configuration file")

    args = parser.parse_args()
    if args.verbose:
        logger.setLevel(level=logging.DEBUG)

    main()
