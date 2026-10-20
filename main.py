import os, json, re, math, base64, wave, random, subprocess, time, datetime
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
STYLE = {
    "M": "Energetic, confident Indian male storyteller. Fast-paced and punchy, stress the key words, emotional, like a viral motivational reel narrator.",
    "F": "Warm, confident Indian woman. Expressive, friendly and inspiring, clear and slightly fast-paced, like a viral reel narrator.",
}
SR = 24000
SCENES = ["fall", "climb", "stress", "happy", "think", "run",
          "desk", "heart", "water", "sleep", "mountain", "clock"]
POSE = {"fall": "stress", "stress": "stress", "happy": "happy", "think": "think",
        "run": "run", "climb": "run", "mountain": "run", "clock": "stress",
        "desk": "idle", "heart": "idle", "water": "idle", "sleep": "idle"}

CATS = {
    "motivation": {"lead": "M", "accent": (255, 150, 40)},
    "corporate": {"lead": "M", "accent": (90, 170, 255)},
    "health": {"lead": "F", "accent": (70, 220, 150)},
}
CATEGORY = os.getenv("CATEGORY", "motivation").strip().lower()
if CATEGORY not in CATS:
    CATEGORY = "motivation"
ACCENT = CATS[CATEGORY]["accent"]
START_DATE = datetime.date(2026, 10, 22)

COL_W = (255, 255, 255)
COL_RED = (255, 77, 77)
COL_PINK = (255, 170, 160)
COL_YEL = (255, 214, 10)
COL_BLUE = (80, 170, 255)


def pick_topic():
    t = os.getenv("TOPIC", "").strip()
    if t:
        return t
    items = []
    if os.path.exists("topics.txt"):
        for line in open("topics.txt", encoding="utf-8"):
            if "|" in line:
                c, x = line.strip().split("|", 1)
                if c.strip().lower() == CATEGORY:
                    items.append(x.strip())
    if not items:
        return "Roz thoda behtar banne ki taqat"
    idx = max(0, (datetime.date.today() - START_DATE).days) % len(items)
    return items[idx]


