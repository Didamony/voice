#!/usr/bin/env bash
# تشغيل التطبيق على ماك أو لينكس: ./run.sh
set -e
cd "$(dirname "$0")"
[ -d .venv ] || python3 -m venv .venv
. .venv/bin/activate
pip install -q -r requirements.txt
( sleep 2; (open http://localhost:5000 || xdg-open http://localhost:5000) >/dev/null 2>&1 ) &
python app.py
