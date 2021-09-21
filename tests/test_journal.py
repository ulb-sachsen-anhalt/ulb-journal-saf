""" Test functionality of journal2saf"""

from journal2saf import DataPoll
from tests.ressources import publishers
from tests.ressources import issue, issues

JURL = 'https://ojs.exampl.com'


def test_rest_call_context():
    """check if methode deliver valid call"""
    journal_url = JURL
    journalid = '23'
    dp = DataPoll()
    restcall = dp.rest_call_context(journal_url, journalid)
    assert journal_url in restcall
    assert restcall.endswith(journalid)
    restcall = dp.rest_call_context(journal_url)
    assert restcall.endswith('contexts')
    restcall = dp.rest_call_context()
    assert restcall.endswith('contexts')


def test_rest_call_issues():
    """check if methode deliver valid call"""
    journal_url = JURL
    journalid = '23'
    dp = DataPoll()
    endpoint = "/api/v1/issues"
    dp.endpoint_issues = endpoint
    restcall = dp.rest_call_issues(journal_url, journalid)
    assert restcall == JURL + endpoint + '/' + journalid
    restcall = dp.rest_call_issues(journal_url)
    assert restcall == JURL + endpoint


def test_serialise_data():
    dp = DataPoll()
    dp.publishers_item_dict = publishers.publisher
    dp.serialise_data()
    assert isinstance(dp.publishers, list)
    assert len(dp.publishers) == 1


def _server_request(a):
    tail = a.split('/')[-1]
    if tail.isdigit():
        return issue.issue
    else:
        return issues.issues


def test_request_issues():
    dp = DataPoll()
    dp.publishers_item_dict = publishers.publisher
    dp.serialise_data()
    dp._server_request = _server_request
    dp._request_issues()
    assert(len(dp.publishers)) == 1
