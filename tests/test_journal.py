""" Test functionality of journal2saf"""

from journal2saf import DataPoll
from tests.ressources import publishers
from export_saf import ExportSAF
from transfer_saf import TransferSAF


def test_rest_call_context():
    """check if methode deliver valid call"""
    journalname = 'ojs'
    journalid = '23'
    dp = DataPoll()
    restcall = dp.rest_call_context(journalname, journalid)
    assert journalname in restcall
    assert restcall.endswith(journalid)
    restcall = dp.rest_call_context(journalname)
    assert restcall.endswith('contexts')
    restcall = dp.rest_call_context()
    assert restcall.endswith('contexts')


def test_rest_call_issues():
    """check if methode deliver valid call"""
    journalname = 'ojs'
    journalid = '23'
    dp = DataPoll()
    restcall = dp.rest_call_issues(journalname, journalid)
    assert journalname in restcall
    assert restcall.endswith(journalid)
    restcall = dp.rest_call_issues(journalname)
    assert restcall.endswith('issues')


def test_serialise_data():
    dp = DataPoll()
    dp.publishers_item_dict = publishers.publisher
    dp.serialise_data()
    assert isinstance(dp.publishers, list)
    assert len(dp.publishers) == 14
