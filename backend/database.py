import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path


SCHEMA = """
CREATE TABLE IF NOT EXISTS schemes (
    id INTEGER PRIMARY KEY,
    scheme_name TEXT NOT NULL,
    scheme_slug TEXT NOT NULL UNIQUE,
    government_level TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL,
    target_beneficiaries TEXT NOT NULL,
    target_beneficiaries_hi TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL,
    description_hi TEXT NOT NULL,
    benefits TEXT NOT NULL,
    benefits_hi TEXT NOT NULL,
    eligibility_rules TEXT NOT NULL,
    required_documents TEXT NOT NULL,
    application_steps TEXT NOT NULL,
    official_source_url TEXT NOT NULL,
    official_application_url TEXT NOT NULL DEFAULT '',
    last_verified_date TEXT NOT NULL,
    verification_status TEXT NOT NULL,
    keywords TEXT NOT NULL DEFAULT ''
)
"""

APPLICATION_SCHEMA = """
CREATE TABLE IF NOT EXISTS applications (
    id TEXT PRIMARY KEY,
    profile_hash TEXT NOT NULL,
    scheme_slug TEXT NOT NULL,
    status TEXT NOT NULL,
    history TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (scheme_slug) REFERENCES schemes(scheme_slug)
);
CREATE INDEX IF NOT EXISTS idx_applications_profile ON applications(profile_hash);
"""


@contextmanager
def get_db(database_path):
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
    except BaseException:
        connection.rollback()
        raise
    else:
        connection.commit()
    finally:
        connection.close()


def init_db(database_path):
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with get_db(path) as db:
        db.execute(SCHEMA)
        db.executescript(APPLICATION_SCHEMA)
        columns = {row["name"] for row in db.execute("PRAGMA table_info(schemes)")}
        if "target_beneficiaries_hi" not in columns:
            db.execute(
                "ALTER TABLE schemes ADD COLUMN target_beneficiaries_hi TEXT NOT NULL DEFAULT ''"
            )
        seed_file = Path(__file__).resolve().parent.parent / "data" / "schemes.json"
        schemes = json.loads(seed_file.read_text(encoding="utf-8"))
        db.executemany(
            """
            INSERT INTO schemes (
                scheme_name, scheme_slug, government_level, state, category,
                target_beneficiaries, target_beneficiaries_hi, description, description_hi,
                benefits, benefits_hi, eligibility_rules, required_documents,
                application_steps, official_source_url, official_application_url,
                last_verified_date, verification_status, keywords
            ) VALUES (
                :scheme_name, :scheme_slug, :government_level, :state, :category,
                :target_beneficiaries, :target_beneficiaries_hi, :description, :description_hi,
                :benefits, :benefits_hi, :eligibility_rules, :required_documents,
                :application_steps, :official_source_url, :official_application_url,
                :last_verified_date, :verification_status, :keywords
            )
            ON CONFLICT(scheme_slug) DO UPDATE SET
                scheme_name = excluded.scheme_name,
                government_level = excluded.government_level,
                state = excluded.state,
                category = excluded.category,
                target_beneficiaries = excluded.target_beneficiaries,
                target_beneficiaries_hi = excluded.target_beneficiaries_hi,
                description = excluded.description,
                description_hi = excluded.description_hi,
                benefits = excluded.benefits,
                benefits_hi = excluded.benefits_hi,
                eligibility_rules = excluded.eligibility_rules,
                required_documents = excluded.required_documents,
                application_steps = excluded.application_steps,
                official_source_url = excluded.official_source_url,
                official_application_url = excluded.official_application_url,
                last_verified_date = excluded.last_verified_date,
                verification_status = excluded.verification_status,
                keywords = excluded.keywords
            """,
            [
                {
                    **item,
                    "eligibility_rules": json.dumps(item["eligibility_rules"], ensure_ascii=False),
                    "required_documents": json.dumps(item["required_documents"], ensure_ascii=False),
                    "application_steps": json.dumps(item["application_steps"], ensure_ascii=False),
                }
                for item in schemes
            ],
        )
        db.commit()
