"""
Debug script v2: scan ALL Gmail folders for recruitment emails.
"""
import imaplib
import email
import sys
from email.header import decode_header
from datetime import datetime, timedelta

# Fix Windows encoding
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

EMAIL = "relivcustomercare.in@gmail.com"
APP_PASS = "ibmj qnlx gchi cfke"

def decode_hdr(value):
    if not value:
        return ""
    parts = decode_header(value)
    out = []
    for txt, enc in parts:
        if isinstance(txt, bytes):
            out.append(txt.decode(enc or "utf-8", errors="replace"))
        else:
            out.append(txt)
    return "".join(out)

print("Connecting to Gmail IMAP...")
imap = imaplib.IMAP4_SSL("imap.gmail.com")
imap.login(EMAIL, APP_PASS)
print("Login OK!\n")

# List all mailboxes
print("=== ALL MAILBOXES ===")
status, folders = imap.list()
mailbox_names = []
for f in folders:
    decoded = f.decode("utf-8", errors="replace") if isinstance(f, bytes) else str(f)
    print(f"  {decoded}")
    # Extract the mailbox name (last quoted string or unquoted name)
    import re
    parts = decoded.rsplit('"', 2)
    if len(parts) >= 2:
        name = parts[-2]
    else:
        name = decoded.split()[-1]
    mailbox_names.append(name)

since_date = (datetime.utcnow() - timedelta(days=730)).strftime("%d-%b-%Y")

# Search each mailbox for relevant emails
for mbox in mailbox_names:
    try:
        status, _ = imap.select(f'"{mbox}"', readonly=True)
        if status != "OK":
            continue
    except Exception as e:
        continue

    # Count total emails
    status, data = imap.uid("SEARCH", None, f'(SINCE {since_date})')
    total = len(data[0].split()) if data and data[0] else 0
    
    if total == 0:
        continue
    
    print(f"\n=== MAILBOX: {mbox} ({total} emails since {since_date}) ===")

    # Search for recruitment keywords in body/text
    for keyword in ["New Application", "Applicant Info", "Applied Position", "Reliv", "Application"]:
        try:
            status, data = imap.uid("SEARCH", None, f'(TEXT "{keyword}" SINCE {since_date})')
            uids = data[0].split() if data and data[0] else []
            if uids:
                print(f"  TEXT '{keyword}' => {len(uids)} match(es)")
                # Show first 5 subjects
                for uid in uids[:5]:
                    uid_str = uid.decode() if isinstance(uid, bytes) else str(uid)
                    status2, msg_data = imap.uid("FETCH", uid, "(BODY[HEADER.FIELDS (SUBJECT FROM DATE)])")
                    if status2 == "OK" and msg_data and msg_data[0]:
                        msg = email.message_from_bytes(msg_data[0][1])
                        subj = decode_hdr(msg.get("Subject", "(no subject)"))
                        frm = decode_hdr(msg.get("From", ""))
                        print(f"    UID={uid_str} | FROM={frm[:50]} | SUBJ={subj[:80]}")
                if len(uids) > 5:
                    print(f"    ... and {len(uids)-5} more")
        except Exception as e:
            print(f"  TEXT '{keyword}' => ERROR: {e}")
    
    # Also search subjects
    for keyword in ["New Application", "Application"]:
        try:
            status, data = imap.uid("SEARCH", None, f'(SUBJECT "{keyword}" SINCE {since_date})')
            uids = data[0].split() if data and data[0] else []
            if uids:
                print(f"  SUBJECT '{keyword}' => {len(uids)} match(es)")
        except Exception:
            pass

    # Show last 10 subjects in this mailbox
    status, data = imap.uid("SEARCH", None, f'(SINCE {since_date})')
    all_uids = data[0].split() if data and data[0] else []
    if all_uids and total <= 30:
        print(f"  -- All {total} subjects in this mailbox: --")
        for uid in all_uids:
            uid_str = uid.decode() if isinstance(uid, bytes) else str(uid)
            try:
                status2, msg_data = imap.uid("FETCH", uid, "(BODY[HEADER.FIELDS (SUBJECT FROM))")
                if status2 == "OK" and msg_data and msg_data[0]:
                    msg = email.message_from_bytes(msg_data[0][1])
                    subj = decode_hdr(msg.get("Subject", "(no subject)"))
                    frm = decode_hdr(msg.get("From", ""))
                    print(f"    UID={uid_str} | {frm[:40]} | {subj[:70]}")
            except:
                pass

imap.logout()
print("\nDone!")
