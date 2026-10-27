"""JobScout on the raw OpenAI Responses API. Wires the harness parts together; each part lives in harness/."""
import time

from shared import prompts
from shared.store import Store

from API.harness import caching, context, items, loop, tools
from API.harness.compaction import Compactor
from API.harness.config import HarnessConfig
from API.harness.history import History
from API.harness.logger import log
from API.harness.memory import Memory
from API.harness.tokens import TokenTracker


class JobScoutAgent:
    def __init__(self, state_dir, client, model, effort, config: HarnessConfig = HarnessConfig()):
        self.client, self.model, self.config = client, model, config
        self.store = Store(state_dir)
        self.memory = Memory(self.store)
        self.history = History(state_dir)
        self.tracker = TokenTracker(model)
        self.compactor = Compactor(client, model, config, self.history, self.tracker)
        self.executor = tools.ToolExecutor(self.store)
        self.prefix_monitor = caching.PrefixMonitor()
        self.request = {"model": model, "instructions": prompts.SYSTEM_PROMPT, "tools": tools.schemas(),
                        "reasoning": {"effort": effort}, "store": False, "include": list(config.include),
                        **caching.extras(model, config)}
        self.session = None
        self.session_end = None   # usage of the end-of-session summary, set by end_session()

    def start_session(self, session):
        self.session = session
        log(__file__, f"session {session} started, state={self.store.dir}")
        self.memory.load_all()
        self.history.load()

    def ask(self, text):
        turn, started = self.store.current_turn(), time.time()
        user = items.user_item(context.build_turn(text, self.memory, self.config))
        outcome = loop.run_turn(
            self.client, self.request, self.history.messages() + [user], self.executor,
            self.config.max_calls_per_turn, on_request=self.prefix_monitor.before_call,
            on_response=lambda resp, seconds: self._observe(turn, resp, seconds))
        self.history.append(self.session, turn, [user] + outcome.new_items)
        if self.compactor.needed(self.tracker.last_context_tokens(turn)):
            self.compactor.compact(self.session, turn, turn)
        result = self.tracker.summary(turn, wall_seconds=time.time() - started)
        log(__file__, f"{turn}: in={result['tokens']['input']} cache_r={result['tokens']['cache_read']} "
                      f"out={result['tokens']['output']} cost={result['cost_usd']} time={result['time_s']}s")
        return {"answer": outcome.text, "tools": outcome.tools, **result}

    def end_session(self):
        if self.config.summarize_on_session_end:
            bucket = f"session{self.session}_end"
            self.compactor.compact(self.session, bucket, bucket, keep_turns=0)
            self.session_end = self.tracker.summary(bucket)
        log(__file__, f"session {self.session} ended")

    def _observe(self, turn, resp, seconds):
        self.tracker.record(turn, resp, seconds)
        self.prefix_monitor.after_call(resp)

