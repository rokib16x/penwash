#!/bin/zsh
# Starts Ollama if needed, then Penwash at http://127.0.0.1:8765
cd "$(dirname "$0")"
curl -s http://127.0.0.1:11434/api/tags >/dev/null || (ollama serve >/dev/null 2>&1 &) && sleep 1
exec uv run --with fastapi --with uvicorn --with httpx uvicorn app:app --host 127.0.0.1 --port 8765
