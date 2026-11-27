"""محرك الإحساس لأصوات مايكروسوفت المصرية (سلمى وشاكر).

الأصوات دي مافيهاش مشاعر جاهزة، فبنعمل الروح بإيدينا:
  * كل جملة بتاخد سرعة وطبقة وعلو حسب المود وشكل الجملة (؟ ! ...).
  * الضحكة بتتعمل من نفس الصوت: مقاطع "ها" ورا بعض وكل مقطع طبقته أوطى من اللي قبله.
  * التريقة: الجملة بتتقسم نصين، الأول طالع والتاني نازل وممطوط، وفي الآخر "هه".
  * الوقفات بين الجمل بنتحكم فيها بنفسنا بدل السكتات الطويلة اللي بتيجي من الصوت.

لو مكتبات الصوت (numpy/miniaudio/lameenc) مش موجودة، بيرجع يلزق ملفات MP3 ورا بعض.
"""
import asyncio
import re

try:
    import lameenc
    import miniaudio
    import numpy as np
    HAVE_FX = True
except Exception:  # pragma: no cover - fallback when audio libs are missing
    HAVE_FX = False

SR = 24000  # edge-tts بيطلّع mp3 بتردد 24kHz مونو

# ظبط كل صوت لوحده. صوت الراجل بيتأثر بتغيير الطبقة أكتر، فبنصغّر الأرقام بتاعته.
VOICES = {
    "salma": {
        "id": "ar-EG-SalmaNeural",
        "hz": 1.0,
        "laugh": "ها",
        "laugh_pitch": [34, 28, 22, 16, 11, 7, 4, 2],
        "laugh_rate": 35,
        "scoff": "هِه",
    },
    "shakir": {
        "id": "ar-EG-ShakirNeural",
        "hz": 0.6,
        "laugh": "ها",
        "laugh_pitch": [30, 24, 18, 13, 9, 6, 3, 1],
        "laugh_rate": 30,
        "scoff": "هِه",
    },
}

# المود: سرعة %، طبقة Hz (قبل ظبط الصوت)، علو %، قد إيه الجمل بتختلف عن بعض، وقفة بين الجمل بالمللي
MOODS = {
    "normal":    dict(rate=0,   pitch=0,   vol=0,   swing=3, gap=260),
    "excited":   dict(rate=16,  pitch=12,  vol=18,  swing=7, gap=170),
    "calm":      dict(rate=-10, pitch=-3,  vol=-8,  swing=2, gap=380),
    "sad":       dict(rate=-20, pitch=-10, vol=-14, swing=2, gap=480),
    "story":     dict(rate=-6,  pitch=2,   vol=0,   swing=8, gap=420),
    "sarcastic": dict(rate=-12, pitch=4,   vol=0,   swing=4, gap=330),
}

LAUGH_EMOJI = "😂🤣😆😅😹"
SAD_EMOJI = "😢😭😔💔☹"
SARC_EMOJI = "🙄😏🙃"
_ENDS = ".!?؟…\n" + LAUGH_EMOJI + SAD_EMOJI + SARC_EMOJI
_EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿️]")

# التاجات اللي المستخدم يقدر يكتبها (بالعربي أو بالإنجليزي)
TAGS = {
    "ضحكة": "laugh", "ضحك": "laugh", "laugh": "laugh", "laughs": "laugh",
    "ضحكة كبيرة": "big_laugh", "big laugh": "big_laugh",
    "هه": "scoff", "chuckles": "scoff", "scoff": "scoff",
    "تريقة": "sarcastic", "sarcastic": "sarcastic",
    "حماس": "excited", "excited": "excited",
    "حزن": "sad", "sad": "sad",
    "همس": "whisper", "whispers": "whisper",
}
# نفس التاجات بس للـ ElevenLabs v3
ELEVEN_TAGS = {
    "laugh": "[laughs]", "big_laugh": "[laughs harder]", "scoff": "[chuckles]",
    "sarcastic": "[sarcastic]", "excited": "[excited]", "sad": "[sad]", "whisper": "[whispers]",
}
_TAG_RE = re.compile(r"\[([^\]\n]{1,20})\]")
_LAUGH_TXT = re.compile(r"(?:ه{3,}|(?:ها){2,}|ﻫ{3,})")


def tags_for_eleven(text):
    """يحوّل التاجات العربي لتاجات ElevenLabs ويحوّل إيموجي الضحك لـ [laughs]."""
    def sub(m):
        kind = TAGS.get(m.group(1).strip().lower())
        return ELEVEN_TAGS.get(kind, m.group(0))
    text = _TAG_RE.sub(sub, text)
    text = re.sub(f"[{LAUGH_EMOJI}]+", " [laughs] ", text)
    return text


