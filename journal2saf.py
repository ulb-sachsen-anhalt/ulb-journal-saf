#!/usr/bin/env python3

import sys
import time
import logging
import logging.config
import argparse
import warnings
import pathlib
from datetime import datetime
from pathlib import Path
from configparser import ConfigParser

from lib.export_saf import ExportSAF
from lib.copy_saf import CopySAF
from lib.retrieve_doi import RetrieveDOI
from lib.write_remote_url import WriteRemoteUrl
from lib.data_miner import DataPoll

warnings.filterwarnings(
    'ignore', message='Unverified HTTPS request')

###############################################################
# defaults:
CONFIG = "conf/config.ini"
CONFIG_META = "conf/config_meta.ini"
###############################################################

LOG_FILE_FORMAT = '%Y-%m-%d'
date_ = time.strftime(LOG_FILE_FORMAT, time.localtime())
logfile_name = Path("log", f"http_record_handler_{date_}.log")
conf_logname = {'logname': logfile_name}

logging.config.fileConfig('conf/logging.conf', defaults=conf_logname)
logger = logging.getLogger('journals-logging-handler')


CP = ConfigParser()
# preserving capital letters with monkey patch
CP.optionxform = lambda option: option


class TaskDispatcher:
    """dispatching following tasks:
       * Ask OJS/OMP api for publications
       * Create objects of all _new_ publications
       * download file data (gallays/publication formats)
       * create ZIP's according to definition of import format SAF
       * push SAF's to Dspace Server
       * retrieve DOI's form Dspace
       * write DOI's back to OJS/OMP
    """

    def __init__(self) -> None:
        self.start = None
        self.end = None
        self.datapoll = None

    def start_dispatcher(self) -> None:
        self.start = datetime.now()

    def stop_dispatcher(self) -> None:
        self.end = datetime.now()

    def schedule(self) -> None:
        self.data_poll()
        self.export_saf_archive()
        self.copy_saf()
        writedoi = CP.getboolean('general', 'update_remote')
        if writedoi:
            logger.info('retrieve DOI')
            self.retrieve_doi()
            logger.info('write DOI')
            self.write_remote_url()
        else:
            logger.info('skip treating DOI (config)')

    def data_poll(self) -> None:
        dp = DataPoll(CP, WHITE, BLACK)
        dp.determine_done()
        dp._request_publishers()
        dp.serialise_data()
        dp._reques_submissions()
        dp._request_contexts()
        self.datapoll = dp

    def export_saf_archive(self) -> None:
        publishers = self.datapoll.publishers
        exportsaf = ExportSAF(publishers, CP)
        exportsaf.export()
        exportsaf.write_zips()

    def copy_saf(self) -> None:
        copysaf = CopySAF(CP)
        copysaf.copy()

    def retrieve_doi(self) -> None:
        retrievedoi = RetrieveDOI(CP)
        doi_done = retrievedoi.determine_done()
        retrievedoi.retrieve_files(doi_done)

    def write_remote_url(self) -> None:
        writeremoteurl = WriteRemoteUrl(CP)
        writeremoteurl.write()


def main() -> None:
    dispatcher = TaskDispatcher()
    dispatcher.start_dispatcher()
    dispatcher.schedule()
    dispatcher.stop_dispatcher()
    delta = str(dispatcher.end - dispatcher.start)
    logger.info(f"Elapsed time: {delta.split('.')[0]}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=("Request Journalserver(OJS/OMP)"
                     " and build SAF's of all published Submissions"))
    parser.add_argument(
        "-v", "--verbose", help="increase output verbosity",
        action="store_true")
    parser.add_argument(
        "-c", required=False,
        default=CONFIG,
        help="path to configuration file")
    parser.add_argument(
        "-m", required=False,
        default=CONFIG_META,
        help="path to META Data configuration file")

    args = vars(parser.parse_args())
    conf = args['c']
    conf_meta = args['m']
    now = str(datetime.now())

    if not pathlib.Path(conf).exists():
        print(f"{now} [ERROR] Missing config '{conf} "
              "or parameter -c with config path, Halt execution!")
        sys.exit(1)
    else:
        print(f"{now} [INFO] use configuration file at {conf}")
    if not pathlib.Path(conf_meta).exists():
        print(f"{now} [ERROR] Missing META-config '{conf_meta}'! "
              "or parameter -m with config path, Halt execution!")
        sys.exit(1)
    else:
        print(f"{now} [INFO] use META-configuration file at {conf_meta}")

    CP.read(conf)
    CP.read(conf_meta)
    WHITE = CP.get('white-list', 'journals', fallback='').split()
    BLACK = CP.get('black-list', 'journals', fallback='').split()
    WHITE and print(f"{now} [INFO] use white list: {WHITE}")
    BLACK and print(f"{now} [INFO] use black list: {BLACK}")
    if args['verbose']:
        logger.setLevel(level=logging.DEBUG)

    main()
