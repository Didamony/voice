# صوت مصري 🎙️

تطبيق ويب بسيط: تكتب كلام، يحوّله لصوت باللهجة المصرية وتقدر تسمعه أو تنزّله MP3.

بيستخدم أصوات Microsoft Edge العصبية المصرية (مجانًا ومن غير API key):
- **سلمى** `ar-EG-SalmaNeural` — صوت ست
- **شاكر** `ar-EG-ShakirNeural` — صوت راجل

## محرك ElevenLabs (صوت فيه روح)

في الصفحة اختار تاب **ElevenLabs**:
1. اعمل حساب على elevenlabs.io وخد الـ API key من Settings → API Keys، وحطه في الصفحة
   (بيتحفظ في المتصفح بتاعك بس). أو حطه على السيرفر في متغير البيئة `ELEVENLABS_API_KEY`.
2. من الـ Voice Library في ElevenLabs دوّر على صوت مصري (Egyptian) وضيفه لحسابك،
   وبعدين دوس "هات أصواتي" واختاره.
3. موديل `eleven_v3` هو اللي فيه أكتر إحساس، وتقدر تكتب جوه الكلام تاجات زي
   `[laughs]` أو `[whispers]` أو `[excited]`.

## التشغيل على الكمبيوتر (لازم يكون عليه Python 3 ونت)

- **ويندوز:** دبل كليك على `run.bat`
- **ماك / لينكس:** `./run.sh`

هينزّل المكتبات لوحده ويفتح المتصفح على http://localhost:5000

أو يدوي:
```bash
pip install -r requirements.txt
python app.py
```

## تشغيله أونلاين (عشان تفتحه من الموبايل)

المشروع فيه `Dockerfile` و`render.yaml`، فتقدر ترفعه مجانًا على [Render](https://render.com):
New → Blueprint → اختار الريبو ده والفرع → حط `ELEVENLABS_API_KEY` لو عايز (اختياري) → Deploy. هيديك لينك تفتحه من أي موبايل.

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
