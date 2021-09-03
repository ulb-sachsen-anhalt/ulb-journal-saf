#!/usr/bin/env python3

import re
import logging
import argparse
import shutil
import mimetypes
import requests
import warnings
import pycountry
from pathlib import Path
from configparser import ConfigParser

warnings.filterwarnings('ignore', message='Unverified HTTPS request')

###############################################################
STATUS_PUBLISHED = 3
CONFIG = "conf/config.ini"
###############################################################

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)-5s %(name)s %(message)s')

logger = logging.getLogger(__file__.split('/')[-1])

CP = ConfigParser()
CP.read(CONFIG)


class Journal():
    """This class stores single journal objects"""

    def __init__(self, data):
        super().__init__()
        self.name = data['name']
        self.url_path = data['urlPath']
        self.url = data['url']
        self.submissions = []
        self.publications = []
        self.description = data['description']


class Submission:
    """This class stores submission objects"""

    def __init__(self, data, parent):
        self._href = data['_href']
        self.parent = parent
        self.data = data
        self.id = data['id']
        self.publications = []
        self.status = data['status']
        self.locale = data['locale']


class Publication:
    """This class stores publication objects"""

    def __init__(self, data, parent):
        self._href = data['_href']
        self.parent = parent
        self.data = data
        self.galleys = []
        self.issue_id = data['issueId']
        self.issue = {}
        self.galleys = []


class Galley:
    """This class stores single galley objects"""

    def __init__(self, data, parent):
        self.parent = parent
        self.approved = data['isApproved']
        file_ = data['file']

        self.gallery_id = data['id']
        self.submission_id = file_['submissionId']
        self.submission_file_id = data['submissionFileId']

        self.href = file_['_href']
        self.url = file_['url']
        self.description = file_['description']
        self.mimetype = file_['mimetype']


class JournalPoll():
    """This class is going to requests the journal server
       and even creating/collecting instances
       of submissions and publication objects
    """

    def __init__(self):
        self.journals = []
        self.load_config()

    def load_config(self) -> None:
        g = CP['general']
        self.endpoint_contexts = g['endpoint_contexts']
        self.endpoint_submissions = g['endpoint_submissions']
        self.endpoint_issue = g['endpoint_issue']
        self.journal_server = f"{g['journal_server']}/"
        self.token = f"apiToken={g['api_token']}"

    def _server_request(self, query) -> dict:
        # no need to verify, 'cause we trust the server
        if '?' in query:
            query += f'&{self.token}'
        else:
            query += f'?{self.token}'
        result = requests.get(query, verify=False)
        result_dct = result.json()
        if 'error' in result_dct.keys():
            logger.error(
                f"server reequest failed due to: {result_dct}")
            raise ValueError(result_dct)
        return result_dct

    def rest_call_contexts(self) -> str:
        rest_call = ''.join([
            self.journal_server,
            self.endpoint_contexts])
        logger.info(
            f"build contexts REST call: {rest_call}")
        return rest_call

    def rest_call_submissions(self, jounal_name,
                              status=STATUS_PUBLISHED) -> str:
        rest_call = ''.join([
            self.journal_server,
            jounal_name,
            self.endpoint_submissions,
            f'?status={status}'])
        logger.debug(
            "build submissions REST call: {rest_call}")
        return rest_call

    def rest_call_publications(self, href):
        rest_call = href
        logger.debug(
            "build publications REST call: {rest_call}")
        return rest_call

    def rest_call_issue(self, jounal_name, issue_id):
        rest_call = ''.join([
            self.journal_server,
            jounal_name,
            self.endpoint_issue,
            f'/{issue_id}'])
        logger.debug(
            "build issue REST call: {rest_call}")
        return rest_call

    def _request_contexts(self) -> None:
        query_contexts = self.rest_call_contexts()
        self.journals_dict = self._server_request(query_contexts)

    def _request_submission(self, journal_name) -> dict:
        query_submission = self.rest_call_submissions(journal_name)
        submission = self._server_request(query_submission)
        logger.info(f"receive {len(submission['items'])} "
                    f"submission items for '{journal_name}'")
        items = [item for item in submission['items']]
        return items

    def _request_issue(self, journal_name, publication) -> None:
        issue_id = publication.issue_id
        query_issue = self.rest_call_issue(journal_name, issue_id)
        logger.info(f'request issue: {query_issue}')
        publication.issue = self._server_request(query_issue)

    def serialise_journals(self, start=0, end=-1) -> None:
        journales = self.journals_dict
        if 'items' in journales.keys():
            logger.info(f"{len(journales['items'])} journals found")
            for data in journales['items'][start:end]:
                journal_obj = Journal(data)
                self.journals.append(journal_obj)

    def serialise_submissions(self) -> None:
        for journal in self.journals:
            journal_name = journal.url_path
            submission_items = self._request_submission(journal_name)
            for item in submission_items:
                if item['status'] != STATUS_PUBLISHED:
                    raise ValueError(
                        f"this item is *not* published yet! {item['_href']}")
                subm_obj = Submission(item, journal)
                journal.submissions.append(subm_obj)
                for publication in item.get('publications'):
                    p = self.rest_call_publications(publication.get('_href'))
                    publication_result = self._server_request(p)
                    pub_obj = Publication(publication_result, item)
                    subm_obj.publications.append(pub_obj)
                    self._request_issue(journal_name, pub_obj)

    def extract_galleys(self) -> None:
        s = p = g = 0
        for j, journal in enumerate(self.journals, start=1):
            for s, subm in enumerate(journal.submissions, start=1):
                for p, publ in enumerate(subm.publications, start=1):
                    for g, galley in enumerate(publ.data['galleys'], start=1):
                        galley_obj = Galley(galley, self)
                        publ.galleys.append(galley_obj)

        logger.info(
            f"proccess {j} journals, {s} submissions, "
            f"{p} publication {g} galleys")


