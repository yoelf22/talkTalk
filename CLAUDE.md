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

This repo is public. Interview content (questions, written answers, recordings, grades) lives outside the repo, in `~/Desktop/talk rehersals/` (override with `TALKTALK_DIR`). Never commit sample questions, a `questions.json`, or anything naming a real interview, and keep the grading prompt generic.

## Architecture

`server.py` (stdlib `http.server`, binds 127.0.0.1:8795) plus two pages with all UI and JS inline: `index.html` (dashboard: search + session list + new-session form) and `rehearse.html?s=<id>` (one session).

Data: `<data dir>/<id>/session.json` = `{id, topic, name, date, grader, questions: [{q, a}], source}` (`a` is the speaker's private notes, shown on the rehearse page and never sent to the grader; `source` is the imported questionnaire's filename); takes in `<data dir>/<id>/takes/`. On every start the server (re)writes `<data dir>/talkTalk.html`, a file:// page that redirects to the live dashboard or says how to start the server. The ID is the topic's first word (alphanumerics only) + `-` + (highest existing counter for that word + 1). The ID is also the folder name; a folder renamed by hand (e.g. `Jane Doe interview`) keeps working as long as `session.json`'s `id` matches. Every endpoint validates IDs against `SID` in `server.py` (letters, digits, spaces, `.'()-`, no slashes).

Questionnaire import: files in the data dir root (`GET /api/files`) are parsed by `parse()` (`GET /api/parse?f=`; macOS `textutil` for anything but .txt/.md): a line ending in `?` starts a question, following lines are its answer, bullets/numbering/`Q:`/`A:`/markdown emphasis stripped. On create, the chosen `source` file moves into `<id>/`.

Endpoints: `GET /api/sessions` (list, with take counts), `POST /api/sessions` (create), `GET /api/session?s=`, `POST /api/session?s=` (edit topic/name/date and the questions; the ID never changes. Takes are filed by question number, so inserting or removing a question shifts which question older takes belong to; grade files written since this change also store the question text), `POST /audio?s=&q=`, `GET /grade?s=&id=`.

Each take:

1. **Browser (while talking):** Chrome's Web Speech API shows a live transcript, and an `AnalyserNode` drives the level meter. Nothing is counted from it: Chrome drops fillers, and showing its counts next to Whisper's once put "0 fillers" beside a grade that quoted four "um"s.
2. **Server (all numbers):** the `MediaRecorder` webm blob is POSTed to `/audio` → saved as `takes/q{n}-{date}-{time}.webm` → Whisper `small.en` with `word_timestamps=True` and a filler-laden `initial_prompt` (so fillers are kept) → `metrics()` returns synchronously (~5 s) and the page renders the "This take" tiles and Whisper's transcript from it (`stats()` in `rehearse.html`). Grading then runs in a **background thread**: `grade()` pipes a prompt to `claude -p --model sonnet --tools ""` and writes `takes/q{n}-{date}-{time}.grade.json`. The page polls `GET /grade` every second until the file exists.

Details that matter when editing:
- Graders are `provider:model` ids (`claude:sonnet`, `openai:gpt-4.1-mini`). `options()` lists what is usable now: Claude Code's `CLAUDE_MODELS` if the CLI is found (`shutil.which` or `~/.local/bin/claude`; the desktop app starts the server with a bare PATH), plus the OpenAI key's chat models from `/v1/models` filtered by `NOT_CHAT`, listed once per process. The dashboard default is saved in `~/.config/talktalk/settings.json` (`POST /api/grader`); before one is picked, the first option is used. A session's `grader` is `""` (use the default) or a pinned id; a pinned id that is no longer available falls back to the default. The OpenAI key comes from the env (`run.sh` borrows `OPENAI_API_KEY` from the login shell) or `~/.config/talktalk/openai_key` (0600), written by `POST /api/openai-key` after checking it. Each grade records `graded_by`.
- `ask()` strips `ANTHROPIC_API_KEY` from the subprocess env so the CLI uses the user's subscription login, not API billing. Keep that.
- Claude's output is parsed by regex-grabbing the first `{...}` block; the JSON shape (`grade`, `fluency`, `coherence`, `recommendation`) is what `rehearse.html` renders.
- Question numbers are 1-based in URLs and filenames. The page drops stale responses if the user has moved to another question (`if(i+1!==qn)return`).
- The grader gets only the transcript and measurements, and judges only how it was said (coherence, fluency), never what it contains: not the question, not whether it is specific or vague. The user explicitly does not want the question, notes, session context or any outside facts fed to it: it once kept pushing a "fact" from the notes that the user never said. Don't add them back.
