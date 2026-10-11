# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/) and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Fixed
- Rewrite mode could emit text in another language (observed with Qwen models) and cut the sentence short. Sampling is now conservative (`repeat_penalty` 1.0, lower temperature) and any output containing unexpected non-English characters is retried, then replaced by the original paragraph.
- Headings such as `**b. Child Affairs Police Officers**` were treated as paragraphs and replaced with invented text. Headings, list items, tables and code are now detected structurally and passed through untouched.
- Chatty openers ("Sure thing.", "Here's the rewrite:"), slang drift ("kids", "folks"), dropped numbers and names, and runaway length are now detected per paragraph and retried. Paragraphs that stay unreliable keep the original text and are listed under Details.

### Changed
- "Retry passes" now means retries after the first attempt.
- The section heading is passed to the model as context so short paragraphs keep their subject.

## [0.1.0] - 2026-10-11

### Added
- Rewrite mode: local model rewriting through Ollama, with tone, strength, voice sample and retry controls.
- Clean up only mode: deterministic removal of em dashes, emoji, markdown symbols, filler openers and stock words, with a list of every change.
- Streaming output, before/after style stats, number-preservation warnings.
- Light and dark themes, single-screen compact layout.
