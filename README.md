# Penwash

[![CI](https://github.com/rokib16x/penwash/actions/workflows/ci.yml/badge.svg)](https://github.com/rokib16x/penwash/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Turn stiff, over-polished drafts into plain, natural writing. Penwash runs entirely on your machine using a local model through [Ollama](https://ollama.com). No accounts, no word limits, and your text never leaves your computer.

## Features

- **Two modes.** *Rewrite* uses a local model to rewrite in plainer words. *Clean up only* keeps your exact wording and removes machine-text tells: em dashes, emoji, markdown symbols, filler openers ("Furthermore,") and stock words ("utilize", "leverage"). Clean-up needs no model and lists every change it made.
- Tone presets: natural, casual, professional, academic
- Rewrite strength slider, from light edits to a full rewrite
- Optional writing sample, so the model imitates your own voice
- Streaming output, paragraph by paragraph
- Retries a paragraph when stock phrases ("delve", "furthermore", ...) remain
- Warns if a number from the original goes missing
- Before/after style stats: sentence length, rhythm variety, stock-phrase count
- Works with any model installed in Ollama; light and dark themes

## Fonts

The UI loads Satoshi (Fontshare) and Newsreader (Google Fonts) from their CDNs. Only font files are requested; your text is never sent anywhere. For a fully offline setup, download the fonts and swap the two `<link>` tags in `static/index.html` for local `@font-face` rules. Check each font's license before redistributing the files.

## Requirements

- macOS, Linux or Windows
- [Ollama](https://ollama.com) with at least one chat model, e.g. `ollama pull qwen2.5:14b`
- [uv](https://docs.astral.sh/uv/) (or Python 3.10+ with `pip install -r requirements.txt`)

## Run

```bash
./run.sh
```

Then open http://127.0.0.1:8765.

Without `uv`:

```bash
pip install -r requirements.txt
uvicorn app:app --port 8765
```

## How it works

```
Browser UI ──NDJSON stream──▶ FastAPI (app.py) ──▶ Ollama (localhost:11434)
```

Each paragraph is rewritten with a system prompt built from your tone, strength and voice sample. The result is cleaned up and checked for leftover stock phrases and missing numbers, then re-rewritten if needed (up to the retry limit).

## Limitations

- Rewrite mode checks every paragraph for language drift, invented content, dropped numbers and names, and chatty openers. Failing paragraphs are retried and, if still unreliable, left as the original. The Details panel lists them. These checks cannot catch subtle changes in meaning, so read legal, medical and other precise text yourself.
- Multilingual models can occasionally slip into another language. English-focused models such as Llama or Gemma are a good alternative to Qwen for English text.

- The stats describe writing style. They do not predict what any commercial AI detector will say, and no local tool can.
- Output quality depends on the model you choose. Larger models preserve meaning better.
- Review the result before you use it. You are responsible for following any school, employer or publisher policy on AI-assisted writing.

## Development

```bash
pip install -r requirements-dev.txt
ruff check . && pytest
```

See [CONTRIBUTING.md](CONTRIBUTING.md). Please follow the [Code of Conduct](CODE_OF_CONDUCT.md); report security issues as described in [SECURITY.md](SECURITY.md).

## License

MIT
