# talkTalk

Rehearse interview answers out loud and get every take measured and graded.

You type in the questions you expect, plus the answer you'd like to give. talkTalk shows one question at a time in
large type, records you answering it, and within about 15 seconds tells you how it went: your pace, your filler
words, where you hesitated, a letter grade, and the single most useful thing to fix on the next take.

Everything runs on your own machine. Recordings are transcribed locally with Whisper; only the transcript and your
written answer go to Claude for grading.

## How it works

1. **Create a session.** On the dashboard, click **+ New session** and fill in the topic, a name, the date, and your
   questions. A written answer for each question is optional; when present, the grade checks your spoken answer
   against it. Each session gets an ID made of the topic's first word and a counter, such as `Product-1`, `Product-2`.
2. **Rehearse.** Open the session and answer each question aloud. Chrome shows a live transcript while you talk.
3. **Read the feedback.** When you stop, Whisper transcribes the recording with word timings and fillers kept
   (about 5 seconds), and talkTalk measures:
   - length and words per minute (target 130 to 160)
   - fillers per 100 words (target under 5)
   - pauses over 0.7 s and over 2 s, and pauses in the middle of a sentence
   - cut-off words ("I- I think")

   Claude (Sonnet, through the Claude Code CLI) then grades the take from A to D, with a note on fluency, a note on
   content, and one concrete fix for the next take.
4. **Come back later.** The dashboard lists every session and can search them by topic, name or ID, so you can
   return to an earlier interview and rehearse it again.

## Requirements

- macOS with [Homebrew](https://brew.sh)
- `brew install openai-whisper ffmpeg`
- [Claude Code](https://claude.com/claude-code) installed at `~/.local/bin/claude` and logged in. Grading uses your
  Claude login, not an API key.
- Google Chrome (the live transcript uses its built-in speech recognition)

`run.sh` starts the server with Homebrew's Python 3.11, because that is where the `openai-whisper` formula installs.
If your Whisper lives elsewhere, edit the interpreter path in `run.sh`.

## Run

    git clone https://github.com/yoelf22/talkTalk.git
    cd talkTalk
    ./run.sh

This starts the server on http://127.0.0.1:8795 (if it isn't already running) and opens it in Chrome. Allow the
microphone when Chrome asks. The first start takes a few seconds while the Whisper model loads.

Keys on the rehearsal page: **Space** records or stops, **← →** change question, **A** shows your written answer.

Optional: `launcher.applescript` builds a double-click Mac app. Edit the path inside it to where you cloned the
repo, then run the `osacompile` line at its top.

## Your data

Sessions, recordings, transcripts and grades are saved outside the repo, in a `talk rehersals` folder on your Desktop
(one subfolder per session). Set `TALKTALK_DIR` to use another folder. The server also puts `talkTalk.html` there:
double-click it to open the dashboard, or to see how to start talkTalk if it isn't running. The server listens on
127.0.0.1 only.

## License

[MIT](LICENSE)
