"""Title -> role tags."""
import re

ROLE_PATTERNS = {
    "backend": r"back[- ]?end|server|\bjava\b|golang|\bgo\b|python|node(\.?js)?|platform engineer|\.net|\bc\+\+|\brust\b|infrastructure engineer",
    "fullstack": r"full[- ]?stack",
    "frontend": r"front[- ]?end|\breact\b|web developer|\bui engineer",
}
# Generic developer titles count as a match for any requested role.
GENERIC = r"software (engineer|developer)|\bdeveloper\b|\bprogrammer\b|\bsde\b|r&d engineer"
EXCLUDE = r"sales|recruit|marketing|finance|\bhr\b|human resources|account (executive|manager)|legal|customer success|support engineer|talent|paralegal|designer"

_ROLE_ALIASES = {"full stack": "fullstack", "full-stack": "fullstack", "back end": "backend",
                 "back-end": "backend", "front end": "frontend", "front-end": "frontend"}


def normalize_role(role):
    r = (role or "").strip().lower()
    return _ROLE_ALIASES.get(r, r)


def role_tags(title):
    t = (title or "").lower()
    if re.search(EXCLUDE, t):
        return set()
    tags = {name for name, pat in ROLE_PATTERNS.items() if re.search(pat, t)}
    if not tags and re.search(GENERIC, t):
        tags.add("general")
    return tags


def matches_roles(title, roles):
    """True if the title is a developer role and (no filter, or matches one of `roles`)."""
    tags = role_tags(title)
    if not tags:
        return False
    if not roles:
        return True
    wanted = {normalize_role(r) for r in roles}
    return "general" in tags or bool(tags & wanted)
