# Contributing to Penwash

Thanks for helping out. Small, focused pull requests are easiest to review.

## Setup

```bash
git clone https://github.com/rokib16x/penwash.git
cd penwash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app:app --reload --port 8765
```

Rewrite mode needs [Ollama](https://ollama.com) with a chat model pulled. Clean up mode and the test suite do not.

## Before you open a PR

```bash
ruff check .
pytest
```

## Where things live

- `cleaner.py`: the rule-based Clean up mode. Add new rules and swaps here, with a test in `tests/test_cleaner.py`.
- `app.py`: the FastAPI app, prompt building and the streaming rewrite endpoint.
- `static/index.html`: the whole UI, no build step.

## Guidelines

- Keep it local-first: no telemetry, no calls to hosted services with user text.
- Clean up mode must never paraphrase. It only removes or swaps known tells.
- Match the surrounding code style; keep the UI dependency-free.

By contributing you agree your work is released under the MIT License.
