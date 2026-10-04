# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Interview-rehearsal tool: one question at a time, record a spoken answer, get it measured and graded. No build, no tests, no dependencies beyond the ones below.

## Run

    ./run.sh                                      # starts server.py if :8795 is down, opens Chrome at http://127.0.0.1:8795
    osacompile -o ~/Desktop/talkTalk.app launcher.applescript   # rebuild the desktop launcher

- The server must run under Homebrew `/opt/homebrew/opt/python@3.11/bin/python3.11`; that is where `openai-whisper` is installed. Plain `python3` will fail on `import whisper`. Also needs `ffmpeg` and the Claude CLI at `~/.local/bin/claude`.
- Not a launchd agent. To restart after editing `server.py`: kill the process on :8795, then `./run.sh`. Logs go to `server.log` (gitignored).
- Python edits take effect only after a restart (Whisper model loads at import, ~3 s). The HTML pages are served statically, so a reload is enough.

## Public repo

This repo is public. Interview content (questions, written answers, recordings, grades) lives only in `sessions/`, which is gitignored. Never commit sample questions, a `questions.json`, or anything naming a real interview, and keep the grading prompt generic.

## Architecture

`server.py` (stdlib `http.server`, binds 127.0.0.1:8795) plus two pages with all UI and JS inline: `index.html` (dashboard: search + session list + new-session form) and `rehearse.html?s=<id>` (one session).

Data: `sessions/<id>/session.json` = `{id, topic, name, date, questions: [{q, a}]}`; takes in `sessions/<id>/takes/`. The ID is the topic's first word (alphanumerics only) + `-` + (highest existing counter for that word + 1). Every endpoint validates the ID against `[A-Za-z0-9]+-\d+`, and static GETs under `/sessions` return 404, so recordings are only reachable through the API.

Endpoints: `GET /api/sessions` (list, with take counts), `POST /api/sessions` (create), `GET /api/session?s=`, `POST /audio?s=&q=`, `GET /grade?s=&id=`, `POST /take?s=&q=`.

Each take has **two independent pipelines**:

1. **Browser-side (instant, rough):** Chrome Web Speech API gives a live transcript; an `AnalyserNode` RMS threshold detects pauses. On stop, `report()` computes wpm/fillers/repeats and POSTs JSON to `/take` → `takes/q{n}-{date}-{time}.json`. Chrome's transcript drops many "um"s, so these numbers are approximate.
2. **Server-side (authoritative):** the `MediaRecorder` webm blob is POSTed to `/audio` → saved as `takes/q{n}-{date}-{time}.webm` → Whisper `small.en` with `word_timestamps=True` and a filler-laden `initial_prompt` (so fillers are kept) → `metrics()` returns synchronously (~5 s). Grading then runs in a **background thread**: `grade()` pipes a prompt to `claude -p --model sonnet --tools ""` and writes `takes/q{n}-{date}-{time}.grade.json`. The page polls `GET /grade` every second until the file exists.

Details that matter when editing:
- `grade()` strips `ANTHROPIC_API_KEY` from the subprocess env so the CLI uses the user's subscription login, not API billing. Keep that.
- Claude's output is parsed by regex-grabbing the first `{...}` block; the JSON shape (`grade`, `fluency`, `content`, `recommendation`) is what `rehearse.html` renders.
- Question numbers are 1-based in URLs and filenames. The page drops stale responses if the user has moved to another question (`if(i+1!==qn)return`).
- Written answers are optional; the grading prompt says `(none)` when empty.