def _clamp(v, lo, hi):
    return max(lo, min(hi, int(round(v))))


def plan(text, voice="salma", mood="normal", auto=True, user_rate=0, user_pitch=0):
    """يحوّل الكلام لقايمة أحداث: كلام بإعداداته، أو ضحكة، أو وقفة."""
    prof = VOICES.get(voice, VOICES["salma"])
    m = MOODS.get(mood, MOODS["normal"])
    hz = prof["hz"]

    # 1) التاجات والضحك المكتوب بيتحولوا لعلامات جوه النص
    def tag_sub(mt):
        kind = TAGS.get(mt.group(1).strip().lower())
        return f"\x00{kind}\x00" if kind else ""
    text = _TAG_RE.sub(tag_sub, text)
    if auto:
        text = _LAUGH_TXT.sub("\x00laugh\x00", text)
    text = re.sub(f"[{LAUGH_EMOJI}]+", lambda s: s.group(0) + "\x00laugh\x00", text)

    # 2) تقسيم لجمل مع الاحتفاظ بالعلامات
    pieces = re.split(r"(\x00\w+\x00)", text)
    events = []
    pending = None  # تاج بيأثر على الجملة اللي بعده (تريقة/حماس/حزن/همس)
    idx = 0
    for piece in pieces:
        if not piece:
            continue
        tm = re.fullmatch(r"\x00(\w+)\x00", piece)
        if tm:
            kind = tm.group(1)
            if kind in ("laugh", "big_laugh", "scoff"):
                events.append(("laugh", kind))
                events.append(("pause", 200))
            else:
                pending = kind
            continue
        for sm in re.finditer(rf"[^{re.escape(_ENDS)}]+(?:\.\.\.|[{re.escape(_ENDS)}]+)?|\n+", piece):
            part = sm.group(0)
            if part.strip() == "" and "\n" in part:
                events.append(("pause", 300))
                continue
            spoken = _EMOJI.sub("", part).strip()
            if not re.search(r"\w", spoken):
                continue
            r, p, v = m["rate"], m["pitch"], m["vol"]
            gap = m["gap"]
            style = pending or ("sarcastic" if mood == "sarcastic" else None)
            if auto:
                p += m["swing"] if idx % 2 else -m["swing"] / 2
                end = part.rstrip()
                if end.endswith(("؟", "?")):
                    p += 8
                if "!" in end:
                    r += 10; p += 6; v += 12; gap -= 40
                if end.endswith(("...", "…")):
                    r -= 12; p -= 3; gap += 250
                if any(e in part for e in SAD_EMOJI):
                    r -= 14; p -= 8; v -= 10
                if any(e in part for e in SARC_EMOJI):
                    style = "sarcastic"
            if style == "excited":
                r += 16; p += 12; v += 18
            elif style == "sad":
                r -= 20; p -= 10; v -= 14
            elif style == "whisper":
                r -= 8; p -= 4; v -= 35
            r += user_rate
            p = p * hz + user_pitch
            if style == "sarcastic":
                events.extend(_sarcastic(spoken, r, p, v, hz))
                events.append(("laugh", "scoff"))
                events.append(("pause", 120))
            else:
                events.append(("speech", spoken, _clamp(r, -50, 100), _clamp(p, -60, 60), _clamp(v, -50, 50)))
            events.append(("pause", max(80, gap)))
            pending = None
            idx += 1
    return events, prof


