"""Test full pipeline: fetch + parse all 29 emails."""
import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from email_handler import EmailHandler
from parser import parse_application

handler = EmailHandler("relivcustomercare.in@gmail.com", "ibmj qnlx gchi cfke")
emails = handler.fetch_applications(subject_keyword="Applicant Info", since_days=730)
print(f"Fetched {len(emails)} emails\n")

parsed_count = 0
for em in emails:
    parsed = parse_application(
        subject=em["subject"],
        html_body=em["html"],
        text_body=em["text"],
        attachments=em["attachments"],
    )
    if parsed:
        parsed_count += 1
        cv = "CV" if parsed["cv_attached"] else "No CV"
        print(f"  {parsed_count}. {parsed['full_name']} | {parsed['email']} | {parsed['position']} | {cv}")
    else:
        print(f"  SKIP: {em['subject'][:60]}")

print(f"\nParsed: {parsed_count}/{len(emails)}")
