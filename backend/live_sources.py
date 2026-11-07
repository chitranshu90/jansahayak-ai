import re
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urlsplit


_CACHE_SECONDS = 300
_MAX_SOURCE_BYTES = 1_000_000
_CACHE = {}
_CACHE_LOCK = threading.Lock()


class SourceUnavailable(Exception):
    pass


class _PageText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title_parts = []
        self.text_parts = []
        self._in_title = False
        self._skip_depth = 0

    def handle_starttag(self, tag, _attrs):
        if tag == "title":
            self._in_title = True
        if tag in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1
        if tag in {"p", "br", "li", "h1", "h2", "h3", "div"}:
            self.text_parts.append(" ")

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        if tag in {"script", "style", "noscript", "svg"}:
            self._skip_depth = max(0, self._skip_depth - 1)
        if tag in {"p", "br", "li", "h1", "h2", "h3", "div"}:
            self.text_parts.append(" ")

    def handle_data(self, data):
        if self._in_title:
            self.title_parts.append(data)
        if not self._skip_depth:
            self.text_parts.append(data)


def _extract(html):
    parser = _PageText()
    parser.feed(html)
    title = re.sub(r"\s+", " ", " ".join(parser.title_parts)).strip()
    text = re.sub(r"\s+", " ", " ".join(parser.text_parts)).strip()
    return title[:240], text[:_MAX_SOURCE_BYTES]


def check_scheme_source(scheme):
    url = scheme.get("official_source_url", "")
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise SourceUnavailable("The stored official source URL is invalid.")

    now = time.monotonic()
    with _CACHE_LOCK:
        cached = _CACHE.get(url)
        if cached and cached["expires_at"] > now:
            return {**cached["result"], "cached": True}

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "JanSahayakAI/1.0 (official-source link check)",
            "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.1",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            final_url = urlsplit(response.geturl())
            if (
                final_url.scheme != "https"
                or not final_url.hostname
                or final_url.hostname.casefold() != parsed.hostname.casefold()
            ):
                raise SourceUnavailable("The official source redirected to a different host.")
            content_type = response.headers.get_content_type()
            if content_type not in {"text/html", "application/xhtml+xml"}:
                raise SourceUnavailable("The official source did not return a readable web page.")
            content = response.read(_MAX_SOURCE_BYTES + 1)
            if len(content) > _MAX_SOURCE_BYTES:
                content = content[:_MAX_SOURCE_BYTES]
    except urllib.error.HTTPError as error:
        raise SourceUnavailable(f"The official source returned HTTP {error.code}.") from error
    except urllib.error.URLError as error:
        raise SourceUnavailable("The official source could not be reached. Try again later.") from error
    except TimeoutError as error:
        raise SourceUnavailable("The official source did not respond in time.") from error

    encoding = "utf-8"
    charset = response.headers.get_content_charset()
    if charset:
        encoding = charset
    title, text = _extract(content.decode(encoding, errors="replace"))
    if not text:
        raise SourceUnavailable("The official page did not expose readable text.")

    result = {
        "scheme_slug": scheme["scheme_slug"],
        "scheme_name": scheme["scheme_name"],
        "source_url": url,
        "source_status": "reachable",
        "page_title": title,
        "excerpt": text[:6000],
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "cached": False,
        "notice": (
            "Live text retrieved from the linked official page. This page excerpt does not update "
            "the scheme record or verify eligibility, documents, benefits, or deadlines."
        ),
    }
    with _CACHE_LOCK:
        _CACHE[url] = {"result": result, "expires_at": time.monotonic() + _CACHE_SECONDS}
    return result
