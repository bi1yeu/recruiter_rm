#!/usr/bin/env python3
"""
recruiter_rm: Recruiter Relationship Manager
Automatically responds to recruiter's emails with a courtesy message.
"""

import json
import os
import re
import smtplib
import sys
import textwrap
import time
import traceback

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from imap_tools import MailBox, MailMessage, MailMessageFlags

import openai


# TODO configuration file?
DRY_RUN = bool(int(os.getenv("DRY_RUN", "1")))
BYPASS_OPENAI = bool(int(os.getenv("BYPASS_OPENAI", "0")))
SIGNATURE = os.getenv("SIGNATURE")
GRACE_PERIOD_SECS = 5


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

        print("Generated response email:")
        print(message.as_string(), flush=True)
        print(f"Going to send this email in {GRACE_PERIOD_SECS} seconds...")

        if not DRY_RUN:
            time.sleep(GRACE_PERIOD_SECS)

        if not DRY_RUN:
            self.smtp_mailbox.sendmail(
                from_addr,
                to_addrs,
                message.as_string(),
            )
            self.save_to_sent_folder(message)
            print("Sent email")
        else:
            print("DRY_RUN; not sending email")

    def _is_reply(self, mail_message: MailMessage):
        return "in-reply-to" in [header.lower() for header in mail_message.headers]

    def get_recruiter_emails(self):
        """Gets all unprocessed recruiter emails from the Recruitment folder."""
        self.imap_mailbox.folder.set(os.getenv("MAILBOX_RECRUITMENT_FOLDER"))
        all_recruiter_emails = list(self.imap_mailbox.fetch())

        filtered_messages = []
        for mail_message in all_recruiter_emails:
            if not self._is_reply(mail_message):
                filtered_messages.append(mail_message)

        return filtered_messages

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

        if not DRY_RUN:
            mailer.move_to_done(recruiter_email)

    except Exception:
        # TODO use logging module throughout
        print("Error creating/sending response email! Skipping")
        traceback.print_exc()
        print("Recruiter email:")
        print(recruiter_email.text)


def respond_to_recruitment_emails(mailer: Mailer):
    """Reads recruiter emails in the MAILBOX_RECRUITMENT_FOLDER, responds to
    them, then moves each conversation to the MAILBOX_DONE_FOLDER so that
    it's not repeatedly processed."""

    emails = mailer.get_recruiter_emails()

    print(f"Going to respond to {len(emails)} emails")

    for index, email in enumerate(emails):
        print(f"Responding to email {index + 1} of {len(emails)}...")
        send_response(mailer, email)
        print("Done")
        print(
            "--------------------------------------------------------------------------------"
        )


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

    # consider disabling expensive OpenAI calls in development if not relevant
    if BYPASS_OPENAI:
        print("Bypassing OpenAI API, mocking data")
        return json.loads('{"name": "Steve", "company": "Apple"}')

    completion = openai.Completion.create(
        model="text-davinci-002",
        prompt=textwrap.dedent(prompt),
        max_tokens=20,
        temperature=0,
    )

    try:
        # If we end up needing more cleaning to ensure the response can be parsed,
        # consider improving the prompt.
        json_str_response = completion.choices[0].text
        json_str_response_clean = re.search(r".*(\{.*\})", json_str_response).groups()[
            0
        ]

        return json.loads(json_str_response_clean)
    except (AttributeError, json.decoder.JSONDecodeError) as exception:
        print("Could not decode completion response from OpenAI:")
        print(completion)
        raise exception


def main():
    """Entrypoint"""

    if not DRY_RUN and BYPASS_OPENAI:
        print(
            "BYPASS_OPENAI can only be used w/ DRY_RUN to avoid sending emails with canned data."
        )
        sys.exit(1)

    if DRY_RUN:
        print("DRY_RUN mode on")

    if BYPASS_OPENAI:
        print("BYPASS_OPENAI mode on")

    openai.organization = os.getenv("OPENAI_ORG")
    openai.api_key = os.getenv("OPENAI_SECRET_KEY")

    mailer = Mailer()

    respond_to_recruitment_emails(mailer)

    mailer.cleanup()


if __name__ == "__main__":
    main()
