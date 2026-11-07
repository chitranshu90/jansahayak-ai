import re

from backend.search_utils import scheme_search_score, search_tokens, tokens_match


KEYWORDS = {
    "scholarship": (
        "scholarship", "education", "student", "school", "college", "padhai", "vidyarthi",
        "छात्रवृत्ति", "शिक्षा", "विद्यार्थी", "पढ़ाई", "स्कूल", "कॉलेज",
    ),
    "farmer": ("farmer", "farming", "agriculture", "kheti", "kisaan", "kisan", "किसान", "खेती", "कृषि"),
    "pension": ("pension", "senior", "vriddh", "buzurg", "पेंशन", "वृद्ध", "बुज़ुर्ग", "बुजुर्ग"),
    "business": ("business", "shop", "startup", "vyapar", "karobar", "व्यवसाय", "व्यापार", "कारोबार"),
    "health": ("health", "medical", "hospital", "swasthya", "स्वास्थ्य", "अस्पताल", "इलाज"),
    "housing": ("housing", "home", "ghar", "awas", "आवास", "घर"),
    "employment": ("employment", "job", "work", "rozgar", "berozgar", "रोज़गार", "रोजगार", "काम", "नौकरी"),
    "women": ("women", "woman", "mahila", "महिला", "स्त्री"),
    "social_welfare": ("welfare", "ujjwala", "samajik", "कल्याण", "उज्ज्वला"),
}


def _relevant_schemes(message, schemes):
    normalized = message.casefold()
    message_tokens = search_tokens(message)
    detected = {
        category
        for category, words in KEYWORDS.items()
        if any(
            word in normalized
            or any(tokens_match(token, word.casefold()) for token in message_tokens)
            for word in words
        )
    }
    category_matches = {
        "scholarship": {"education"},
        "farmer": {"agriculture"},
        "pension": {"pension"},
        "business": {"business"},
        "health": {"health"},
        "housing": {"housing"},
        "employment": {"employment"},
        "women": {"women"},
        "social_welfare": {"social welfare"},
    }
    relevant = []
    for scheme in schemes:
        if (
            scheme_search_score(message, scheme) > 0
            or scheme["category"].casefold() in {
                category_name
                for category in detected
                for category_name in category_matches[category]
            }
        ):
            relevant.append(scheme)
    return relevant


def _is_up_request(message):
    normalized = message.casefold()
    return bool(
        re.search(r"\b(?:up|uttar\s+pradesh)\b", normalized)
        or "उत्तर प्रदेश" in normalized
        or "यूपी" in normalized
    )


def _up_scope_note(message, schemes, language):
    if not _is_up_request(message):
        return ""
    has_up_scheme = any(
        scheme.get("state", "").casefold().replace(" ", "") in {"up", "uttarpradesh"}
        for scheme in schemes
    )
    if has_up_scheme:
        return ""
    if language == "hi":
        return (
            "नोट: उपलब्ध रिकॉर्ड में उत्तर प्रदेश-विशिष्ट योजना की पुष्टि नहीं है। "
            "नीचे दी गई योजनाएँ केवल मिलते-जुलते विषय की सिफारिशें हैं; इन्हें यूपी की योजनाएँ न मानें।\n\n"
        )
    return (
        "Note: the available records do not confirm a Uttar Pradesh-specific scheme. "
        "The schemes below are related recommendations, not confirmed as UP schemes.\n\n"
    )