# ---------- Gemini ----------
def gpost(model, body, tries=4):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    for i in range(tries):
        try:
            r = requests.post(url, headers={"x-goog-api-key": KEY}, json=body, timeout=180)
            if r.ok:
                return r.json()
            print("Gemini error", r.status_code, r.text[:300])
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
                {"spk": "M", "scene": "fall", "text": "Jab sab kuch girne lagta hai, to ghabra mat jaana.", "voice": "जब सब कुछ गिरने लगे, तो घबराना मत।"},
                {"spk": "M", "scene": "desk", "text": "Kyunki har gira hua graph ek din upar jaata hai.", "voice": "क्योंकि हर गिरा हुआ ग्राफ एक दिन ऊपर जाता है।"},
                {"spk": "F", "scene": "heart", "text": "Bas ek ek seedhi chadhte raho, roz thoda sa.", "voice": "बस एक एक सीढ़ी चढ़ते रहो।"},
                {"spk": "F", "scene": "water", "text": "Aaj ka chhota kadam kal ki badi jeet banega.", "voice": "आज का छोटा कदम कल की बड़ी जीत बनेगा।"},
                {"spk": "M", "scene": "sleep", "text": "Neend poori lo, dimaag taaza rakho.", "voice": "नींद पूरी लो।"},
                {"spk": "M", "scene": "mountain", "text": "Chotti tak pahunchna hai to chalte raho.", "voice": "चोटी तक पहुंचना है तो चलते रहो।"},
                {"spk": "F", "scene": "clock", "text": "Waqt kisi ka intezaar nahi karta.", "voice": "वक्त किसी का इंतज़ार नहीं करता।"},
                {"spk": "F", "scene": "happy", "text": "Shuru karo, abhi, isi pal.", "voice": "शुरू करो, अभी।"},
            ],
        }
    other = "F" if lead == "M" else "M"
    prompt = f"""Tu ek viral Hindi-English (Hinglish) YouTube Shorts / Reels script writer hai. Audience: Indian log, 22-45 saal, job karne wale aur gharelu log.
Topic: {topic}
Category: {CATEGORY}

Rules:
- 9 se 11 lines, total bolne ka time 40-50 second.
- Har line max 14 shabd. Bolchaal wali simple Hinglish, ek dost se baat karne jaisi.
- Line 1 ek zabardast HOOK ho (shock, sawal ya chhoti sachchi baat) jo scroll rok de.
- Beech mein story/fact/example, phir twist, phir ek chhota practical step, aur aakhri line strong closing (follow/share ko bina bheek maange).
- Lead speaker "{lead}" ho. Twist, solution aur closing line "{other}" bole.
- Health topic me sirf general healthy habits batao. Koi dawa, ilaaj, bimari ka claim ya diagnosis nahi.
- Career/paise topic me koi guaranteed result ya investment salah nahi.
- Har line ke liye scene chuno: {", ".join(SCENES)}. Scene line ke matlab se match kare (desk=office kaam, clock=waqt, heart=dil/health, water=paani, sleep=neend, mountain=bada goal, climb=taraqqi, fall=giravat, stress=tension, happy=jeet, think=sochna, run=action).
- Har line ke 2 version do:
  "text": Roman Hinglish (subtitle ke liye).
  "voice": wahi line Devanagari Hindi me (bolne ke liye). Common English shabd (jaise stress, deadline, office) Latin script me rakh sakte ho. Emoji, bracket ya stage direction nahi.
- title: max 4 shabd, CAPS, hook jaisa.
- caption: ek line + 3 hashtags.
Sirf JSON do: {{"title":"","caption":"","lines":[{{"spk":"M","scene":"fall","text":"","voice":""}}]}}"""
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
        if not l.get("voice"):
            l["voice"] = l["text"]
    return data


# ---------- Voice ----------
def to_wav24(src, dst):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-ar", str(SR), "-ac", "1",
                    "-af", "atempo=1.05", dst], check=True)


