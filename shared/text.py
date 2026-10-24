"""HTML -> plain text, boilerplate removal, truncation."""
import html
import re
from html.parser import HTMLParser

MAX_CHARS = 1500

_BLOCK = {"p", "div", "br", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "tr"}
_BOILER = re.compile(
    r"^(about (us|the company|[a-z0-9 .&-]{1,30})\b|who we are|equal opportunity|we are an equal|"
    r"diversity|our (values|mission)|why join|benefits|perks|privacy)", re.I)
_BOILER_BODY = re.compile(r"equal opportunity employer|without regard to|reasonable accommodation", re.I)
_PRIORITY = re.compile(r"responsib|what you|you will|requirement|qualif|you have|you bring|skills|must have|the role", re.I)


class _Extract(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag == "li":
            self.parts.append("\n- ")
        elif tag in _BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in _BLOCK or tag == "li":
            self.parts.append("\n")

    def handle_data(self, data):
        self.parts.append(data)


def html_to_text(raw, escaped=False):
    """Convert HTML (optionally HTML-escaped, as Greenhouse returns) to plain text."""
    if escaped:
        raw = html.unescape(raw or "")
    p = _Extract()
    p.feed(raw or "")
    text = html.unescape("".join(p.parts)).replace("\xa0", " ")
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in text.splitlines()]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def _sections(text):
    """Split into (heading, body) sections; a heading is a short line without a period."""
    secs, head, body = [], "", []
    for ln in text.splitlines():
        is_head = ln and len(ln) < 70 and not ln.startswith("-") and not ln.endswith(".")
        if is_head:
            if head or body:
                secs.append((head, "\n".join(body).strip()))
            head, body = ln, []
        else:
            body.append(ln)
    secs.append((head, "\n".join(body).strip()))
    return secs


def clean_description(text, max_chars=MAX_CHARS):
    """Drop boilerplate, put requirement/responsibility sections first, truncate."""
    secs = [(h, b) for h, b in _sections(text)
            if not (h and _BOILER.match(h)) and not _BOILER_BODY.search(b)]
    first = [s for s in secs if _PRIORITY.search(s[0])]
    rest = [s for s in secs if s not in first]
    out = "\n\n".join(f"{h}\n{b}".strip() for h, b in first + rest if h or b).strip()
    if len(out) > max_chars:
        out = out[:max_chars].rsplit(" ", 1)[0].rstrip() + "..."
    return out
