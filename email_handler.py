"""
IMAP (fetch applications) + SMTP (send accept/reject mails) for Reliv Recruitment.

The application emails are SENT from this Gmail account (via Google Apps Script / form),
so they live in [Gmail]/Sent Mail and [Gmail]/All Mail — NOT in INBOX.

We use TEXT-based search for "Applicant Info" to reliably find them.
"""

import imaplib
import smtplib
import email
import os
import re
from email.header import decode_header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import parsedate_to_datetime, formataddr
from datetime import datetime


IMAP_HOST = "imap.gmail.com"
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_PORT_SSL = 465

CV_DIR = "data/cvs"

# TEXT keywords that reliably appear inside every recruitment application email body
TEXT_KEYWORDS = [
    "Applicant Info",
    "Applied Position",
]

WHATSAPP_LINK = "https://chat.whatsapp.com/EGxKqgWmLr1CRur1sxtNk1"
INSTAGRAM_HANDLE = "reliv_care"
INSTAGRAM_LINK = "https://www.instagram.com/reliv_care"


def _decode_header(value: str) -> str:
    if not value:
        return ""
    parts = decode_header(value)
    out = []
    for txt, enc in parts:
        if isinstance(txt, bytes):
            try:
                out.append(txt.decode(enc or "utf-8", errors="replace"))
            except Exception:
                out.append(txt.decode("utf-8", errors="replace"))
        else:
            out.append(txt)
    return "".join(out)


def _extract_bodies_and_attachments(msg, save_attachments_to: str | None = None):
    """Return (html_body, text_body, [attachment_filenames])."""
    html_body, text_body, attachments = "", "", []

    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            disp = str(part.get("Content-Disposition") or "")

            if "attachment" in disp.lower() or (part.get_filename() and "inline" not in disp.lower()):
                fname = part.get_filename()
                if fname:
                    fname = _decode_header(fname)
                    attachments.append(fname)
                    if save_attachments_to:
                        os.makedirs(save_attachments_to, exist_ok=True)
                        safe_name = re.sub(r"[^\w.\-]", "_", fname)
                        path = os.path.join(save_attachments_to, safe_name)
                        with open(path, "wb") as f:
                            f.write(part.get_payload(decode=True) or b"")
                continue

            payload = part.get_payload(decode=True)
            if payload is None:
                continue
            charset = part.get_content_charset() or "utf-8"
            try:
                decoded = payload.decode(charset, errors="replace")
            except LookupError:
                decoded = payload.decode("utf-8", errors="replace")

            if ctype == "text/html" and not html_body:
                html_body = decoded
            elif ctype == "text/plain" and not text_body:
                text_body = decoded
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            try:
                text_body = payload.decode(charset, errors="replace")
            except LookupError:
                text_body = payload.decode("utf-8", errors="replace")

    return html_body, text_body, attachments


