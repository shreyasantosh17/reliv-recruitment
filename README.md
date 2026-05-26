# Reliv Recruitment Dashboard

A smart, one-screen recruitment system for Reliv. Pulls application emails from
Gmail, lets you ✓ Accept or ✗ Reject each applicant with one click, and sends a
polished, editable acceptance or rejection email instantly.

## What it does

- 📥 Fetches every "New Application" email from your Gmail inbox
- 🧠 Parses Name, Email, Phone, Location, LinkedIn, Position, Why-Reliv, Referred-By, Time-Commitment, Equity, Domains, and CV attachments
- 🗂 Groups applicants by **position** (Intern, etc.) so your records stay separated
- ✓ / ✗ One-click accept or reject — preview and **edit** the mail before sending
- 📤 Sends the mail **immediately** via Gmail SMTP
  - **Accepted** applicants → polished welcome + Instagram + WhatsApp links + ask for scope of work
  - **Rejected** applicants → kind rejection + Instagram link only
- 🎨 Per-position email templates (different scope of work for each role)
- 📎 Downloads any attached CVs
- 📊 Live stats: total, pending, accepted, rejected
- 🔎 Filter by status, position, or search by name/email/domain
- 💾 Everything stored locally (SQLite) — no cloud, no third party

## One-time setup

### 1. Install Python 3.10+ and the dependencies

```bash
cd reliv_recruitment
pip install -r requirements.txt
```

### 2. Generate a fresh Gmail App Password

⚠️ **Important:** The password you shared in chat (`ibmj qnlx gchi cfke`) is
compromised. Revoke it and generate a new one:

1. Go to <https://myaccount.google.com/security>
2. Make sure 2-Step Verification is ON
3. Open <https://myaccount.google.com/apppasswords>
4. Create a new app password (name it "Reliv Recruitment")
5. Copy the 16-character password

### 3. Start the app

```bash
python app.py
```

Then open <http://localhost:5000>

### 4. First-run configuration

Click **⚙ Settings** in the top-right.

- **Gmail address:** `relivcustomercare.in@gmail.com`
- **App password:** the new 16-char password from step 2 above
- **From name:** `Team Reliv`
- Click **Test connection** — should say `OK`
- Click **Save**

Now click **Fetch new applications** and the dashboard fills with every applicant
already in your inbox.

## Daily use

1. Click **Fetch new applications** (pulls anything new since last run)
2. Cards appear, grouped by status and position
3. For each applicant:
   - Click **View** to read the full application
   - Click **✓ Accept** or **✗ Reject** to open the editable mail preview
   - Edit anything (scope of work, dates, links — placeholders like `{name}` are auto-filled)
   - Click **Send** — the mail goes out immediately and the card moves to Accepted/Rejected
4. Filter by **Status**, **Position**, or search by name/email/domain

## Customizing email templates

**Settings → Email templates** lets you:

- Edit the default acceptance and rejection emails
- Create position-specific templates (e.g. one for *Intern*, another for *Marketing Lead*)
  with different scope-of-work text
- Use placeholders: `{name}`, `{full_name}`, `{position}`, `{email}`, `{domains}`

If a position-specific template exists for the applicant's role, it's used
automatically. Otherwise the *default* template is used. You can still
hand-edit the mail in the popup before sending.

## File layout

```
reliv_recruitment/
├── app.py                  # Flask server + API routes
├── email_handler.py        # Gmail IMAP fetch + SMTP send
├── parser.py               # Parse Reliv application emails
├── requirements.txt
├── templates/index.html    # UI
├── static/style.css        # UI styles
├── static/app.js           # UI logic
└── data/                   # auto-created
    ├── applicants.db       # SQLite — your records
    ├── config.json         # credentials + templates (do NOT share)
    └── cvs/                # downloaded CV attachments
```

## Security notes

- Your Gmail app password is stored locally in `data/config.json`. Do not
  commit this folder to git or share it. A `.gitignore` is included.
- The app binds to `127.0.0.1` only — it's not reachable from other devices on
  your network unless you change that in `app.py`.
- Always use a **Gmail App Password**, never your main Google password.
- If your laptop is shared, consider setting an OS user password.

## Troubleshooting

- **`IMAP login failed`** — Wrong app password, or 2FA not enabled on Gmail.
- **`SMTPAuthenticationError`** — Same fix: re-generate app password.
- **No applicants appear after Fetch** — Open Settings, check the
  *Subject keyword*. The default is `New Application` (matches your format
  "🧑‍💼 New Application — Intern"). You can also increase *Look back days*.
- **CV not downloading** — Some senders include the CV as an inline image
  rather than a real attachment. The badge "📎 CV" only appears for actual
  file attachments.
