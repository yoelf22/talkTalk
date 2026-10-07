# Serves the rehearsal page on localhost (secure context for mic + speech), saves takes,
# keeps interview sessions (questions typed in by the user), and grades each take: Whisper (local, word timestamps) -> metrics -> grade + tip from Claude Code or OpenAI.
import http.server, json, os, re, shutil, subprocess, threading, time, urllib.request
from urllib.parse import parse_qsl, urlsplit
import whisper
MODEL = whisper.load_model("small.en")  # loaded once; first load ~3 s
D = os.path.dirname(os.path.abspath(__file__))
# Personal data lives outside the repo: <id>/session.json + <id>/takes/. Override with TALKTALK_DIR.
S = os.environ.get("TALKTALK_DIR") or os.path.expanduser("~/Desktop/talk rehersals")
SID = re.compile(r"[A-Za-z0-9][\w .'()-]*")  # session folder name: new ones are Word-N, but a folder may be renamed by hand
# Graders. Claude Code: found on PATH or at its default install path (the desktop app starts us with a bare PATH).
CLAUDE = shutil.which("claude") or next((p for p in [os.path.expanduser("~/.local/bin/claude")] if os.path.exists(p)), None)
CLAUDE_MODELS = ["sonnet", "opus", "haiku"]  # Claude Code model aliases
# OpenAI: the key comes from the environment (run.sh also borrows it from the login shell) or from a key the user
# pasted on the dashboard. Key and the chosen default grader live outside the repo and the data folder.
CONF = os.path.expanduser("~/.config/talktalk")
KEYFILE, SETTINGS = f"{CONF}/openai_key", f"{CONF}/settings.json"
if not os.environ.get("OPENAI_API_KEY") and os.path.exists(KEYFILE):
    os.environ["OPENAI_API_KEY"] = open(KEYFILE).read().strip()
# Chat models only: drop dated snapshots and audio/image/search/embedding/etc. models from the key's model list
NOT_CHAT = re.compile(r"audio|realtime|tts|transcribe|image|search|embedding|moderation|instruct|codex|computer|research|preview|-pro\b|-\d{4}(-\d\d-\d\d)?$")
openai_models = None  # the key's chat models, listed once per process (and again after a new key)

def openai(path, body=None, key=None):
    req = urllib.request.Request("https://api.openai.com/v1/" + path, data=body and json.dumps(body).encode(), headers={
        "Authorization": "Bearer " + (key or os.environ["OPENAI_API_KEY"]), "Content-Type": "application/json"})
    try:
        return json.load(urllib.request.urlopen(req, timeout=180))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"OpenAI {e.code}: {json.load(e).get('error', {}).get('message', '')}")

def options():
    """Every grader usable on this Mac right now, as {"id": "provider:model", "label"}."""
    global openai_models
    out = [{"id": f"claude:{m}", "label": f"Claude Code · {m.capitalize()}"} for m in CLAUDE_MODELS] if CLAUDE else []
    if os.environ.get("OPENAI_API_KEY"):
        if openai_models is None:
            try: openai_models = sorted(x["id"] for x in openai("models")["data"]
                                        if re.match(r"gpt-|o\d|chatgpt-", x["id"]) and not NOT_CHAT.search(x["id"]))
            except Exception: return out  # offline or key revoked: offer what works, list again next time
        out += [{"id": f"openai:{m}", "label": f"OpenAI · {m}"} for m in openai_models]
    return out

def settings():
    try: return json.load(open(SETTINGS))
    except Exception: return {}

def graders():
    opts = options(); ids = [o["id"] for o in opts]; chosen = settings().get("grader")
    return {"options": opts, "default": chosen if chosen in ids else (ids[0] if ids else None),
            "chosen": chosen in ids, "openai_key": bool(os.environ.get("OPENAI_API_KEY"))}

def set_default(gid):
    if gid not in [o["id"] for o in options()]: raise ValueError("that grader isn't available on this Mac")
    os.makedirs(CONF, exist_ok=True)
    json.dump({**settings(), "grader": gid}, open(SETTINGS, "w"))
    return graders()

