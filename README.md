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

## Run
```bash
python scripts/record_fixtures.py                       # once, live: records board responses
set JOBSCOUT_HTTP=replay
python SDK/main.py --scenario scenario.json --out results/sdk.json
pytest -q tests/                                        # offline, no key, no network
```
