#!/usr/bin/env python3

import re
import logging
import argparse
import warnings
import requests
import pathlib
from datetime import datetime
from pathlib import Path
from configparser import ConfigParser

from export_saf import ExportSAF
from copy_saf import CopySAF
from retrieve_doi import RetrieveDOI
from write_remote_url import WriteRemoteUrl

warnings.filterwarnings(
    'ignore', message='Unverified HTTPS request')

###############################################################
STATUS_PUBLISHED = 3
CONFIG = "conf/config.ini"
CONFIG_META = "conf/config_meta.ini"
###############################################################

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)-5s %(name)s %(message)s')

logger = logging.getLogger(__file__.split('/')[-1])

CP = ConfigParser()
# preserving capital letters with monkey patch
CP.optionxform = lambda option: option


__all__ = ['Publisher', 'Submission', 'DataPoll']


class Publisher():
    """This class stores single Publisher object"""

    def __init__(self, data) -> None:
        self._data = data
        self.name = data['name']
        self.url_path = data['urlPath']
        self.url = data['url']
        self.publisher_id = data['id']
        self.submissions = []

    def __getattr__(self, name: str) -> any:
        if name in self._data:
            return self._data[name]
        else:
            return self.__getattribute__(name)


class Submission():
    """This class stores single issue objects"""

    def __init__(self, data, parent) -> None:
        self._data = data
        self.parent = parent   # journal object

    def __getattr__(self, name: str) -> any:
        if name in self._data:
            return self._data[name]
        else:
            return self.__getattribute__(name)


class DataPoll():
    """This class is going to requests the omp/ojs server
       and even creating/collecting instances
       of Submission and Publication objects
    """

    def __init__(self, configparser) -> None:
        self.publishers = []
        self.load_config(configparser)

    def load_config(self, configparser) -> None:
        g = configparser['general']
        self.endpoint_contexts = g['endpoint_contexts']
        self.endpoint_submissions = g['endpoint_submissions']
        self.endpoint_issues = g['endpoint_issues']
        self.journal_server = f"{g['journal_server']}/"
        self.token = f"apiToken={g['api_token']}"
        e = configparser['export']
        self.export_path = e['export_path']

    def determine_done(self):
        self.processed = {}
        export = [f for f in Path(self.export_path).iterdir() if f.is_file()]
        for file_ in export:
            parts = re.split('[_.]', file_.name)
            publication_id = parts[3]
            submission_file_id = parts[7]
            self.processed[submission_file_id] = publication_id

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

    def rest_call_contexts(self, offset=0) -> str:
        """build contexts call for server request"""
        endpoint = self.endpoint_contexts
        mark = '&' if '?' in endpoint else '?'
        endpoint = f"{endpoint}{mark}offset={offset}&isEnabled=true"
        rest_call = ''.join([
            self.journal_server, '_', endpoint])
        logger.info(
            f"build contexts REST call: {rest_call}")
        return rest_call

    def _request_publishers(self) -> None:
        allitems = 1
        offset = 0
        self.items = []
        while allitems > offset:
            query_publishers = self.rest_call_contexts(offset)
            batch_ = self._server_request(query_publishers)
            logger.info([publ['urlPath'] for publ in batch_['items']])
            self.items.extend(batch_['items'])
            allitems = batch_['itemsMax']
            offset = len(self.items)
        logger.info(F'got all published items ({len(self.items)}), done...')

    def serialise_data(self, start=0, end=-1) -> None:
        logger.info(f"{len(self.items)} publishers found")
        for data in self.items[start:end]:
            publisher = Publisher(data)
            self.publishers.append(publisher)

    def _request_contexts(self) -> None:
        for publisher in self.publishers:
            publisher_url = publisher._href
            context_dict = self._server_request(publisher_url)
            logger.info(
                f'got {len(context_dict)} keys/values for {publisher_url}')
            logger.info(f"Contact Email {context_dict['contactEmail']}")
            publisher._data.update(context_dict)

    def rest_call_issue(self, journal_url, issue_id) -> str:
        """build issue call by id for server request"""
        endpoint = self.endpoint_issues
        endpoint = f"{endpoint}/{issue_id}"
        rest_call = ''.join([journal_url, endpoint])
        logger.debug(f"build issue REST call: {rest_call}")
        return rest_call

    def rest_call_submissions(self, journal_url, offset=0) -> str:
        """build submissions call for server request"""
        endpoint = self.endpoint_submissions
        mark = '&' if '?' in endpoint else '?'
        endpoint = f"{endpoint}{mark}offset={offset}&isPublish=true"
        rest_call = ''.join([
            journal_url, endpoint])
        logger.debug(
            f"build issues REST call: {rest_call}")
        return rest_call

    def _reques_submissions(self) -> None:
        for publisher in self.publishers:
            url = publisher.url
            allsubmission = 1
            offset = 0
            submissions_dict = {'items': []}
            while allsubmission > offset:
                query_submissions = self.rest_call_submissions(
                    publisher.url, offset)
                logger.info(f'request all submission for {publisher.url_path}:'
                            f' {query_submissions}')
                batch_ = self._server_request(query_submissions)
                submissions_dict['items'].extend(batch_['items'])
                allsubmission = batch_['itemsMax']
                offset = len(submissions_dict['items'])
            logger.info('got {} issues'.format(len(submissions_dict['items'])))

            for subm in submissions_dict['items']:
                subm_data = self._server_request(subm['_href'])
                href = subm.get('_href')
                logger.debug(f'process subm {href}')
                for publication in subm['publications']:
                    subm_data['publication'] = publication
                    # hier nach den datails fragen
                    publ_href = publication['_href']
                    publication_detail = self._server_request(publ_href)
                    subm_data.update(publication_detail)

                    issue_id = publication_detail['issueId']

                    if issue_id:
                        issue_request = self.rest_call_issue(url, issue_id)
                        issue_detail = self._server_request(issue_request)
                    subm_data.update(issue_detail)

                    for index, galley in enumerate(publication['galleys']):
                        remote_url = galley['urlRemote']
                        if remote_url:
                            logger.info(
                                f"remote_url already set for {publ_href}"
                                " ({remote_url}), continue")
                            # the galley['urlRemote'] is already set!
                            # no need for further processing
                            del publication['galleys'][index]
                            continue
                        file_id = str(galley['submissionFileId'])
                        publ_id = str(galley['publicationId'])
                        if publ_id == self.processed.get(file_id):
                            logger.warning(f'file exist in export {publ_href}')
                            continue
                        subm_data['galley'] = galley

                subm.update(subm_data)
                subm_ob = Submission(subm, publisher)
                publisher.submissions.append(subm_ob)


