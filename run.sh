#!/bin/sh
# Starts talkTalk on http://127.0.0.1:8795 and opens it in Chrome.
# Uses Homebrew's python3.11 because that is where openai-whisper (brew) is installed.
cd "$(dirname "$0")"
# Optional .env (gitignored): OPENAI_API_KEY=... and OPENAI_MODEL=... for OpenAI grading
[ -f .env ] && set -a && . ./.env && set +a
lsof -nP -iTCP:8795 -sTCP:LISTEN >/dev/null || (nohup /opt/homebrew/opt/python@3.11/bin/python3.11 server.py > server.log 2>&1 &)
while ! lsof -nP -iTCP:8795 -sTCP:LISTEN >/dev/null; do sleep 1; done
open -a "Google Chrome" http://127.0.0.1:8795/
