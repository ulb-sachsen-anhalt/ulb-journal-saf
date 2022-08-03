#!/usr/bin/env python3
import smtplib

import zipfile
import os
import datetime

from email import encoders
from email.mime.base import MIMEBase
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
    ListOfAttachements = []
    for key in report.keys():
        Content = Content + key + ":\n"
        if "remote_url already set for" in key:
            Filename = key + ".txt"
            with open(Filename, mode="a", encoding="utf-8") as file:
                for item in report[key]:
                    file.write(str(item))
                    file.write("\n")
            ListOfAttachements.append(Filename)
            Content = Content + "See attached file." + "\n"
        else:
            for item in report[key]:
                Content = Content + str(item) + "\n"
        Content = Content + "--------------------------------\n"

    # Subject contains warning if error in log
    if error:
        Subject = "[ERROR]"
    else:
        Subject = "[Success]"

    # Create zip for attachements
    ZipFileName = "Logs_" + datetime.date.today().strftime("%Y-%m-%d") + ".zip"
    with zipfile.ZipFile(ZipFileName, mode="w") as zipF:
        for file in ListOfAttachements:
            zipF.write(file)

    # Attach zipfile
    with open(ZipFileName, "rb") as attach:
        Attachement = MIMEBase("application", "octet-stream")
        Attachement.set_payload(attach.read())
    encoders.encode_base64(Attachement)
    Attachement.add_header("Content-Disposition",
                           "attachment; filename=" + ZipFileName,)
    message = MIMEMultipart()
    message["From"] = sender
    message["To"] = receiver
    message["Subject"] = Subject + " OJS-DSpace-Migration: Report"
    message.attach(MIMEText(Content, "plain"))
    message.attach(Attachement)
    Full_Email = message.as_string()

    try:
        with create_smtp_session(login, passwd, server, port) as session:
            session.sendmail(sender, receiver, Full_Email)
    except (smtplib.SMTPException, ConnectionRefusedError) as exc:
        logger = logging.getLogger('journals-logging-handler')
        logger.error('could not send report %s', exc)

    # Cleanup Step
    for file in ListOfAttachements:
        os.remove(file)
    os.remove(ZipFileName)
