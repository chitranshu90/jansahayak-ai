import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from dotenv import load_dotenv

from backend.ai_service import answer_question
from backend.citizen_services import (
    APPLICATION_STATUSES,
    check_suspicious_link,
    draft_complaint,
    inspect_uploaded_document,
)
from backend.database import get_db, init_db
from backend.eligibility_engine import assess_eligibility
from backend.live_sources import SourceUnavailable, check_scheme_source
from backend.scheme_service import list_schemes, scheme_by_slug


ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env", override=False)
MAX_DOCUMENT_SIZE = 5 * 1024 * 1024


def _utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _profile_hash():
    profile_id = request.headers.get("X-Profile-Id", "")
    try:
        normalized = str(uuid.UUID(profile_id))
    except (ValueError, AttributeError):
        return None
    return hashlib.sha256(normalized.encode("ascii")).hexdigest()


def create_app(test_config=None):
    app = Flask(__name__, static_folder=None)
    app.config.update(
        DATABASE=os.environ.get("JANSAHAYAK_DATABASE") or str(ROOT / "data" / "jansahayak.db"),
        MAX_CONTENT_LENGTH=MAX_DOCUMENT_SIZE + 64 * 1024,
    )
    if test_config:
        app.config.update(test_config)

    Path(app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)
    init_db(app.config["DATABASE"])

    @app.get("/")
    def home():
        return send_from_directory(ROOT / "frontend", "index.html")

    @app.get("/css/<path:filename>")
    def css_file(filename):
        return send_from_directory(ROOT / "frontend" / "css", filename)

    @app.get("/js/<path:filename>")
    def js_file(filename):
        return send_from_directory(ROOT / "frontend" / "js", filename)

    @app.get("/api/health")
    def health():
        with get_db(app.config["DATABASE"]) as db:
            db.execute("SELECT 1").fetchone()
        return jsonify({"status": "ok", "service": "JanSahayak AI"})

    @app.get("/api/categories")
    def categories():
        with get_db(app.config["DATABASE"]) as db:
            rows = db.execute(
                "SELECT DISTINCT category FROM schemes WHERE category != '' ORDER BY category"
            ).fetchall()
        return jsonify({"categories": [row["category"] for row in rows]})

    @app.get("/api/filters")
    def scheme_filters():
        with get_db(app.config["DATABASE"]) as db:
            states = db.execute(
                "SELECT DISTINCT state FROM schemes WHERE state != '' ORDER BY state"
            ).fetchall()
            levels = db.execute(
                "SELECT DISTINCT government_level FROM schemes ORDER BY government_level"
            ).fetchall()
        return jsonify(
            {
                "states": [row["state"] for row in states],
                "government_levels": [row["government_level"] for row in levels],
            }
        )

    @app.get("/api/schemes")
    @app.get("/api/schemes/")
    def schemes():
        filters = {
            "q": request.args.get("q", "").strip()[:100],
            "state": request.args.get("state", "").strip()[:80],
            "government_level": request.args.get("government_level", "").strip()[:30],
            "category": request.args.get("category", "").strip()[:80],
            "target": request.args.get("target", "").strip()[:80],
        }
        with get_db(app.config["DATABASE"]) as db:
            results = list_schemes(db, filters)
        return jsonify({"schemes": results, "count": len(results)})

    @app.get("/api/schemes/<slug>")
    def scheme_detail(slug):
        with get_db(app.config["DATABASE"]) as db:
            scheme = scheme_by_slug(db, slug)
        if scheme is None:
            return jsonify({"error": "Scheme not found."}), 404
        return jsonify({"scheme": scheme})

    @app.get("/api/schemes/<slug>/source")
    def scheme_source(slug):
        with get_db(app.config["DATABASE"]) as db:
            scheme = scheme_by_slug(db, slug)
        if scheme is None:
            return jsonify({"error": "Scheme not found."}), 404
        try:
            return jsonify(check_scheme_source(scheme))
        except SourceUnavailable as error:
            return jsonify({"error": str(error), "source_status": "unavailable"}), 502

    @app.get("/api/schemes/compare")
    def compare_schemes():
        slugs = request.args.getlist("slug")
        if not 2 <= len(slugs) <= 3 or len(set(slugs)) != len(slugs):
            return jsonify({"error": "Compare between two and three different schemes."}), 400
        with get_db(app.config["DATABASE"]) as db:
            results = [scheme_by_slug(db, slug) for slug in slugs]
        if any(scheme is None for scheme in results):
            return jsonify({"error": "One or more schemes were not found."}), 404
        return jsonify({"schemes": results})

    @app.post("/api/eligibility/check")
    def eligibility_check():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "Request body must be a JSON object."}), 400
        slug = payload.get("scheme_slug")
        answers = payload.get("answers", {})
        if not isinstance(slug, str) or not slug.strip():
            return jsonify({"error": "scheme_slug is required."}), 400
        if not isinstance(answers, dict) or len(answers) > 30:
            return jsonify({"error": "answers must be an object with at most 30 fields."}), 400
        with get_db(app.config["DATABASE"]) as db:
            scheme = scheme_by_slug(db, slug.strip())
        if scheme is None:
            return jsonify({"error": "Scheme not found."}), 404
        return jsonify(assess_eligibility(scheme, answers))

    @app.post("/api/chat")
    def chat():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "Request body must be a JSON object."}), 400
        message = payload.get("message")
        language = payload.get("language", "en")
        if not isinstance(message, str) or not message.strip():
            return jsonify({"error": "Enter a question before sending."}), 400
        if len(message) > 1200:
            return jsonify({"error": "Please keep your question under 1,200 characters."}), 400
        if language not in ("en", "hi"):
            return jsonify({"error": "language must be 'en' or 'hi'."}), 400
        with get_db(app.config["DATABASE"]) as db:
            available_schemes = list_schemes(db, {"q": message})
            all_schemes = available_schemes or list_schemes(db, {})
        result = answer_question(message.strip(), language, all_schemes)
        return jsonify(result)

    @app.post("/api/documents/analyze")
    def analyze_document():
        uploaded = request.files.get("file")
        if uploaded is None or not uploaded.filename:
            return jsonify({"error": "Choose a PDF, PNG, or JPEG document."}), 400
        result, error = inspect_uploaded_document(uploaded, MAX_DOCUMENT_SIZE)
        if error:
            return jsonify({"error": error}), 400
        return jsonify({"analysis": result})

    @app.post("/api/fraud/check")
    def fraud_check():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "Request body must be a JSON object."}), 400
        url = payload.get("url")
        message = payload.get("message", "")
        if not isinstance(url, str) or not url.strip() or len(url) > 2048:
            return jsonify({"error": "Provide a URL under 2,048 characters."}), 400
        if not isinstance(message, str) or len(message) > 2000:
            return jsonify({"error": "Message must be under 2,000 characters."}), 400
        result = check_suspicious_link(url, message)
        return jsonify(
            {
                **result,
                "notice": (
                    "This is a heuristic check only. It does not open the link or prove that a page, "
                    "message, or payment request is genuine."
                ),
            }
        )

    @app.post("/api/complaints/generate")
    def complaint_draft():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "Request body must be a JSON object."}), 400
        message = payload.get("message")
        language = payload.get("language", "en")
        topic = payload.get("topic", "")
        if not isinstance(message, str) or not message.strip() or len(message) > 3000:
            return jsonify({"error": "Describe the issue in 1 to 3,000 characters."}), 400
        if language not in ("en", "hi"):
            return jsonify({"error": "language must be 'en' or 'hi'."}), 400
        if not isinstance(topic, str) or len(topic) > 120:
            return jsonify({"error": "Topic must be under 120 characters."}), 400
        return jsonify(
            {
                **draft_complaint(message, language, topic),
                "submitted": False,
                "channel": None,
            }
        )

    @app.get("/api/applications")
    def list_applications():
        profile_hash = _profile_hash()
        if profile_hash is None:
            return jsonify({"error": "A valid browser profile ID is required."}), 400
        with get_db(app.config["DATABASE"]) as db:
            rows = db.execute(
                """
                SELECT id, scheme_slug, status, history, created_at, updated_at
                FROM applications WHERE profile_hash = ? ORDER BY updated_at DESC
                """,
                (profile_hash,),
            ).fetchall()
        return jsonify(
            {
                "applications": [
                    {
                        "id": row["id"],
                        "scheme_slug": row["scheme_slug"],
                        "status": row["status"],
                        "history": json.loads(row["history"]),
                        "created_at": row["created_at"],
                        "updated_at": row["updated_at"],
                    }
                    for row in rows
                ],
                "notice": "Status is manually entered; no government application system is connected.",
            }
        )

    @app.post("/api/applications")
    def save_application():
        profile_hash = _profile_hash()
        if profile_hash is None:
            return jsonify({"error": "A valid browser profile ID is required."}), 400
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "Request body must be a JSON object."}), 400
        status = payload.get("status", "Application Submitted")
        if status not in APPLICATION_STATUSES:
            return jsonify({"error": "Choose one of the supported application statuses."}), 400
        application_id = payload.get("application_id")
        now = _utc_now()
        with get_db(app.config["DATABASE"]) as db:
            if application_id is not None:
                if not isinstance(application_id, str):
                    return jsonify({"error": "application_id must be a string."}), 400
                row = db.execute(
                    "SELECT history, scheme_slug FROM applications WHERE id = ? AND profile_hash = ?",
                    (application_id, profile_hash),
                ).fetchone()
                if row is None:
                    return jsonify({"error": "Application record not found."}), 404
                history = json.loads(row["history"])
                scheme_slug = row["scheme_slug"]
                history.append({"status": status, "at": now})
                db.execute(
                    """
                    UPDATE applications SET status = ?, history = ?, updated_at = ?
                    WHERE id = ? AND profile_hash = ?
                    """,
                    (status, json.dumps(history), now, application_id, profile_hash),
                )
            else:
                scheme_slug = payload.get("scheme_slug")
                if not isinstance(scheme_slug, str) or not scheme_slug.strip():
                    return jsonify({"error": "scheme_slug is required for a new record."}), 400
                scheme = scheme_by_slug(db, scheme_slug.strip())
                if scheme is None:
                    return jsonify({"error": "Scheme not found."}), 404
                scheme_slug = scheme["scheme_slug"]
                application_id = str(uuid.uuid4())
                history = [{"status": status, "at": now}]
                db.execute(
                    """
                    INSERT INTO applications (
                        id, profile_hash, scheme_slug, status, history, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        application_id,
                        profile_hash,
                        scheme_slug.strip(),
                        status,
                        json.dumps(history),
                        now,
                        now,
                    ),
                )
        return jsonify(
            {
                "application": {
                    "id": application_id,
                    "scheme_slug": scheme_slug,
                    "status": status,
                    "history": history,
                    "updated_at": now,
                },
                "notice": "Status is manually entered; no government application system is connected.",
            }
        ), 201

    @app.errorhandler(413)
    def request_too_large(_error):
        return jsonify({"error": "Request is too large."}), 413

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5000")), debug=False)