def build_html_email(body_text: str, decision: str = "accepted") -> str:
    """
    Wrap the plain-text email body in a beautiful, formal HTML email template
    with Reliv branding, WhatsApp community link, and Instagram CTA.

    The logo is rendered as styled HTML text — NO embedded PNG/images that
    stick to the top or break in mail clients.
    """

    # Decide colour scheme based on decision
    if decision == "accepted":
        accent_color = "#2dd47a"
        accent_bg = "rgba(45, 212, 122, 0.08)"
        status_label = "🎉 Congratulations!"
        status_bar_color = "#2dd47a"
    else:
        accent_color = "#ff6b6b"
        accent_bg = "rgba(255, 107, 107, 0.06)"
        status_label = "Application Update"
        status_bar_color = "#ff6b6b"

    # Convert plain text body to HTML paragraphs
    body_html = ""
    for line in body_text.strip().split("\n"):
        stripped = line.strip()
        if not stripped:
            body_html += '<div style="height:12px;"></div>\n'
        else:
            body_html += f'<p style="margin:0 0 6px 0;line-height:1.7;color:#2d3748;font-size:15px;">{_escape_html(stripped)}</p>\n'

    html = f"""\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Reliv</title>
</head>
<body style="margin:0;padding:0;background-color:#f4f6fb;font-family:'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;">

  <!-- Wrapper Table -->
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#f4f6fb;">
    <tr>
      <td align="center" style="padding:30px 16px 40px;">

        <!-- Main Container -->
        <table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" style="background-color:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.06);max-width:600px;width:100%;">

          <!-- Accent Bar -->
          <tr>
            <td style="height:5px;background:linear-gradient(90deg, #5b8def, #8e6cff, {status_bar_color});"></td>
          </tr>

          <!-- Header / Logo -->
          <tr>
            <td style="padding:28px 36px 8px;text-align:center;">
              <table role="presentation" cellpadding="0" cellspacing="0" border="0" align="center">
                <tr>
                  <td style="width:48px;height:48px;border-radius:12px;background:linear-gradient(135deg,#5b8def,#8e6cff);text-align:center;vertical-align:middle;color:#ffffff;font-weight:700;font-size:22px;font-family:'Segoe UI',Roboto,sans-serif;">
                    R
                  </td>
                  <td style="padding-left:14px;">
                    <div style="font-size:22px;font-weight:700;color:#1a202c;letter-spacing:0.3px;">Reliv</div>
                    <div style="font-size:11px;color:#8a93a6;text-transform:uppercase;letter-spacing:1.5px;margin-top:1px;">Recruitment Team</div>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Status Badge -->
          <tr>
            <td style="padding:12px 36px 4px;text-align:center;">
              <span style="display:inline-block;background:{accent_bg};color:{accent_color};font-weight:700;font-size:13px;padding:6px 18px;border-radius:20px;border:1px solid {accent_color}22;letter-spacing:0.3px;">
                {status_label}
              </span>
            </td>
          </tr>

          <!-- Divider -->
          <tr>
            <td style="padding:16px 36px 0;">
              <div style="height:1px;background:linear-gradient(90deg,transparent,#e2e8f0,transparent);"></div>
            </td>
          </tr>

          <!-- Body Content -->
          <tr>
            <td style="padding:20px 36px 12px;">
              {body_html}
            </td>
          </tr>

          <!-- WhatsApp Community CTA -->
          <tr>
            <td style="padding:8px 36px 4px;">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:linear-gradient(135deg,#dcfce7,#d1fae5);border-radius:12px;border:1px solid #bbf7d0;">
                <tr>
                  <td style="padding:18px 22px;">
                    <table role="presentation" cellpadding="0" cellspacing="0" border="0">
                      <tr>
                        <td style="vertical-align:top;padding-right:14px;">
                          <div style="width:40px;height:40px;border-radius:10px;background:#25D366;text-align:center;line-height:40px;font-size:20px;color:#fff;">💬</div>
                        </td>
                        <td>
                          <div style="font-weight:700;color:#166534;font-size:14px;margin-bottom:4px;">Join Our WhatsApp Community</div>
                          <div style="font-size:13px;color:#15803d;margin-bottom:10px;">Stay connected with the Reliv team — updates, events &amp; more.</div>
                          <a href="{WHATSAPP_LINK}" target="_blank" style="display:inline-block;background:#25D366;color:#ffffff;font-weight:700;font-size:13px;padding:9px 22px;border-radius:8px;text-decoration:none;letter-spacing:0.2px;">
                            Join WhatsApp Group &rarr;
                          </a>
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Instagram CTA -->
          <tr>
            <td style="padding:10px 36px 6px;">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:linear-gradient(135deg,#fdf2f8,#fce7f3);border-radius:12px;border:1px solid #fbcfe8;">
                <tr>
                  <td style="padding:16px 22px;">
                    <table role="presentation" cellpadding="0" cellspacing="0" border="0">
                      <tr>
                        <td style="vertical-align:top;padding-right:14px;">
                          <div style="width:40px;height:40px;border-radius:10px;background:linear-gradient(45deg,#f09433,#e6683c,#dc2743,#cc2366,#bc1888);text-align:center;line-height:40px;font-size:20px;color:#fff;">📸</div>
                        </td>
                        <td>
                          <div style="font-weight:700;color:#9d174d;font-size:14px;margin-bottom:4px;">Follow Us on Instagram</div>
                          <div style="font-size:13px;color:#be185d;margin-bottom:10px;">Follow <strong>@{INSTAGRAM_HANDLE}</strong> for behind-the-scenes, opportunities &amp; culture.</div>
                          <a href="{INSTAGRAM_LINK}" target="_blank" style="display:inline-block;background:linear-gradient(45deg,#f09433,#e6683c,#dc2743,#cc2366);color:#ffffff;font-weight:700;font-size:13px;padding:9px 22px;border-radius:8px;text-decoration:none;letter-spacing:0.2px;">
                            Follow @{INSTAGRAM_HANDLE} &rarr;
                          </a>
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Divider -->
          <tr>
            <td style="padding:16px 36px 0;">
              <div style="height:1px;background:linear-gradient(90deg,transparent,#e2e8f0,transparent);"></div>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="padding:18px 36px 24px;text-align:center;">
              <table role="presentation" cellpadding="0" cellspacing="0" border="0" align="center" style="margin-bottom:10px;">
                <tr>
                  <td style="width:32px;height:32px;border-radius:8px;background:linear-gradient(135deg,#5b8def,#8e6cff);text-align:center;vertical-align:middle;color:#ffffff;font-weight:700;font-size:15px;">
                    R
                  </td>
                  <td style="padding-left:10px;font-size:16px;font-weight:700;color:#4a5568;letter-spacing:0.3px;">
                    Reliv
                  </td>
                </tr>
              </table>
              <div style="font-size:11px;color:#a0aec0;line-height:1.6;">
                Building the future, one team member at a time.<br/>
                &copy; {datetime.now().year} Reliv &mdash; All rights reserved.
              </div>
              <div style="margin-top:10px;">
                <a href="{WHATSAPP_LINK}" style="font-size:11px;color:#5b8def;text-decoration:none;margin:0 8px;">WhatsApp</a>
                <span style="color:#cbd5e0;">&bull;</span>
                <a href="{INSTAGRAM_LINK}" style="font-size:11px;color:#5b8def;text-decoration:none;margin:0 8px;">Instagram</a>
              </div>
            </td>
          </tr>

        </table>
        <!-- End Main Container -->

      </td>
    </tr>
  </table>
  <!-- End Wrapper -->

</body>
</html>"""

    return html


