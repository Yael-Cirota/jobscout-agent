# JobScout

A personal job-hunting agent for software developer roles in Israel. You talk to it in plain language
("Find me backend jobs in Tel Aviv", "Save the JFrog one", "Anything new?"). It searches the public
Greenhouse and Lever career boards of a list of companies, keeps track of the jobs you save and apply to,
and remembers your preferences between sessions.

The agent is built **twice on the same domain code** so the two approaches can be compared:

| Version | Folder | How it works | Billing |
|---|---|---|---|
| **SDK** | [`SDK/`](SDK/) | OpenAI Codex SDK runs the agent loop. The tools are served to Codex over an MCP server. | ChatGPT Plus (`codex login`) |
| **API** | [`API/`](API/) | A hand-written harness on the OpenAI Responses API: loop, history, memory, context, compaction, caching and token accounting. | OpenAI API key |

Both versions share the system prompt, the 7 tools, the persisted state and the pass/fail checks, so
any difference in the results comes from the harness. The comparison (tokens, cost, time, lines of code,
and which version to choose) is in [`REPORT.md`](REPORT.md).

## What the agent can do

The model has 7 tools (defined once in [`shared/tool_specs.py`](shared/tool_specs.py), implemented in
[`shared/tools_impl.py`](shared/tools_impl.py)):

| Tool | Purpose |
|---|---|
| `search_jobs` | Search the saved companies' boards for developer jobs in Israel. Returns short rows only (id, title, company, city, url). `only_new=true` skips jobs already shown. |
| `get_job_details` | Fetch the cleaned description of one job, only when the user asks about it. |
| `track_job` | Save a job or move it through `saved` → `applied` → `interview` → `offer` / `rejected`. |
| `get_tracker` | List tracked jobs, optionally by status. |
| `update_profile` | Change preferences (roles, cities, strict cities, skipped companies) and record why. |
| `get_profile` | Return the profile, including the log of past changes. |
| `manage_companies` | List, add or remove the companies that are searched (adding validates the board token). |

Behavior rules from the system prompt ([`shared/prompts.py`](shared/prompts.py)):
- Report only jobs that the tools returned. Never invent jobs, companies or links.
- Keep search results short. Fetch a full description only for one specific job.
- Respect the saved profile. If a request conflicts with it (for example, a Haifa job when the user only wants
  Tel Aviv), point out the conflict and ask before changing the profile.

The search starts from 11 companies (Lightrun, Riskified, JFrog and others) listed in
[`shared/data/companies.seed.json`](shared/data/companies.seed.json).

## Project layout

```
shared/              Domain code used by both versions
  boards.py            Greenhouse + Lever clients, normalized to one job shape
  http_client.py       fetch with timeout, retry, logging and live / record / replay modes
  locations.py         City aliases and Israel detection
  roles.py             Job title -> role tags (backend, fullstack, ...)
  text.py              HTML -> plain text, boilerplate removal, truncation
  store.py             JSON persistence: profile, companies, tracker, seen jobs, logs
  tool_specs.py        Names, descriptions and JSON schemas of the 7 tools
  tools_impl.py        The 7 tools as plain Python functions
  prompts.py           System prompt (identical in both versions)
  pricing.py           $ per million tokens per model (unknown model -> cost is null)
  scenario_runner.py   Runs a scenario, saves per-turn snapshots, writes the result file
  checks.py            Pass/fail checks C1-C8
  fixtures/            Recorded board responses for replay mode
SDK/                 Codex SDK version
  agent.py             Configures Codex (prompt, AGENTS.md memory, thread start/resume)
  mcp_server.py        Stdio MCP server exposing the 7 tools to Codex
  tools.py             Codex config for the MCP server and tool restrictions
  main.py              CLI
API/                 Hand-written harness version
  agent.py             Wires the harness parts into one agent
  harness/             One file per harness part:
    loop.py              Call the model, run function calls, send outputs back, repeat
    history.py           Append-only JSONL conversation history
    memory.py            Reads profile / tracker / seen jobs
    context.py           Picks a small <context> block per turn by the request's intent
    compaction.py        Summarizes the conversation past a threshold and at session end
    caching.py           Keeps the prompt prefix stable so OpenAI's prompt cache hits
    tokens.py            Token usage and cost per turn
    tools.py             Tool schemas and dispatch
    items.py             Helpers for Responses API items
    config.py            Every tunable in one place (limits, thresholds, intent rules)
    logger.py            One-line logs prefixed with the file that acted
  main.py              CLI
scripts/record_fixtures.py   Records live board responses once for replay
tests/               Offline unit and end-to-end tests (no key, no network)
scenario.json        The 8-turn, 2-session test scenario
results/             Result files of past runs
REPORT.md            API vs SDK comparison
```

## The test scenario

