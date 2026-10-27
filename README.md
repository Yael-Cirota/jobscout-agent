# JobScout

Personal job hunter for software developer roles in Israel (Greenhouse + Lever public boards).
Built on the same `shared/` domain code twice: `SDK/` (OpenAI Codex SDK, ChatGPT Plus login) and
`API/` (hand-written harness on the OpenAI API, Part 2). See `JobScout_Project_Spec.md`.

## Setup (SDK version)
```bash
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
codex login            # sign in with ChatGPT Plus
```
The SDK version always uses the `codex login`. If `OPENAI_API_KEY` is set, `SDK/main.py` ignores it
(removes it from its own environment) and prints a notice, so billing never goes to the key.
Set `model` in `scenario.json` (a model available in Codex with Plus and in the API).

## Setup (API version)
Same venv and `pip install -r requirements.txt`. Copy `.env.example` to `.env` and put your key there (`.env` is git-ignored), or set the
`OPENAI_API_KEY` environment variable (it wins over `.env`). `API/main.py` exits without a key. `shared/pricing.py` needs the model's prices, or `cost_usd` stays `null`.

## Run
```bash
python scripts/record_fixtures.py                       # once, live: records board responses
set JOBSCOUT_HTTP=replay
python SDK/main.py                                      # interactive: type your own turns
python API/main.py                                      # same, API version (needs OPENAI_API_KEY)
python SDK/main.py --scenario scenario.json --out results/sdk.json
python API/main.py --scenario scenario.json --out results/api.json   # needs OPENAI_API_KEY
python API/main.py --scenario scenario.json --out results/api.json --compact-threshold 2000   # shows compaction
pytest -q tests/                                        # offline, no key, no network
```
Without `--scenario`, both versions are interactive: type a message at `you>`, `/new` ends the session
and starts a new agent instance (like session 2 in the scenario), `/quit` (or Ctrl+C / Ctrl+Z) finishes the run.
Model and effort still come from `scenario.json`. Turns are numbered t1, t2, ... across sessions and the result
file (`results/<version>_<timestamp>.json`) is written the same way, so typing the 8 scenario turns in order still
gives meaningful checks; free-form chats will mostly fail them.
