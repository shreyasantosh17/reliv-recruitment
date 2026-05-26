"""
Parses Reliv application emails into structured applicant data.

Handles both HTML (Gmail table) and plain-text (tab-separated) formats.
Tolerant to extra whitespace, missing fields, and emoji variations.

Subject formats seen:
  - 🧑‍💼 Application — Machine Learning | RIZWANULLAH <email>
  - 🧑‍💼 VP Engineering — RIZWANULLAH <email>
  - 🧑‍💼 Head of Operations — NATASHA BEERS <email>
  - 🧑‍💼 CEO — Faizan <email>
  - 🧑‍💼 New Application — Intern
"""

import re
from bs4 import BeautifulSoup


# Field labels we look for in the email. Map label -> canonical key.
FIELD_LABELS = {
    "Full Name": "full_name",
    "Email": "email",
    "Phone": "phone",
    "City / Location": "location",
    "City/Location": "location",
    "Location": "location",
    "LinkedIn": "linkedin",
    "Applied Position": "position",
    "Position": "position",
    "Why Reliv?": "why_reliv",
    "Why Reliv": "why_reliv",
    "Referred By": "referred_by",
    "Time Commitment": "time_commitment",
    "Open to Equity?": "open_to_equity",
    "Open to Equity": "open_to_equity",
}

DOMAIN_PATTERNS = [
    r"\U0001F527\s*Domains?\s*[—\-:]\s*(.+)",   # 🔧
    r"Domains?\s*[—\-:]\s*(.+)",
]

CV_PATTERNS = [
    (r"\U0001F4ED\s*No CV attached", False),   # 📭
    (r"No CV attached", False),
    (r"\U0001F4CE\s*CV attached", True),       # 📎
    (r"CV attached", True),
]


def _strip(text: str) -> str:
    """Collapse whitespace and trim."""
    return re.sub(r"\s+", " ", text or "").strip()


def _html_to_pairs(html: str):
    """Extract (label, value) pairs from an HTML email body."""
    soup = BeautifulSoup(html, "html.parser")

    pairs = []

    # 1) Try table rows (most Gmail-rendered applications use tables)
    for row in soup.find_all("tr"):
        cells = row.find_all(["td", "th"])
        if len(cells) >= 2:
            label = _strip(cells[0].get_text(" ", strip=True))
            value = _strip(cells[1].get_text(" ", strip=True))
            if label and value:
                pairs.append((label, value))

    # 2) Fall back to text-based extraction from the rendered text
    text = soup.get_text("\n", strip=True)
    return pairs, text


def _text_to_pairs(text: str):
    """Extract (label, value) pairs from plain-text body using tabs/colons."""
    pairs = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        # Try tab separator first (matches the user's format)
        if "\t" in line:
            parts = line.split("\t", 1)
            label = _strip(parts[0])
            value = _strip(parts[1])
            if label and value:
                pairs.append((label, value))
                continue
        # Try "Label  Value" with multiple spaces
        m = re.match(r"^([A-Za-z][A-Za-z /?]+?)\s{2,}(.+)$", line)
        if m:
            pairs.append((_strip(m.group(1)), _strip(m.group(2))))
            continue
        # Try "Label: Value"
        m = re.match(r"^([A-Za-z][A-Za-z /?]+?):\s*(.+)$", line)
        if m:
            pairs.append((_strip(m.group(1)), _strip(m.group(2))))
    return pairs


def _extract_position_from_subject(subject: str) -> str | None:
    """
    Extract position from various subject formats:
      - '🧑‍💼 Application — Machine Learning | RIZWANULLAH <email>'  -> 'Machine Learning'
      - '🧑‍💼 VP Engineering — RIZWANULLAH <email>'  -> 'VP Engineering'
      - '🧑‍💼 New Application — Intern'  -> 'Intern'
      - '🧑‍💼 CEO — Faizan <email>'  -> 'CEO'
    """
    if not subject:
        return None

    # Remove ALL emoji, ZWJ, variation selectors, and non-ASCII symbols
    clean = re.sub(r'[\U0001F000-\U0001FFFF\u200d\ufe0f\u2600-\u27bf\u2b50\u2764\u200b-\u200f\u2028-\u202f]+', '', subject).strip()

    # Pattern 1: "Application — Position | Name <email>"
    m = re.search(r"Application\s*[—\-:]\s*(.+?)\s*\|\s*", clean)
    if m:
        return _strip(m.group(1))

    # Pattern 2: "Application — Position"  (no pipe, no name after)
    m = re.search(r"Application\s*[—\-:]\s*(.+?)(?:\s*$)", clean)
    if m:
        pos = _strip(m.group(1))
        # Don't return if it looks like a name (contains < for email)
        if "<" not in pos:
            return pos

    # Pattern 3: "Position — Name <email>"  (no "Application" word)
    m = re.search(r"^(.+?)\s*[—\-]\s*.+<.+>", clean)
    if m:
        return _strip(m.group(1))

    # Pattern 4: "Position — Name" (no email in subject)
    m = re.search(r"^(.+?)\s*[—\-]\s*", clean)
    if m:
        return _strip(m.group(1))

    return None


