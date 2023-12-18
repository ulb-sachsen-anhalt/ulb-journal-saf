#!/usr/bin/env python3
import smtplib

import zipfile
import os
import datetime

from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate

import logging


def create_smtp_session(login, password, server, port):
    # Creating SMTP session with TLS authentification
    session = smtplib.SMTP(server, port)
    session.ehlo()
    session.starttls()
    session.ehlo()
    session.login(login, password)
    return session


def send_report(sender, login, passwd, server, port, receiver, error,
                report, system):
    # sender: Sender email
    # login: Login for mailserver
    # passwd: Password for login
    # receiver: Receiver email
    # error: If an error appeared, set to True, else False
    # report: The actual report
    content = ""  # "content" will be the body of the mail
    list_of_attachements = []
    MaxEntries = 10
    New_Data = False
    for key in report.keys():
        if "elapsed time" not in key:
            if "remote_url already set" not in key:
                if "processed journals" not in key:
                    New_Data = True # Something interesting to report
        content = content + key + ":\n"
        if len(report[key]) > MaxEntries:
            filename = ""
            for char in key:
                if char.isalpha() or char.isdigit():
                    filename = filename + char
                else:
                    filename = filename + "_"
            filename = filename + ".txt"
            with open(filename, mode="a", encoding="utf-8") as file:
                file.write(key)
                file.write("\n")
                for item in report[key]:
                    file.write(str(item))
                    file.write("\n")
            list_of_attachements.append(filename)
            content = content + "More than " + str(MaxEntries) + " entries!" + "\n"
            content = content + "Full list in file: " + filename + "\n"
        else:
            for item in report[key]:
                content = content + str(item) + "\n"
        content = content + "--------------------------------\n"
    message = MIMEMultipart()
    # Subject contains warning if error in log
    if error:
        subject = "[ERROR]"
    else:
        subject = "[Success]"

    # Create zip for attachements, if attachements exist
    if list_of_attachements:
        current_date = datetime.date.today().strftime("%Y-%m-%d")
        zip_filename = "Logs_" + current_date + ".zip"
        with zipfile.ZipFile(zip_filename, mode="w") as zipF:
            for file in list_of_attachements:
                zipF.write(file)

        # Attach zipfile
        with open(zip_filename, "rb") as attach:
            attachement = MIMEBase("application", "octet-stream")
            attachement.set_payload(attach.read())
        encoders.encode_base64(attachement)
        attachement.add_header("Content-Disposition",
                               "attachment; filename=" + zip_filename,)
        message.attach(attachement)

    message["From"] = sender
    message["To"] = receiver
    message["Subject"] = subject + " " + system.upper() +\
        "-DSpace-Migration: Report"
    message["Date"] = formatdate(localtime=True)
    message.attach(MIMEText(content, "plain"))

    full_email = message.as_string()
    if New_Data: # Only send mail if something happened
        try:
            with create_smtp_session(login, passwd, server, port) as session:
                session.sendmail(sender, receiver, full_email)
        except (smtplib.SMTPException, ConnectionRefusedError) as exc:
            logger = logging.getLogger('journals-logging-handler')
            logger.error('could not send report %s', exc)
    else:
        print("Not sending email, nothing to report")


    # Cleanup Step
    if list_of_attachements:
        for file in list_of_attachements:
            os.remove(file)
        os.remove(zip_filename)
