import dataclasses

from API.harness import config, context
from API.harness.memory import Memory


def seed(store):
    store.save_profile({**store.profile(), "roles": ["backend"], "cities": ["Tel Aviv"], "strict_cities": True,
                        "changes": [{"n": 1}, {"n": 2}, {"n": 3}]})
    store.save_tracker({"jobs": {f"gh:a:{i}": {"company": "Acme", "title": f"Job {i}", "status": "saved",
                                                "history": [{"status": "saved", "at": f"2026-10-2{i}T10:00:00Z"}]}
                                 for i in range(5)}})


def test_intent_routing():
    def ask(t):
        return context.classify_intent(t).name

    assert ask("Find me backend jobs in Tel Aviv.") == "search"
    assert ask("Anything new?") == "search"
    assert ask("Show me that Haifa job.") == "search"
    assert ask("Save the JFrog one.") == "tracker"
    assert ask("I applied to it.") == "tracker"
    assert ask("What's the status of my applications?") == "tracker"
    assert ask("Don't show me jobs outside Tel Aviv.") == "profile_change"  # beats the search rule
    assert ask("Yes, add Haifa to my cities.") == "profile_change"
    assert ask("thanks") == "other"


def test_profile_slice_per_intent(store):
    seed(store)
    mem = Memory(store)
    assert "profile:" not in context.build_turn("What's the status?", mem)  # tracker intent: no profile
    search = context.build_turn("Find me jobs", mem)
    assert 'roles=["backend"]' in search and "skip_companies=[]" in search
    change = context.build_turn("Only Tel Aviv please", mem)
    assert '{"n": 2}' in change and '{"n": 3}' in change and '{"n": 1}' not in change  # last 2 changes


def test_context_block_shape_and_one_line_tracker(store):
    seed(store)
    turn = context.build_turn("Find me jobs", Memory(store))
    head, text = turn.split("</context>\n")
    assert head.startswith("<context>\nprofile: ") and text == "Find me jobs"
    assert len([ln for ln in head.splitlines() if ln.startswith("tracker:")]) == 1
    assert head.count("Job ") <= 3  # only the latest 3 entries, never the full tracker of 5


def test_rules_are_data_not_code(store):
    seed(store)
    cfg = dataclasses.replace(config.HarnessConfig(), intents=(
        config.IntentRule("custom", (r"hello",), ("roles",)),))
    out = context.build_turn("hello", Memory(store), cfg)
    assert out.startswith('<context>\nprofile: roles=["backend"]\n')


def test_memory_reads(store):
    seed(store)
    mem = Memory(store)
    assert mem.seen_ids() == set() and mem.snapshot()["profile"]["cities"] == ["Tel Aviv"]
    assert mem.load_all()["tracker"]
