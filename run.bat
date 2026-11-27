@echo off
REM تشغيل التطبيق على ويندوز: دبل كليك على الملف ده
cd /d "%~dp0"
if not exist .venv python -m venv .venv
call .venv\Scripts\activate.bat
pip install -q -r requirements.txt
start "" http://localhost:5000
python app.py
pause
