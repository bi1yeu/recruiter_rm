# Recruiter Relationship Manager

This is a small Python script for sending a personalized response to recruiter emails. It uses the OpenAI GPT-3 API to extract the recruiter's information, and IMAP and SMTP to read and send emails.

The script will:

- get all emails in a specified recruitment folder
- send a personalized response to each one
- append the response to the Sent folder
- move the thread to a done folder

## Installation

``` sh
pip install -r requirements.txt
```

## Usage

Copy the `.env.sample` file to `.env`, and fill out the configuration environment variables.

``` sh
source .env && python recruiter_rm.py
```