def data_poll() -> DataPoll:
    dp = DataPoll(CP)
    dp.determine_done()
    dp._request_publishers()
    dp.serialise_data(3, 4)
    dp._reques_submissions()
    dp._request_contexts()
    return dp


def export_saf(dp: DataPoll) -> None:
    exportsaf = ExportSAF(dp.publishers, CP)
    exportsaf.export()
    exportsaf.write_zips()


def copy_saf(CP: ConfigParser) -> None:
    copysaf = CopySAF(CP)
    copysaf.copy()


def retrieve_doi(CP: ConfigParser) -> None:
    retrievedoi = RetrieveDOI(CP)
    doi_done = retrievedoi.determine_done()
    retrievedoi.retrieve_files(doi_done)


def write_remote_url(CP: ConfigParser) -> None:
    writeremoteurl = WriteRemoteUrl(CP)
    writeremoteurl.write()


def main() -> None:
    start = datetime.now()
    datapoll = data_poll()
    export_saf(datapoll)
    copy_saf(CP)
    retrieve_doi(CP)
    write_remote_url(CP)

    end = datetime.now()
    logger.info(f"Elapsed time: {str(end-start).split('.')[0]}")


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
    parser.add_argument(
        "-m", required=False,
        default=CONFIG_META,
        help="path to META Data configuration file")

    args = vars(parser.parse_args())
    conf = args['c']
    conf_meta = args['m']
    now = str(datetime.now())

    if not pathlib.Path(conf).exists():
        print(f"{now} [ERROR] Missing config '{conf}'! Halt execution!")
        exit(1)
    else:
        print(f"{now} [INFO] use configuration file at {conf}")
    if not pathlib.Path(conf_meta).exists():
        print(f"{now} [ERROR] Missing META-config '{conf_meta}'! "
              "Halt execution!")
        exit(1)
    else:
        print(f"{now} [INFO] use META-configuration file at {conf_meta}")

    CP.read(conf)
    CP.read(conf_meta)

    if args['verbose']:
        logger.setLevel(level=logging.DEBUG)

    main()
