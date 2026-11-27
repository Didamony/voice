# انسخ الملف ده كله والزقه في ملف اسمه Dockerfile جوه الـ Space بتاعتك على Hugging Face
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
RUN git clone --depth 1 --branch claude/vibrant-johnson-oakxy8 https://github.com/didamony/voice /app
WORKDIR /app
RUN pip install --no-cache-dir -r requirements.txt gunicorn
ENV PORT=7860
EXPOSE 7860
CMD gunicorn -w 2 -b 0.0.0.0:$PORT --timeout 120 app:app
