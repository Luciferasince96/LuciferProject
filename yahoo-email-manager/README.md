# Yahoo email manager — local starter

This project is for local development only. It has no user authentication. Do not deploy it to Azure or expose it to a network until proper security is implemented.

## Folder structure

```
yahoo-email-manager/
├── .gitignore
├── README.md
├── backend/
│   ├── .env.example
│   ├── requirements.txt
│   └── app/
│       ├── __init__.py
│       ├── main.py
│       ├── mail.py
│       └── settings.py
└── frontend/
    ├── index.html
    ├── package.json
    ├── vite.config.js
    └── src/
        ├── App.jsx
        ├── main.jsx
        └── styles.css
```

## Prerequisites

- VS Code, Python 3.12+ and Node.js 24 LTS (with npm). Open a new terminal after installing.
- A Yahoo third-party app password (not your usual Yahoo password). Generate it in Yahoo Account Security > External connections > Create app password. Yahoo determines eligibility; if unavailable this version cannot connect.
- Optional: an OpenAI API key, model access and any applicable billing, for the two AI buttons. The rest works without the key.

## Backend (Windows PowerShell)

Open the project root folder in VS Code. Open a terminal:

```powershell
cd backend
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `backend/.env`: replace the password placeholder with the Yahoo app password. Optionally set the OpenAI key. Do not put quotes or spaces around the value unless needed, share it, or commit `.env`. Save and run:

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Check `http://127.0.0.1:8000/api/health` and `http://127.0.0.1:8000/docs`. The health check only tests the API, not Yahoo credentials.

On macOS/Linux, instead use `python3 -m venv .venv`, `source .venv/bin/activate`, `cp .env.example .env`, then the same pip and uvicorn commands. If Windows PowerShell prevents activation, run `.\.venv\Scripts\python.exe -m pip install -r requirements.txt` and `.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload` without activating.

## Frontend

In another VS Code terminal, starting from the project root:

```powershell
cd frontend
npm install
npm run dev
```

Visit the URL printed by Vite, normally `http://127.0.0.1:5173`. Click Load / refresh inbox. Each terminal must remain running. Stop each with Ctrl+C.

## What it does and does not do

- Unread count is for Inbox; previews are the latest 20 unread messages. Sender counts use the latest 100 Inbox and the latest 100 Spam folder messages. Spam means messages Yahoo placed in that folder, not independent detection. Displayed sender addresses can be spoofed.
- Opening an unread message retrieves its body and a best-effort matching thread from headers of the latest 100 Inbox and 100 Sent messages, capped at 10 messages. It may omit older, moved or unlinked messages, and content is truncated. Viewing uses IMAP PEEK and doesn't mark mail read. HTML is converted to plain text; attachments are not read or sent. Counts and previews are fetched live; no database is used.
- AI requests are opt-in: the summary sends displayed unread previews to OpenAI; drafting sends selected and matched conversation content and your instructions. Review privacy obligations and OpenAI terms before use. AI is not guaranteed correct or safe; review drafts and recipients. This does not automatically send.
- The To and Cc fields are editable and require confirmation to send; default To is Reply-To or From. There is no automatic reply-all, Bcc, attachment handling, or built-in authentication. Always verify recipients and content. Message threading headers are set when available.
- After SMTP acceptance, a best-effort Sent-folder copy is appended. Yahoo may also save one automatically, which can cause duplicates. If a connection fails while sending, delivery can be uncertain: check Yahoo before retrying.
- Credentials live in backend `.env`, never in React. Do not commit `.env` or paste credentials in chat. Revoke compromised app passwords in Yahoo Account Security. This is a learning prototype with no auth or CSRF protection; localhost reduces exposure but is not a security boundary against a malicious local process or website. Don't run it on shared/untrusted machines.

## Before Azure

Choose a container host and implement authentication/authorisation, CSRF protections, HTTPS, secret management, restricted networking, rate limits, secure logging, robust mail access and monitoring. Confirm outbound connectivity to Yahoo on ports 993 and 465. Do not use the Vite development server or `--reload` for production. Azure setup is deliberately deferred.
