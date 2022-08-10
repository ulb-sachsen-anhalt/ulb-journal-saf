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
    # report: The actual report
    Content = ""  # "Content" will be the body of the mail
    ListOfAttachements = []
    for key in report.keys():
        Content = Content + key + ":\n"
        if len(report[key]) > 20:
            Filename = ""
            for char in key:
                if char.isalpha() or char.isdigit():
                    Filename = Filename + char
                else:
                    Filename = Filename + "_"
            Filename = Filename + ".txt"
            with open(Filename, mode="a", encoding="utf-8") as file:
                file.write(key)
                file.write("\n")
                for item in report[key]:
                    file.write(str(item))
                    file.write("\n")
            ListOfAttachements.append(Filename)
            Content = Content + "More than 20 entries!" + "\n"
            Content = Content + "Full list in file: " + Filename + "\n"
        else:
            for item in report[key]:
                Content = Content + str(item) + "\n"
        Content = Content + "--------------------------------\n"
    message = MIMEMultipart()
    # Subject contains warning if error in log
    if error:
        Subject = "[ERROR]"
    else:
        Subject = "[Success]"

    # Create zip for attachements, if attachements exist
    if ListOfAttachements:
        Current_Date = datetime.date.today().strftime("%Y-%m-%d")
        ZipFileName = "Logs_" + Current_Date + ".zip"
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
        message.attach(Attachement)

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

    # Cleanup Step
    if ListOfAttachements:
        for file in ListOfAttachements:
            os.remove(file)
        os.remove(ZipFileName)
