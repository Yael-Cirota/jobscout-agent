"""Every tunable of the harness in one place. Nothing else hard-codes these values."""
from dataclasses import dataclass, field

SUMMARY_INSTRUCTIONS = (
    "Summarize this conversation so it can be continued later: decisions made, jobs discussed "
    "(keep their ids exactly), profile changes, open questions. Be short and factual.")


@dataclass(frozen=True)
class IntentRule:
    """A request matching any pattern gets these profile fields. A field `name:N` keeps the last N items."""
    name: str
    patterns: tuple
    fields: tuple


# First match wins, so the more specific rules come first.
DEFAULT_INTENTS = (
    IntentRule("profile_change",
               (r"don'?t show", r"\bonly\b", r"\bprefer", r"\badd\b.*\bcit", r"\bmy cities\b"),
               ("cities", "strict_cities", "changes:2")),
    IntentRule("tracker",
               (r"\bstatus\b", r"\bapplied\b", r"\binterview", r"\breject", r"\bsave", r"\boffer\b",
                r"\btracker\b"),
               ()),
    IntentRule("search",
               (r"\bfind\b", r"\bjobs?\b", r"anything new", r"\bshow me\b", r"\bsearch\b"),
               ("roles", "cities", "strict_cities", "skip_companies")),
)
FALLBACK_INTENT = IntentRule("other", (), ("roles", "cities"))


@dataclass(frozen=True)
class HarnessConfig:
    max_calls_per_turn: int = 10
    compact_threshold: int = 30_000          # context tokens of the last call that trigger compaction
    keep_recent_turns: int = 2               # user turns kept verbatim after a compaction
    summarize_on_session_end: bool = True    # forced summary so the next session starts small
    summary_effort: str = "low"
    summary_instructions: str = SUMMARY_INSTRUCTIONS
    transcript_output_chars: int = 300       # tool output length kept in the summarizer's transcript
    include: tuple = ("reasoning.encrypted_content",)   # needed to replay reasoning with store=False
    cache_key_prefix: str = "jobscout"
    intents: tuple = DEFAULT_INTENTS
    fallback_intent: IntentRule = field(default=FALLBACK_INTENT)
