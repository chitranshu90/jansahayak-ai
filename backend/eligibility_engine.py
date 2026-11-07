DISCLAIMER = (
    "This is a preliminary check of information recorded in this prototype, "
    "not an official eligibility decision or guarantee of benefits."
)


def _evaluate(rule, answers):
    key = rule["key"]
    value = answers.get(key)
    if value is None or value == "":
        return "unknown", "More information is needed for this recorded condition."

    operator = rule["operator"]
    expected = rule["value"]
    try:
        if operator == "equals":
            passed = str(value).strip().casefold() == str(expected).strip().casefold()
        elif operator == "one_of":
            passed = str(value).strip().casefold() in {
                str(item).strip().casefold() for item in expected
            }
        elif operator == "gte":
            passed = float(value) >= float(expected)
        elif operator == "lte":
            passed = float(value) <= float(expected)
        elif operator == "boolean":
            if not isinstance(value, bool):
                return "unknown", "Please answer this condition with yes or no."
            passed = value is expected
        else:
            return "unknown", "This condition uses an unsupported rule and was not evaluated."
    except (TypeError, ValueError):
        return "unknown", "The answer format could not be evaluated."

    return (
        ("meets", rule["pass_explanation"])
        if passed
        else ("does_not_meet", rule["fail_explanation"])
    )


def assess_eligibility(scheme, answers):
    results = []
    for rule in scheme["eligibility_rules"]:
        status, explanation = _evaluate(rule, answers)
        results.append(
            {"key": rule["key"], "name": rule["name"], "status": status, "explanation": explanation}
        )

    if scheme["verification_status"] != "verified" or not results:
        overall = "needs_more_information"
    elif any(item["status"] == "does_not_meet" for item in results):
        overall = "does_not_meet_recorded_conditions"
    elif any(item["status"] == "unknown" for item in results):
        overall = "needs_more_information"
    else:
        overall = "meets_recorded_conditions"

    return {
        "scheme_id": scheme["id"],
        "scheme_slug": scheme["scheme_slug"],
        "overall_status": overall,
        "conditions": results,
        "disclaimer": DISCLAIMER,
    }
