"""
Reliv Recruitment Dashboard -- Flask backend.

Run: python app.py
Then open http://localhost:5000
"""

import os
import io
import csv
import json
import sqlite3
import secrets
import traceback

from datetime import datetime
from pathlib import Path
from threading import Lock
from functools import wraps

from dotenv import load_dotenv

load_dotenv()

from flask import (
    Flask,
    render_template,
    jsonify,
    request,
    send_from_directory,
    abort,
    Response,
    session,
    redirect,
    url_for,
)

from email_handler import EmailHandler
from parser import parse_application


BASE_DIR = Path(__file__).parent.resolve()
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

DB_PATH = DATA_DIR / "applicants.db"
CONFIG_PATH = DATA_DIR / "config.json"
CV_DIR = DATA_DIR / "cvs"

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

db_lock = Lock()


# =========================================================
# DEFAULT SETTINGS
# =========================================================

DEFAULT_TEMPLATES = {
    "default": {
        "accept_subject": "Welcome to Reliv, {name}! 🎉 You've Been Selected — {position}",
        "accept_body": (
            "Dear {name},\n\n"
            "Greetings from Team Reliv!\n\n"
            "We are thrilled to inform you that after careful review of your application, "
            "you have been selected for the {position} role at Reliv.\n\n"
            "Your skills, passion, and drive stood out amongst a competitive pool of candidates, "
            "and we are confident that you will be a valuable addition to our growing team.\n\n"
            "Here's what happens next:\n"
            "• You will receive an onboarding email within the next few days with further details.\n"
            "• In the meantime, please join our WhatsApp Community to stay connected with the team.\n"
            "• Follow us on Instagram @reliv_care for the latest updates, culture, and opportunities.\n\n"
            "We look forward to building something incredible together.\n\n"
            "With warm regards,\n"
            "Team Reliv\n"
            "Recruitment Division"
        ),
        "reject_subject": "Your Reliv Application Update — {position}",
        "reject_body": (
            "Dear {name},\n\n"
            "Greetings from Team Reliv.\n\n"
            "Thank you sincerely for taking the time to apply for the {position} position at Reliv. "
            "We truly appreciate your interest in being a part of our mission.\n\n"
            "After careful consideration, we regret to inform you that we have decided to move forward "
            "with other candidates whose profiles more closely align with our current requirements.\n\n"
            "Please know that this decision does not diminish the value of your skills and experience. "
            "We encourage you to:\n"
            "• Stay connected — join our WhatsApp Community for future openings and updates.\n"
            "• Follow us on Instagram @reliv_care to keep up with our journey.\n"
            "• Feel free to reapply in the future as new roles open up.\n\n"
            "We wish you the very best in your career journey and hope our paths cross again.\n\n"
            "With warm regards,\n"
            "Team Reliv\n"
            "Recruitment Division"
        ),
    }
}


DEFAULT_CONFIG = {
    "email_address": os.getenv("EMAIL_USER"),
    "app_password": os.getenv("EMAIL_PASS"),
    "from_name": "Team Reliv",
    "subject_keyword": "Applicant Info",
    "since_days": 730,
    "dashboard_password": "reliv2026",
    "templates": DEFAULT_TEMPLATES,
}


# =========================================================
# CONFIG
# =========================================================

def load_config() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            cfg = json.load(f)

        for k, v in DEFAULT_CONFIG.items():
            cfg.setdefault(k, v)

        cfg["templates"].setdefault(
            "default",
            DEFAULT_TEMPLATES["default"]
        )

        return cfg

    return json.loads(json.dumps(DEFAULT_CONFIG))


def save_config(cfg: dict):
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)


def ensure_config():
    if not CONFIG_PATH.exists():
        save_config(DEFAULT_CONFIG)


# =========================================================
# AUTH
# =========================================================

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):

        if not session.get("logged_in"):

            if request.is_json or request.path.startswith("/api/"):
                return jsonify({
                    "ok": False,
                    "error": "Login required"
                }), 401

            return redirect(url_for("login_page"))

        return f(*args, **kwargs)

    return decorated


@app.route("/login", methods=["GET"])
def login_page():
    return render_template("login.html")


@app.route("/api/login", methods=["POST"])
def do_login():

    cfg = load_config()

    payload = request.get_json(force=True)

    pwd = payload.get("password", "")

    if pwd == cfg.get("dashboard_password", "reliv2026"):

        session["logged_in"] = True
        session.permanent = True

        return jsonify({"ok": True})

    return jsonify({
        "ok": False,
        "error": "Wrong password"
    }), 403


@app.route("/api/logout", methods=["POST"])
def do_logout():
    session.clear()
    return jsonify({"ok": True})


