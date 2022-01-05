""" Test functionality of journal2saf"""

import pytest
import configparser
from journal2saf import DataPoll
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
    CP.set('general', 'endpoint_contexts', '/api/v1/contexts?isEnabled=true')
    CP.set('general', 'endpoint_submissions', '/api/v1/issues')
    CP.set('general', 'endpoint_issues', '/api/v1/issues')
    CP.set('export', 'dc.date.available', 'issue.datePublished')
    CP.set('export', 'collection', COLLECTION)
    CP.set('export', 'doi_prefix', 'http://dx.doi.org/')
    CP.set('meta', 'dc.date.available', 'issue.datePublished')
    CP.set('meta', 'local.bibliographicCitation.pagestart', '"pagestart"')
    return CP


def test_s(configuration):
    """check if methode deliver valid call"""
    dp = DataPoll(configuration)
    restcall = dp.rest_call_contexts(1)
    assert restcall.endswith('isEnabled=true')


def test_rest_call_issues(configuration):
    """check if methode deliver valid call"""
    journal_url = JURL
    journalid = '23'
    dp = DataPoll(configuration)
    endpoint = "/api/v1/issues"
    dp.endpoint_issues = endpoint
    restcall = dp.rest_call_issue(journal_url, journalid)
    assert restcall == JURL + endpoint + '/' + journalid


def test_serialise_data(configuration):
    dp = DataPoll(configuration)
    dp.submissions_dict = publishers.publisher
    dp.items = dp.submissions_dict['items']
    dp.serialise_data()
    assert isinstance(dp.publishers, list)
    assert len(dp.publishers) == 2


def _server_request(a):
    tail = a.split('/')[-1]
    if tail.isdigit():
        return issue.issue
    else:
        return issues.issues


def test_request_issues(configuration):
    dp = DataPoll(configuration)
    dp.submissions_dict = publishers.publisher
    dp.items = dp.submissions_dict['items']
    dp.serialise_data()
    dp._server_request = _server_request
    dp.rest_call_issue('url', 1)
    assert(len(dp.publishers)) == 2
