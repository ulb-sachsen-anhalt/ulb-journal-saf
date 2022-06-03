#!/usr/bin/env python3

import re
import logging
import requests

from pathlib import Path

logger = logging.getLogger('journals-logging-handler')


class WriteRemoteUrl:
    """Write property 'remote_url' on OMP/OJS server
       to achieve this, you need to install the 'setRemoteUrlPlugin'
       on your OMP or OJS server
    """

    def __init__(self, configparser, report) -> None:
        self.load_config(configparser)
        self.client = None
        self.report = report

    def load_config(self, configparser) -> None:
        e = configparser['export']
        g = configparser['general']
        self.export_path = e['export_path']
        self.doi_prefix = e['doi_prefix']
        self.journal_server = g['journal_server']
        self.token = g['token']

    def write(self):
        logger.info('process dois')
        export = Path(self.export_path).glob('*.doi')
        if not export:
            logger.info('no dois found...')
        doiprefix = self.doi_prefix
        count_doi_set = 0
        for doi in export:
            doi = Path(doi)
            with open(doi) as fh:
                doival = fh.read()
                remote_url = (doiprefix + doival.split(':')[-1]).strip()
                parts = re.split('[_.]', doi.name)
                publication_id = parts[3]
                logger.info(
                    f'got DOI {remote_url} '
                    f'for publication_id {publication_id}')
                params = {'publication_id': publication_id,
                          'remote_url': remote_url,
                          'token': self.token}
                result = requests.get(
                    url=self.journal_server, params=params, verify=False)

                if result.status_code == 200:
                    logger.info(
                        f'successfully committed remote_url {remote_url} '
                        f'with publication_id {publication_id} ')
                    done = doi.with_suffix(doi.suffix + '.done')
                    doi.rename(done)
                    count_doi_set += 1
                    logger.debug(f'rename DOI file to {done}')
                    self.report.add('rename DOI file to', done)
                else:
                    logger.error(f'rename DOI file to failed {result.reason}')
                    self.report.add('rename DOI file to failed', result.reason)

        if count_doi_set:
            logger.info(f"{count_doi_set} DOIs successfully set")
