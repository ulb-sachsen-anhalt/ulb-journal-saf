def create_local_smtp_server(Login, Password):
    # Creating local SMTP Server with TLS authentification
    import smtplib
    mailserver = smtplib.SMTP("smtpauth.uni-halle.de", 587)
    mailserver.ehlo()
    mailserver.starttls()
    mailserver.ehlo()
    mailserver.login(Login, Password) # Fünfsteller + Pass
    return mailserver


def send_report(sender, login, passwd, receiver, error, log):
    # sender: Sender email
    # login: Login for smtpauth.uni-halle.de (usually "abcde")
    # passwd: Password for login
    # receiver: Receiver email
    # error: If a error appeared, set to True, else False
    # log: The actual report
    
    Sender = sender
    Login = login
    Password = passwd
    Receiver = receiver
    Error = error
    Inhalt = log  # Mailbody is the log

    
    # Subject contains warning if error in log
    if Error:
        Subject = "[ERROR]"
    else:
        Subject = "[Success]"

    from email import encoders
    from email.mime.base import MIMEBase
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    import datetime
    now = datetime.datetime.now()

    message = MIMEMultipart()
    message["From"] = Sender
    message["To"] = Receiver
    message["Subject"] = Subject + " OJS-DSpace-Migration: Report - " + str(now)
    message.attach(MIMEText(Inhalt, "plain"))
    Nachricht = message.as_string()

    try:
        mailserver = create_local_smtp_server(Login, Password)
        mailserver.sendmail(Sender, Receiver, Nachricht)
        mailserver.quit()
    except Error as e:
        print(e)
