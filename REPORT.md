# JobScout: API harness vs. Codex SDK

Both versions ran the same 8-turn, 2-session scenario (`scenario.json`) on the same model (`gpt-5.6-luna`, effort `medium`) with recorded board data (`JOBSCOUT_HTTP=replay`). Raw numbers are in `results/api.json` and `results/sdk.json`. Offline tests: 60 passed.

## 1. Results

| | API (hand-written harness) | SDK (Codex) |
|---|---|---|
| Uncached input tokens | 1,775 | 20,266 |
| Cache-read tokens | 22,471 | 246,144 |
| Cache-write tokens | 5,284 | 0 (not reported) |
| Output tokens | 1,476 | 2,386 |
| **Total tokens (all input + output)** | **~31,000** | **~268,800** |
| Cache % (cache read / all input) | 76.1% | 92.4% |
| Model calls | 15 | 15 |
| **Cost (USD, API list price)** | **$0.0043** (8 turns $0.0036 + session-end summaries $0.0007) | **$0.0118** |
| Time | 29.5 s | 36.3 s |
| Tests passed (scenario checks C1–C8) | 8/8 | 8/8 |
| Unit tests (`pytest tests/`) | 60/60 (shared by both; the API loop is covered by `test_loop`, `test_caching`, `test_compaction`, `test_api_end_to_end`) | |

- **How cost was calculated.** Prices for `gpt-5.6-luna` (short-context tier): $0.20 per 1M input, $0.02 per 1M cached input, $1.20 per 1M output. They come from public aggregator listings (OpenRouter, Requesty, Vercel, AIHubMix), not from openai.com, so check them before budgeting. They are now in `shared/pricing.py` (dated 2026-10-28), so future runs fill `cost_usd` themselves. Cost = uncached input x $0.20 + cache reads x $0.02 + output x $1.20.
- The API's "cache write" tokens (5,284) are billed as normal input at $0.20, since OpenAI charges no separate cache-write fee.
- **Result:** the SDK run costs about **2.8x** the API run ($0.0118 vs $0.0043), far less than the 8.7x token gap, because 92% of the SDK's tokens are cheap cache reads. Per million-run scale: roughly $4.3 vs $11.8 per 1,000 scenario runs. The SDK run is actually billed through ChatGPT Plus, so the SDK figure is API-equivalent.
- Without any caching, the same tokens would cost $0.0077 (API) vs $0.0561 (SDK), so caching helps the SDK a lot (79% saved) and the API less (44% saved).
- The API figures exclude two end-of-session summary calls (1,218 + 875 input, 209 output, in `session_end_summaries`). They add 2 calls and about 2.3k tokens, which doesn't change the picture.
- Cache % is lower for the API even though it uses far fewer tokens. Its prompts are small, so the cold first call of each session and the new tail of every turn weigh more. The SDK has a big stable prefix that is re-read on every call.
- Run-to-run noise: an earlier SDK run (committed before this report) had 392k cache-read tokens and 16 calls. Treat SDK token totals as ±30%.

## 2. Lines of code per harness part

API counts non-blank, non-comment lines per file in `API/harness/`, via `count_loc`. SDK counts lines tagged `# replaces: <part>` in `SDK/`.

| Part | API | SDK |
|---|---|---|
| Loop | 47 | 2 |
| History | 48 | 4 |
| Tools | 37 | 17 (MCP server + Codex config) |
| Memory | 26 | 3 |
| Context building | 21 | 2 |
| Tokens / accounting | 34 | 4 |
| Compaction | 70 | 0 (built in) |
| Caching | 33 | 0 (built in) |
| Config | 37 | 0 |
| Items (message types) | 34 | 0 |
| Logger | 12 | 0 |
| Agent + main glue | 115 | (counted in the rows above) |
| **Total** | **514** | **32** |

The SDK files are 214 raw lines in total (`agent.py` 86, `main.py` 50, `mcp_server.py` 47, `tools.py` 31). Only 32 of those implement a harness part. The rest is CLI, boilerplate and the per-turn token accounting.

## 3. Where the SDK used more tokens, where fewer, and why