# =========================================================
# DATABASE
# =========================================================

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():

    conn = get_db()

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS applicants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uid TEXT UNIQUE,
            full_name TEXT,
            email TEXT,
            phone TEXT,
            location TEXT,
            linkedin TEXT,
            position TEXT,
            why_reliv TEXT,
            referred_by TEXT,
            time_commitment TEXT,
            open_to_equity TEXT,
            domains TEXT,
            cv_attached INTEGER DEFAULT 0,
            cv_filename TEXT DEFAULT '',
            cv_dir TEXT DEFAULT '',
            status TEXT DEFAULT 'pending',
            received_at TEXT,
            sent_at TEXT,
            raw_subject TEXT DEFAULT '',
            from_addr TEXT DEFAULT '',
            notes TEXT DEFAULT ''
        );
    """)

    conn.commit()
    conn.close()


def upsert_applicant(data: dict):

    with db_lock:

        conn = get_db()
        c = conn.cursor()

        c.execute(
            "SELECT id FROM applicants WHERE uid = ?",
            (data["uid"],)
        )

        if c.fetchone():
            conn.close()
            return False

        c.execute("""
            INSERT INTO applicants
            (
                uid,
                full_name,
                email,
                phone,
                location,
                linkedin,
                position,
                why_reliv,
                referred_by,
                time_commitment,
                open_to_equity,
                domains,
                cv_attached,
                cv_filename,
                cv_dir,
                received_at,
                raw_subject,
                from_addr
            )
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            data["uid"],
            data["full_name"],
            data["email"],
            data["phone"],
            data["location"],
            data["linkedin"],
            data["position"],
            data["why_reliv"],
            data["referred_by"],
            data["time_commitment"],
            data["open_to_equity"],
            data["domains"],
            1 if data["cv_attached"] else 0,
            data["cv_filename"],
            data.get("cv_dir", ""),
            data["received_at"],
            data["raw_subject"],
            data["from_addr"],
        ))

        conn.commit()
        conn.close()

        return True

# Initialize database and config on startup
init_db()
ensure_config()
# =========================================================
# ROUTES
# =========================================================

@app.route("/")
@login_required
def index():
    return render_template("index.html")


@app.route("/api/applicants", methods=["GET"])
@login_required
def get_applicants():

    conn = get_db()

    # Build query with optional filters
    query = "SELECT * FROM applicants"
    params = []
    conditions = []

    status = request.args.get("status")
    if status and status != "all":
        conditions.append("status = ?")
        params.append(status)

    position = request.args.get("position")
    if position and position != "all":
        conditions.append("position = ?")
        params.append(position)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    # Sorting
    sort = request.args.get("sort", "newest")
    if sort == "oldest":
        query += " ORDER BY received_at ASC"
    elif sort == "name":
        query += " ORDER BY full_name ASC"
    else:
        query += " ORDER BY received_at DESC"

    rows = [
        dict(r)
        for r in conn.execute(query, params).fetchall()
    ]

    conn.close()

    return jsonify(rows)


@app.route("/api/fetch", methods=["POST"])
@login_required
def fetch():

    try:

        cfg = load_config()

        if not cfg.get("email_address") or not cfg.get("app_password"):
            return jsonify({
                "ok": False,
                "error": "Gmail credentials not configured. Go to Settings → Credentials and save your Gmail address + App Password first."
            }), 400

        handler = EmailHandler(
            cfg["email_address"],
            cfg["app_password"]
        )

        raw_emails = handler.fetch_applications(
            subject_keyword=cfg.get(
                "subject_keyword",
                "Applicant Info"
            ),
            since_days=cfg.get("since_days", 730),
        )

        new_count = 0

        for em in raw_emails:

            parsed = parse_application(
                subject=em["subject"],
                html_body=em["html"],
                text_body=em["text"],
                attachments=em["attachments"],
            )

            if parsed:

                parsed["uid"] = em["uid"]
                parsed["received_at"] = em["received_at"]
                parsed["raw_subject"] = em["subject"]
                parsed["from_addr"] = em["from"]
                parsed["cv_dir"] = em.get("cv_dir", "")

                if upsert_applicant(parsed):
                    new_count += 1

        return jsonify({
            "ok": True,
            "fetched": len(raw_emails),
            "new": new_count
        })

    except Exception as e:

        print(traceback.format_exc())

        return jsonify({
            "ok": False,
            "error": str(e),
            "trace": traceback.format_exc()
        }), 500