def parse_application(subject: str, html_body: str | None, text_body: str | None,
                       attachments: list | None = None) -> dict:
    """
    Parse a single application email into a dict.
    Returns None if the email does not look like an application.
    """
    attachments = attachments or []
    html_body = html_body or ""
    text_body = text_body or ""

    # Quick sanity check — must look like a Reliv application
    full_blob = (subject or "") + "\n" + html_body + "\n" + text_body
    if "Applicant" not in full_blob and "Application" not in full_blob and "Applied" not in full_blob:
        return None

    # Collect label/value pairs from both HTML and text
    html_pairs, html_text = _html_to_pairs(html_body) if html_body else ([], "")
    text_pairs = _text_to_pairs(text_body or html_text)

    # Merge — HTML pairs take priority since they're more structured
    pairs = {}
    for label, value in html_pairs + text_pairs:
        # Normalize label (strip stray emojis/punctuation)
        clean_label = re.sub(r"[^\w\s/?]", "", label).strip()
        if clean_label and clean_label not in pairs:
            pairs[clean_label] = value

    # Build canonical dict
    data = {key: "" for key in FIELD_LABELS.values()}
    for label, value in pairs.items():
        for label_pat, canonical in FIELD_LABELS.items():
            if label.lower() == label_pat.lower():
                if not data[canonical]:
                    data[canonical] = value
                break

    # Position fallback from subject
    if not data["position"]:
        sub_pos = _extract_position_from_subject(subject)
        if sub_pos:
            data["position"] = sub_pos

    # Try to extract name/email from subject if not found in body
    # Subject format: "🧑‍💼 Position — NAME <email>"
    if not data["full_name"] or not data["email"]:
        m = re.search(r"[—\-]\s*([^<]+?)\s*<([^>]+)>", subject or "")
        if m:
            if not data["full_name"]:
                data["full_name"] = _strip(m.group(1))
            if not data["email"]:
                data["email"] = _strip(m.group(2))

    # Domains
    domains = ""
    search_blob = html_text + "\n" + text_body
    for pat in DOMAIN_PATTERNS:
        m = re.search(pat, search_blob, re.IGNORECASE)
        if m:
            domains = _strip(m.group(1))
            break
    data["domains"] = domains

    # CV status
    cv_attached = False
    for pat, val in CV_PATTERNS:
        if re.search(pat, search_blob, re.IGNORECASE):
            cv_attached = val
            break
    if attachments:
        cv_attached = True
    data["cv_attached"] = cv_attached
    data["cv_filename"] = attachments[0] if attachments else ""

    # Need at least name + email to be a valid application
    if not data["full_name"] or not data["email"]:
        return None

    return data


if __name__ == "__main__":
    # Quick test with the user's sample
    sample_text = """Reliv
\U0001F9D1\u200D\U0001F4BC New Application \u2014 Intern
\U0001F464 Applicant Info
Full Name\tDiyasha Ghosh
Email\tghoshdiyasha86@gmail.com
Phone\t+917439436032
City / Location\tSrerampore
LinkedIn\thttps://www.linkedin.com/in/diyasha-ghosh-34531533b
\U0001F3E2 Position Details
Applied Position\tIntern
\U0001F4CB Mission & Vision
Why Reliv?\tI want to join Reliv because I would like to learn different skills and also want to experience how the work culture is in a start up.
\U0001F4AC Additional Info
Referred By\tI got to know about Reliv from Chairperson of IEEE RAS
Time Commitment\t\u2705 Yes, fully committed
Open to Equity?\t\u2705 Yes
\U0001F527 Domains \u2014 electronics, webdev, ml
\U0001F4ED No CV attached.
"""
    result = parse_application(
        subject="New Application \u2014 Intern",
        html_body=None,
        text_body=sample_text,
    )
    import json
    print(json.dumps(result, indent=2))

    # Test with the actual subject format from the inbox
    result2 = parse_application(
        subject="\U0001F9D1\u200D\U0001F4BC VP Engineering \u2014 RIZWANULLAH <khanrizwan2704@gmail.com>",
        html_body=None,
        text_body=sample_text,
    )
    print("\nTest 2 (VP Engineering subject):")
    print(json.dumps(result2, indent=2))
