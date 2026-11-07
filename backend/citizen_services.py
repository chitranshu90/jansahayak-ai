import re
from urllib.parse import urlsplit


APPLICATION_STATUSES = (
    "Application Submitted",
    "Under Verification",
    "Approved",
    "Rejected",
)

_SENSITIVE_REQUESTS = re.compile(
    r"\b(?:otp|password|pin|cvv|pay(?:ment)?|fee|transfer money)\b|"
    r"ओटीपी|पासवर्ड|पिन|सीवीवी|पैसे भेजें|भुगतान",
    re.IGNORECASE,
)
_SHORTENERS = {"bit.ly", "tinyurl.com", "t.co", "goo.gl", "is.gd"}


def check_suspicious_link(url, message=""):
    parsed = urlsplit(url.strip())
    signals = []
    host = ""
    try:
        host = (parsed.hostname or "").encode("idna").decode("ascii").casefold()
        port = parsed.port
    except (UnicodeError, ValueError):
        port = None

    if parsed.scheme != "https" or not host or parsed.username or parsed.password:
        signals.append("Use of HTTPS and a clear host could not be confirmed.")
    if port not in (None, 443):
        signals.append("The link uses a non-standard web port.")
    if host in _SHORTENERS:
        signals.append("The link uses a URL-shortening service.")
    if _SENSITIVE_REQUESTS.search(f"{url} {message}"):
        signals.append("The text asks for a sensitive code, password, or payment.")

    official_domain = host.endswith((".gov.in", ".nic.in")) or host in {
        "gov.in",
        "nic.in",
    }
    if signals:
        category = "Suspicious"
    elif official_domain:
        category = "Verified Official"
        signals.append("The domain uses a government or NIC suffix; page content is not verified.")
    else:
        category = "Unable to Verify"
        signals.append("The domain is not in the limited government-domain allowlist.")
    return {"category": category, "host": host, "signals": signals}


def draft_complaint(message, language="en", topic=""):
    normalized = message.casefold()
    issue = next(
        (
            key
            for key, words in {
                "scholarship": ("scholarship", "छात्रवृत्ति"),
                "pension": ("pension", "पेंशन"),
                "ration": ("ration", "राशन"),
                "delay": ("delay", "delayed", "देर", "विलंब"),
            }.items()
            if any(word in normalized for word in words)
        ),
        "general",
    )
    if language == "hi":
        title = topic.strip() or "सरकारी सेवा संबंधी शिकायत"
        questions = {
            "scholarship": ["किस शैक्षणिक सत्र का भुगतान लंबित है?", "आधिकारिक आवेदन माध्यम पर अभी क्या स्थिति दिखती है?"],
            "pension": ["किस अवधि से पेंशन नहीं मिली?", "क्या संबंधित विभाग ने कोई सूचना भेजी है?"],
            "ration": ["किस महीने का राशन नहीं मिला?", "क्या उचित मूल्य दुकान या विभाग से संपर्क किया है?"],
            "delay": ["कौन-सी सेवा और किस तारीख़ से लंबित है?", "क्या आवेदन की स्थिति आधिकारिक माध्यम पर उपलब्ध है?"],
            "general": ["कौन-सी सरकारी सेवा प्रभावित है?", "समस्या कब शुरू हुई और आधिकारिक माध्यम पर क्या स्थिति दिखती है?"],
        }[issue]
        body = (
            f"विषय: {title}\n\n"
            "सेवा-संबंधी समस्या के बारे में निवेदन है:\n"
            f"{message.strip()}\n\n"
            "कृपया मामले की जाँच कर उचित कार्रवाई करें और स्थिति से अवगत कराएँ। "
            "आवश्यक सहायक विवरण मैं आधिकारिक माध्यम से उपलब्ध करा सकता/सकती हूँ।\n\n"
            "धन्यवाद।"
        )
        notice = (
            "यह केवल संपादन योग्य मसौदा है। इसे JanSahayak AI जमा नहीं करता। "
            "जमा करने से पहले निजी पहचान, बैंक जानकारी और OTP हटाएँ; सही विभागीय "
            "शिकायत माध्यम आधिकारिक स्रोत से जाँचें।"
        )
    else:
        title = topic.strip() or "Government service grievance"
        questions = {
            "scholarship": ["Which academic year is affected?", "What status does the official application channel show?"],
            "pension": ["Since which period has the pension been delayed?", "Has the department sent any notice?"],
            "ration": ["Which month's ration is missing?", "Have you contacted the fair-price shop or department?"],
            "delay": ["Which service is delayed, and since what date?", "Is a status available through the official channel?"],
            "general": ["Which government service is affected?", "When did the issue start, and what status does the official channel show?"],
        }[issue]
        body = (
            f"Subject: {title}\n\n"
            "I am writing to report the following service-related issue:\n"
            f"{message.strip()}\n\n"
            "Please review the matter, take appropriate action, and share an update. "
            "I can provide relevant supporting details through the department's official channel.\n\n"
            "Thank you."
        )
        notice = (
            "This is an editable draft only; JanSahayak AI does not submit it. Remove personal "
            "identifiers, bank details, and OTPs before sharing, and verify the department's "
            "grievance channel on its official site."
        )
    return {"subject": title, "draft": body, "notice": notice, "clarifying_questions": questions}


def inspect_uploaded_document(file_storage, max_size):
    filename = file_storage.filename or ""
    extension = filename.rsplit(".", 1)[-1].casefold() if "." in filename else ""
    allowed_extensions = {"pdf", "png", "jpg", "jpeg"}
    if extension not in allowed_extensions:
        return None, "Upload a PDF, PNG, or JPEG file."

    content = file_storage.stream.read(max_size + 1)
    if len(content) > max_size:
        return None, "The document is larger than the allowed 5 MB limit."
    signatures = {
        "pdf": content.startswith(b"%PDF-"),
        "png": content.startswith(b"\x89PNG\r\n\x1a\n"),
        "jpg": content.startswith(b"\xff\xd8\xff"),
        "jpeg": content.startswith(b"\xff\xd8\xff"),
    }
    if not signatures[extension]:
        return None, "The file content does not match its PDF, PNG, or JPEG extension."

    document_type = {"pdf": "PDF document", "png": "PNG image", "jpg": "JPEG image", "jpeg": "JPEG image"}[extension]
    return {
        "filename": filename[:120],
        "document_type": document_type,
        "size_bytes": len(content),
        "storage": "not_saved",
        "text_extraction": "unavailable",
        "quality_assessment": "unavailable",
        "message": (
            "The file was checked in memory and discarded. OCR and image-quality analysis "
            "are not configured in this installation."
        ),
    }, None