@app.route("/api/preview/<int:applicant_id>", methods=["GET"])
@login_required
def preview_email(applicant_id: int):

    decision = request.args.get("decision", "accepted")

    conn = get_db()

    row = conn.execute(
        "SELECT * FROM applicants WHERE id=?",
        (applicant_id,)
    ).fetchone()

    conn.close()

    if not row:
        abort(404)

    cfg = load_config()

    first_name = (
        row["full_name"].split()[0]
        if row["full_name"]
        else "Applicant"
    )

    position = row["position"] or "Role"

    tpl = cfg["templates"]["default"]

    if decision == "accepted":

        subject = tpl["accept_subject"]
        body = tpl["accept_body"]

    else:

        subject = tpl["reject_subject"]
        body = tpl["reject_body"]

    replacements = {
        "{name}": first_name,
        "{full_name}": row["full_name"] or first_name,
        "{position}": position,
        "{email}": row["email"] or "",
        "{domains}": row["domains"] or "",
    }

    for k, v in replacements.items():
        subject = subject.replace(k, v)
        body = body.replace(k, v)

    return jsonify({
        "to": row["email"],
        "subject": subject,
        "body": body
    })

@app.route("/api/decide/<int:applicant_id>", methods=["POST"])
@login_required
def decide(applicant_id: int):

    payload = request.get_json(force=True)

    decision = payload.get("decision")
    subject = payload.get("subject", "")
    body = payload.get("body", "")

    if decision not in ("accepted", "rejected"):
        return jsonify({
            "ok": False,
            "error": "Invalid decision"
        }), 400

    conn = get_db()

    row = conn.execute(
        "SELECT * FROM applicants WHERE id=?",
        (applicant_id,)
    ).fetchone()

    if not row:
        conn.close()
        abort(404)

    cfg = load_config()

    if not cfg.get("email_address") or not cfg.get("app_password"):
        conn.close()
        return jsonify({
            "ok": False,
            "error": "Gmail credentials not configured. Go to Settings → Credentials and save your Gmail address + App Password first."
        }), 400

    handler = EmailHandler(
        cfg["email_address"],
        cfg["app_password"]
    )

    try:

        handler.send_mail(
            to_email=row["email"],
            subject=subject,
            body=body,
            from_name=cfg.get("from_name", "Team Reliv"),
            decision=decision,
        )

    except Exception as e:

        import traceback

        conn.close()

        print(traceback.format_exc())

        return jsonify({
            "ok": False,
            "error": str(e),
            "trace": traceback.format_exc()
        }), 500

    with db_lock:

        conn.execute(
            "UPDATE applicants SET status=?, sent_at=? WHERE id=?",
            (
                decision,
                datetime.utcnow().isoformat(),
                applicant_id,
            )
        )

        conn.commit()

    conn.close()

    return jsonify({
        "ok": True,
        "sent_to": row["email"]
    })


@app.route("/api/stats", methods=["GET"])
@login_required
def get_stats():

    conn = get_db()

    total = conn.execute(
        "SELECT COUNT(*) FROM applicants"
    ).fetchone()[0]

    pending = conn.execute(
        "SELECT COUNT(*) FROM applicants WHERE status='pending'"
    ).fetchone()[0]

    accepted = conn.execute(
        "SELECT COUNT(*) FROM applicants WHERE status='accepted'"
    ).fetchone()[0]

    rejected = conn.execute(
        "SELECT COUNT(*) FROM applicants WHERE status='rejected'"
    ).fetchone()[0]

    # Get distinct positions with counts
    positions_raw = conn.execute(
        "SELECT position, COUNT(*) as cnt FROM applicants WHERE position != '' GROUP BY position ORDER BY cnt DESC"
    ).fetchall()

    positions = [{"name": r[0], "count": r[1]} for r in positions_raw]

    conn.close()

    return jsonify({
        "total": total,
        "pending": pending,
        "accepted": accepted,
        "rejected": rejected,
        "positions": positions,
    })


# =========================================================
# CONFIG API
# =========================================================

@app.route("/api/config", methods=["GET"])
@login_required
def get_config():

    cfg = load_config()

    # Mask the app password for security
    safe = dict(cfg)
    if safe.get("app_password"):
        safe["app_password"] = "***"

    return jsonify(safe)


@app.route("/api/config", methods=["POST"])
@login_required
def update_config():

    payload = request.get_json(force=True)
    cfg = load_config()

    # Update only provided fields
    for key in ["email_address", "from_name", "subject_keyword", "since_days"]:
        if key in payload:
            cfg[key] = payload[key]

    # Only update password if it's not the masked value
    if payload.get("app_password") and payload["app_password"] != "***":
        cfg["app_password"] = payload["app_password"]

    # Templates
    if "templates" in payload:
        cfg["templates"] = payload["templates"]

    save_config(cfg)

    return jsonify({"ok": True})


# =========================================================
# VERIFY CREDENTIALS
# =========================================================

@app.route("/api/verify", methods=["POST"])
@login_required
def verify_credentials():

    cfg = load_config()

    handler = EmailHandler(
        cfg["email_address"],
        cfg["app_password"]
    )

    ok, message = handler.verify_credentials()

    return jsonify({"ok": ok, "message": message})


