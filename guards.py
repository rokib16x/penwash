"""Guards for Rewrite mode: decide what the model may touch, and validate what it returns.

Local models drift: they switch language, invent content, add chatty openers or drop facts.
Every paragraph passes through these checks so bad output is retried or replaced by the original.
"""
import re

CJK = re.compile("[　-〿぀-ヿ㐀-䶿一-鿿가-힯＀-￯]")
LEAD_FILLER = re.compile(r"^(?:sure(?: thing)?|certainly|of course|absolutely|okay|alright)[,.!]\s+", re.IGNORECASE)
LEAD_META = re.compile(r"^here(?:'s| is| are)\b[^\n:]{0,80}:\s*", re.IGNORECASE)
SLANG = [
    "you know", "here's the thing", "let's talk", "let's dive", "first off", "so yeah", "big deal",
    "the biggie", "folks", "stuff", "grown-up", "grown up", "kids", "pretty much", "a thing or two",
    "dodge", "mess with", "tangled up", "run afoul",
]


def has_cjk(text: str) -> bool:
    return bool(CJK.search(text))


def is_structural(para: str) -> bool:
    """True for headings, list items, tables, code and other lines the model must not rewrite."""
    p = para.strip()
    if not p:
        return True
    first = p.splitlines()[0].lstrip()
    if first.startswith(("#", "```", "|")):
        return True
    if re.match(r"^([-*•]|\d+[.)])\s+", first):
        return True
    if re.fullmatch(r"(\*\*|__)[^*_\n]+\1:?", p):
        return True
    words = p.split()
    if "\n" not in p and len(words) <= 14 and not re.search(r"[.!?:;,]$", p):
        return True  # one short line with no sentence punctuation is a heading
    return len(words) < 5


def strip_preface(text: str, original: str) -> str:
    """Remove chatty lead-ins ("Sure thing.", "Here's the rewrite:") the original did not have."""
    out = text.strip()
    if LEAD_META.match(original) or LEAD_FILLER.match(original):
        return out
    m = LEAD_META.match(out)
    if m:
        out = out[m.end():]
    m = LEAD_FILLER.match(out)
    if m:
        out = out[m.end():]
        out = out[:1].upper() + out[1:]
    return out.strip()


def _core(word: str) -> str:
    return re.sub(r"(?:'s|’s)$", "", word.strip(".,;:!?()[]\"'“”‘’*")).lower()


def protected(text: str) -> tuple[set[str], set[str]]:
    """Numbers, and capitalised words that are not sentence-initial (names, laws, places)."""
    nums = {n.rstrip(".,") for n in re.findall(r"\d+(?:[.,]\d+)*", text)}
    names = set()
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        for w in sentence.split()[1:]:
            c = _core(w)
            if len(c) >= 3 and w.lstrip("(*\"“‘'")[:1].isupper():
                names.add(c)
    return nums, names


def check(orig: str, out: str, tone: str = "natural") -> list[tuple[str, str]]:
    """Return (kind, detail) problems. Empty list means the paragraph is safe to keep."""
    problems = []
    if has_cjk(out) and not has_cjk(orig):
        problems.append(("language", "contains non-English characters"))
    n_in, n_out = len(orig.split()), len(out.split())
    lo, hi = (0.6, 1.4) if n_in >= 25 else (0.45, 1.8)
    if n_in and not lo <= n_out / n_in <= hi:
        problems.append(("length", f"{n_out} words from {n_in}"))
    nums_in, names_in = protected(orig)
    nums_out, _ = protected(out)
    out_low = out.lower()
    miss_nums = sorted(n for n in nums_in if n not in nums_out and n not in out_low)
    if miss_nums:
        problems.append(("missing", "numbers: " + ", ".join(miss_nums)))
    miss_names = sorted(n for n in names_in if n not in out_low)
    if miss_names and (len(miss_names) >= 2 or len(miss_names) / max(len(names_in), 1) >= 0.5):
        problems.append(("missing", "names: " + ", ".join(miss_names[:5])))
    quotes = dialogue(orig)
    if quotes:
        flat = re.sub(r"\s+", " ", _straight(out))
        lost = [q for q in quotes if f'"{q}"' not in flat]
        if lost:
            problems.append(("dialogue", f"{len(lost)} line(s) changed: " + "; ".join(x[:30] for x in lost[:2])))
    if tone not in ("casual", "fiction"):
        orig_low = orig.lower()
        slang = [s for s in SLANG if s in out_low and s not in orig_low]
        if slang:
            problems.append(("slang", ", ".join(slang[:4])))
    return problems


def _straight(text: str) -> str:
    return text.replace("\u201c", '"').replace("\u201d", '"')


def dialogue(text: str) -> list[str]:
    spans = re.findall(r'"([^"\n]{3,})"', _straight(text))
    return [re.sub(r"\s+", " ", x).strip() for x in spans]


def hard(problems: list[tuple[str, str]]) -> bool:
    """Problems serious enough that the original paragraph is safer than the rewrite."""
    return any(kind in ("language", "length") for kind, _ in problems)
