import json

from backend.search_utils import scheme_search_score


def _as_scheme(row):
    scheme = dict(row)
    if "target_beneficiaries_hi" not in scheme:
        scheme["target_beneficiaries_hi"] = ""
    for key in ("eligibility_rules", "required_documents", "application_steps"):
        scheme[key] = json.loads(scheme[key])
    return scheme


def list_schemes(db, filters):
    clauses = []
    values = []
    search = filters.get("q", "")
    for key, column in (
        ("state", "state"),
        ("government_level", "government_level"),
        ("category", "category"),
    ):
        value = filters.get(key, "")
        if value:
            clauses.append(f"{column} = ?")
            values.append(value)
    target = filters.get("target", "")
    if target:
        clauses.append("(target_beneficiaries LIKE ? OR keywords LIKE ?)")
        values.extend([f"%{target}%", f"%{target}%"])
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = db.execute(f"SELECT * FROM schemes{where} ORDER BY scheme_name", values).fetchall()
    schemes = [_as_scheme(row) for row in rows]
    if not search:
        return schemes

    scored_schemes = [
        (scheme_search_score(search, scheme), scheme)
        for scheme in schemes
    ]
    matches = [(score, scheme) for score, scheme in scored_schemes if score]
    matches.sort(
        key=lambda item: (
            -item[0],
            item[1]["verification_status"] != "verified",
            item[1]["scheme_name"].casefold(),
        )
    )
    return [scheme for _, scheme in matches]


def scheme_by_slug(db, slug):
    row = db.execute("SELECT * FROM schemes WHERE scheme_slug = ?", (slug,)).fetchone()
    return _as_scheme(row) if row else None