def _sarcastic(spoken, r, p, v, hz):
    """التريقة: نص الجملة الأول طالع، والتاني نازل وممطوط."""
    words = spoken.split()
    if len(words) < 3:
        return [("speech", spoken, _clamp(r - 8, -50, 100), _clamp(p + 10 * hz, -60, 60), _clamp(v, -50, 50))]
    cut = max(1, len(words) // 2)
    first, second = " ".join(words[:cut]), " ".join(words[cut:])
    return [
        ("speech", first, _clamp(r - 4, -50, 100), _clamp(p + 14 * hz, -60, 60), _clamp(v + 5, -50, 50)),
        ("pause", 90),
        ("speech", second, _clamp(r - 22, -50, 100), _clamp(p - 8 * hz, -60, 60), _clamp(v - 3, -50, 50)),
    ]


class _Done:
    """نتيجة جاهزة تتعمل لها await زي الـ Future (عشان الكاش يعيش بين الطلبات)."""
    def __init__(self, data):
        self.data = data

    def __await__(self):
        return self.data
        yield  # noqa: unreachable - يخليها generator


_LAUGH_CACHE = {}


def _laugh_specs(kind, prof):
    """مقاطع الضحكة: (نص، سرعة، طبقة، علو، أقصى طول بالمللي، وقفة بعدها)."""
    hz = prof["hz"]
    pitches = prof["laugh_pitch"]
    if kind == "scoff":
        return [(prof["scoff"], 10, round(-4 * hz), -10, 260, 60)]
    n = 7 if kind == "big_laugh" else 4
    vol = 25 if kind == "big_laugh" else 12
    specs = []
    for i in range(n):
        specs.append((prof["laugh"], prof["laugh_rate"], round(pitches[i] * hz), vol - i * 3, 210, 55 + i * 8))
    return specs


async def render(text, voice, mood, auto, user_rate, user_pitch, tts):
    """يرجّع ملف MP3 واحد. tts(text, voice_id, rate, pitch, volume) -> mp3 bytes."""
    events, prof = plan(text, voice, mood, auto, user_rate, user_pitch)
    if not any(e[0] == "speech" for e in events):
        events = [("speech", text, user_rate, user_pitch, 0)]

    sem = asyncio.Semaphore(6)
    cache = _LAUGH_CACHE if len(_LAUGH_CACHE) < 300 else {}

    async def synth(t, r, p, v):
        key = (prof["id"], t, r, p, v)
        if key not in cache:
            async def go():
                async with sem:
                    return await tts(t, prof["id"], f"{r:+d}%", f"{p:+d}Hz", f"{v:+d}%")
            cache[key] = asyncio.ensure_future(go())
        try:
            data = await cache[key]
        except Exception:
            cache.pop(key, None)
            raise
        if isinstance(cache.get(key), asyncio.Future):
            cache[key] = _Done(data)  # نحتفظ بالنتيجة لطلبات بعدين
        return data

    # كل حدث بيتحول لقايمة أجزاء: (mp3, أقصى طول, وقفة بعده)
    async def build(ev):
        if ev[0] == "speech":
            return [(await synth(ev[1], ev[2], ev[3], ev[4]), None, 0)]
        if ev[0] == "laugh":
            specs = _laugh_specs(ev[1], prof)
            mp3s = await asyncio.gather(*(synth(t, r, p, v) for t, r, p, v, _, _ in specs))
            return [(mp3, mx, gap) for mp3, (_, _, _, _, mx, gap) in zip(mp3s, specs)]
        return [(None, None, ev[1])]

    parts = [x for group in await asyncio.gather(*(build(e) for e in events)) for x in group]
    return assemble(parts)


# ---------------- معالجة الصوت ----------------

def assemble(parts):
    """يلزق الأجزاء بعد ما يشيل السكوت الزيادة، ويحط الوقفات اللي إحنا عايزينها."""
    if not HAVE_FX:
        return b"".join(mp3 for mp3, _, _ in parts if mp3)
    out = []
    for mp3, max_ms, gap_ms in parts:
        if mp3:
            x = _trim(_decode(mp3), pad_ms=25 if max_ms else 60)
            if max_ms and len(x) > SR * max_ms // 1000:
                x = x[: SR * max_ms // 1000]
            out.append(_fade(x))
        if gap_ms:
            out.append(np.zeros(SR * gap_ms // 1000, dtype=np.float32))
    while out and not out[-1].any():
        out.pop()
    if not out:
        return b""
    return _encode(np.concatenate(out))


def _decode(mp3):
    snd = miniaudio.decode(mp3, output_format=miniaudio.SampleFormat.SIGNED16, nchannels=1, sample_rate=SR)
    return np.frombuffer(snd.samples, dtype=np.int16).astype(np.float32) / 32768.0


def _trim(x, thresh=0.012, pad_ms=60):
    if not len(x):
        return x
    win = max(1, SR // 100)  # 10ms
    env = np.convolve(np.abs(x), np.ones(win) / win, mode="same")
    idx = np.where(env > thresh)[0]
    if not len(idx):
        return x[:0]
    pad = SR * pad_ms // 1000
    return x[max(0, idx[0] - pad): min(len(x), idx[-1] + pad)]


def _fade(x, ms=12):
    n = min(len(x) // 2, SR * ms // 1000)
    if n > 0:
        x = x.copy()
        ramp = np.linspace(0, 1, n, dtype=np.float32)
        x[:n] *= ramp
        x[-n:] *= ramp[::-1]
    return x


def _encode(x):
    pcm = (np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes()
    enc = lameenc.Encoder()
    enc.set_bit_rate(64)
    enc.set_in_sample_rate(SR)
    enc.set_channels(1)
    enc.set_quality(2)
    return bytes(enc.encode(pcm) + enc.flush())
