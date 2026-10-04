# talkTalk

Rehearse interview answers aloud and get each take graded.

- **Dashboard** (`/`): every session you've set up, searchable by topic, name or session ID. Pick one to rehearse again.
- **New session**: enter topic, name, date and your questions (with an optional written answer for each). The session ID is the
  first word of the topic plus a counter, e.g. `Product-1`, `Product-2`.
- **Rehearse**: one question at a time in large type; Space records, arrows move, A shows your written answer.
- Each take: Whisper (local, `small.en`, word timestamps, fillers kept) → measurements in ~5 s
  (length, pace, fillers per 100 words, long pauses, cut-off words) → Claude (`claude -p`, Sonnet)
  grades it against your written answer and gives one fix for the next take (~15 s total).
- Sessions, recordings, transcripts and grades are saved in `sessions/` on your machine (not committed).

## Run

    ./run.sh            # http://127.0.0.1:8795

Or build a Mac app from `launcher.applescript` (the osacompile line is in it).

Needs: Homebrew `openai-whisper` and `ffmpeg`, the Claude Code CLI at `~/.local/bin/claude`, Chrome.
