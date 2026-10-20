import os, json, re, math, base64, wave, random, subprocess, time
import numpy as np
import requests
from PIL import Image, ImageDraw, ImageFont

W, H, FPS = 1080, 1920, 30
KEY = os.getenv("GEMINI_API_KEY", "")
TG_TOKEN = os.getenv("TG_TOKEN", "")
TG_CHAT = os.getenv("TG_CHAT_ID", "")
MOCK = os.getenv("MOCK") == "1"
TEXT_MODEL = os.getenv("TEXT_MODEL", "gemini-3.8-flash")
TTS_MODEL = os.getenv("TTS_MODEL", "gemini-3.8-flash-tts")
VOICES = {"M": os.getenv("VOICE_M", "Fenrir"), "F": os.getenv("VOICE_F", "Kore")}
EDGE = {"M": "hi-IN-MadhurNeural", "F": "hi-IN-SwaraNeural"}
SR = 24000
SCENES = ["fall", "climb", "stress", "happy", "think", "run"]

TOPICS = [
    ("Motivation: har din thoda better banne ki taqat", "M"),
    ("Motivation: fail hone ke baad dobara uthna", "M"),
    ("Health: corporate job mein 9 ghante baithne ka nuksan aur chhoti walking habit", "M"),
    ("Health: office stress aur neend ki kami se kaise bachein (general habits)", "M"),
    ("Health: paani peene ki aadat jo energy badhati hai", "M"),
    ("Housewife: ghar ke kaam ke beech apne liye 15 minute nikalna", "F"),
    ("Housewife: din bhar ki thakaan kam karne ki simple aadatein", "F"),
    ("Housewife: apni value pehchano, tum sirf ghar nahi chalati", "F"),
]

COL_BG = (0, 0, 0)
COL_W = (255, 255, 255)
COL_RED = (255, 77, 77)
COL_PINK = (255, 160, 150)
COL_YEL = (255, 214, 10)


# ---------- Gemini ----------
def gpost(model, body, tries=4):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    for i in range(tries):
        try:
            r = requests.post(url, headers={"x-goog-api-key": KEY}, json=body, timeout=180)
            if r.ok:
                return r.json()
            print("Gemini error", r.status_code, r.text[:200])
        except Exception as e:
            print("Gemini exception", e)
        time.sleep(3 * (i + 1))
    return None


def make_script(topic, lead):
    if MOCK:
        return {
            "title": "2009: AADHI",
            "caption": "Test short #motivation",
            "lines": [
                {"spk": "M", "scene": "fall", "text": "Jab sab kuch girne lagta hai, to ghabra mat jaana."},
                {"spk": "M", "scene": "stress", "text": "Kyunki har gira hua graph ek din upar jaata hai."},
                {"spk": "F", "scene": "climb", "text": "Bas ek ek seedhi chadhte raho, roz thoda sa."},
                {"spk": "F", "scene": "happy", "text": "Aaj ka chhota kadam kal ki badi jeet banega."},
            ],
        }
    other = "F" if lead == "M" else "M"
    prompt = f"""Tu ek viral Hindi-English (Hinglish, Roman script) YouTube Shorts script writer hai.
Topic: {topic}
Rules:
- 9 se 11 lines, total bolne ka time 40-50 second.
- Har line max 14 shabd, simple bolchaal wali Hinglish, Roman script me.
- Pehli line ek zabardast hook (sawal ya shock) ho.
- Lead speaker "{lead}" ho. Twist, solution aur closing line "{other}" bole.
- Health topic me sirf general habits batao, koi dawa/ilaaj/bimari ka claim nahi.
- Har line ke liye scene chuno in me se: {", ".join(SCENES)}.
- title: max 4 shabd, CAPS, hook jaisa.
- caption: ek line + 3 hashtags.
Sirf JSON do: {{"title":"","caption":"","lines":[{{"spk":"M","scene":"fall","text":""}}]}}"""
    body = {"contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0.9}}
    j = gpost(TEXT_MODEL, body)
    txt = j["candidates"][0]["content"]["parts"][0]["text"]
    txt = re.sub(r"^```(?:json)?|```$", "", txt.strip(), flags=re.M).strip()
    data = json.loads(txt)
    for l in data["lines"]:
        if l.get("spk") not in ("M", "F"):
            l["spk"] = lead
        if l.get("scene") not in SCENES:
            l["scene"] = random.choice(SCENES)
    return data


# ---------- Voice ----------
def tts_gemini(text, spk, path):
    body = {"contents": [{"parts": [{"text": text}]}],
            "generationConfig": {"responseModalities": ["AUDIO"],
                                 "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": VOICES[spk]}}}}}
    j = gpost(TTS_MODEL, body)
    if not j:
        return False
    try:
        d = j["candidates"][0]["content"]["parts"][0]["inlineData"]["data"]
    except Exception:
        return False
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(base64.b64decode(d))
    return True