class ExportSAF:
    """Export given data to -Simple Archive Format-"""

    def __init__(self, journals):
        self.journals = journals
        self.load_config()

    def load_config(self) -> None:
        e = CP['export']
        g = CP['general']
        self.export_path = e['export_path']
        self.collection = e['collection']
        self.token = f"&apiToken={g['api_token']}"
        self.journal_server = g['journal_server']
        self.type = g['type']

    @staticmethod
    def write_xml_file(work_dir, dblcore, name, schema=None) -> None:
        work_dir.mkdir(parents=True, exist_ok=True)
        pth = work_dir / name
        dcline = '  <dcvalue element="{}" qualifier="{}"{}>{}</dcvalue>'
        dcvalues = [dcline.format(*tpl) for tpl in dblcore]
        schema = f' schema="{schema}"' if schema else ''

        with open(pth, 'w') as fh:
            fh.write('<?xml version="1.0" encoding="UTF-8"?>\n')
            fh.write(f'<dublin_core{schema}>\n')
            fh.write('\n'.join(dcvalues))
            fh.write('\n</dublin_core>')

    @staticmethod
    def locale2isolang(local_code) -> str:
        locale = local_code[0:2]
        lang = pycountry.languages.get(alpha_2=locale)
        isolang = lang.bibliographic if hasattr(lang, 'bibliographic')\
            else lang.alpha_3
        return isolang

    @staticmethod
    def write_contents_file(work_dir, file_list) -> None:
        filename = 'contents'
        pth = work_dir / filename
        with open(pth, 'w') as fh:
            fh.writelines("{}\n".format(line) for line in file_list)

    @staticmethod
    def write_collections_file(work_dir, collection) -> None:
        filename = 'collections'
        pth = work_dir / filename
        with open(pth, 'w') as fh:
            fh.write(collection)

    def write_local_file(self, item_folder, submission):
        schema = 'local'
        mapping = []
        publications = submission.publications
        assert len(publications) == 1
        publication = publications[0]
        # data = publication.data.get('')
        publications = submission.data['publications']
        data = publications[0]
        # local.OJSinternalid
        # id_ = data.get('id')
        # local.bibliographicCitation.page<{start,end}>
        # ('OJSinternalid', 'none', '', id_),

        issue = publication.issue
        # identification = (issue.get('identification'))  # e.g.: Bd. 20 (2021)
        volume = issue.get('volume')
        number = issue.get('number')
        locale = submission.locale
        title = submission.parent.name[locale]
        description = submission.parent.description[locale]
        mapping.append(('bibliographicCitation', 'volume', '', volume), )
        mapping.append(('bibliographicCitation', 'number', '', number), )
        mapping.append(('bibliographicCitation', 'journaltitle', '', title), )
        mapping.append((
            'description', 'abstract', '', f'<![CDATA[{description}]]>'), )

        try:
            start, end = data.get('pages').split('-')
            mapping.extend([
                ('bibliographicCitation', 'pagestart', '', start),
                ('bibliographicCitation', 'pageend', '', end)]
            )
        except ValueError:
            logger.info(f"'pages' property for {item_folder} missing")

        self.write_xml_file(
            item_folder, mapping,
            f'metadata_{schema}.xml',
            schema=schema)

    def create_meta_file(self, item_folder, submission) -> None:
        publications = submission.publications
        publication = publications[0]

        filename = 'dublin_core.xml'
        dcl = []

        lang = self.locale2isolang(publication.data.get('locale'))

        # dc.title, dc.title.translated
        for locale, title in publication.data.get('fullTitle').items():
            if title:
                if locale == 'de_DE':
                    lng = self.locale2isolang(locale)
                    dcl.append(
                        ('title', 'none', f' language="{lng}"', title)
                        )
                if locale == 'en_US':
                    lng = self.locale2isolang(locale)
                    dcl.append(
                        ('title', 'translated', f' language="{lng}"', title)
                        )

        # dc.date.available
        date_ = publication.data.get('datePublished')
        dcl.append(('date', 'available', '', date_), )

        # dc.contributor.author
        authors = publication.data.get('authorsString')
        for author in authors.split(','):
            dcl.append(('contributor', 'author', '', author.strip()), )



        # dc.language.iso
        # dcl.append(('language', 'iso', '', isolang), )

        # dc.description.abstract
        galleys = publication.galleys
        for galley in galleys:
            for locale, desc in galley.description.items():
                lang = self.locale2isolang(locale)
                if desc:
                    dcl.append(
                        ('description', 'abstract',
                         f' language="{lang}"', desc), )

            dcl.append(('type', 'none', '', self.type), )

        self.write_xml_file(item_folder, dcl, filename)

    @staticmethod
    def get_filename_from_cd(cd) -> str:
        """Get filename from content-disposition"""
        if not cd:
            return None
        fname = re.findall('filename=(.+)', cd)
        if len(fname) == 0:
            return None
        return fname[0]

    def download_galley(self, journal, work_dir, submission) -> list:
        publications = submission.publications
        publication = publications[0]
        journal_url = journal.url
        galleys = publication.galleys

        filenames = []
        for galley in galleys:
            galley_id = galley.gallery_id
            submission_id = galley.submission_id
            mime_type = galley.mimetype
            extension = mimetypes.guess_extension(mime_type)
            submission_file_id = galley.submission_file_id
            url = "{}/article/download/{}/{}/{}".format(
                journal_url, submission_id, galley_id, submission_file_id)
            response = requests.get(url, verify=False)
            status_code = response.status_code
            if status_code != 200:
                logger.error(f'error download file code:{status_code} {url}')
                continue
            filename = '{}_{}_{}{}'.format(
                journal.url_path, submission_id, submission_file_id, extension)

            export_path = work_dir / filename

            with open(export_path, 'wb') as fh:
                for chunk in response.iter_content(chunk_size=16*1024):
                    fh.write(chunk)
                logger.info(
                    f'download file at {url} '
                    f'size: {Path(export_path).stat().st_size >> 20} Mb')
                filenames.append(filename)
        return filenames

    def export(self) -> None:
        for journal in self.journals:
            journal_name = journal.url_path
            for submission in journal.submissions:

                item_folder = Path(self.export_path)\
                    .joinpath(journal_name,
                              f'submission_{submission.id}')

                self.create_meta_file(item_folder, submission)

                # write schema files
                schemas = ['local', ]
                for schema in schemas:
                    method = f'write_{schema}_file'
                    try:
                        getattr(self, method)(item_folder, submission)
                    except AttributeError as err:
                        logger.error(
                            f'method for schema "{method}" not found {err}')
                        raise NotImplementedError(err)

                # write collections file
                self.write_collections_file(item_folder, self.collection)

                # write contents file
                filenames = self.download_galley(
                    journal, item_folder, submission)
                self.write_contents_file(item_folder, filenames)

    def write_zips(self):
        export_pth = Path(self.export_path)
        journals = [d for d in export_pth.iterdir() if d.is_dir()]
        size_abs = 0
        for journal in journals:
            items = [i for i in journal.iterdir() if i.is_dir()]
            for item in items:
                logger.info(f'zip folder at {item}')
                name = f'{journal.name}_{item.name}'
                zipfile = shutil.make_archive(export_pth / name, 'zip', item)
                zipsize = Path(zipfile).stat().st_size
                size_abs += zipsize
                logger.info(f'write zip file {name}.zip '
                            f'with {zipsize >> 20} Mb')
                if Path(zipfile).is_file():
                    shutil.rmtree(item)
            shutil.rmtree(journal)
        logger.info(f'finally wrote {size_abs >> 20} Mb, done...')


def main():
    jp = JournalPoll()
    jp._request_contexts()
    jp.serialise_journals(1, 3)
    jp.serialise_submissions()
    jp.extract_galleys()

    saf = ExportSAF(jp.journals)
    saf.export()
    saf.write_zips()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=("Request Journalserver(OJS/OMP)"
                     " and build SAF's of all published Submissions"))
    parser.add_argument(
        "-v", "--verbose", help="increase output verbosity",
        action="store_true")
    args = parser.parse_args()
    if args.verbose:
        logger.setLevel(level=logging.DEBUG)

    main()
