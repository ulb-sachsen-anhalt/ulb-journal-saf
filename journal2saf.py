#!/usr/bin/env python3

import sys
import time
import logging
import logging.config
import argparse
import warnings
import pathlib
from smtplib import SMTPException
from datetime import datetime
from pathlib import Path
from configparser import ConfigParser

from lib.export_saf import ExportSAF
from lib.copy_saf import CopySAF
from lib.retrieve_doi import RetrieveDOI
from lib.write_remote_url import WriteRemoteUrl
from lib.data_miner import DataPoll
from lib.send_mail import send_report

warnings.filterwarnings(
    'ignore', message='Unverified HTTPS request')

###############################################################
# defaults:
CONFIG = "conf/config.ini"
CONFIG_META = "conf/config_meta.ini"
###############################################################

logger = logging.getLogger('journals-logging-handler')


CP = ConfigParser()
# preserving capital letters with monkey patch
CP.optionxform = lambda option: option


class Report:
    """Gather information from all modules during
       they processing her tasks.
    """

    def __init__(self):
        self.report = {}

    def add(self, key, value):
        self.report.setdefault(key, []).append(value)

    def __get__(self):
        return str(self.report)

    def has_error(self) -> bool():
        "check if error occurs"
        return 'ERROR' in self.report.keys()

    def print(self):
        print('################### report ###################')
        for k, v in self.report.items():
            print(f"{k}: {', '.join(map(str, v))} "
                  f"{'['+str(len(v))+']' if len(v)>1 else ''}")
        print('################### report ###################')


class TaskDispatcher:
    """dispatching following tasks:
       * Ask OJS/OMP API for publications
       * Create objects of all _new_ publications
       * download file data (galleys/publicationFormats)
       * create ZIP's according to definition of import format SAF
       * push SAF's to Dspace Server
       * retrieve DOI's form Dspace
       * write DOI's back to OJS/OMP
    """

    def __init__(self) -> None:
        self.datapoll = None
        self.report = Report()
        self.duration = 1

    def gauge(func):
        def to_time(self):
            start = datetime.now()
            func(self)
            end = datetime.now()
            delta = str(end - start)
            self.duration = delta.split('.')[0]
        return to_time

    def update_doi_constraint(func):
        def check_and_proceed(self):
            do_writedoi = CP.getboolean('general', 'update_remote')
            if do_writedoi:
                func(self)
        return check_and_proceed

    @gauge
    def launch(self) -> None:
        self.data_poll()
        self.export_saf_archive()
        self.copy_saf()
        self.retrieve_doi()
        self.write_remote_url()

    def data_poll(self) -> None:
        dp = DataPoll(CP, self.report, WHITE, BLACK)
        dp.determine_done()
        dp.request_publishers()
        dp.serialise_data()
        dp.request_submissions()
        dp.request_contexts()
        self.datapoll = dp

    def export_saf_archive(self) -> None:
        publishers = self.datapoll.publishers
        exportsaf = ExportSAF(CP, self.report, publishers)
        exportsaf.export()
        exportsaf.write_zips()

    def copy_saf(self) -> None:
        copysaf = CopySAF(CP, self.report)
        copysaf.copy()

    @update_doi_constraint
    def retrieve_doi(self) -> None:
        logger.info('retrieve DOI')
        retrievedoi = RetrieveDOI(CP, self.report)
        doi_done = retrievedoi.determine_done()
        retrievedoi.retrieve_files(doi_done)

    @update_doi_constraint
    def write_remote_url(self) -> None:
        logger.info('write DOI')
        writeremoteurl = WriteRemoteUrl(CP, self.report)
        writeremoteurl.write()

    def send_report(self):
        receivers = None
        if CP.has_section('email'):
            receivers = CP.get('email', 'receivers')
            sender = CP.get('email', 'sender')
            user_ = CP.get('email', 'smtp_username')
            pass_ = CP.get('email', 'smtp_password')
            server_ = CP.get('email', 'smtp_server')
            port_ = CP.get('email', 'smtp_port')
        if receivers:
            for receiver in receivers.split():
                logger.info('try send report to %s', receiver)
                try: 
                    msg = self.report.report
                    send_report(sender, user_, pass_
                                , server_, port_, receiver
                                , self.report.has_error()
                                , msg)
                except (SMTPException, ConnectionRefusedError) as exc:
                    logger.error('could not send report %s', exc)
        else:
            logger.info('no section email found in config, skip')


def main() -> None:
    dispatcher = TaskDispatcher()
    dispatcher.launch()
    delta = dispatcher.duration
    logger.info(f"Elapsed time: {delta}")
    dispatcher.report.add('elapsed time', delta)
    dispatcher.send_report()
    dispatcher.report.print()


def init_logger():
    logpath = CP.get('general', 'logpath', fallback='log')
    LOG_FILE_FORMAT = '%Y-%m-%d'
    date_ = time.strftime(LOG_FILE_FORMAT, time.localtime())
    logfile_name = Path(logpath, f"http_record_handler_{date_}.log")
    conf_logname = {'logname': logfile_name}
    home_ = Path(__file__).parent.absolute()
    print(f'{home_}/conf/logging.conf')
    try:
        logging.config.fileConfig(
            f'{home_}/conf/logging.conf', defaults=conf_logname)
    except FileNotFoundError as err:
        print("check configuration 'general/logpath'!, "
              "or create path for logging: ", err)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=("Request Journalserver(OJS/OMP)"
                     " and build SAF's of all published Submissions"))
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

    init_logger()

    main()
