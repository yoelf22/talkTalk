# Serves the rehearsal page on localhost (secure context for mic + speech), saves takes,
# keeps interview sessions (questions typed in by the user), and grades each take: Whisper (local, word timestamps) -> metrics -> Claude grade + tip.
import http.server, json, os, re, subprocess, threading, time
from urllib.parse import parse_qsl, urlsplit
import whisper
MODEL = whisper.load_model("small.en")  # loaded once; first load ~3 s
D = os.path.dirname(os.path.abspath(__file__))
# Personal data lives outside the repo: <id>/session.json + <id>/takes/. Override with TALKTALK_DIR.
S = os.environ.get("TALKTALK_DIR") or os.path.expanduser("~/Desktop/talk rehersals")
SID = re.compile(r"[A-Za-z0-9][\w .'()-]*")  # session folder name: new ones are Word-N, but a folder may be renamed by hand
CLAUDE = os.path.expanduser("~/.local/bin/claude")
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
        "fillers": fill, "fillers_per_100w": round(fill / max(1, len(words)) * 100, 1),
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

def grade(text, m, q, sess):
    prompt = f"""You are a speaking coach. Someone is rehearsing an interview answer out loud. Judge ONLY what they
actually said and how they said it. You know nothing about their subject beyond this transcript, so never add,
correct or suggest facts, examples, dates or claims they did not say themselves.

Judge two things:
- Coherence: does what they said hold together? One clear thread, ideas in a sensible order, no detours or
  restarts, and a clear final line instead of trailing off.
- Fluency: even pace, pauses between sentences rather than mid-sentence, few fillers, few cut-off words.

The question (only to tell whether they stayed on it): {sess["questions"][q - 1]["q"]}

Whisper transcript of what they said (fillers kept):
{text}

Measured: {json.dumps(m)}
Targets: 130-160 wpm; under 5 fillers per 100 words; 45-120 seconds; pauses only between sentences.

The recommendation must work with their own words: quote or point to a specific part of what they said (where the
thread broke, which sentence to cut or move, which line could close the answer) or name one delivery fix.

Return ONLY JSON: {{"grade": "A|A-|B+|B|B-|C+|C|C-|D", "fluency": "<=12 words", "coherence": "<=12 words",
"recommendation": "the single most useful fix for the next take, <=35 words, concrete, no preamble"}}"""
    out = subprocess.run([CLAUDE, "-p", "--model", "sonnet", "--tools", ""], input=prompt, capture_output=True,
                         text=True, env={k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}, timeout=180).stdout
    g = json.loads(re.search(r"\{.*\}", out, re.S).group(0))
    return g

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

def files():
    """Questionnaire files dropped in the data folder root, waiting to be imported."""
    return sorted(f for f in os.listdir(S) if os.path.isfile(f"{S}/{f}") and not f.startswith(".") and f != "talkTalk.html")

def parse(f):
    """A line ending in '?' starts a question; the lines after it, up to the next question, are the written answer."""
    if f not in files(): raise ValueError("no such file in the folder")
    p = f"{S}/{f}"
    txt = open(p, errors="replace").read() if f.lower().endswith((".txt", ".md", ".markdown")) else \
        subprocess.run(["textutil", "-convert", "txt", "-stdout", p], capture_output=True, text=True, check=True).stdout  # docx, doc, rtf, odt, html...
    qs, cur = [], None
    for line in txt.splitlines():
        t = re.sub(r"\*\*|__|`", "", line)  # markdown emphasis
        t = re.sub(r"^\s*(?:[-*•#>]+\s*)?(?:\(?\d+[.)]|Q\d*[:.)]|A[:.)])?\s*", "", t).strip()  # bullets, numbering, Q:/A:
        if t.endswith("?"): cur = {"q": t, "a": ""}; qs.append(cur)
        elif cur is not None and t: cur["a"] += t + "\n"
    if not qs: raise ValueError("no questions found: each question must be on its own line and end with '?'")
    return [{"q": x["q"], "a": x["a"].strip()} for x in qs]

def details(t):
    topic, name, date = (str(t.get(k, "")).strip() for k in ("topic", "name", "date"))
    if not (topic and name and date): raise ValueError("topic, name and date are required")
    return {"topic": topic, "name": name, "date": date}

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
    if src and src not in files(): raise ValueError("questionnaire file is no longer in the folder")
    word = re.sub(r"[^A-Za-z0-9]", "", d["topic"].split()[0]) or "Session"
    n = 1 + max([int(m[1]) for x in (os.listdir(S) if os.path.isdir(S) else []) if (m := re.fullmatch(re.escape(word) + r"-(\d+)", x))], default=0)
    sid = f"{word}-{n}"
    os.makedirs(f"{S}/{sid}/takes")
    sess = {"id": sid, **d, "questions": qs, "source": src}
    if src: os.rename(f"{S}/{src}", f"{S}/{sid}/{src}")  # the questionnaire moves in with its session
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
            if path == "/api/files": return s.reply({"dir": S, "files": files()})
            if path == "/api/parse": return s.reply(parse(a.get("f", "")))
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
            if path == "/api/session": return s.reply(update(a.get("s"), json.loads(body)))
            sess, q = load(a.get("s")), int(a.get("q", 0))
            if not 1 <= q <= len(sess["questions"]): raise ValueError("bad question number")
        except Exception as e:
            return s.reply({"error": str(e)[:300]}, 400)
        T = f"{S}/{sess['id']}/takes"
        if path == "/audio":
            base = f"{T}/q{q}-{stamp}"
            open(base + ".webm", "wb").write(body)
            try:
                os.makedirs(f"{T}/w", exist_ok=True)
                text, m = transcribe(base + ".webm", f"{T}/w/q{q}-{stamp}.json")
            except Exception as e:
                return s.reply({"error": str(e)[:300]}, 500)
            def bg():
                try: r = grade(text, m, q, sess)
                except Exception as e: r = {"error": str(e)[:300]}
                json.dump({**r, "question": sess["questions"][q - 1]["q"], "metrics": m, "transcript": text}, open(base + ".grade.json", "w"), indent=1, ensure_ascii=False)
            threading.Thread(target=bg, daemon=True).start()
            s.reply({"id": f"q{q}-{stamp}", "metrics": m, "transcript": text})
        else:
            open(f"{T}/q{q}-{stamp}.json", "w").write(json.dumps(json.loads(body), indent=1, ensure_ascii=False))
            s.send_response(204); s.end_headers()

os.makedirs(S, exist_ok=True)
open(f"{S}/talkTalk.html", "w").write("""<!doctype html><meta charset="utf-8"><title>talkTalk</title>
<body style="font:20px/1.5 system-ui;max-width:640px;margin:60px auto;padding:0 16px">
<p id="m">Opening talkTalk…</p>
<script>/* Opened from disk: jump to the live dashboard, or explain how to start it */
fetch("http://127.0.0.1:8795/api/sessions",{mode:"no-cors"}).then(()=>location.href="http://127.0.0.1:8795/")
 .catch(()=>document.getElementById("m").textContent="talkTalk isn't running. Start it with talkTalk.app or ./run.sh in the talkTalk folder, then reopen this page.")</script>""")
http.server.ThreadingHTTPServer(("127.0.0.1", 8795), H).serve_forever()