def answer_question(message, language, schemes):
    relevant = _relevant_schemes(message, schemes)
    scope_note = _up_scope_note(message, relevant, language)
    lowered = message.casefold()
    asks_documents = any(word in lowered for word in (
        "document", "documents", "paper", "papers", "कागज़", "कागज", "दस्तावेज़", "दस्तावेज",
    ))
    asks_eligibility = any(word in lowered for word in (
        "eligible", "eligibility", "qualify", "पात्र", "पात्रता", "योग्य",
    ))

    if asks_documents and relevant:
        scheme = relevant[0]
        summary = (
            "इस योजना के लिए आवश्यक दस्तावेज़ों की सूची इस प्रोटोटाइप के रिकॉर्ड में उपलब्ध नहीं है। सही जानकारी के लिए आधिकारिक स्रोत देखें।"
            if language == "hi"
            else "This prototype does not have a recorded list of required documents for this scheme. Please check the official source."
        )
        answer = (
            f"{scope_note}{scheme['scheme_name']}: {summary} आधिकारिक स्रोत: {scheme['official_source_url']}"
            if language == "hi"
            else f"{scope_note}{scheme['scheme_name']}: {summary} Official source: {scheme['official_source_url']}"
        )
        return {
            "answer": answer,
            "schemes": [{"scheme_name": s["scheme_name"], "scheme_slug": s["scheme_slug"]} for s in relevant[:3]],
            "mode": "rule-based",
        }

    if asks_documents:
        answer = (
            "किस योजना के दस्तावेज़ जानना चाहते हैं? योजना का नाम बताइए। इस प्रोटोटाइप में दस्तावेज़ों की सूची अधूरी है और हम उसका अनुमान नहीं लगाएंगे।"
            if language == "hi"
            else "Which scheme's documents do you mean? Please share its name. Document lists are incomplete in this prototype, so I won't guess them."
        )
        return {"answer": answer, "schemes": [], "mode": "rule-based"}

    if asks_eligibility and relevant:
        scheme = relevant[0]
        rules = scheme["eligibility_rules"]
        if language == "hi":
            details = "\n".join(
                f"• {rule.get('name_hi', rule['name'])}: {rule.get('pass_explanation_hi', rule['pass_explanation'])}"
                for rule in rules
            )
            answer = (
                f"{scope_note}{scheme['scheme_name']} के बारे में दर्ज जानकारी:\n{details}\n\n"
                if details
                else f"{scope_note}{scheme['scheme_name']} के लिए पात्रता के नियम इस रिकॉर्ड में उपलब्ध नहीं हैं।\n\n"
            )
            answer += (
                f"यह शुरुआती जानकारी है, आधिकारिक पात्रता निर्णय नहीं। विवरण आधिकारिक स्रोत पर जाँचें: "
                f"{scheme['official_source_url']}"
            )
        else:
            details = "\n".join(
                f"• {rule['name']}: {rule['pass_explanation']}" for rule in rules
            )
            answer = (
                f"{scope_note}Recorded information for {scheme['scheme_name']}:\n{details}\n\n"
                if details
                else f"{scope_note}No eligibility rules for {scheme['scheme_name']} are recorded here.\n\n"
            )
            answer += (
                f"This is not an official eligibility decision. Verify details at the official source: "
                f"{scheme['official_source_url']}"
            )
        return {
            "answer": answer,
            "schemes": [{"scheme_name": s["scheme_name"], "scheme_slug": s["scheme_slug"]} for s in relevant[:3]],
            "mode": "rule-based",
        }

    if asks_eligibility:
        answer = (
            "किस योजना की पात्रता जानना चाहते हैं? योजना का नाम और राज्य/केंद्रशासित प्रदेश बता सकते हैं। यहाँ दी गई जानकारी आधिकारिक पात्रता निर्णय नहीं है।"
            if language == "hi"
            else "Which scheme's eligibility would you like to check? Share its name and your state/UT. This tool cannot make an official eligibility decision."
        )
        return {"answer": answer, "schemes": [], "mode": "rule-based"}

    if not relevant:
        answer = (
            "मेरी उपलब्ध योजना सूची में इस सवाल से मिलती-जुलती योजना नहीं मिली। कृपया आधिकारिक "
            "myScheme पोर्टल पर जानकारी जांचें: https://www.myscheme.gov.in/"
            if language == "hi"
            else "I couldn't find a matching scheme in the available records. Check the official "
            "myScheme portal for current information: https://www.myscheme.gov.in/"
        )
        return {"answer": answer, "schemes": [], "mode": "rule-based"}

    summaries = []
    for scheme in relevant[:3]:
        if language == "hi":
            summaries.append(
                f"मिलती-जुलती योजना: {scheme['scheme_name']}। दर्ज लक्षित समूह: "
                f"{scheme.get('target_beneficiaries_hi') or scheme['target_beneficiaries']}। "
                f"{scheme['description_hi']} "
                f"रिकॉर्ड की स्थिति: {scheme['verification_status']}। आधिकारिक स्रोत: {scheme['official_source_url']}"
            )
        else:
            summaries.append(
                f"Related scheme: {scheme['scheme_name']}. Recorded target group: "
                f"{scheme['target_beneficiaries']}. {scheme['description']} "
                f"Verification: {scheme['verification_status']}. Source: {scheme['official_source_url']}"
            )
    if language == "hi":
        answer = (
            scope_note + "आपके सवाल से जुड़ी उपलब्ध योजना की जानकारी नीचे है। जहां जानकारी अधूरी है, उसे "
            "अधूरा बताया गया है; कृपया आवेदन से पहले आधिकारिक स्रोत जांचें।\n\n"
            + "\n\n".join(summaries)
            + "\n\nऔर सही दिशा बताने के लिए, अपना राज्य/केंद्रशासित प्रदेश और सहायता का प्रकार बता सकते हैं। "
            "कृपया व्यक्तिगत पहचान या बैंक जानकारी साझा न करें।"
        )
        if asks_eligibility:
            answer += " पात्रता के सभी नियम रिकॉर्ड में उपलब्ध नहीं हैं, इसलिए यह सूची आपकी आधिकारिक पात्रता की पुष्टि नहीं करती।"
    else:
        answer = (
            scope_note + "Here is the available information related to your question. Incomplete details are "
            "labelled as such; check the official source before applying.\n\n"
            + "\n\n".join(summaries)
            + "\n\nTo narrow this down, you can share your state/UT and the broad support you need. "
            "Please don't share personal identifiers or bank information."
        )
    return {
        "answer": answer,
        "schemes": [{"scheme_name": s["scheme_name"], "scheme_slug": s["scheme_slug"]} for s in relevant[:3]],
        "mode": "rule-based",
    }
