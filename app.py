"""تطبيق تحويل النص المكتوب إلى صوت باللهجة المصرية.

بيستخدم أصوات Microsoft Edge العصبية المصرية (مجانية ومن غير API key):
  - ar-EG-SalmaNeural  (سلمى - صوت ست)
  - ar-EG-ShakirNeural (شاكر - صوت راجل)
"""
import asyncio
import io
import re

import edge_tts
from flask import Flask, jsonify, render_template, request, send_file

VOICES = {
    "salma": "ar-EG-SalmaNeural",
    "shakir": "ar-EG-ShakirNeural",
}
MAX_CHARS = 5000

app = Flask(__name__)


def _percent(value, default=0, lo=-50, hi=100):
    try:
        v = int(value)
    except (TypeError, ValueError):
        v = default
    v = max(lo, min(hi, v))
    return f"{v:+d}%"


def _hz(value, default=0, lo=-50, hi=50):
    try:
        v = int(value)
    except (TypeError, ValueError):
        v = default
    v = max(lo, min(hi, v))
    return f"{v:+d}Hz"


async def synthesize(text, voice, rate="+0%", pitch="+0Hz"):
    communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
    buf = io.BytesIO()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            buf.write(chunk["data"])
    return buf.getvalue()


@app.get("/")
def index():
    return render_template("index.html", max_chars=MAX_CHARS)


@app.post("/api/tts")
def tts():
    data = request.get_json(silent=True) or request.form
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify(error="اكتب أي كلام الأول"), 400
    if len(text) > MAX_CHARS:
        return jsonify(error=f"الكلام طويل أوي، الحد الأقصى {MAX_CHARS} حرف"), 400

    voice = VOICES.get(data.get("voice", "salma"), VOICES["salma"])
    rate = _percent(data.get("rate"))
    pitch = _hz(data.get("pitch"))

    try:
        audio = asyncio.run(synthesize(text, voice, rate, pitch))
    except Exception as exc:  # network / service errors
        app.logger.exception("TTS failed")
        return jsonify(error=f"حصلت مشكلة في تحويل الصوت: {exc}"), 502
    if not audio:
        return jsonify(error="مفيش صوت رجع، جرب تاني"), 502

    safe = re.sub(r"[^\w]+", "_", text[:30]).strip("_") or "voice"
    return send_file(
        io.BytesIO(audio),
        mimetype="audio/mpeg",
        as_attachment=False,
        download_name=f"{safe}.mp3",
    )


if __name__ == "__main__":
    import os
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