def save_key(key):
    """Checks the key with OpenAI, then keeps it (owner-only file) and lists its models right away."""
    global openai_models
    key = str(key or "").strip()
    if not key.startswith("sk-"): raise ValueError("that doesn't look like an OpenAI API key (they start with sk-)")
    openai("models", key=key)
    os.makedirs(CONF, exist_ok=True)
    fd = os.open(KEYFILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    os.write(fd, key.encode()); os.close(fd)
    os.environ["OPENAI_API_KEY"], openai_models = key, None
    return graders()

FILL = {"um", "uh", "er", "ah", "erm", "hmm", "mm"}

def metrics(wjson):
    d = json.load(open(wjson))
    W = [w for s in d["segments"] for w in s.get("words", [])]
    if not W:
        return d["text"].strip(), {"words": 0}
    toks = [re.sub(r"[^a-z'-]", "", w["word"].lower()) for w in W]
    dur = W[-1]["end"] - W[0]["start"]
    words = [t for t in toks if t and t not in FILL]
    gaps = [W[k + 1]["start"] - W[k]["end"] for k in range(len(W) - 1)]
    mid = sum(1 for k, g in enumerate(gaps) if g >= 0.7 and not re.search(r"[.?!,]$", W[k]["word"].strip()))
    fill = sum(t in FILL for t in toks)
    return d["text"].strip(), {
        "seconds": round(dur), "words": len(words), "wpm": round(len(words) / (dur / 60)),
        "fillers": fill, "filler_words": {f: toks.count(f) for f in FILL if f in toks}, "fillers_per_100w": round(fill / max(1, len(words)) * 100, 1),
        "cutoffs": sum(1 for w in W if w["word"].strip().endswith("-")),
        "pauses_0_7s": sum(g >= 0.7 for g in gaps), "pauses_2s": sum(g >= 2 for g in gaps),
        "mid_sentence_pauses": mid}

def transcribe(audio, wjson):
    run = lambda cond: MODEL.transcribe(audio, language="en", word_timestamps=True, fp16=False, condition_on_previous_text=cond,
                                        initial_prompt="Um, uh, so, er, you know, I mean... I- I think, like, hmm.")
    r = run(True)  # conditioning carries the filler prompt past the first 30 s, but can loop ("of- of- of- ...")
    W = [w["word"].strip() for s in r["segments"] for w in s.get("words", [])]
    if sum(w.endswith("-") for w in W) > max(5, 0.15 * len(W)):
        # ponytail: cut-off share as loop detector (looped takes ~40%, real speech <5%); the retry undercounts fillers
        r = run(False)
    json.dump(r, open(wjson, "w"))
    return metrics(wjson)

def pick(choice):
    """A session's grader if it pinned one that is still available, otherwise the default."""
    g = graders()
    gid = choice if choice in [o["id"] for o in g["options"]] else g["default"]
    if not gid: raise RuntimeError("No grader available: add an OpenAI key on the dashboard, or install Claude Code")
    return gid, next(o["label"] for o in g["options"] if o["id"] == gid)

def ask(prompt, gid):
    who, name = gid.split(":", 1)
    if who == "claude":
        # Own process group, so a timeout kills the CLI and anything it started (a child holding the pipe hangs us otherwise)
        p = subprocess.Popen([CLAUDE, "-p", "--model", name, "--tools", ""], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=subprocess.DEVNULL, text=True, start_new_session=True,
                             env={k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"})
        try: return p.communicate(prompt, timeout=180)[0]
        except subprocess.TimeoutExpired:
            os.killpg(p.pid, 9); p.wait()
            raise RuntimeError("Claude Code didn't answer within 3 minutes; record the take again")
    return openai("chat/completions", {"model": name, "messages": [{"role": "user", "content": prompt}]})["choices"][0]["message"]["content"]

def grade(text, m, choice=""):
    prompt = f"""You are a speaking coach. Someone is rehearsing an interview answer out loud. Judge ONLY how they said
what they said. Do not judge what the answer contains: not whether it answers a question, not whether it is specific,
detailed, vague or complete, not whether its claims are right. Never ask for a moment, an example, a fact, a date or
more detail, and never add or suggest content of your own. Don't call anything vague, generic, specific or detailed.

Judge two things:
- Coherence: does what they said hold together as spoken? One thread, sentences that follow from each other, no
  detours, restarts or abandoned sentences, and a clear final line instead of trailing off.
- Fluency: even pace, pauses between sentences rather than mid-sentence, few fillers, few cut-off words.

Whisper transcript of what they said (fillers kept):
{text}

Measured: {json.dumps(m)}
Targets: 130-160 wpm; under 5 fillers per 100 words; 45-120 seconds; pauses only between sentences.

The recommendation names one fix to how they said it, using their own words: a sentence that broke off or restarted,
a detour to cut, a line to move, a stronger existing line to end on, or one delivery fix (pace, fillers, pauses).

Return ONLY JSON: {{"grade": "A|A-|B+|B|B-|C+|C|C-|D+|D", "fluency": "<=12 words", "coherence": "<=12 words",
"recommendation": "the single most useful fix for the next take, <=35 words, concrete, no preamble"}}"""
    gid, label = pick(choice)
    g = json.loads(re.search(r"\{.*\}", ask(prompt, gid), re.S).group(0))
    return {**g, "graded_by": label}

def load(sid):
    if not SID.fullmatch(sid or ""): raise ValueError("bad session id")
    return json.load(open(f"{S}/{sid}/session.json"))

def sessions():
    out = []
    for sid in os.listdir(S) if os.path.isdir(S) else []:
        try: x = load(sid)
        except Exception: continue
        tk = f"{S}/{sid}/takes"
        x["takes"] = sum(f.endswith(".webm") for f in os.listdir(tk)) if os.path.isdir(tk) else 0
        out.append(x)
    return sorted(out, key=lambda x: x["date"], reverse=True)

INBOX = f"{S}/.inbox"  # uploaded questionnaires wait here until their session is created

def upload(name, body):
    """Keeps an uploaded questionnaire and fills the session from it: the default model if there is one, else '?' lines."""
    f = os.path.basename(name or "")
    if not f or f.startswith(".") or not body: raise ValueError("choose a questionnaire file")
    os.makedirs(INBOX, exist_ok=True)
    open(f"{INBOX}/{f}", "wb").write(body)
    try:
        txt = read_text(f)
        try: return {"source": f, **extract(txt)}
        except Exception as e: return {"source": f, "topic": "", "name": "", "date": "", "questions": parse(txt), "filled_by": "",
                                       "note": f"The model couldn't fill it in ({str(e)[:120]})"}
    except Exception: os.remove(f"{INBOX}/{f}"); raise

def read_text(f):
    p = f"{INBOX}/{os.path.basename(f)}"
    return open(p, errors="replace").read() if f.lower().endswith((".txt", ".md", ".markdown")) else \
        subprocess.run(["textutil", "-convert", "txt", "-stdout", p], capture_output=True, text=True, check=True).stdout  # docx, doc, rtf, odt, html...

def clean(line):
    t = re.sub(r"\*\*|__|`", "", line)  # markdown emphasis
    return re.sub(r"^\s*(?:[-*•#>]+\s*)?(?:\(?\d+[.)]|Q\d*[:.)]|A[:.)])?\s*", "", t).strip()  # bullets, numbering, Q:/A:

def parse(txt):
    """A line ending in '?' starts a question; the lines after it, up to the next question, are the notes."""
    qs, cur = [], None
    for t in map(clean, txt.splitlines()):
        if t.endswith("?"): cur = {"q": t, "a": ""}; qs.append(cur)
        elif cur is not None and t: cur["a"] += t + "\n"
    if not qs: raise ValueError("no questions found: each question must be on its own line and end with '?'")
    return [{"q": x["q"], "a": x["a"].strip()} for x in qs]

def extract(txt):
    """The default model finds topic, name, date and the questions; notes are then cut from the file verbatim."""
    gid, label = pick("")
    prompt = f"""This is an interview questionnaire. Return ONLY JSON:
{{"topic": "a short title for the interview: the show, outlet or subject, as stated",
 "name": "the host, interviewer or show name, if stated, else empty",
 "date": "the interview or recording date as YYYY-MM-DD, if stated, else empty",
 "questions": ["every question the guest will be asked, in order, copied exactly as written"]}}
Copy text exactly; never invent, reword or summarize. Prepared answers or notes under a question are not questions.

{txt[:60000]}"""
    d = json.loads(re.search(r"\{.*\}", ask(prompt, gid), re.S).group(0))
    lines = [clean(l) for l in txt.splitlines()]
    found, start = [], 0  # (question, line index or None), matched in order
    for q in (clean(str(x)) for x in d.get("questions", [])):
        i = next((k for k in range(start, len(lines)) if q and lines[k] and (q in lines[k] or lines[k] in q and len(lines[k]) > 20)), None)
        found.append((q, i))
        if i is not None: start = i + 1
    if not found: raise ValueError("the model found no questions")
    idx = [i for _, i in found if i is not None] + [len(lines)]
    qs = [{"q": q, "a": "" if i is None else "\n".join(l for l in lines[i + 1:min(j for j in idx if j > i)] if l)} for q, i in found]
    date = str(d.get("date", "")) if re.fullmatch(r"\d{4}-\d\d-\d\d", str(d.get("date", ""))) else ""
    return {"topic": str(d.get("topic", "")).strip(), "name": str(d.get("name", "")).strip(), "date": date,
            "questions": qs, "filled_by": label}

def details(t):
    topic, name, date = (str(t.get(k, "")).strip() for k in ("topic", "name", "date"))
    if not (topic and name and date): raise ValueError("topic, name and date are required")
    grader = t.get("grader") or ""  # "" = the dashboard default; otherwise a pinned "provider:model"
    if grader and not re.fullmatch(r"(claude|openai):[\w.-]+", grader): raise ValueError("unknown grader")
    return {"topic": topic, "name": name, "date": date, "grader": grader}

def questions(t):
    qs = [{"q": str(x.get("q", "")).strip(), "a": str(x.get("a", "")).strip()} for x in t.get("questions", [])]
    qs = [x for x in qs if x["q"]]
    if not qs: raise ValueError("add at least one question")
    return qs

def update(sid, t):
    """Edits topic, name, date and the questions. The ID stays as it is."""
    sess = {**load(sid), **details(t), "questions": questions(t)}
    sess.pop("context", None)  # retired field: the grader judges only what was said
    json.dump(sess, open(f"{S}/{sid}/session.json", "w"), indent=1, ensure_ascii=False)
    return sess

def create(t):
    d = details(t)
    qs = questions(t)
    src = t.get("source") or None
    if src and not os.path.isfile(f"{INBOX}/{os.path.basename(src)}"): raise ValueError("upload the questionnaire again")
    word = re.sub(r"[^A-Za-z0-9]", "", d["topic"].split()[0]) or "Session"
    n = 1 + max([int(m[1]) for x in (os.listdir(S) if os.path.isdir(S) else []) if (m := re.fullmatch(re.escape(word) + r"-(\d+)", x))], default=0)
    sid = f"{word}-{n}"
    os.makedirs(f"{S}/{sid}/takes")
    sess = {"id": sid, **d, "questions": qs, "source": src}
    if src: os.rename(f"{INBOX}/{os.path.basename(src)}", f"{S}/{sid}/{os.path.basename(src)}")  # the questionnaire moves in with its session
    json.dump(sess, open(f"{S}/{sid}/session.json", "w"), indent=1, ensure_ascii=False)
    return sess

class H(http.server.SimpleHTTPRequestHandler):
    def __init__(s, *a, **k): super().__init__(*a, directory=D, **k)
    def reply(s, obj, code=200):
        b = json.dumps(obj).encode(); s.send_response(code)
        s.send_header("Content-Type", "application/json"); s.send_header("Content-Length", str(len(b))); s.end_headers(); s.wfile.write(b)
    def args(s): return dict(parse_qsl(urlsplit(s.path).query))
    def do_GET(s):
        path, a = urlsplit(s.path).path, s.args()
        try:
            if path == "/api/sessions": return s.reply(sessions())
            if path == "/api/session": return s.reply(load(a.get("s")))
            if path == "/api/graders": return s.reply(graders())
            if path == "/grade":
                load(a.get("s"))
                f = f"{S}/{a['s']}/takes/{os.path.basename(a.get('id', ''))}.grade.json"
                return s.reply(json.load(open(f)) if os.path.exists(f) else {"pending": True})
        except Exception as e:
            return s.reply({"error": str(e)[:300]}, 400)
        super().do_GET()
    def do_POST(s):
        body = s.rfile.read(int(s.headers.get("Content-Length", 0)))
        path, a = urlsplit(s.path).path, s.args()
        stamp = time.strftime("%Y%m%d-%H%M%S")
        try:
            if path == "/api/sessions": return s.reply(create(json.loads(body)))
            if path == "/api/upload": return s.reply(upload(a.get("name"), body))
            if path == "/api/session": return s.reply(update(a.get("s"), json.loads(body)))
            if path == "/api/openai-key": return s.reply(save_key(json.loads(body).get("key")))
            if path == "/api/grader": return s.reply(set_default(json.loads(body).get("id")))
            sess, q = load(a.get("s")), int(a.get("q", 0))
            if not 1 <= q <= len(sess["questions"]): raise ValueError("bad question number")
        except Exception as e:
            return s.reply({"error": str(e)[:300]}, 400)
        if path != "/audio": return s.send_error(404)
        T = f"{S}/{sess['id']}/takes"
        base = f"{T}/q{q}-{stamp}"
        open(base + ".webm", "wb").write(body)
        try:
            os.makedirs(f"{T}/w", exist_ok=True)
            text, m = transcribe(base + ".webm", f"{T}/w/q{q}-{stamp}.json")
        except Exception as e:
            return s.reply({"error": str(e)[:300]}, 500)
        if m.get("words", 0) < 5:  # nothing to coach on; the recording and transcript are still kept
            return s.reply({"id": f"q{q}-{stamp}", "metrics": m, "transcript": text, "skipped": True})
        def bg():
            try: r = grade(text, m, sess.get("grader", ""))
            except Exception as e: r = {"error": str(e)[:300]}
            json.dump({**r, "question": sess["questions"][q - 1]["q"], "metrics": m, "transcript": text}, open(base + ".grade.json", "w"), indent=1, ensure_ascii=False)
        threading.Thread(target=bg, daemon=True).start()
        s.reply({"id": f"q{q}-{stamp}", "metrics": m, "transcript": text})

os.makedirs(S, exist_ok=True)
if not any(SID.fullmatch(x) for x in os.listdir(S)) and os.path.isdir(f"{D}/example/Example-1"):
    shutil.copytree(f"{D}/example/Example-1", f"{S}/Example-1")  # first run: a graded sample session to look at
open(f"{S}/talkTalk.html", "w").write("""<!doctype html><meta charset="utf-8"><title>talkTalk</title>
<body style="font:20px/1.5 system-ui;max-width:640px;margin:60px auto;padding:0 16px">
<p id="m">Opening talkTalk…</p>
<script>/* Opened from disk: jump to the live dashboard, or explain how to start it */
fetch("http://127.0.0.1:8795/api/sessions",{mode:"no-cors"}).then(()=>location.href="http://127.0.0.1:8795/")
 .catch(()=>document.getElementById("m").textContent="talkTalk isn't running. Start it with talkTalk.app or ./run.sh in the talkTalk folder, then reopen this page.")</script>""")
http.server.ThreadingHTTPServer(("127.0.0.1", 8795), H).serve_forever()
