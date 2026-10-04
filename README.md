# talkTalk

Rehearse interview answers out loud and get every take measured and graded.

## The problem: knowing it is not the same as saying it

Most people prepare for an interview, a podcast or a panel by writing. They draft their answers, tighten them, read
them over until they feel ready. Then they answer out loud and it comes out differently: longer than planned, slower
in some places and rushed in others, with "um" filling every gap where the next idea should be. Sentences start,
stall and start again. The point they meant to land somehow gets lost halfway through.

None of this shows on the page, and little of it is audible to the person speaking. The listener hears all of it.

Speaking well in public comes down to two things:

- **Coherence:** the answer goes somewhere. It responds to the question that was asked, makes its point, and ends
  on a clear final line instead of trailing off.
- **Fluency:** the answer comes out at an even pace, with pauses between thoughts rather than in the middle of
  them, few fillers, and few false starts.

Both are learned the same way: by saying the answer out loud, many times, and getting specific feedback after each
attempt. That is rehearsal. Rehearsing alone gives you no feedback, though, and a coach or a patient friend won't sit
through fifteen questions times ten takes.

## What talkTalk does

talkTalk is the feedback half of rehearsal. You give it the questions you expect and the answers you'd like to give.
It shows one question at a time in large type, records you answering it, and within about 15 seconds tells you how
it went: your pace, your fillers, where you hesitated, a letter grade with a note on fluency and one on coherence,
and the single most useful thing to fix on the next take.

The grade is about how you said what you said, nothing else. It never sees the question or your notes, and never
judges what the answer contains or tells you what you should have said. Its advice points at your own words: a
sentence that broke off, a detour to cut, a line to move, a stronger line of yours to end on, or your pace.

## How to prepare with it

1. **Prepare notes if they help, not scripts.** Each question can carry your own notes. They are for you only and
   are never sent to the grader. A memorized answer sounds memorized.
2. **Answer without looking.** Read the question, press Space, and talk. Peek at your notes (press A) only after
   the take.
3. **Fix one thing per take.** Each grade ends with one recommendation. Apply that, and only that, on the next take.
4. **Repeat until it holds.** Move on when the grade stays steady and the answer fits the targets talkTalk grades
   against: 45 seconds to 2 minutes, 130 to 160 words per minute, under 5 fillers per 100 words, pauses only between
   sentences, and a clear final line.
5. **Come back another day.** Every session is kept and searchable on the dashboard, so you can run an interview's
   questions again closer to the date. Every take (recording, transcript, grade) is saved in the session's folder.

Recordings and transcription stay on your machine (Whisper runs locally). Only the transcript and its measurements go to
Claude for grading, and Chrome's live transcript uses Google's speech recognition.

## How it works

1. **Create a session.** On the dashboard, click **+ New session** and fill in the topic, a name, the date, and your
   questions, with optional notes for yourself under each. To skip the typing, drop your questionnaire (.txt, .md, .docx, .rtf, .odt, .html…) into the data
   folder and pick it in the form: every line ending in `?` becomes a question, and the lines after it its notes. Check the rows before you create the session; the file then moves into the session's folder. Each
   session gets an ID made of the topic's first word and a counter, such as `Product-1`, `Product-2`.
2. **Rehearse.** Open the session and answer each question aloud. Chrome shows a live transcript while you talk.
3. **Read the feedback.** When you stop, Whisper transcribes the recording with word timings and fillers kept
   (about 5 seconds), and talkTalk measures:
   - length and words per minute (target 130 to 160)
   - fillers per 100 words (target under 5)
   - pauses over 0.7 s and over 2 s, and pauses in the middle of a sentence
   - cut-off words ("I- I think")

   Claude (Sonnet, through the Claude Code CLI) then grades the take from A to D, with a note on fluency, a note on
   coherence, and one concrete fix for the next take.
4. **Come back later.** The dashboard lists every session and can search them by topic, name or ID, so you
   can return to an earlier interview and rehearse it again. **Edit** on a session changes its topic, name, date,
   questions and notes; the session ID stays the same.

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

Keys on the rehearsal page: **Space** records or stops, **← →** change question, **A** shows your notes.

Optional: `launcher.applescript` builds a double-click Mac app. Edit the path inside it to where you cloned the
repo, then run the `osacompile` line at its top.

## Your data

Sessions, recordings, transcripts and grades are saved outside the repo, in a `talk rehersals` folder on your Desktop
(one subfolder per session). Set `TALKTALK_DIR` to use another folder. The server also puts `talkTalk.html` there:
double-click it to open the dashboard, or to see how to start talkTalk if it isn't running. The server listens on
127.0.0.1 only.

## License

[MIT](LICENSE)
