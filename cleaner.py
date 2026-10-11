"""Clean-up mode: keeps the author's wording and strips common machine-text tells.

Deterministic and offline. No model involved, so the text is never paraphrased.
"""
import re
from collections import defaultdict

ZERO_WIDTH = re.compile("[\u200b‌‍⁠﻿­]")
EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿⭐⭕️]")
DASH = re.compile(r"\s*(?:—|\s–\s|\s--\s)\s*")
BOLD = re.compile(r"(\*\*|__)(?=\S)(.+?)(?<=\S)\1")
ITALIC = re.compile(r"(?<![*\w])\*(?=\S)([^*\n]+?)(?<=\S)\*(?![*\w])")
HEADING = re.compile(r"^[ \t]*#{1,6}[ \t]+", re.MULTILINE)

OPENERS = (
    "Furthermore|Moreover|Additionally|In conclusion|In summary|To summarize|Overall|Ultimately"
    "|Notably|Importantly|In essence"
)
OPENER = re.compile(rf"(^|[.!?]\s+)(?:{OPENERS}),\s+([A-Za-z])", re.MULTILINE)
NOTE_THAT = re.compile(
    r"(^|[.!?]\s+)It(?:'s| is) (?:important to note|worth noting|worth mentioning|crucial to note) that,?\s+([A-Za-z])",
    re.MULTILINE,
)

SWAPS = {
    "in order to": "to", "a myriad of": "many", "myriad of": "many", "delve into": "look into",
    "delving into": "looking into", "delves into": "looks into", "delved into": "looked into",
    "utilize": "use", "utilizes": "uses", "utilizing": "using", "utilized": "used",
    "utilise": "use", "utilises": "uses", "utilising": "using", "utilised": "used",
    "leverage": "use", "leverages": "uses", "leveraging": "using", "leveraged": "used",
    "seamlessly": "smoothly", "seamless": "smooth", "robust": "solid", "pivotal": "key",
    "paramount": "essential", "multifaceted": "many-sided", "holistic": "complete",
    "ever-evolving": "changing", "game-changer": "big change", "facilitate": "help",
    "facilitates": "helps", "commence": "start", "endeavor": "effort", "meticulous": "careful",
    "in today's fast-paced world": "today", "plays a crucial role in": "matters for",
}
SWAP_RE = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in sorted(SWAPS, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)


def _match_case(src: str, dst: str) -> str:
    if src.isupper() and len(src) > 1:
        return dst.upper()
    if src[:1].isupper():
        return dst[:1].upper() + dst[1:]
    return dst


class _Log:
    def __init__(self):
        self.counts = defaultdict(int)
        self.examples = defaultdict(list)

    def add(self, label: str, before: str = "", after: str = ""):
        self.counts[label] += 1
        ex = f"{before.strip()} → {after.strip()}" if after.strip() else before.strip()
        if ex and len(self.examples[label]) < 3 and ex not in self.examples[label]:
            self.examples[label].append(ex[:60])

    def out(self):
        return [{"label": k, "count": v, "examples": self.examples[k]} for k, v in self.counts.items()]


def clean(text: str) -> tuple[str, list[dict]]:
    log = _Log()
    t = text

    def sub(pattern, repl, label, show=None):
        nonlocal t

        def fn(m):
            new = repl(m) if callable(repl) else m.expand(repl)
            log.add(label, *(show(m) if show else (m.group(0), new)))
            return new

        t = pattern.sub(fn, t)

    sub(ZERO_WIDTH, "", "Hidden characters removed")
    t = t.replace(" ", " ")
    sub(EMOJI, "", "Emoji removed")
    sub(DASH, ", ", "Em dashes replaced with commas")
    sub(HEADING, "", "Markdown headings stripped")
    sub(BOLD, r"\2", "Bold markers stripped")
    sub(ITALIC, r"\1", "Italic markers stripped")
    sub(OPENER, lambda m: m.group(1) + m.group(2).upper(), "Filler openers dropped",
        show=lambda m: (m.group(0)[len(m.group(1)):-1].strip(), ""))
    sub(NOTE_THAT, lambda m: m.group(1) + m.group(2).upper(), "'It's important to note' dropped",
        show=lambda m: (m.group(0)[len(m.group(1)):-1].strip(), ""))
    sub(SWAP_RE, lambda m: _match_case(m.group(1), SWAPS[m.group(1).lower()]), "Stock words swapped")

    t = re.sub(r"[ \t]+([.,!?;:])", r"\1", t)
    t = re.sub(r"[ \t]+\n", "\n", t)
    t = re.sub(r"[ \t]{2,}", " ", t).strip()
    return t, log.out()
