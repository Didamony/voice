# صوت مصري 🎙️

تطبيق ويب بسيط: تكتب كلام، يحوّله لصوت باللهجة المصرية وتقدر تسمعه أو تنزّله MP3.

بيستخدم أصوات Microsoft Edge العصبية المصرية (مجانًا ومن غير API key):
- **سلمى** `ar-EG-SalmaNeural` — صوت ست
- **شاكر** `ar-EG-ShakirNeural` — صوت راجل

## التشغيل

```bash
pip install -r requirements.txt
python app.py
```

وافتح المتصفح على: http://localhost:5000

## الـ API

```bash
curl -X POST http://localhost:5000/api/tts \
  -H "Content-Type: application/json" \
  -d '{"text":"إزيك يا صاحبي؟ عامل إيه؟","voice":"shakir","rate":0,"pitch":0}' \
  -o out.mp3
```

| الحقل  | القيم |
|--------|-------|
| `text`  | النص (لحد 5000 حرف) |
| `voice` | `salma` أو `shakir` |
| `rate`  | السرعة من -50 لـ 100 (نسبة مئوية) |
| `pitch` | طبقة الصوت من -50 لـ 50 (Hz) |

## نصيحة
عشان الصوت يطلع مصري أكتر، اكتب بالعامية المصرية زي ما بتتكلم
(مثلاً "عامل إيه" بدل "كيف حالك")، وحط التشكيل على الكلمات اللي ممكن تتقري غلط.