def tts_edge(text, spk, path):
    mp3 = path + ".mp3"
    r = subprocess.run(["edge-tts", "--voice", EDGE[spk], "--text", text, "--write-media", mp3])
    if r.returncode != 0:
        return False
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", mp3, "-ar", str(SR), "-ac", "1", path], check=True)
    return True


def tts_mock(text, path):
    n = int(max(1.5, len(text.split()) * 0.4) * SR)
    t = np.arange(n) / SR
    a = (np.sin(2 * np.pi * 180 * t) * 3000 * (np.sin(np.pi * t * 3) > 0)).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(a.tobytes())


def read_wav(path):
    with wave.open(path, "rb") as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)


def build_audio(lines):
    chunks, cursor = [], 0.4
    chunks.append(np.zeros(int(0.4 * SR), dtype=np.int16))
    for i, l in enumerate(lines):
        p = f"line{i}.wav"
        if MOCK:
            tts_mock(l["text"], p)
        elif not (tts_gemini(l["text"], l["spk"], p) or tts_edge(l["text"], l["spk"], p)):
            raise RuntimeError("Voice generation failed")
        a = read_wav(p)
        dur = len(a) / SR
        l["start"], l["end"] = cursor, cursor + dur
        chunks.append(a)
        gap = np.zeros(int(0.3 * SR), dtype=np.int16)
        chunks.append(gap)
        cursor += dur + 0.3
    audio = np.concatenate(chunks)
    with wave.open("voice.wav", "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(audio.tobytes())
    return cursor + 0.5


def word_timeline(lines):
    words = []
    for l in lines:
        ws = l["text"].split()
        weights = [len(x) + 1 for x in ws]
        tot = sum(weights)
        t = l["start"]
        for x, wt in zip(ws, weights):
            d = (l["end"] - l["start"]) * wt / tot
            words.append({"w": x, "s": t, "e": t + d, "spk": l["spk"]})
            t += d
    # chunks of 3 words
    chunks = [words[i:i + 3] for i in range(0, len(words), 3)]
    return chunks


# ---------- Drawing ----------
def get_font(size):
    for p in ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"]:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def limb(d, p, ang, length, w, col):
    a = math.radians(ang)
    e = (p[0] + length * math.sin(a), p[1] + length * math.cos(a))
    d.line([p, e], fill=col, width=w)
    d.ellipse([e[0] - w / 2, e[1] - w / 2, e[0] + w / 2, e[1] + w / 2], fill=col)
    return e


def figure(d, cx, base, col, scene, t, p):
    s = 1.0
    bob = math.sin(t * 5) * 6
    jump = 0
    la, ra, ll, rl = 25, -25, 10, -10
    if scene in ("stress", "fall"):
        sh = math.sin(t * 40) * 10
        la, ra, ll, rl = 140 + sh, -140 - sh, 14, -14
    elif scene == "happy":
        jump = abs(math.sin(t * 6)) * 50
        la, ra, ll, rl = 165 + math.sin(t * 10) * 10, -165 - math.sin(t * 10) * 10, 12, -12
    elif scene == "think":
        la, ra, ll, rl = 25, -150, 8, -8
    elif scene in ("run", "climb"):
        sw = math.sin(t * 12) * 40
        la, ra, ll, rl = -sw, sw, sw, -sw
    base = base - jump
    hip = (cx, base - 110 + bob / 2)
    neck = (cx, base - 190 + bob / 2)
    head = (cx, base - 235 + bob / 2)
    d.line([neck, hip], fill=col, width=10)
    limb(d, hip, ll, 110, 10, col)
    limb(d, hip, rl, 110, 10, col)
    sp = (cx, neck[1] + 12)
    limb(d, sp, la, 85, 10, col)
    limb(d, sp, ra, 85, 10, col)
    r = 42
    d.ellipse([head[0] - r, head[1] - r, head[0] + r, head[1] + r], outline=col, width=9)
    if scene in ("stress", "fall"):
        d.ellipse([head[0] - 7, head[1] + 4, head[0] + 7, head[1] + 20], outline=col, width=5)
        for ang in (-50, 0, 50):
            a = math.radians(ang)
            x1, y1 = head[0] + 62 * math.sin(a), head[1] - 62 * math.cos(a)
            x2, y2 = head[0] + 92 * math.sin(a), head[1] - 92 * math.cos(a)
            d.line([(x1, y1), (x2, y2)], fill=COL_RED, width=7)
    elif scene == "happy":
        d.arc([head[0] - 20, head[1] - 5, head[0] + 20, head[1] + 22], 10, 170, fill=col, width=5)
    else:
        d.line([(head[0] - 14, head[1] + 14), (head[0] + 14, head[1] + 14)], fill=col, width=5)
    d.ellipse([head[0] - 18, head[1] - 12, head[0] - 10, head[1] - 4], fill=col)
    d.ellipse([head[0] + 10, head[1] - 12, head[0] + 18, head[1] - 4], fill=col)


def draw_scene(d, scene, t, p, col):
    floor = 1350
    if scene == "climb":
        steps = 6
        x0, y0, sw_, sh_ = 150, floor, 140, 100
        pts = [(x0, y0)]
        for i in range(steps):
            pts += [(x0 + i * sw_, y0 - (i + 1) * sh_), (x0 + (i + 1) * sw_, y0 - (i + 1) * sh_)]
        d.line(pts, fill=COL_W, width=10, joint="curve")
        k = min(steps - 1, int(p * steps))
        cx = x0 + k * sw_ + sw_ / 2
        cy = y0 - (k + 1) * sh_
        figure(d, cx, cy, col, scene, t, p)
        return
    d.line([(60, floor), (W - 60, floor)], fill=COL_W, width=10)
    if scene == "fall":
        pts = [(160, 620), (300, 760), (400, 700), (560, 930), (650, 860), (880, 1180)]
        n = max(2, int(2 + p * (len(pts) - 1)))
        d.line(pts[:n], fill=COL_RED, width=16, joint="curve")
        figure(d, 540, floor, col, scene, t, p)
    elif scene == "run":
        x = 200 + p * 680
        for i in range(8):
            xx = (i * 140 - t * 400) % (W - 120) + 60
            d.line([(xx, floor + 40), (xx + 50, floor + 40)], fill=(120, 120, 120), width=6)
        figure(d, x, floor, col, scene, t, p)
    elif scene == "think":
        figure(d, 540, floor, col, scene, t, p)
        d.text((640, 780 + math.sin(t * 4) * 10), "?", font=get_font(220), fill=COL_YEL)
    elif scene == "happy":
        random.seed(5)
        for _ in range(10):
            x, y = random.randint(100, 980), random.randint(500, 1000)
            if math.sin(t * 6 + x) > -0.3:
                d.line([(x - 18, y), (x + 18, y)], fill=COL_YEL, width=6)
                d.line([(x, y - 18), (x, y + 18)], fill=COL_YEL, width=6)
        figure(d, 540, floor, col, scene, t, p)
    else:
        figure(d, 540, floor, col, scene, t, p)


def fit_font(d, text, max_w, start):
    size = start
    while size > 30:
        f = get_font(size)
        if d.textlength(text, font=f) <= max_w:
            return f
        size -= 4
    return get_font(30)


def draw_title(d, title):
    f = fit_font(d, title, 940, 130)
    wd = d.textlength(title, font=f)
    d.text(((W - wd) / 2, 230), title, font=f, fill=COL_RED)


def draw_sub(d, chunks, t):
    cur = None
    for c in chunks:
        if c[0]["s"] - 0.05 <= t < c[-1]["e"] + 0.15:
            cur = c
            break
    if not cur:
        return
    text = " ".join(w["w"] for w in cur)
    f = fit_font(d, text, 980, 100)
    total = d.textlength(text, font=f)
    x = (W - total) / 2
    y = 1560
    for w in cur:
        active = w["s"] <= t < w["e"]
        d.text((x, y), w["w"], font=f, fill=COL_YEL if active else COL_W,
               stroke_width=8, stroke_fill=(0, 0, 0))
        x += d.textlength(w["w"] + " ", font=f)


def render(data, total, chunks):
    lines = data["lines"]
    n = int(total * FPS)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", "voice.wav"]
    if os.path.exists("music.mp3"):
        cmd += ["-stream_loop", "-1", "-i", "music.mp3", "-filter_complex",
                "[2:a]volume=0.10[m];[1:a][m]amix=inputs=2:duration=first:dropout_transition=0[a]",
                "-map", "0:v", "-map", "[a]"]
    cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "160k", "-t", f"{total:.2f}", "out.mp4"]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for f in range(n):
        t = f / FPS
        idx = 0
        for i, l in enumerate(lines):
            if t >= l["start"] - 0.2:
                idx = i
        l = lines[idx]
        nxt = lines[idx + 1]["start"] if idx + 1 < len(lines) else total
        p = max(0.0, min(1.0, (t - l["start"]) / max(0.1, nxt - l["start"])))
        col = COL_W if l["spk"] == "M" else COL_PINK
        img = Image.new("RGB", (W, H), COL_BG)
        d = ImageDraw.Draw(img)
        draw_title(d, data["title"])
        draw_scene(d, l["scene"], t, p, col)
        draw_sub(d, chunks, t)
        proc.stdin.write(img.tobytes())
    proc.stdin.close()
    proc.wait()


# ---------- Telegram ----------
def send_tg(path, caption):
    if not (TG_TOKEN and TG_CHAT):
        print("Telegram secrets missing, skipping send")
        return
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendVideo"
    with open(path, "rb") as f:
        r = requests.post(url, data={"chat_id": TG_CHAT, "caption": caption[:1000],
                                     "supports_streaming": "true", "width": W, "height": H},
                          files={"video": f}, timeout=300)
    print("Telegram:", r.status_code, r.text[:200])
    r.raise_for_status()


def main():
    t = os.getenv("TOPIC", "").strip()
    topic, lead = (t, "M") if t else random.choice(TOPICS)
    print("Topic:", topic)
    data = make_script(topic, lead)
    print(json.dumps(data, ensure_ascii=False, indent=1))
    total = build_audio(data["lines"])
    chunks = word_timeline(data["lines"])
    render(data, total, chunks)
    print("size MB:", os.path.getsize("out.mp4") / 1e6)
    script_txt = "\n".join(f'{l["spk"]}: {l["text"]}' for l in data["lines"])
    send_tg("out.mp4", f'{data["title"]}\n\n{data["caption"]}\n\n{script_txt}')


if __name__ == "__main__":
    main()
