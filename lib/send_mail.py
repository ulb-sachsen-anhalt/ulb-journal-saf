#!/usr/bin/env python3
import smtplib

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import logging


def create_smtp_session(login, password, server, port):
    # Creating SMTP session with TLS authentification
    session = smtplib.SMTP(server, port)
    session.ehlo()
    session.starttls()
    session.ehlo()
    session.login(login, password)
    return session


def send_report(sender, login, passwd, server, port, receiver, error, report):
    # sender: Sender email
    # login: Login for mailserver
    # passwd: Password for login
    # receiver: Receiver email
    # error: If an error appeared, set to True, else False
    # log: The actual report
    Content = ""  # "Content" will be the body of the mail
    for key in report.keys():
        Content = Content + key + "\n"
        for item in report[key]:
            Content = Content + str(item) + "\n"
        Content = Content + "--------------------------------\n"

    # Subject contains warning if error in log
    if error:
        Subject = "[ERROR]"
    else:
        Subject = "[Success]"

    message = MIMEMultipart()
    message["From"] = sender
    message["To"] = receiver
    message["Subject"] = Subject + " OJS-DSpace-Migration: Report"
    message.attach(MIMEText(Content, "plain"))
    Full_Email = message.as_string()

    try:
        with create_smtp_session(login, passwd, server, port) as session:
            session.sendmail(sender, receiver, Full_Email)
    except (smtplib.SMTPException, ConnectionRefusedError) as exc:
        logger = logging.getLogger('journals-logging-handler')
        logger.error('could not send report %s', exc)
