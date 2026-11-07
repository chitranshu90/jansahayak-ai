import re
from difflib import SequenceMatcher


_WORD_PATTERN = re.compile(r"[a-z0-9]+|[\u0900-\u097f]+")
_MIN_FUZZY_TOKEN_LENGTH = 4
_FUZZY_MATCH_THRESHOLD = 0.78
_STOP_WORDS = {
    "a", "about", "an", "and", "can", "do", "for", "from", "i", "in", "is", "it",
    "me", "my", "need", "of", "on", "please", "tell", "the", "to", "want", "what",
    "which", "with", "you", "your", "document", "documents", "scheme", "schemes",
    "मुझे", "मेरे", "मेरा", "मेरी", "कौन", "से", "क्या", "है", "हैं", "में", "पर",
    "किस", "का", "की", "के", "बताएं", "बताओ", "जानकारी", "दो", "चाहिए",
    "दस्तावेज़", "दस्तावेज", "कागज़", "कागज", "पात्रता", "योग्यता",
}


def search_tokens(text):
    return _WORD_PATTERN.findall(str(text).casefold())


def tokens_match(query_token, candidate_token):
    if query_token == candidate_token:
        return True
    if min(len(query_token), len(candidate_token)) < _MIN_FUZZY_TOKEN_LENGTH:
        return False
    if query_token in candidate_token or candidate_token in query_token:
        return True
    return SequenceMatcher(None, query_token, candidate_token).ratio() >= _FUZZY_MATCH_THRESHOLD


def scheme_search_score(query, scheme):
    query_tokens = [
        token for token in search_tokens(query)
        if token not in _STOP_WORDS
    ]
    if not query_tokens:
        return 0

    fields = (
        ("scheme_name", 6),
        ("keywords", 5),
        ("target_beneficiaries", 4),
        ("target_beneficiaries_hi", 4),
        ("category", 3),
        ("description", 2),
        ("description_hi", 2),
    )
    score = 0
    for token in query_tokens:
        best_match = 0
        for field, weight in fields:
            if any(tokens_match(token, candidate) for candidate in search_tokens(scheme.get(field, ""))):
                best_match = max(best_match, weight)
        score += best_match
    return score
