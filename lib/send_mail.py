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

    Content = str(report)  # "Content" will be the body of the mail

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
    except smtplib.SMTPException as e:
        logger = logging.getLogger('journals-logging-handler')
        logger.error('Error in smtp session: %s', e)