def _escape_html(text: str) -> str:
    """Escape HTML special characters."""
    return (
        text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


class EmailHandler:
    """Connects to Gmail via IMAP/SMTP using app-password credentials."""

    def __init__(self, email_address: str, app_password: str):
        self.email_address = email_address
        self.app_password = app_password

    # ---------- IMAP ----------

    def fetch_applications(self, subject_keyword: str = "Applicant Info", since_days: int = 730):
        """
        Fetch raw application emails from Gmail.

        These emails are SENT from this account (by a Google Form / Apps Script),
        so they live in [Gmail]/Sent Mail.  We search both Sent Mail and All Mail
        using TEXT (body) search for "Applicant Info" which appears in every
        recruitment application email.

        Returns a list of dicts: {uid, subject, from, date, html, text, attachments}
        """
        from datetime import timedelta

        imap = imaplib.IMAP4_SSL(IMAP_HOST)
        imap.login(self.email_address, self.app_password)

        since_date = (datetime.utcnow() - timedelta(days=since_days)).strftime("%d-%b-%Y")

        # Mailboxes to scan — Sent Mail is where the applications live
        mailboxes_to_try = [
            '"[Gmail]/Sent Mail"',
            '"[Gmail]/All Mail"',
            "INBOX",
        ]

        seen_message_ids = set()
        results = []

        for mailbox in mailboxes_to_try:
            try:
                status, _ = imap.select(mailbox, readonly=True)
                if status != "OK":
                    continue
            except Exception:
                continue

            # Use TEXT search (searches body) for "Applicant Info" — the most reliable marker
            collected_uids = set()
            for keyword in TEXT_KEYWORDS:
                try:
                    search_query = f'(TEXT "{keyword}" SINCE {since_date})'
                    status, data = imap.uid("SEARCH", None, search_query)
                    if status == "OK" and data and data[0]:
                        for uid in data[0].split():
                            collected_uids.add(uid)
                except Exception:
                    continue

            # Also try subject search as fallback
            for keyword in ["Application", "New Application"]:
                try:
                    search_query = f'(SUBJECT "{keyword}" SINCE {since_date})'
                    status, data = imap.uid("SEARCH", None, search_query)
                    if status == "OK" and data and data[0]:
                        for uid in data[0].split():
                            collected_uids.add(uid)
                except Exception:
                    continue

            for uid in collected_uids:
                uid_str = uid.decode() if isinstance(uid, bytes) else str(uid)

                try:
                    status2, msg_data = imap.uid("FETCH", uid, "(RFC822)")
                    if status2 != "OK" or not msg_data or not msg_data[0]:
                        continue
                    raw = msg_data[0][1]
                    msg = email.message_from_bytes(raw)
                except Exception:
                    continue

                # Deduplicate by Message-ID across mailboxes
                msg_id = msg.get("Message-ID", "")
                if msg_id:
                    if msg_id in seen_message_ids:
                        continue
                    seen_message_ids.add(msg_id)

                subject = _decode_header(msg.get("Subject", ""))
                from_ = _decode_header(msg.get("From", ""))
                date_hdr = msg.get("Date", "")
                try:
                    received_at = parsedate_to_datetime(date_hdr).isoformat()
                except Exception:
                    received_at = datetime.utcnow().isoformat()

                # Use a stable UID for dedup in the DB
                # Prefix with clean mailbox tag to avoid cross-mailbox UID collisions
                mbox_tag = re.sub(r'[^a-zA-Z]', '', mailbox)[:6]
                stable_uid = f"{mbox_tag}_{uid_str}"

                cv_subdir = os.path.join(CV_DIR, stable_uid)
                html_body, text_body, attachments = _extract_bodies_and_attachments(
                    msg, save_attachments_to=cv_subdir if msg.is_multipart() else None
                )

                results.append({
                    "uid": msg_id or stable_uid,  # Use Message-ID as primary dedup key
                    "subject": subject,
                    "from": from_,
                    "received_at": received_at,
                    "html": html_body,
                    "text": text_body,
                    "attachments": attachments,
                    "cv_dir": cv_subdir if attachments else "",
                })

            # Once we found results in Sent Mail or All Mail, we can skip others
            # to avoid fetching duplicates. But All Mail is a superset, so if we
            # already scanned it, we're done.
            if results and mailbox == '"[Gmail]/All Mail"':
                break

        try:
            imap.logout()
        except Exception:
            pass

        return results

    # ---------- SMTP ----------

    def send_mail(
        self,
        to_email: str,
        subject: str,
        body: str,
        from_name: str = "Team Reliv",
        decision: str = "accepted",
    ):
        """
        Send a beautifully formatted HTML email with Reliv branding.

        Uses SMTP_SSL on port 465 (direct SSL — faster and more reliable
        than port 587 STARTTLS which can hang on some networks).
        """

        html_body = build_html_email(body, decision=decision)

        msg = MIMEMultipart("alternative")
        msg["From"] = formataddr((from_name, self.email_address))
        msg["To"] = to_email
        msg["Subject"] = subject

        # Plain-text fallback (for email clients that don't support HTML)
        plain_fallback = (
            f"{body}\n\n"
            f"---\n"
            f"Join our WhatsApp Community: {WHATSAPP_LINK}\n"
            f"Follow us on Instagram: @{INSTAGRAM_HANDLE} — {INSTAGRAM_LINK}\n\n"
            f"© {datetime.now().year} Reliv — All rights reserved.\n"
        )

        part_text = MIMEText(plain_fallback, "plain", "utf-8")
        part_html = MIMEText(html_body, "html", "utf-8")

        # Attach plain text first, then HTML (email clients prefer the last alternative)
        msg.attach(part_text)
        msg.attach(part_html)

        # Use SMTP (port 587) with STARTTLS.
        # Timeout of 15 seconds prevents hanging and fixes the 502 error.
        try:
            server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15)
            server.starttls()
            server.login(self.email_address, self.app_password)
            server.send_message(msg)
            server.quit()
        except smtplib.SMTPAuthenticationError as e:
            raise RuntimeError(
                f"Gmail authentication failed. Check your App Password. ({e.smtp_code})"
            ) from e
        except smtplib.SMTPException as e:
            raise RuntimeError(f"SMTP error: {e}") from e
        except TimeoutError:
            raise RuntimeError(
                "Connection to Gmail timed out (15s). Check your internet connection."
            )
        except OSError as e:
            raise RuntimeError(f"Network error connecting to Gmail: {e}") from e

    def verify_credentials(self) -> tuple[bool, str]:
        """Test both IMAP and SMTP login."""
        try:
            imap = imaplib.IMAP4_SSL(IMAP_HOST, timeout=10)
            imap.login(self.email_address, self.app_password)
            imap.logout()
        except Exception as e:
            return False, f"IMAP login failed: {e}"
        try:
            server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10)
            server.starttls()
            server.login(self.email_address, self.app_password)
            server.quit()
        except Exception as e:
            return False, f"SMTP login failed: {e}"
        return True, "OK"