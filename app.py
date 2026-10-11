"""Penwash: a local text rewriter built on FastAPI + Ollama. Everything stays on this machine."""
import json
import re
import statistics
from pathlib import Path

import httpx
from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from cleaner import clean as clean_text
from guards import check, hard, is_structural, strip_preface

OLLAMA = "http://127.0.0.1:11434"
STATIC = Path(__file__).parent / "static"
DEFAULT_MODEL = "qwen2.5:14b"

app = FastAPI(title="Penwash")

STOCK_PHRASES = [
    "delve", "tapestry", "testament to", "in today's fast-paced", "it's important to note",
    "it is important to note", "furthermore", "moreover", "in conclusion", "in summary",
    "navigate the complexities", "landscape of", "realm of", "game-changer", "unlock the",
    "leverage", "seamless", "robust", "holistic", "multifaceted", "pivotal", "foster",
    "underscore", "embark", "elevate", "harness the power", "ever-evolving", "plays a crucial role",
    "in the world of", "stands as a", "a myriad of", "paramount", "meticulous",
]

FICTION_TELLS = [
    "shiver ran down", "shivers down", "heart pounded in", "heart hammered", "breath she didn't know",
    "breath he didn't know", "little did", "barely above a whisper", "the air was thick", "couldn't help but",
    "eyes sparkled", "a mix of", "a wave of", "a sense of", "washed over", "sent a chill", "orbs",
    "mind raced", "time seemed to", "the weight of", "palpable", "unspoken", "a testament to",
    "chill running", "chill ran", "hint of", "no idea how", "human heart", "human spirit", "resilience of",
    "barely a breath", "barely a whisper", "mingling", "tugged at", "scars spoke", "in the end",
    "something new", "change everything", "start of something", "silence stretched", "hung in the air",
]

TONES = {
    "fiction": "Natural storytelling prose. Concrete detail, subtext instead of stated emotion, varied rhythm.",
    "natural": "Plain, clear, natural prose. Contractions are fine. No slang and no chatty filler.",
    "casual": "Relaxed and friendly. Contractions, short punchy lines, a little personality.",
    "professional": "Clear and confident business writing. Direct, no jargon, no fluff.",
    "academic": "Measured and precise, but still readable. Formal register, no slang, no inflated vocabulary.",
}


class Req(BaseModel):
    text: str
    model: str = DEFAULT_MODEL
    tone: str = "natural"
    strength: int = 60  # 0..100
    passes: int = 2
    voice_sample: str = ""
    keep_dashes: bool = False


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p for p in parts if p]


def stock_hits(text: str, fiction: bool = False) -> list[str]:
    low = text.lower()
    return [p for p in STOCK_PHRASES + (FICTION_TELLS if fiction else []) if p in low]


def metrics(text: str) -> dict:
    sents = split_sentences(text)
    lens = [len(s.split()) for s in sents] or [0]
    mean = statistics.mean(lens)
    sd = statistics.pstdev(lens) if len(lens) > 1 else 0
    return {
        "words": sum(lens),
        "sentences": len(sents),
        "avg_sentence": round(mean, 1),
        "burstiness": round(sd / mean, 2) if mean else 0,  # higher = more varied rhythm
        "stock_phrases": len(stock_hits(text)),
    }


def system_prompt(r: Req) -> str:
    s = r.strength
    if s < 35:
        depth = "Make light edits: fix stiff phrasing and swap out stock AI wording, keep structure mostly as is."
    elif s < 70:
        depth = "Rewrite substantially: reorder clauses, merge and split sentences, change how points are introduced."
    else:
        depth = "Rewrite heavily in your own words while keeping every fact. Restructure freely."
    voice = ""
    if r.voice_sample.strip():
        voice = f"\nMatch the voice, rhythm and word choice of this writing sample:\n\"\"\"\n{r.voice_sample.strip()[:2500]}\n\"\"\"\n"
    dashes = "" if r.keep_dashes else "- Do not use em dashes. Use commas, periods or parentheses.\n"
    fiction_rules = ""
    if r.tone == "fiction":
        fiction_rules = (
            "Fiction rules:\n"
            "- Keep every line of dialogue exactly as written, inside its quotation marks.\n"
            "- Keep the point of view, the tense and the narrator's voice. Add no events, names or backstory.\n"
            "- Show, don't explain: cut sentences that tell the reader what a gesture or feeling means.\n"
            "- Replace stock reactions with something specific to this scene. Avoid: "
            + ", ".join(FICTION_TELLS[:14]) + ".\n"
            "- Do not end on a tidy moral or summary line. Vary paragraph and sentence length.\n"
        )
    return (
        "You are an editor who rewrites text so it reads like a real person wrote it.\n"
        f"Tone: {TONES.get(r.tone, TONES['natural'])}\n{depth}\n{voice}"
        f"{fiction_rules}"
        "Rules:\n"
        "- Write in the same language as the input. Never switch languages or add other scripts.\n"
        "- Preserve the exact meaning. Keep every fact, name, law, section number, year and figure.\n"
        "- Never add ideas, examples, definitions or explanations that are not in the input. "
        "Keep roughly the same length.\n"
        "- Keep the input's wording level: if it says 'children', do not change it to 'kids'.\n"
        "- Vary sentence length: mix short sentences with longer ones. Prefer simple, concrete words.\n"
        "- Avoid stock phrases such as: " + ", ".join(STOCK_PHRASES[:18]) + ".\n"
        "- No tidy summary sentence at the end. No lists unless the input has one.\n"
        f"{dashes}"
        "- The user message may begin with a 'Section' line. It is context only: never rewrite or repeat it.\n"
        "- Output ONLY the rewritten text. No preface such as 'Sure' or 'Here is', no notes, no quotes."
    )


