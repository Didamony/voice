# نقطة الدخول على Vercel: بتشغّل نفس تطبيق Flask اللي في app.py
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app  # noqa: E402,F401
