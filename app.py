"""تطبيق تحويل النص المكتوب بالعامية المصرية إلى صوت مصري.

محركين للصوت:
  1) Microsoft Edge (مجاني، من غير مفتاح): سلمى وشاكر - صوت مصري واضح بس طريقته قراية.
  2) ElevenLabs (بفلوس، محتاج API key): صوت فيه إحساس وروح أكتر، وبيدعم
     تاجات زي [laughs] و [whispers] مع موديل eleven_v3.
"""
import asyncio
import io
import os
import re

import edge_tts
import requests
from flask import Flask, jsonify, render_template, request, send_file

EDGE_VOICES = {
    "salma": "ar-EG-SalmaNeural",
    "shakir": "ar-EG-ShakirNeural",
}
ELEVEN_API = "https://api.elevenlabs.io/v1"
ELEVEN_MODELS = {"eleven_v3", "eleven_multilingual_v2"}
MAX_CHARS = 5000
MAX_CLONE_FILES = 25

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 60 * 1024 * 1024  # 60MB للتسجيلات


def _clamp_int(value, lo, hi, default=0):
    try:
        v = int(value)
    except (TypeError, ValueError):
        v = default
    return max(lo, min(hi, v))


def _clamp_float(value, lo, hi, default):
    try:
        v = float(value)
    except (TypeError, ValueError):
        v = default
    return max(lo, min(hi, v))


def _eleven_key(data):
    """المفتاح من السيرفر (متغير بيئة) أو اللي المستخدم كتبه في الصفحة."""
    return (os.environ.get("ELEVENLABS_API_KEY") or (data.get("api_key") or "")).strip()


async def edge_synthesize(text, voice, rate="+0%", pitch="+0Hz"):
    communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
    buf = io.BytesIO()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            buf.write(chunk["data"])
    return buf.getvalue()


def eleven_synthesize(text, api_key, voice_id, model_id, stability, style):
    if model_id == "eleven_v3":
        # eleven_v3 بيقبل 0 (Creative) أو 0.5 (Natural) أو 1 (Robust) بس
        stability = min((0.0, 0.5, 1.0), key=lambda s: abs(s - stability))
        settings = {"stability": stability}
    else:
        settings = {"stability": stability, "similarity_boost": 0.75,
                    "style": style, "use_speaker_boost": True}
    r = requests.post(
        f"{ELEVEN_API}/text-to-speech/{voice_id}",
        params={"output_format": "mp3_44100_128"},
        headers={"xi-api-key": api_key, "Content-Type": "application/json"},
        json={"text": text, "model_id": model_id,
              "voice_settings": settings},
        timeout=120,
    )
    if r.status_code != 200:
        try:
            detail = r.json().get("detail")
            msg = detail.get("message") if isinstance(detail, dict) else detail
        except ValueError:
            msg = r.text[:200]
        raise RuntimeError(f"ElevenLabs ({r.status_code}): {msg}")
    return r.content


@app.get("/sw.js")
def service_worker():
    resp = app.send_static_file("sw.js")
    resp.headers["Cache-Control"] = "no-cache"
    resp.headers["Service-Worker-Allowed"] = "/"
    return resp


@app.get("/")
def index():
    return render_template("index.html", max_chars=MAX_CHARS,
                           server_key=bool(os.environ.get("ELEVENLABS_API_KEY")))


@app.post("/api/eleven/voices")
def eleven_voices():
    data = request.get_json(silent=True) or {}
    key = _eleven_key(data)
    if not key:
        return jsonify(error="محتاج ElevenLabs API key"), 400
    try:
        r = requests.get(f"{ELEVEN_API}/voices", headers={"xi-api-key": key}, timeout=30)
    except requests.RequestException as exc:
        return jsonify(error=f"مش قادر أوصل لـ ElevenLabs: {exc}"), 502
    if r.status_code != 200:
        return jsonify(error=f"ElevenLabs رفض الطلب ({r.status_code}) - اتأكد من المفتاح"), 502
    voices = [{"id": v["voice_id"], "name": v.get("name", v["voice_id"])}
              for v in r.json().get("voices", [])]
    return jsonify(voices=voices)