def tts_gemini(text, spk, path):
    voice_cfg = {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": VOICES[spk]}}}
    variants = [
        {"text": text, "speech_metadata": {"style": STYLE[spk]}},
        {"text": text},
    ]
    j = None
    for part in variants:
        body = {"contents": [{"parts": [part]}],
                "generationConfig": {"responseModalities": ["AUDIO"], "speechConfig": voice_cfg}}
        j = gpost(TTS_MODEL, body, tries=2)
        if j:
            break
    if not j:
        return False
    try:
        inl = j["candidates"][0]["content"]["parts"][0]["inlineData"]
        raw = base64.b64decode(inl["data"])
        mime = inl.get("mimeType", "").lower()
    except Exception:
        print("TTS: no audio in response", str(j)[:200])
        return False
    src = path + ".src.wav"
    if "l16" in mime or "pcm" in mime:
        m = re.search(r"rate=(\d+)", mime)
        rate = int(m.group(1)) if m else 24000
        with wave.open(src, "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
            w.writeframes(raw)
    else:
        with open(src, "wb") as f:
            f.write(raw)
    try:
        to_wav24(src, path)
    except Exception as e:
        print("TTS convert failed", e)
        return False
    return True


def tts_edge(text, spk, path):
    mp3 = path + ".mp3"
    r = subprocess.run(["edge-tts", "--voice", EDGE[spk], "--rate=+5%", "--text", text, "--write-media", mp3])
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
        vt = l.get("voice") or l["text"]
        if MOCK:
            tts_mock(l["text"], p)
        else:
            ok = tts_gemini(vt, l["spk"], p)
            if not ok:
                print("Gemini voice failed on line", i, "-> using edge-tts")
                ok = tts_edge(vt, l["spk"], p)
            if not ok:
                raise RuntimeError("Voice generation failed")
            time.sleep(2)
        a = read_wav(p)
        dur = len(a) / SR
        l["start"], l["end"] = cursor, cursor + dur
        chunks.append(a)
        chunks.append(np.zeros(int(0.2 * SR), dtype=np.int16))
        cursor += dur + 0.2
    audio = np.concatenate(chunks)
    with wave.open("voice.wav", "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(audio.tobytes())
    return cursor + 0.6


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
    return [words[i:i + 3] for i in range(0, len(words), 3)]


# ---------- Background ----------
def make_bg():
    ys = np.linspace(0, 1, H)[:, None]
    top = np.array([16, 18, 46], dtype=np.float32)
    bot = np.array([3, 3, 10], dtype=np.float32)
    base = top[None, None, :] * (1 - ys[:, :, None]) + bot[None, None, :] * ys[:, :, None]
    arr = np.repeat(base, W, axis=1)
    yy, xx = np.mgrid[0:H, 0:W]
    glow = np.exp(-(((xx - W / 2) / 650.0) ** 2 + ((yy - 1250) / 520.0) ** 2))
    for c in range(3):
        arr[:, :, c] += glow * ACCENT[c] * 0.22
    vig = 1 - 0.35 * (((xx - W / 2) / (W / 1.2)) ** 2 + ((yy - H / 2) / (H / 1.2)) ** 2)
    arr *= np.clip(vig, 0.5, 1)[:, :, None]
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


random.seed(11)
PARTS = [(random.randint(0, W), random.randint(0, H), random.uniform(25, 90), random.randint(2, 6),
          random.uniform(0, 6.28)) for _ in range(32)]


def draw_particles(d, t):
    for x0, y0, sp, r, ph in PARTS:
        y = (y0 - t * sp) % H
        x = x0 + math.sin(t * 0.8 + ph) * 25
        a = 0.35 + 0.25 * math.sin(t * 2 + ph)
        c = tuple(int(v * a) for v in ACCENT)
        d.ellipse([x - r, y - r, x + r, y + r], fill=c)


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


def figure(d, cx, base, col, pose, t, S=1.3):
    bob = math.sin(t * 5) * 6 * S
    jump = 0
    la, ra, ll, rl = 25, -25, 10, -10
    if pose == "stress":
        sh = math.sin(t * 40) * 10
        la, ra, ll, rl = 140 + sh, -140 - sh, 14, -14
    elif pose == "happy":
        jump = abs(math.sin(t * 6)) * 60
        la, ra, ll, rl = 165 + math.sin(t * 10) * 10, -165 - math.sin(t * 10) * 10, 12, -12
    elif pose == "think":
        la, ra, ll, rl = 25, -150, 8, -8
    elif pose == "run":
        sw = math.sin(t * 12) * 40
        la, ra, ll, rl = -sw, sw, sw, -sw
    base = base - jump
    w = max(8, int(11 * S))
    hip = (cx, base - 110 * S + bob / 2)
    neck = (cx, base - 190 * S + bob / 2)
    head = (cx, base - 237 * S + bob / 2)
    d.line([neck, hip], fill=col, width=w)
    limb(d, hip, ll, 110 * S, w, col)
    limb(d, hip, rl, 110 * S, w, col)
    sp = (cx, neck[1] + 12 * S)
    limb(d, sp, la, 85 * S, w, col)
    limb(d, sp, ra, 85 * S, w, col)
    r = 42 * S
    d.ellipse([head[0] - r, head[1] - r, head[0] + r, head[1] + r], outline=col, width=max(7, int(9 * S)))
    e = 8 * S
    if pose == "stress":
        d.ellipse([head[0] - 7 * S, head[1] + 4 * S, head[0] + 7 * S, head[1] + 20 * S], outline=col, width=5)
        for ang in (-50, 0, 50):
            a = math.radians(ang)
            x1, y1 = head[0] + 62 * S * math.sin(a), head[1] - 62 * S * math.cos(a)
            x2, y2 = head[0] + 92 * S * math.sin(a), head[1] - 92 * S * math.cos(a)
            d.line([(x1, y1), (x2, y2)], fill=COL_RED, width=7)
    elif pose == "happy":
        d.arc([head[0] - 20 * S, head[1] - 5 * S, head[0] + 20 * S, head[1] + 22 * S], 10, 170, fill=col, width=5)
    else:
        d.line([(head[0] - 14 * S, head[1] + 14 * S), (head[0] + 14 * S, head[1] + 14 * S)], fill=col, width=5)
    d.ellipse([head[0] - 18 * S, head[1] - 12 * S, head[0] - 18 * S + e, head[1] - 12 * S + e], fill=col)
    d.ellipse([head[0] + 10 * S, head[1] - 12 * S, head[0] + 10 * S + e, head[1] - 12 * S + e], fill=col)


def heart_pts(cx, cy, k):
    pts = []
    for i in range(0, 361, 6):
        a = math.radians(i)
        x = 16 * math.sin(a) ** 3
        y = 13 * math.cos(a) - 5 * math.cos(2 * a) - 2 * math.cos(3 * a) - math.cos(4 * a)
        pts.append((cx + x * k, cy - y * k))
    return pts


def draw_clock(d, cx, cy, r, t, col, speed=1.0):
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=col, width=12)
    for i in range(12):
        a = math.radians(i * 30)
        d.line([(cx + (r - 26) * math.sin(a), cy - (r - 26) * math.cos(a)),
                (cx + (r - 8) * math.sin(a), cy - (r - 8) * math.cos(a))], fill=col, width=7)
    for ang, ln, w, c in ((t * 140 * speed, r - 40, 8, COL_RED), (t * 12 * speed, r - 85, 12, col)):
        a = math.radians(ang)
        d.line([(cx, cy), (cx + ln * math.sin(a), cy - ln * math.cos(a))], fill=c, width=w)
    d.ellipse([cx - 12, cy - 12, cx + 12, cy + 12], fill=col)


def draw_scene(d, scene, t, p, col):
    floor = 1350
    pose = POSE.get(scene, "idle")
    if scene == "climb":
        steps = 6
        x0, y0, sw_, sh_ = 120, floor, 150, 105
        pts = [(x0, y0)]
        for i in range(steps):
            pts += [(x0 + i * sw_, y0 - (i + 1) * sh_), (x0 + (i + 1) * sw_, y0 - (i + 1) * sh_)]
        d.line(pts, fill=ACCENT, width=11, joint="curve")
        k = min(steps - 1, int(p * steps))
        figure(d, x0 + k * sw_ + sw_ / 2, y0 - (k + 1) * sh_, col, pose, t, S=1.0)
        return
    if scene == "mountain":
        peak = (700, 650)
        d.line([(100, floor), peak, (1040, floor)], fill=COL_W, width=11, joint="curve")
        d.line([peak, (peak[0], peak[1] - 130)], fill=COL_W, width=8)
        d.polygon([(peak[0], peak[1] - 130), (peak[0] + 90, peak[1] - 100), (peak[0], peak[1] - 70)], fill=COL_RED)
        q = 0.08 + 0.84 * p
        px = 100 + (peak[0] - 100) * q - 40
        py = floor + (peak[1] - floor) * q
        figure(d, px, py, col, pose, t, S=0.9)
        return
    d.line([(60, floor), (W - 60, floor)], fill=ACCENT, width=10)
    if scene == "fall":
        pts = [(160, 620), (300, 760), (400, 700), (560, 930), (650, 860), (880, 1180)]
        n = max(2, int(2 + p * (len(pts) - 1)))
        d.line(pts[:n], fill=COL_RED, width=18, joint="curve")
        figure(d, 540, floor, col, pose, t)
    elif scene == "run":
        x = 200 + p * 680
        for i in range(8):
            xx = (i * 140 - t * 400) % (W - 120) + 60
            d.line([(xx, floor + 40), (xx + 50, floor + 40)], fill=(120, 120, 140), width=6)
        figure(d, x, floor, col, pose, t)
    elif scene == "think":
        figure(d, 460, floor, col, pose, t)
        d.text((600, 760 + math.sin(t * 4) * 12), "?", font=get_font(260), fill=COL_YEL)
    elif scene == "happy":
        random.seed(5)
        for _ in range(12):
            x, y = random.randint(100, 980), random.randint(500, 1050)
            if math.sin(t * 6 + x) > -0.3:
                d.line([(x - 20, y), (x + 20, y)], fill=COL_YEL, width=7)
                d.line([(x, y - 20), (x, y + 20)], fill=COL_YEL, width=7)
        figure(d, 540, floor, col, pose, t)
    elif scene == "desk":
        top = floor - 230
        d.line([(600, top), (1020, top)], fill=COL_W, width=10)
        d.line([(630, top), (630, floor)], fill=COL_W, width=10)
        d.line([(990, top), (990, floor)], fill=COL_W, width=10)
        d.rectangle([700, top - 150, 900, top - 12], outline=COL_BLUE, width=8)
        d.line([(680, top - 4), (920, top - 4)], fill=COL_BLUE, width=8)
        for i in range(3):
            yy = top - 120 + i * 32
            ww = 60 + ((int(t * 3) + i * 2) % 4) * 25
            d.line([(720, yy), (720 + ww, yy)], fill=COL_BLUE, width=6)
        for i in range(4):
            d.rectangle([930, top - 18 - i * 16, 985, top - 4 - i * 16], outline=COL_YEL, width=4)
        draw_clock(d, 800, 760, 110, t, COL_W, 1.0)
        figure(d, 380, floor, col, "stress" if p > 0.5 else "idle", t)
    elif scene == "heart":
        k = 12.5 * (1 + 0.12 * abs(math.sin(t * 7)))
        d.polygon(heart_pts(540, 690, k), fill=COL_RED)
        pts = []
        for i in range(0, 20):
            x = 100 + i * 44
            ph = (i + int(t * 6)) % 10
            y = 1020 + {3: -60, 4: 80, 5: -30}.get(ph, 0)
            pts.append((x, y))
        d.line(pts, fill=ACCENT, width=8, joint="curve")
        figure(d, 540, floor, col, "happy" if p > 0.6 else "idle", t)
    elif scene == "water":
        gl, gr, gt, gb = 700, 940, 880, 1330
        lvl = gb - (gb - gt - 30) * (0.15 + 0.8 * p)
        d.polygon([(gl + 12, lvl), (gr - 12, lvl), (gr - 28, gb - 8), (gl + 28, gb - 8)], fill=(50, 150, 255))
        d.line([(gl, gt), (gl + 22, gb), (gr - 22, gb), (gr, gt)], fill=COL_W, width=10, joint="curve")
        for i in range(3):
            yy = 820 + ((t * 120 + i * 90) % 220)
            d.ellipse([820 - 8 + i * 10, yy, 820 + 8 + i * 10, yy + 22], fill=(120, 190, 255))
        figure(d, 380, floor, col, "idle", t)
    elif scene == "sleep":
        d.arc([640, 520, 900, 780], 110, 290, fill=COL_YEL, width=20)
        for i in range(3):
            yy = 900 - ((t * 60 + i * 60) % 180)
            d.text((300 + i * 70 + math.sin(t * 2 + i) * 10, yy), "Z", font=get_font(70 + i * 30), fill=COL_BLUE)
        random.seed(8)
        for _ in range(8):
            x, y = random.randint(80, 1000), random.randint(480, 800)
            if math.sin(t * 3 + x) > -0.2:
                d.ellipse([x - 5, y - 5, x + 5, y + 5], fill=COL_W)
        figure(d, 380, floor, col, "idle", t)
    elif scene == "clock":
        draw_clock(d, 540, 680, 170, t, COL_W, 2.0)
        figure(d, 540, floor, col, "stress", t)
    else:
        figure(d, 540, floor, col, pose, t)


def fit_font(d, text, max_w, start):
    size = start
    while size > 30:
        f = get_font(size)
        if d.textlength(text, font=f) <= max_w:
            return f
        size -= 4
    return get_font(30)


def draw_title(d, title, t):
    f = fit_font(d, title, 940, 130)
    wd = d.textlength(title, font=f)
    d.text(((W - wd) / 2, 230), title, font=f, fill=COL_RED, stroke_width=6, stroke_fill=(0, 0, 0))
    lbl = CATEGORY.upper()
    f2 = get_font(40)
    lw = d.textlength(lbl, font=f2)
    d.rounded_rectangle([(W - lw) / 2 - 28, 150, (W + lw) / 2 + 28, 212], radius=30, fill=ACCENT)
    d.text(((W - lw) / 2, 156), lbl, font=f2, fill=(10, 10, 20))


def draw_sub(d, chunks, t):
    cur = None
    for c in chunks:
        if c[0]["s"] - 0.05 <= t < c[-1]["e"] + 0.15:
            cur = c
            break
    if not cur:
        return
    text = " ".join(w["w"] for w in cur)
    f = fit_font(d, text, 980, 105)
    total = d.textlength(text, font=f)
    x = (W - total) / 2
    y = 1540
    for w in cur:
        active = w["s"] <= t < w["e"]
        d.text((x, y), w["w"], font=f, fill=COL_YEL if active else COL_W,
               stroke_width=9, stroke_fill=(0, 0, 0))
        x += d.textlength(w["w"] + " ", font=f)


def draw_frame(bg, data, lines, chunks, t, total):
    idx = 0
    for i, l in enumerate(lines):
        if t >= l["start"] - 0.2:
            idx = i
    l = lines[idx]
    nxt = lines[idx + 1]["start"] if idx + 1 < len(lines) else total
    p = max(0.0, min(1.0, (t - l["start"]) / max(0.1, nxt - l["start"])))
    col = COL_W if l["spk"] == "M" else COL_PINK
    img = bg.copy()
    d = ImageDraw.Draw(img)
    draw_particles(d, t)
    d.rectangle([0, 0, int(W * min(1, t / total)), 12], fill=ACCENT)
    draw_title(d, data["title"], t)
    draw_scene(d, l["scene"], t, p, col)
    draw_sub(d, chunks, t)
    return img


def render(data, total, chunks):
    lines = data["lines"]
    n = int(total * FPS)
    bg = make_bg()
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", "voice.wav"]
    if os.path.exists("music.mp3"):
        cmd += ["-stream_loop", "-1", "-i", "music.mp3", "-filter_complex",
                "[2:a]volume=0.10[m];[1:a][m]amix=inputs=2:duration=first:dropout_transition=0[a]",
                "-map", "0:v", "-map", "[a]"]
    cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "160k", "-t", f"{total:.2f}", "out.mp4"]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for f in range(n):
        proc.stdin.write(draw_frame(bg, data, lines, chunks, f / FPS, total).tobytes())
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
    topic = pick_topic()
    lead = CATS[CATEGORY]["lead"]
    print("Category:", CATEGORY, "| Topic:", topic)
    data = make_script(topic, lead)
    print(json.dumps(data, ensure_ascii=False, indent=1))
    total = build_audio(data["lines"])
    chunks = word_timeline(data["lines"])
    render(data, total, chunks)
    print("size MB:", os.path.getsize("out.mp4") / 1e6)
    script_txt = "\n".join(f'{l["spk"]}: {l["text"]}' for l in data["lines"])
    send_tg("out.mp4", f'[{CATEGORY.upper()}] {data["title"]}\n{topic}\n\n{data["caption"]}\n\n{script_txt}')


if __name__ == "__main__":
    main()