def cleanup(text: str, keep_dashes: bool, orig: str = "") -> str:
    t = text.strip()
    wrapped = len(t) > 1 and t[0] == t[-1] == '"' and t.count('"') == 2
    if wrapped and not orig.lstrip().startswith(('"', "\u201c")):
        t = t[1:-1].strip()  # the model wrapped its answer in quotes; real dialogue is left alone
    if not keep_dashes:
        t = re.sub(r"\s*[—–]\s*", ", ", t)
    return re.sub(r"[ \t]+", " ", t)


async def chat_stream(client: httpx.AsyncClient, model: str, system: str, user: str, temp: float, limit: int):
    payload = {
        "model": model,
        "stream": True,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        # repeat_penalty stays at 1.0: higher values push multilingual models into other languages.
        "options": {"temperature": temp, "top_p": 0.9, "repeat_penalty": 1.0, "num_ctx": 8192, "num_predict": limit},
    }
    async with client.stream("POST", f"{OLLAMA}/api/chat", json=payload) as resp:
        async for line in resp.aiter_lines():
            if not line:
                continue
            chunk = json.loads(line)
            piece = chunk.get("message", {}).get("content", "")
            if piece:
                yield piece


def ev(**kw) -> bytes:
    return (json.dumps(kw) + "\n").encode()


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/models")
async def models():
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            data = (await c.get(f"{OLLAMA}/api/tags")).json()
        return {"ok": True, "models": [m["name"] for m in data.get("models", [])]}
    except (httpx.HTTPError, ValueError):
        return {"ok": False, "models": []}


@app.post("/api/analyze")
def analyze(body: dict):
    t = body.get("text", "")
    return {"metrics": metrics(t), "stock": stock_hits(t)}


@app.post("/api/clean")
def clean_only(body: dict):
    src = body.get("text", "")
    out, changes = clean_text(src)
    return {"text": out, "changes": changes, "before": metrics(src), "after": metrics(out)}


def build_user(para: str, section: str, prev: str, problems: list[tuple[str, str]] | None) -> str:
    ctx = []
    if section:
        ctx.append(f"Section (context only): {section}")
    if prev:
        ctx.append(f"Previous paragraph, already rewritten (context only, do not repeat): {prev[-500:]}")
    msg = "\n".join(ctx) + f"\n\nText to rewrite:\n{para}" if ctx else para
    if problems:
        why = "; ".join(f"{k}: {d}" for k, d in problems)
        msg += f"\n\n(Your last attempt was rejected: {why}. Rewrite the text again, in English only, fixing this.)"
    return msg


@app.post("/api/rewrite")
async def rewrite(r: Req):
    async def gen():
        paras = [p for p in re.split(r"\n\s*\n", r.text.strip()) if p.strip()]
        fiction = r.tone == "fiction"
        base_temp = 0.3 + r.strength / 100 * 0.4 + (0.1 if fiction else 0)
        system = system_prompt(r)
        final, warnings, section = [], [], ""
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(300, connect=5)) as client:
                for i, para in enumerate(paras):
                    if is_structural(para):
                        kept = para.strip()
                        if kept.startswith(("#", "**", "__")):
                            section = re.sub(r"[#*_]", "", kept).strip()
                        yield ev(type="para_done", para=i, text=kept)
                        final.append(kept)
                        continue
                    prev = final[-1] if final and not is_structural(final[-1]) else ""
                    best, best_problems, best_score = "", [], None
                    for attempt in range(max(0, r.passes) + 1):
                        temp = max(0.15, base_temp - 0.12 * attempt)
                        user = build_user(para, section, prev, best_problems if attempt else None)
                        yield ev(type="start", para=i, attempt=attempt)
                        buf = ""
                        async for piece in chat_stream(client, r.model, system, user, temp, len(para.split()) * 3 + 120):
                            buf += piece
                            yield ev(type="token", para=i, text=piece)
                        cand = cleanup(strip_preface(buf, para), r.keep_dashes, para)
                        problems = check(para, cand, r.tone)
                        hits = stock_hits(cand, fiction)
                        if hits:
                            problems.append(("stock phrases", ", ".join(hits[:4])))
                        score = (1000 if hard(problems) else 0) + 10 * len(problems) + len(hits)
                        if best_score is None or score < best_score:
                            best, best_problems, best_score = cand, problems, score
                        if not problems:
                            break
                    if hard(best_problems):
                        detail = "; ".join(d for _, d in best_problems)
                        warnings.append(f"Paragraph {i + 1}: the rewrite was unreliable ({detail}), so the original was kept.")
                        best = para.strip()
                    elif best_problems:
                        warnings.append(f"Paragraph {i + 1}: check this one ({'; '.join(f'{k}: {d}' for k, d in best_problems)}).")
                    yield ev(type="para_done", para=i, text=best)
                    final.append(best)
        except httpx.ConnectError:
            yield ev(type="error", message="Can't reach Ollama. Run `ollama serve` and try again.")
            return
        except Exception as e:  # noqa: BLE001
            yield ev(type="error", message=str(e))
            return
        out = "\n\n".join(final)
        yield ev(type="done", text=out, before=metrics(r.text), after=metrics(out), warnings=warnings)

    return StreamingResponse(gen(), media_type="application/x-ndjson")