@app.post("/api/eleven/clone")
def eleven_clone():
    """يعمل نسخة من صوت المستخدم (Instant Voice Cloning) ويرجّع voice_id."""
    form = request.form
    key = _eleven_key(form)
    if not key:
        return jsonify(error="محتاج ElevenLabs API key"), 400
    if form.get("consent") != "yes":
        return jsonify(error="لازم تأكد إن الصوت ده صوتك إنت أو معاك إذن صاحبه"), 400
    files = [f for f in request.files.getlist("files") if f and f.filename]
    if not files:
        return jsonify(error="سجّل صوتك أو ارفع ملف صوت الأول"), 400
    if len(files) > MAX_CLONE_FILES:
        return jsonify(error=f"أقصى عدد {MAX_CLONE_FILES} ملف"), 400
    name = (form.get("name") or "").strip()[:80] or "صوتي"

    multipart = [("files", (f.filename, f.stream.read(), f.mimetype or "application/octet-stream"))
                 for f in files]
    try:
        r = requests.post(
            f"{ELEVEN_API}/voices/add",
            headers={"xi-api-key": key},
            data={"name": name, "remove_background_noise": "true",
                  "description": "Egyptian Arabic voice clone",
                  "labels": '{"accent": "egyptian", "language": "ar"}'},
            files=multipart,
            timeout=180,
        )
    except requests.RequestException as exc:
        return jsonify(error=f"مش قادر أوصل لـ ElevenLabs: {exc}"), 502
    if r.status_code != 200:
        try:
            detail = r.json().get("detail")
            msg = detail.get("message") if isinstance(detail, dict) else detail
        except ValueError:
            msg = r.text[:200]
        return jsonify(error=f"ElevenLabs رفض عمل النسخة ({r.status_code}): {msg}"), 502
    return jsonify(voice_id=r.json().get("voice_id"), name=name)


@app.post("/api/tts")
def tts():
    data = request.get_json(silent=True) or request.form
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify(error="اكتب أي كلام الأول"), 400
    if len(text) > MAX_CHARS:
        return jsonify(error=f"الكلام طويل أوي، الحد الأقصى {MAX_CHARS} حرف"), 400

    engine = data.get("engine", "edge")
    try:
        if engine == "eleven":
            key = _eleven_key(data)
            voice_id = (data.get("voice_id") or "").strip()
            model = data.get("model") if data.get("model") in ELEVEN_MODELS else "eleven_v3"
            if not key:
                return jsonify(error="محتاج ElevenLabs API key"), 400
            if not re.fullmatch(r"[A-Za-z0-9]{10,40}", voice_id):
                return jsonify(error="اختار صوت من ElevenLabs أو حط Voice ID صحيح"), 400
            audio = eleven_synthesize(
                text, key, voice_id, model,
                stability=_clamp_float(data.get("stability"), 0, 1, 0.5),
                style=_clamp_float(data.get("style"), 0, 1, 0.3),
            )
        else:
            voice = EDGE_VOICES.get(data.get("voice", "salma"), EDGE_VOICES["salma"])
            rate = f"{_clamp_int(data.get('rate'), -50, 100):+d}%"
            pitch = f"{_clamp_int(data.get('pitch'), -50, 50):+d}Hz"
            audio = asyncio.run(edge_synthesize(text, voice, rate, pitch))
    except Exception as exc:  # network / service errors
        app.logger.exception("TTS failed")
        return jsonify(error=f"حصلت مشكلة في تحويل الصوت: {exc}"), 502
    if not audio:
        return jsonify(error="مفيش صوت رجع، جرب تاني"), 502

    return send_file(io.BytesIO(audio), mimetype="audio/mpeg",
                     as_attachment=False, download_name="voice.mp3")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
