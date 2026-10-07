#!/bin/sh
# Starts talkTalk on http://127.0.0.1:8795 and opens it in Chrome.
# Uses Homebrew's python3.11 because that is where openai-whisper (brew) is installed.
cd "$(dirname "$0")"
# OpenAI grading: borrow OPENAI_API_KEY from the login shell when started from the desktop app (which has no shell env)
[ -n "$OPENAI_API_KEY" ] || export OPENAI_API_KEY="$("${SHELL:-/bin/zsh}" -ilc 'printf "\n@@%s\n" "$OPENAI_API_KEY"' 2>/dev/null </dev/null | sed -n 's/^@@//p' | tail -1)"
lsof -nP -iTCP:8795 -sTCP:LISTEN >/dev/null || (nohup /opt/homebrew/opt/python@3.11/bin/python3.11 server.py > server.log 2>&1 &)
while ! lsof -nP -iTCP:8795 -sTCP:LISTEN >/dev/null; do sleep 1; done
open -a "Google Chrome" http://127.0.0.1:8795/
