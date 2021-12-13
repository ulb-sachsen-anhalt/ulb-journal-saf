""" Test functionality of journal2saf"""

import configparser
from zipfile import ZipFile
from pathlib import Path
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
    CP.set('general', 'endpoint_contexts', '/api/v1/contexts?isEnabled=true')
    CP.set('general', 'endpoint_submissions', '/api/v1/submissions')
    CP.set('general', 'endpoint_issues', '/api/v1/issues')
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
    return ['journal.pdf', ]


@pytest.fixture(name="contexts")
def fixture_contexts(configuration):
    dp = DataPoll(configuration)
    dp.submissions_dict = publishers.publisher
    dp.items = dp.submissions_dict['items']
    dp.serialise_data()
    dp._server_request = _server_request
    return(dp.publishers)


def test_locale2isolang():
    locale = ExportSAF.locale2isolang('de_DE')
    assert locale == 'ger'
    locale = ExportSAF.locale2isolang('en_EN')
    assert locale == 'eng'


def test_write_contents_file(tmpdir):
    saf_files = ['testfile.foo', 'testfile.bar', ]
    ExportSAF.write_contents_file(tmpdir, saf_files)
    paths = list(Path(tmpdir).iterdir())
    contents_file = paths[0]
    assert contents_file.name == 'contents'
    with open(contents_file) as fh:
        name = fh.readline()
        assert name.strip() in saf_files


def test_write_collections_file(tmpdir):
    collection = 'foo/bar'
    ExportSAF.write_collections_file(tmpdir, collection)
    paths = list(Path(tmpdir).iterdir())
    collections_file = paths[0]
    assert collections_file.name == 'collections'
    with open(collections_file) as fh:
        name = fh.readline()
        assert name.strip() == collection


def test_write_zip(tmpdir, contexts, configuration):
    configuration.set('export', 'export_path', str(tmpdir))
    saf = ExportSAF(contexts, configuration)
    saf.download_galley = download_galley
    saf.export()
    saf.write_zips()
    paths = Path(tmpdir).iterdir()
    zipfiles = ['cicadina_publication_id_102_submission_file_id_398.zip']
    contains = [
        '', 'contents', 'dublin_core.xml', 'metadata_local.xml', 'collections']
    for path in paths:
        assert path.name in zipfiles
        zipfile = ZipFile(path)
        assert min([f.split('/')[-1] in contains for f in zipfile.namelist()])
