#!/usr/bin/env python3

import re
import shutil
import logging
import mimetypes
import pycountry
from pathlib import Path

import requests

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)-5s %(name)s %(message)s')

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
        pth = work_dir / filename
        with open(pth, 'w') as fh:
            fh.write(collection)

    def write_meta_file(self, item_folder, issue) -> None:
        context = issue.parent
        locale = issue.locale
        schema_dict = {}

        # eval-call will use following variables
        language = self.locale2isolang(locale)
        pagestart = issue.publication['pages']
        pageend = issue.publication['pages']
        logger.debug(f'{context} {language} {pagestart} {pageend}')

        for k, v in self.meta.items():
            meta_tpl = k.split('.')
            schema = meta_tpl.pop(0)
            while len(meta_tpl) < 3:
                meta_tpl.append('', )

            if v.startswith('"') and v.endswith('"'):
                # fixed value read from config
                value = v[1:-1]
            else:
                value = eval(v)
                if isinstance(value, str) and\
                        (value.count('<') > 0 or value.count('>')):
                    value = f'<![CDATA[{value}]]>'

            if value:
                schema_dict.setdefault(
                    schema, []).append((value, *meta_tpl), )

        for schema, dcl in schema_dict.items():
            self.write_xml_file(item_folder, dcl, schema)

    @staticmethod
    def get_filename_from_cd(cd) -> str:
        """Get filename from content-disposition"""
        if not cd:
            return None
        fname = re.findall('filename=(.+)', cd)
        if len(fname) == 0:
            return None
        return fname[0]

    def download_galley(self, context, work_dir, issue) -> list:
        publications = issue.publications
        publication = publications[0]
        context_url = context.url
        galleys = publication['galleys']

        filenames = []
        for galley in galleys:
            galley_id = galley['id']
            mime_type = galley['file']['mimetype']
            submission_id = galley['file']['submissionId']
            extension = mimetypes.guess_extension(mime_type)
            submission_file_id = galley['submissionFileId']
            url = "{}/article/download/{}/{}/{}".format(
                context_url, submission_id, galley_id, submission_file_id)
            response = requests.get(url, verify=False)
            status_code = response.status_code
            if status_code != 200:
                logger.error(f'error download file code:{status_code} {url}')
                continue
            filename = '{}_{}_{}{}'.format(
                context.url_path, submission_id, submission_file_id, extension)

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
            for num, issue in enumerate(context.issues):

                item_folder = Path(self.export_path)\
                    .joinpath(context_name, f'item_{num:03d}',
                              f'issue_{issue.id}')

                self.write_meta_file(item_folder, issue)
                self.write_collections_file(item_folder, self.collection)

                # write contents file
                filenames = self.download_galley(
                    context, item_folder, issue)
                self.write_contents_file(item_folder, filenames)

    def write_zips(self) -> None:
        export_pth = Path(self.export_path)
        contexts = [d for d in export_pth.iterdir() if d.is_dir()]
        size_abs = 0
        for context in contexts:
            items = [i for i in context.iterdir() if i.is_dir()]
            for item in items:
                logger.info(f'zip folder at {item}')
                name = f'{context.name}_{item.name}'
                zipfile = shutil.make_archive(
                    export_pth / name, 'zip', item)
                zipsize = Path(zipfile).stat().st_size
                size_abs += zipsize
                logger.info(f'write zip file {name}.zip '
                            f'with {zipsize >> 20} Mb')
                if Path(zipfile).is_file():
                    shutil.rmtree(item)
            shutil.rmtree(context)
        logger.info(f'finally wrote {size_abs >> 20} Mb, done...')