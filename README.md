# Recruiter Relationship Manager

This is a small Python script for sending a personalized response to recruiter emails. It uses the OpenAI GPT-3 API to extract the recruiter's information, and IMAP and SMTP to read and send emails.

The script will:

- get all emails in a specified recruitment folder
- send a personalized response to each one
- append the response to the Sent folder
- move the thread to a done folder

## Installation

```sh
pip install -r requirements.txt
```

## Usage

Copy the `.env.sample` file to `.env`, and fill out the configuration environment variables.

```sh
source .env && python recruiter_rm.py
```

## Example

Given an email from a recruiter like this:

> Hello Perce,
>
> My name is Ernest Shackleton, and I'm the CEO of Endurance, a new startup in the exploration space. I think you'd be a great addition to our team.
>
> Let me know if you're interested in our open roles, and we can set up a quick intro call.
>
> Sincerely,
> Ernest

The program will use GPT-3 to extract the relevant info (recruiter name and company) and send a templatized response like this:

> Hi Ernest,
>
> Thanks for reaching out! I'm not interested in new opportunities at this time, but I'll keep Endurance in mind for the future.
>
> Thanks again,
> Perce Blackborow

## Learn more

You can learn more on my blog: [Responding to recruiter emails with GPT-3](https://matthewbilyeu.com/blog/2022-09-01/responding-to-recruiter-emails-with-gpt-3).
