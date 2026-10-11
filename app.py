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

TONES = {
    "natural": "Plain, conversational, the way a thoughtful person writes an email to a colleague.",
    "casual": "Relaxed and friendly. Contractions, short punchy lines, a little personality.",
    "professional": "Clear and confident business writing. Direct, no jargon, no fluff.",
    "academic": "Measured and precise, but still readable. No inflated vocabulary.",
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


def stock_hits(text: str) -> list[str]:
    low = text.lower()
    return [p for p in STOCK_PHRASES if p in low]


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


def numbers(text: str) -> set[str]:
    return set(re.findall(r"\d[\d,.]*", text))


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
    return (
        "You are an editor who rewrites text so it reads like a real person wrote it.\n"
        f"Tone: {TONES.get(r.tone, TONES['natural'])}\n{depth}\n{voice}"
        "Rules:\n"
        "- Preserve the exact meaning, facts, names, numbers and any quoted text. Do not add new claims.\n"
        "- Vary sentence length a lot: mix very short sentences with longer ones.\n"
        "- Prefer simple, concrete words. Use contractions where natural.\n"
        "- Avoid stock phrases such as: " + ", ".join(STOCK_PHRASES[:18]) + ".\n"
        "- No tidy summary sentence at the end of paragraphs. No lists unless the input has one.\n"
        f"{dashes}"
        "- Output ONLY the rewritten text. No preface, no notes, no quotes around it."
    )


def cleanup(text: str, keep_dashes: bool) -> str:
    t = text.strip().strip('"').strip()
    if not keep_dashes:
        t = re.sub(r"\s*[—–]\s*", ", ", t)
    return re.sub(r"[ \t]+", " ", t)


async def chat_stream(client: httpx.AsyncClient, model: str, system: str, user: str, temp: float):
    payload = {
        "model": model,
        "stream": True,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "options": {"temperature": temp, "top_p": 0.92, "repeat_penalty": 1.1, "num_ctx": 8192},
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


@app.post("/api/rewrite")
async def rewrite(r: Req):
    async def gen():
        paras = [p for p in re.split(r"\n\s*\n", r.text.strip()) if p.strip()]
        temp = 0.5 + r.strength / 100 * 0.5
        system = system_prompt(r)
        final = []
        warnings = []
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(300, connect=5)) as client:
                for i, para in enumerate(paras):
                    if para.lstrip().startswith("#") or len(para.split()) < 5:
                        kept = re.sub(r"^\s*#+\s*", "", para).strip()
                        yield ev(type="para_done", para=i, text=kept)
                        final.append(kept)
                        continue
                    best = ""
                    for attempt in range(max(1, r.passes)):
                        user = para if attempt == 0 else (
                            f"{para}\n\n(Previous attempt still used these stock phrases or was too uniform: "
                            f"{', '.join(stock_hits(best)) or 'uniform sentence length'}. Rewrite again, avoiding them.)"
                        )
                        yield ev(type="start", para=i, attempt=attempt)
                        buf = ""
                        async for piece in chat_stream(client, r.model, system, user, temp):
                            buf += piece
                            yield ev(type="token", para=i, text=piece)
                        best = cleanup(buf, r.keep_dashes)
                        if not stock_hits(best):
                            break
                    if numbers(para) - numbers(best):
                        warnings.append(f"Paragraph {i + 1}: a number from the original may be missing.")
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
