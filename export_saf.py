#!/usr/bin/env python3

import shutil
import logging
import mimetypes
import pycountry
from pathlib import Path

import requests
from bs4 import BeautifulSoup


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)-5s %(message)s')

logger = logging.getLogger(__file__.split('/')[-1])


class ExportSAF:
    """Export given data to -Simple Archive Format-"""

    def __init__(self, contexts, configparser) -> None:
        self.contexts = contexts
        self.load_config(configparser)

    def load_config(self, configparser) -> None:
        e = configparser['export']
        g = configparser['general']
        self.meta = configparser['meta']
        self.export_path = e['export_path']
        self.collection = e['collection']
        self.token = f"&apiToken={g['api_token']}"
        self.journal_server = g['journal_server']
        self.type = g['type']
        self.dc_identifier_external_prefix = 'ojs'  # TODO: use config

    @staticmethod
    def write_xml_file(work_dir, dblcore, schema) -> None:
        name = 'dublin_core.xml' if schema == 'dc'\
                else f'metadata_{schema}.xml'
        work_dir.mkdir(parents=True, exist_ok=True)
        pth = work_dir / name
        logger.info(f"write {name}")
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
        logger.debug(f"{context} {language}")
        pages = submission.publication['pages']
        pagestart = pageend = pages
        try:
            pagestart, pageend = pages.split('-')
        except (ValueError, AttributeError):
            logger.warning(
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

                if isinstance(value, dict):
                    if locale in value:
                        value = value[locale]
                        meta_tpl[-1] = f' language="{language}"'

                if isinstance(value, str) and\
                        (value.count('<') and value.count('>')):
                    soup = BeautifulSoup(value, features="html.parser")
                    value = soup.get_text()
                    value = value.replace('& ', '&amp; ')

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
            publication_id = galley['publicationId']
            extension = mimetypes.guess_extension(mime_type)
            submission_file_id = galley['submissionFileId']
            url = "{}/article/download/{}/{}/{}".format(
                context_url, submission_id, galley_id, submission_file_id)
            logger.info(f'download file: {url}')
            response = requests.get(url, verify=False)
            status_code = response.status_code
            if status_code != 200:
                logger.error(f'error download file code:{status_code} {url}')
                continue
            filename = '{}_{}_{}{}'.format(
                context.url_path, publication_id,
                submission_file_id, extension)

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
        for context in self.contexts:
            context_name = context.url_path
            for num, submission in enumerate(context.submissions):
                if not (hasattr(submission, 'galley') and submission.galley):
                    logger.warning(
                        'no galley found for publisher_id '
                        f'{submission.parent.publisher_id}')
                    continue
                submission_file_id = submission.galley['submissionFileId']
                publication_id = submission.galley['publicationId']
                item_folder = Path(self.export_path)\
                    .joinpath(context_name, f'publication_id_{publication_id}',
                              f'submission_file_id_{submission_file_id}')

                self.write_meta_file(item_folder, submission)
                self.write_collections_file(item_folder, self.collection)

                # write contents file
                filenames = self.download_galley(
                    context, item_folder, submission)
                self.write_contents_file(item_folder, filenames)

    def write_zips(self) -> None:
        export_pth = Path(self.export_path)
        if not export_pth.is_dir():
            logger.info(f"Path not found -> '{export_pth}', stop export")
            exit()
        contexts = [d for d in export_pth.iterdir() if d.is_dir()]
        size_abs = 0
        for context in contexts:
            items = [i for i in context.iterdir() if i.is_dir()]
            for item in items:
                logger.info(f'zip folder at {item}')
                submission_file_id = list(item.iterdir())[0].name
                name = f'{context.name}_{item.name}_{submission_file_id}'
                alredy_done = Path(export_pth / (name+'.zip.done'))
                if alredy_done.is_file():
                    logger.info(
                        f'{alredy_done} is alredy processed, skip...')
                    continue
                zipfile = shutil.make_archive(
                    export_pth / name, 'zip', item)
                zipsize = Path(zipfile).stat().st_size
                size_abs += zipsize
                logger.info(f'write zip file {name}.zip '
                            f'with {zipsize >> 20} Mb')
                if Path(zipfile).is_file():
                    shutil.rmtree(item)
            shutil.rmtree(context)
        if size_abs:    
            logger.info(f'finally wrote {size_abs >> 20} Mb, done...')
        else:
            logger.info(f'nothing to write, exit')

