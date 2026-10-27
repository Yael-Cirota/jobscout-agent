"""What goes into each user turn: a small <context> block chosen by the request's intent."""
import re

from .config import HarnessConfig
from .logger import log
from .memory import Memory


def classify_intent(text, config=HarnessConfig()):
    """Keyword rules from the config; first match wins, no model call."""
    lowered = text.lower()
    for rule in config.intents:
        if any(re.search(p, lowered) for p in rule.patterns):
            return rule
    return config.fallback_intent


def build_turn(text, memory: Memory, config=HarnessConfig()):
    """`<context>` (profile slice + one-line tracker summary) followed by the user's text."""
    rule = classify_intent(text, config)
    profile = memory.profile_slice(rule.fields)
    tracker = memory.tracker_summary()
    lines = ([f"profile: {profile}"] if profile else []) + [tracker]
    log(__file__, f"intent={rule.name} -> profile slice: {', '.join(rule.fields) or 'none'}; "
                  f"tracker summary: {len(tracker)} chars")
    return "<context>\n" + "\n".join(lines) + "\n</context>\n" + text
