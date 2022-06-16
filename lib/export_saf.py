#!/usr/bin/env python3

import sys
import string
import logging
import shutil
import mimetypes
import pycountry
from pathlib import Path
from .data_miner import STATE_PROCESSED, STATE_SKIP
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger('journals-logging-handler')


class ExportSAF:
    """Export given data to -Simple Archive Format-"""

    def __init__(self, configparser, report, contexts) -> None:
        self.contexts = contexts
        self.load_config(configparser)
        self.report = report

    def load_config(self, configparser) -> None:
        e = configparser['export']
        g = configparser['general']
        self.meta = configparser['meta']
        self.system = g['system']
        self.export_path = e['export_path']
        self.collection = e['collection']
        self.token = f"&apiToken={g['api_token']}"
        self.journal_server = g['journal_server']
        self.type = g['type']
        self.generate_filename = e.getboolean(
            'generate_filename', fallback=False)

    @staticmethod
    def write_xml_file(work_dir, dblcore, schema) -> None:
        name = 'dublin_core.xml' if schema == 'dc'\
                else f'metadata_{schema}.xml'
        work_dir.mkdir(parents=True, exist_ok=True)
        pth = work_dir / name
        logger.debug(f"write {name}")
        dcline = '  <dcvalue element="{1}" qualifier="{2}"{3}>{0}</dcvalue>'
        dcvalues = [dcline.format(*tpl) for tpl in dblcore]
        schema = f' schema="{schema}"' if schema != 'dc' else ''

        with open(pth, 'w', encoding='utf-8') as fh:
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
        Path(work_dir).mkdir(parents=True, exist_ok=True)
        pth = work_dir / filename
        with open(pth, 'w') as fh:
            fh.write(collection)

    def write_meta_file(self, item_folder, submission) -> None:
        locale = submission.locale
        schema_dict = {}
        # eval-call will use following variables
        context = submission.parent
        language = self.locale2isolang(locale)
        logger.debug(f"{context.url_path} {language}")
        pages = submission.publication.get('pages', 0)
        pagestart = pageend = pages
        try:
            pagestart, pageend = pages.split('-')
        except (ValueError, AttributeError):
            logger.debug(
                f"cannot split pages ({pages}) into start and end")

        for k, v in self.meta.items():
            meta_tpl = k.split('.')
            schema = meta_tpl.pop(0)
            while len(meta_tpl) < 3:
                meta_tpl.append('', )

            if v.startswith('"') and v.endswith('"'):
                # static value, read from config as string
                value = v[1:-1]
            else:
                value = eval(v)
                if value == '':
                    logger.warning("no value for %s", k)
                    self.report.add("WARNING: no value for meta", k)
                if isinstance(value, dict):
                    if locale in value:
                        value = value[locale]
                        meta_tpl[-1] = f' language="{language}"'

                if isinstance(value, str) and\
                        (value.count('<') and value.count('>')):
                    # parse html input
                    soup = BeautifulSoup(value, features="html.parser")
                    # value = soup.get_text()
                    # value = value.replace('& ', '&amp; ')
                    value = soup.get_text().replace('& ', '&amp; ')\
                        .replace('<', '&lt;')\
                        .replace('>', '&gt;')\

                # special treatment for multiple entries
                if k == "dc.contributor.author":
                    if isinstance(value, list):
                        for auth in value:
                            first = auth['givenName'][locale]
                            family = auth['familyName'][locale]
                            value = f"{family}, {first}"
                            schema_dict.setdefault(
                                schema, []).append((value, *meta_tpl), )
                    continue
            if value:
                schema_dict.setdefault(
                    schema, []).append((value, *meta_tpl), )

        for schema, dcl in schema_dict.items():
            self.write_xml_file(item_folder, dcl, schema)

    def download_galley(self, context, work_dir, submission) -> list:
        publication = submission.publication
        context_url = context.url
        galleys = publication['galleys']

        filenames = []
        for galley in galleys:
            if galley['file'] is None:
                logger.warning(
                    'no file in galley with '
                    f'publication_id {galley["publicationId"]}')
                continue
            galley_id = galley['id']
            mime_type = galley['file']['mimetype']
            submission_id = galley['file']['submissionId']
            extension = mimetypes.guess_extension(mime_type)
            submission_file_id = galley['submissionFileId']
            url = "{}/article/download/{}/{}/{}".format(
                context_url, submission_id, galley_id, submission_file_id)
            logger.debug(f'download file: {url}')
            response = requests.get(url, verify=False)
            status_code = response.status_code
            if status_code != 200:
                logger.error(f'error download file code:{status_code} {url}')
                self.report.add(f'error download file code:{status_code}', url)
                continue
            filename = '{}_volume_{}{}'.format(
                context.url_path, submission.volume, extension)
            if not self.generate_filename:
                try:
                    cd = response.headers.get('Content-Disposition')
                    filename = cd.split('"')[1]
                    filename = self.clean_filename(filename)
                except Exception:
                    logger.warning(f'could not extract filename from {cd}')
            export_path = work_dir / filename

            with open(export_path, 'wb') as fh:
                for chunk in response.iter_content(chunk_size=16*1024):
                    fh.write(chunk)
                    print(".", end=(''))
                else:
                    print('')
                logger.debug(
                    f'download galley file at {url} '
                    f'size: {Path(export_path).stat().st_size >> 20} Mb')
                filenames.append(filename)
        return filenames

    def download_publicationFormat(
            self, context, work_dir, submission) -> list:
        publication = submission.publication
        context_url = context.url
        pubformats = publication['publicationFormats']

        filenames = []
        for pubformat in pubformats:
            format_id = pubformat['id']
            submission_id = submission.submissionId
            submission_file_id = pubformat['submissionFileId']
            url = "{}/catalog/download/{}/{}/{}".format(
                context_url, submission_id, format_id, submission_file_id)

            logger.debug(f'download file: {url}')
            response = requests.get(url, verify=False)
            status_code = response.status_code
            if status_code != 200:
                logger.error(f'error download file code:{status_code} {url}')
                self.report.add(f'error download file code:{status_code}', url)
                continue
            mime_type = response.headers.get('content-type')
            extension = mimetypes.guess_extension(mime_type)
            filename = '{}_volume_{}{}'.format(
                context.url_path, submission.seriesPosition, extension)
            if not self.generate_filename:
                try:
                    cd = response.headers.get('Content-Disposition')
                    filename = cd.split('"')[1]
                    filename = self.clean_filename(filename)
                except Exception:
                    logger.warning(f'could not extract filename from {cd}')
            export_path = work_dir / filename

            with open(export_path, 'wb') as fh:
                for chunk in response.iter_content(chunk_size=16*1024):
                    fh.write(chunk)
                    print(".", end=(''))
                else:
                    print('')
                logger.debug(
                    f'download publicationFormat file at {url} '
                    f'size: {Path(export_path).stat().st_size >> 20} Mb')
                filenames.append(filename)
        return filenames

    @staticmethod
    def clean_filename(filename):
        pct = string.punctuation.replace('.', '') + ' '
        return "".join(c for c in filename if c not in pct)

    def export(self) -> None:
        for context in self.contexts:
            context_name = context.url_path
            for num, submission in enumerate(context.submissions):
                filerecordname = 'galley' if self.system == 'ojs'\
                    else 'publicationFormat'
                filerecord = getattr(submission, filerecordname, None)
                if not filerecord:
                    logger.info(
                        f'no {filerecordname} found for publisher_id '
                        f'{submission.parent.publisher_id} '
                        f'submission id {submission.id} '
                        '--> {submission.publishedUrl}')
                    self.report.add(
                        (f'{context_name}: no {filerecordname} found for'),
                        submission.publishedUrl)
                    continue
                if filerecord['state'] == STATE_PROCESSED:
                    logger.info(
                        f'{filerecordname} already processed '
                        f'{submission.parent.publisher_id} '
                        f'submission id {submission.id}')
                    self.report.add(
                        (f'{context_name}: {filerecordname} already processed'
                         '(publisher_id, submission_id) '),
                        (submission.parent.publisher_id, submission.id,))
                    continue
                if filerecord['state'] == STATE_SKIP:
                    self.report.add(
                        (f'[{context_name}] remote_url set for'
                         '(publisher_id, submission_id) '),
                        (submission.parent.publisher_id, submission.id,))
                    continue
                submission_file_id = filerecord['submissionFileId']
                publication_id = filerecord['publicationId']
                item_folder = Path(self.export_path)\
                    .joinpath(context_name, f'publication_id_{publication_id}',
                              f'submission_file_id_{submission_file_id}')

                self.write_meta_file(item_folder, submission)
                self.write_collections_file(item_folder, self.collection)

                if self.system == 'ojs':
                    filenames = self.download_galley(
                        context, item_folder, submission)
                else:
                    filenames = self.download_publicationFormat(
                        context, item_folder, submission)

                self.write_contents_file(item_folder, filenames)

    def write_zips(self) -> None:
        export_pth = Path(self.export_path)
        if not export_pth.is_dir():
            logger.info(f"export path not found ->'{export_pth}', stop export")
            sys.exit(1)
        contexts = [d for d in export_pth.iterdir() if d.is_dir()]
        size_abs = 0
        for context in contexts:
            items = [i for i in context.iterdir() if i.is_dir()]
            for item in items:
                logger.debug(f'zip folder at {item}')
                submission_file_id = list(item.iterdir())[0].name
                name = f'{context.name}_{item.name}_{submission_file_id}'
                already_done = Path(export_pth / (name + '.zip.done'))
                if already_done.is_file():
                    logger.debug(
                        f'{already_done} is already transfered, skip...')
                    self.report.add("zip already transfered", name)
                    if already_done.stat().st_size > 0:
                        open(already_done, "w").close()
                        logger.info('empty file content to save space')
                    continue
                zipfile = shutil.make_archive(
                    export_pth / name, 'zip', item)
                zipsize = Path(zipfile).stat().st_size
                size_abs += zipsize
                fsize = zipsize >> 20 and str(zipsize >> 20) + " Mb"\
                    or str(zipsize) + " bytes"
                logger.info(f"write zip file {name}.zip with {fsize}")
                self.report.add("write zip file", f"{name}.zip")
                if Path(zipfile).is_file():
                    shutil.rmtree(item)
            shutil.rmtree(context)
        if size_abs:
            fsizeabs = size_abs >> 20 and str(size_abs >> 20) + " Mb"\
                    or str(size_abs) + " bytes"
            logger.info(f'finally wrote {fsizeabs}, done...')
            self.report.add("finally wrote", fsizeabs)
        else:
            logger.info('nothing to write, exit')