**More (about 8.7x in total):**
- **Fixed per-call overhead.** Every SDK turn re-reads 28k–36k cached tokens, against 1k–5.5k for the API. Codex adds its own large built-in system prompt and tool definitions (shell, patch, plan and so on), even though only the 7 MCP tools are allowed. The API sends only our system prompt and 7 tool schemas.
- **No context slicing.** The API harness picks a profile and tracker slice by intent (`context.py`), so "Save the JFrog one" gets only what it needs. Codex gets a full `AGENTS.md` dump of profile and tracker.
- **Uncached input on the first turn is 8k.** That is the cold start with the full Codex prompt. The API's first turn is about 0.8k uncached plus 1.5k written to the cache.
- **More output tokens (2,386 vs 1,476).** Codex's agent prompt makes it more verbose and it spends more tokens on reasoning.
- **t5 ("what's my status?").** The SDK called `get_tracker` (2 calls, 2.4k uncached input). The API harness already had the tracker summary in context and answered in 1 call.

**Fewer:**
- **t7 (the conflicting request).** The SDK answered with no tool call, 1 call and 460 input tokens. The API harness ran a `search_jobs` first (2 calls). The API's behavior is arguably safer (it checks the data before pushing back), but it costs more on this one turn.
- **Cache accounting.** The SDK shows no cache writes, so its numbers look cache-friendly (92%). Codex handles the prefix for us, and we can't see how.
- **Search results.** On t1 the SDK returned only 4 ids on the first search, where the API returned 9 (C3). That is a small difference in how many results each model chose to show, not a harness effect.

## 4. What I controlled in the API and lost in the SDK

- **The whole prompt.** In the API I decide exactly what is in every request, down to the order. The SDK always includes Codex's own instructions, and I can only add `developer_instructions` and `AGENTS.md`.
- **Context per turn.** Intent-based slicing of the profile and tracker is impossible in the SDK, which gives the model the same memory file every turn.
- **Compaction.** The API compacts at a configurable threshold (`--compact-threshold`), keeps the last N turns and writes a summary at session end. In the SDK compaction is automatic, and I can't set when or how it summarizes. I also can't test it with a small threshold.
- **Prompt caching.** The API sets an explicit cache key and checks that the prefix stays identical (`caching.py` logs it). The SDK gives no way to inspect or change this.
- **Loop limits and per-call visibility.** `max_calls_per_turn`, one log line per model call, per-call token counts and per-call reasoning tokens all exist in the API. The SDK only gives cumulative usage per thread, so per-turn numbers are deltas I compute.
- **History as data.** The API stores append-only JSONL I can read, edit and replay. The SDK keeps history inside Codex's thread, and I only hold the thread id.
- **Tool execution.** I handle errors, logging and result shaping myself. In the SDK everything goes through an MCP subprocess, which means extra process startup and no direct control of the tool-call path.
- **Determinism and tests.** A fake client lets me unit-test the API loop offline. There is no equivalent for the SDK's loop.

What the SDK gives in return: working compaction, caching, sandboxing, approvals and resume with almost no code, and billing through a ChatGPT Plus plan.

## 5. Which version I would choose

**The API harness, for this agent.** JobScout is a narrow agent with 7 tools, short turns and a small amount of state. Its cost is dominated by the fixed prompt overhead, and that is exactly where the API wins, with about 9x fewer tokens and about 2.8x lower cost for the same 8/8 correctness and slightly lower latency. The extra 480 lines of harness code (514 vs 32) buy a prompt we can read and tune, slicing and compaction we can test offline, and per-call logs for debugging when a check fails.

I would choose the SDK only for a quick prototype, or if the agent needed the things Codex gives for free (file edits, shell, sandboxing) or if running on a ChatGPT Plus plan mattered more than token efficiency. Neither applies here. The decision would shift if the agent grew many more tools or very long conversations, because the SDK's built-in compaction would then save real work.

Caveats: one run per version, so small differences (time, call counts on single turns) are within noise. The SDK token totals varied by about 30% between two runs. The prices are aggregator list prices, and the costs in this report were computed from the saved token counts. `results/*.json` still show `cost_usd: null` because they were produced before the prices were added.