[`scenario.json`](scenario.json) runs 8 turns over 2 sessions. Session 2 starts a **new agent
instance**, so anything it knows about session 1 must come from saved memory.

| Turn | User says | What it tests |
|---|---|---|
| t1 | Find me backend jobs in Tel Aviv. | Tool use, live board search |
| t2 | Save the JFrog one. | Save to memory |
| t3 | I applied to it. | Status update |
| t4 | Don't show me jobs outside Tel Aviv. | Profile change |
| t5 | What's the status of my applications? | Recall from memory in a new session |
| t6 | Anything new? | Only jobs not shown before |
| t7 | Show me that Haifa job. | Conflict with the saved profile |
| t8 | Yes, add Haifa to my cities. | Profile change after the user agrees |

After the run, [`shared/checks.py`](shared/checks.py) grades the saved state and logs:

| Check | Passes when |
|---|---|
| C1 | The JFrog job is tracked with history `saved` → `applied` after t3. |
| C2 | After t4 the profile has cities `["Tel Aviv"]`, strict cities on, and a logged change. |
| C3 | The t6 search returns no job already seen before. |
| C4 | t1 and t6 really hit the Greenhouse / Lever APIs through `search_jobs`. |
| C5 | t5 mentions the JFrog application, and session 2 used a new agent instance. |
| C6 | t7 leaves the profile unchanged and mentions the rule or asks. |
| C7 | After t8 the cities include Tel Aviv and Haifa, with a new change entry. |
| C8 | Job details are fetched only in t7, and no search result contains a description. |

## Setup

Python 3 and a virtual environment (Windows commands shown):

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### SDK version
```powershell
codex login            # sign in with ChatGPT Plus
```
The SDK version always uses the `codex login`. If `OPENAI_API_KEY` is set, `SDK/main.py` removes it from
its own environment and prints a notice, so billing never goes to the key.
Set `model` in `scenario.json` to a model that is available both in Codex with Plus and in the API.

### API version
Copy `.env.example` to `.env` and put your key there (`.env` is git-ignored), or set the `OPENAI_API_KEY`
environment variable (it wins over `.env`). `API/main.py` exits without a key. `shared/pricing.py` needs
the model's prices, or `cost_usd` stays `null`.

## Running

Board data can come from the live APIs or from recorded fixtures, set by `JOBSCOUT_HTTP`:
- `live` (default): real requests.
- `record`: real requests, saved to `shared/fixtures/`.
- `replay`: only the saved fixtures, so every run sees the same jobs.

```powershell
python scripts/record_fixtures.py            # once, live: records board responses
$env:JOBSCOUT_HTTP = "replay"                # cmd: set JOBSCOUT_HTTP=replay

python SDK/main.py --scenario scenario.json
python API/main.py --scenario scenario.json                            # needs OPENAI_API_KEY
python API/main.py --scenario scenario.json --compact-threshold 2000   # forces compaction

pytest -q tests/                             # offline, no key, no network
```

Options:
- `--out PATH`: result file. By default each run writes a new `results/<version>_<timestamp>.json`.
- `--state-dir DIR`: where the agent's memory lives (default `state/sdk` or `state/api`). It is wiped and
  re-seeded at the start of every run.
- `--compact-threshold N` (API only): context size in tokens that triggers compaction (default 30,000).

## Output

Each run prints one line per turn (tools called, model calls, tokens) and the PASS / FAIL of each check.
The result file holds:
- per-turn tokens (uncached input, cache read, cache write, output), model calls, tools, cost and time
- totals, including the cache hit percentage
- the C1-C8 results
- lines of code per harness part
- for the API version, the token usage of the end-of-session summaries

A folder named after the result file (`<result>_snapshots/`) holds the saved state after each turn.
During a run the agent's memory lives in `state/<version>/`: `profile.json`, `tracker.json`, `seen.json`,
`companies.json`, plus `tool_log.jsonl` and `http_log.jsonl`.

## Results summary

Same scenario, same model (`gpt-5.6-luna`, effort `medium`), replayed board data. Full details in
[`REPORT.md`](REPORT.md).

| | API harness | Codex SDK |
|---|---|---|
| Checks passed | 8/8 | 8/8 |
| Total tokens | ~31,000 | ~268,800 |
| Cost (API list price) | $0.0043 | $0.0118 |
| Time | 29.5 s | 36.3 s |
| Harness code lines | 514 | 32 |

The SDK needs far less code, but Codex adds a large fixed prompt to every call. For a small agent like
this one, the API harness uses about 9x fewer tokens and costs about 2.8x less, and it gives full control
over the prompt, context, compaction and caching.

## Tests

`pytest -q tests/` runs 60 offline tests: the shared tools and checks, every API harness part (loop,
history, compaction, caching, memory and context, tokens, tool dispatch), the SDK configuration, and an
end-to-end API run against a fake model client.
