""" Test functionality of journal2saf"""

import configparser
from pathlib import Path
from typing import Collection
import pytest
from journal2saf import ExportSAF, DataPoll
from tests.ressources import publishers
from tests.ressources import issue, issues

JURL = 'https://ojs.exampl.com'
COLLECTION = '123456789/26132'

@pytest.fixture(name="configuration")
def fixture_configuration():
    """provide minimal working configuration"""
    CP = configparser.ConfigParser()
    CP.add_section('general')
    CP.add_section('meta')
    CP.add_section('export')
    CP.set('general', 'api_token', 'acb')
    CP.set('general', 'journal_server', 'https://ojs.example.com')
    CP.set('general', 'type', 'article')
    CP.set('export', 'export_path', './export')
    CP.set('export', 'dc.date.available', 'issue.datePublished')
    CP.set('export', 'collection', COLLECTION)
    CP.set('export', 'doi_prefix', 'http://dx.doi.org/')
    CP.set('meta', 'dc.date.available', 'issue.datePublished')
    CP.set('meta', 'local.bibliographicCitation.pagestart', '"pagestart"')
    return CP


def _server_request(a):
    tail = a.split('/')[-1]
    if tail.isdigit():
        return issue.issue
    else:
        return issues.issues


def download_galley(context, work_dir, issue):
    return ['journal.pdf']

@pytest.fixture(name="contexts")
def fixture_contexts():
    dp = DataPoll()
    dp.publishers_item_dict = publishers.publisher
    dp.serialise_data()
    dp._server_request = _server_request
    dp._request_issues()
    return(dp.publishers)


def test_write_xml_file(tmpdir, contexts, configuration):
    configuration.set('export', 'export_path', str(tmpdir))
    saf = ExportSAF(contexts, configuration)
    saf.download_galley = download_galley
    saf.export()
    saf.write_zips()
    p = Path(tmpdir).iterdir()
    p = p
    
    
