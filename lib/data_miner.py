#!/usr/bin/env python3

import re
import sys
import requests
import logging
from pathlib import Path

PKP_STATUS_PUBLISHED = 3  # convention by PKP ojs/omp
STATE_PROCESSED = 'state_processed'
STATE_SKIP = 'state_skip'

logger = logging.getLogger('journals-logging-handler')


class Publisher():
    """This class stores single Publisher objects
        and according submissions"""

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
    """This class stores single Submission objects"""

    def __init__(self, data, parent) -> None:
        self._data = data
        self.parent = parent   # journal object

    def __getattr__(self, name: str) -> any:
        if name in self._data:
            return self._data[name]
        else:
            return self.__getattribute__(name)


class DataPoll():
    """This class is going to requests the OMP/OJS server
       and even creating/collecting instances
       of Submission and Publication objects
    """

    WHITE = []
    BLACK = []

    def __init__(self,
                 configparser,
                 report,
                 whitelist, blacklist) -> None:
        global WHITE, BLACK
        WHITE = whitelist
        BLACK = blacklist
        self.publishers = []
        self.load_config(configparser)
        self.report = report

    def load_config(self, configparser) -> None:
        """extract data from configuration"""
        g = configparser['general']
        self.endpoint_contexts = g['endpoint_contexts']
        self.endpoint_submissions = g['endpoint_submissions']
        self.endpoint_issues = g['endpoint_issues']
        self.journal_server = f"{g['journal_server']}/"
        self.token = f"apiToken={g['api_token']}"
        e = configparser['export']
        self.export_path = e['export_path']

    def determine_done(self):
        """check and register all former processed items
           to avoid repeated downloads """
        self.processed = {}
        try:
            paths = Path(self.export_path).iterdir()
            export_done = [f for f in paths if f.is_file()]
        except FileNotFoundError as err:
            logger.error(f'export path failure {err}')
            self.report.add('ERROR', err)
            sys.exit(1)
        for file_ in export_done:
            parts = re.split('[_.]', file_.name)
            publication_id = parts[3]
            submission_file_id = parts[7]
            self.processed[submission_file_id] = publication_id

    def _server_request(self, query) -> dict:
        """do the http request"""
        mark = '&' if '?' in query else '?'
        query += f'{mark}{self.token}'
        # no need to verify, 'cause we trust the server
        result = requests.get(query, verify=False)

        result_dct = result.json()
        if 'error' in result_dct.keys():
            logger.error(
                f"server request failed due to: {result_dct}")
            logger.info(
                "is your api key from ini file matching the apiToken?")
            raise ValueError(result_dct)
        return result_dct

    def rest_call_contexts(self, offset=0) -> str:
        """build contexts call for server REST-request"""

        endpoint = self.endpoint_contexts
        mark = '&' if '?' in endpoint else '?'
        endpoint = f"{endpoint}{mark}offset={offset}&isEnabled=true"
        rest_call = ''.join([
            self.journal_server, '_', endpoint])
        logger.info(
            f"build contexts REST call: {rest_call}")
        return rest_call

    def request_publishers(self) -> None:
        """batched reqquest for publishers"""
        allitems = 1
        offset = 0
        items = []
        while allitems > offset:
            query_publishers = self.rest_call_contexts(offset)
            batch_ = self._server_request(query_publishers)
            logger.info(
                f"Itmes: {[publ['urlPath'] for publ in batch_['items']]}")

            for item in batch_['items']:
                _href = item['_href']
                batch_extra_data = self._server_request(_href)
                item.update(batch_extra_data)
            items.extend(batch_['items'])
            allitems = batch_['itemsMax']
            offset = len(items)
        if WHITE:
            items = list(filter(lambda w: w['urlPath'] in WHITE, items))
            logger.info(f"filter white-list {WHITE}")
        if BLACK:
            items = list(filter(lambda b: b['urlPath'] not in BLACK, items))
            logger.info(f"filter black-list {BLACK}")
        paths_ = [b['urlPath'] for b in items]
        logger.info(f"after filter {paths_}")
        for b in items:
            self.report.add('processed journals', b['urlPath'])
        self.items = items
        logger.info(
            f'got all published items ({len(self.items)}), done...')

    def serialise_data(self) -> None:
        """ store all received data as Publisher object"""
        logger.info(f"process {len(self.items)} publishers")
        for data in self.items:
            publisher = Publisher(data)
            self.publishers.append(publisher)

    def request_contexts(self) -> None:
        """loop publishers, request data form server"""
        for publisher in self.publishers:
            publisher_url = publisher._href
            context_dict = self._server_request(publisher_url)
            logger.info(
                f"request {publisher_url}"
                f" / Contact Email {context_dict['contactEmail']}")
            publisher._data.update(context_dict)

    def rest_call_issue(self, journal_url, issue_id) -> str:
        """build issue call by id for server REST-request"""
        endpoint = self.endpoint_issues
        endpoint = f"{endpoint}/{issue_id}"
        rest_call = ''.join([journal_url, endpoint])
        logger.debug(f"build issue REST call: {rest_call}")
        return rest_call

    def rest_call_submissions(self, journal_url, offset=0) -> str:
        """build submissions call for server REST-request"""
        endpoint = self.endpoint_submissions
        mark = '&' if '?' in endpoint else '?'
        endpoint = f"{endpoint}{mark}offset={offset}&isPublish=true"
        rest_call = ''.join([
            journal_url, endpoint])
        logger.debug(
            f"build issues REST call: {rest_call}")
        return rest_call

    def get_submission_file_id(self, href, assocId):
        """only for OMP"""
        filesdata = self._server_request(href + '/files')
        for fd in filesdata['items']:
            if fd['assocId'] == int(assocId):
                return fd['id']

    def request_submissions(self) -> None:
        """query all informations via OJS/OMP REST api"""
        for publisher in self.publishers:
            url_path = publisher.url_path
            logger.debug('#' * 100)
            logger.debug(url_path)
            logger.debug('#' * 100)
            url = publisher.url
            allsubmission = 1
            offset = 0
            published = not_published = 0
            submissions_dict = {'items': []}
            while allsubmission > offset:
                query_submissions = self.rest_call_submissions(
                    publisher.url, offset)
                logger.debug(
                    f'request submission for {url_path}:'
                    f' {query_submissions}')
                batch_ = self._server_request(query_submissions)
                submissions_dict['items'].extend(batch_['items'])
                allsubmission = batch_['itemsMax']
                offset = len(submissions_dict['items'])
            logger.info(
                f'request all submissions for {url_path}')
            logger.info(
                'got {} issues'.format(len(submissions_dict['items'])))

            for subm in submissions_dict['items']:
                if subm['status'] != PKP_STATUS_PUBLISHED:
                    not_published += 1
                    continue
                published += 1
                subm_data = self._server_request(subm['_href'])
                href = subm.get('_href')
                logger.debug(f'process subm {href}')
                for publication in subm['publications']:
                    subm_data['publication'] = publication
                    publ_href = publication['_href']
                    submission_id = subm['id']
                    publication_id = subm['currentPublicationId']
                    publication_detail = self._server_request(publ_href)
                    subm_data.update(publication_detail)

                    issue_id = publication_detail.get('issueId')

                    if issue_id:
                        issue_request = self.rest_call_issue(url, issue_id)
                        issue_detail = self._server_request(issue_request)
                        subm_data.update(issue_detail)

                    omp = 'publicationFormats' in publication

                    file_records = publication['publicationFormats'] if omp\
                        else publication['galleys']

                    for index, record in enumerate(file_records):
                        record['state'] = None
                        remote_url = record['urlRemote']
                        if remote_url:
                            logger.debug(
                                f"remote_url already set for {publ_href}"
                                f" ({remote_url}), continue")
                            # the record['urlRemote'] is already set!
                            # no further processing is required
                            publ_href_tail = (publication_id, submission_id)
                            mess = ('remote_url already set for '
                                    '(publication_id, submission_id)')
                            self.report.add(
                                f'{url_path}: {mess}', publ_href_tail)
                            record['state'] = STATE_SKIP
                            continue

                        if omp:
                            assoc = str(record['id'])
                            file_id = self.get_submission_file_id(href, assoc)
                            record['submissionFileId'] = file_id
                        else:
                            file_id = str(record['submissionFileId'])

                        publ_id = str(record['publicationId'])

                        if publ_id == self.processed.get(file_id):
                            logger.info(
                                f'file exists in export {publ_href}, skip')
                            self.report.add(
                                'already processed submissions', submission_id)
                            record['state'] = STATE_PROCESSED
                        subm_data.setdefault('files', []).append(record)

                subm.update(subm_data)
                subm_ob = Submission(subm, publisher)
                publisher.submissions.append(subm_ob)
            print()
            logger.info(
                f"request {published} publications, "
                f"{not_published} unpublished skipped")