# =========================================================
# CHANGE PASSWORD
# =========================================================

@app.route("/api/change-password", methods=["POST"])
@login_required
def change_password():

    payload = request.get_json(force=True)
    cfg = load_config()

    old_pwd = payload.get("old", "")
    new_pwd = payload.get("new", "")

    if old_pwd != cfg.get("dashboard_password", "reliv2026"):
        return jsonify({
            "ok": False,
            "error": "Current password is incorrect"
        }), 403

    if not new_pwd or len(new_pwd) < 4:
        return jsonify({
            "ok": False,
            "error": "New password must be at least 4 characters"
        }), 400

    cfg["dashboard_password"] = new_pwd
    save_config(cfg)

    return jsonify({"ok": True})


# =========================================================
# DELETE / RESET / BULK
# =========================================================

@app.route("/api/delete/<int:applicant_id>", methods=["POST"])
@login_required
def delete_applicant(applicant_id: int):

    with db_lock:

        conn = get_db()

        conn.execute(
            "DELETE FROM applicants WHERE id=?",
            (applicant_id,)
        )

        conn.commit()
        conn.close()

    return jsonify({"ok": True})


@app.route("/api/reset/<int:applicant_id>", methods=["POST"])
@login_required
def reset_applicant(applicant_id: int):

    with db_lock:

        conn = get_db()

        conn.execute(
            "UPDATE applicants SET status='pending', sent_at=NULL WHERE id=?",
            (applicant_id,)
        )

        conn.commit()
        conn.close()

    return jsonify({"ok": True})


@app.route("/api/bulk", methods=["POST"])
@login_required
def bulk_action():

    payload = request.get_json(force=True)
    ids = payload.get("ids", [])
    action = payload.get("action", "")

    if not ids:
        return jsonify({"ok": False, "error": "No IDs provided"}), 400

    with db_lock:

        conn = get_db()

        placeholders = ",".join("?" * len(ids))

        if action == "delete":
            conn.execute(
                f"DELETE FROM applicants WHERE id IN ({placeholders})",
                ids
            )
        elif action in ("accepted", "rejected", "pending"):
            conn.execute(
                f"UPDATE applicants SET status=? WHERE id IN ({placeholders})",
                [action] + ids
            )
        else:
            conn.close()
            return jsonify({"ok": False, "error": "Invalid action"}), 400

        conn.commit()
        conn.close()

    return jsonify({"ok": True})


# =========================================================
# EXPORT CSV
# =========================================================

@app.route("/api/export.csv", methods=["GET"])
@login_required
def export_csv():

    conn = get_db()

    rows = conn.execute(
        "SELECT * FROM applicants ORDER BY received_at DESC"
    ).fetchall()

    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    columns = [
        "ID", "Full Name", "Email", "Phone", "Location", "LinkedIn",
        "Position", "Why Reliv?", "Referred By", "Time Commitment",
        "Open to Equity", "Domains", "CV Attached", "Status",
        "Received At", "Decision Sent At"
    ]
    writer.writerow(columns)

    for row in rows:
        r = dict(row)
        writer.writerow([
            r.get("id", ""),
            r.get("full_name", ""),
            r.get("email", ""),
            r.get("phone", ""),
            r.get("location", ""),
            r.get("linkedin", ""),
            r.get("position", ""),
            r.get("why_reliv", ""),
            r.get("referred_by", ""),
            r.get("time_commitment", ""),
            r.get("open_to_equity", ""),
            r.get("domains", ""),
            "Yes" if r.get("cv_attached") else "No",
            r.get("status", "pending"),
            r.get("received_at", ""),
            r.get("sent_at", ""),
        ])

    csv_data = output.getvalue()
    output.close()

    return Response(
        csv_data,
        mimetype="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=reliv_applicants_{datetime.utcnow().strftime('%Y%m%d')}.csv"
        }
    )


# =========================================================
# CV DOWNLOAD
# =========================================================

@app.route("/cv/<int:applicant_id>")
@login_required
def serve_cv(applicant_id: int):

    conn = get_db()

    row = conn.execute(
        "SELECT cv_dir, cv_filename FROM applicants WHERE id=?",
        (applicant_id,)
    ).fetchone()

    conn.close()

    if not row or not row["cv_dir"] or not row["cv_filename"]:
        abort(404)

    import re

    safe_name = re.sub(r"[^\w.\-]", "_", row["cv_filename"])
    cv_path = Path(row["cv_dir"])

    if not cv_path.exists():
        abort(404)

    return send_from_directory(
        cv_path.resolve(),
        safe_name,
        as_attachment=True,
        download_name=row["cv_filename"],
    )


# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":

    init_db()
    ensure_config()

    cfg = load_config()

    print("\nReliv Recruitment Dashboard")
    print("---------------------------")
    print("http://localhost:5000")
    print()

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )