#!/usr/bin/env python3
"""
recruiter_rm: Recruiter Relationship Manager
Automatically responds to recruiter's emails with a courtesy message.
"""

import json
import textwrap
import os
import smtplib

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from imap_tools import MailBox, MailMessage, MailMessageFlags

import openai

IS_PROD = bool(int(os.getenv("IS_PROD", 0)))
SIGNATURE = os.getenv("SIGNATURE")


class Mailer:
    """Handles interfacing with the IMAP and SMTP email clients."""

    def __init__(self):
        self.imap_mailbox = MailBox(
            os.getenv("IMAP_HOST"), os.getenv("IMAP_PORT")
        ).login(os.getenv("MAILBOX_USER"), os.getenv("MAILBOX_PASS"))

        self.smtp_mailbox = smtplib.SMTP_SSL(
            os.getenv("SMTP_HOST"), os.getenv("SMTP_PORT")
        )

        self.smtp_mailbox.ehlo()
        self.smtp_mailbox.login(os.getenv("MAILBOX_USER"), os.getenv("MAILBOX_PASS"))

    def save_to_sent_folder(self, message):
        """Saves a sent message to the Sent folder."""
        self.imap_mailbox.append(
            str.encode(message.as_string()),
            os.getenv("MAILBOX_SENT_FOLDER"),
            dt=None,
            flag_set=[MailMessageFlags.SEEN],
        )

    def compose_and_send_mail(self, subject, in_reply_to, from_addr, to_addrs, body):
        """Builds email and sends it over SMTP."""

        message = MIMEMultipart()

        message["From"] = from_addr
        message["To"] = ", ".join(to_addrs)
        message["Subject"] = subject
        message["In-Reply-To"] = in_reply_to

        message.attach(MIMEText(body))

        self.smtp_mailbox.sendmail(
            from_addr,
            to_addrs,
            message.as_string(),
        )

        self.save_to_sent_folder(message)

    def get_recruiter_emails(self):
        """Gets all unprocessed recruiter emails from the Recruitment folder."""
        self.imap_mailbox.folder.set(os.getenv("MAILBOX_RECRUITMENT_FOLDER"))
        return list(self.imap_mailbox.fetch())

    def move_to_done(self, email):
        """After processing a message, used to move message to Done folder."""
        self.imap_mailbox.move(email.uid, os.getenv("MAILBOX_DONE_FOLDER"))

    def cleanup(self):
        """Cleans up mailbox client(s)."""
        self.smtp_mailbox.quit()


def send_response(mailer: Mailer, recruiter_email: MailMessage):
    """Given an email from a recruiter, sends a courtesy response."""

    quoted_original = ""

    for line in recruiter_email.text.splitlines():
        quoted_original += f"> {line}\n"

    try:
        name_and_co = get_recruiter_name_and_company(recruiter_email.text)
        recruiter_name = name_and_co["name"]
        recruiter_company = name_and_co["company"]
        response = f"""\
        Hi {recruiter_name or ""},

        Thanks for reaching out! I'm not interested in new opportunities at this time, but I'll keep {recruiter_company or "your company"} in mind for the future.


        Thanks again,
        {SIGNATURE}

        """

        response_body = textwrap.dedent(response) + quoted_original

        mailer.compose_and_send_mail(
            subject=f"Re:{recruiter_email.subject}",
            in_reply_to=recruiter_email.headers["message-id"][0],
            from_addr=os.getenv("EMAIL_ADDRESS"),
            to_addrs=[recruiter_email.from_],
            body=response_body,
        )

        mailer.move_to_done(recruiter_email)

    except Exception as expn:
        print(expn)
        print("Error creating/sending response email!")
        print(recruiter_email.text)


def respond_to_recruitment_emails(mailer: Mailer):
    """Reads recruiter emails in the MAILBOX_RECRUITMENT_FOLDER, responds to
    them, then moves each conversation to the MAILBOX_DONE_FOLDER so that
    it's not repeatedly processed."""

    emails = mailer.get_recruiter_emails()

    for email in emails:
        send_response(mailer, email)


def get_recruiter_name_and_company(email_text: str):
    """Uses OpenAI text models to automatically parse the recruiter's name
    and company from their email."""

    prompt = f"""
    Given an email from a recruiter, return the recruiter's first name and the recruiter's company's name formatted as valid JSON.

    Example: ***
    Email:
    '''
    Hi Matt! This is Steve Jobs with Apple Computer Company! I'm interested in having you join our team here.
    '''

    Response:
    {{"name": "Steve", "company": "Apple Computer Company"}}
    ***

    Email:
    '''
    {email_text}

    '''

    Response:
    """

    # don't make expensive OpenAI API calls unless operating in production
    if not IS_PROD:
        return json.loads('{"name": "Steve", "company": "Apple"}')

    completion = openai.Completion.create(
        model="text-davinci-002",
        prompt=textwrap.dedent(prompt),
        max_tokens=20,
        temperature=0,
    )

    return json.loads(completion.choices[0].text)


def main():
    """Entrypoint"""

    openai.organization = os.getenv("OPENAI_ORG")
    openai.api_key = os.getenv("OPENAI_SECRET_KEY")

    mailer = Mailer()

    respond_to_recruitment_emails(mailer)

    mailer.cleanup()


if __name__ == "__main__":
    main()
