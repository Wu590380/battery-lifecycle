# Hugging Face Spaces entry point — delegates to trade_platform.py
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
exec(open("trade_platform.py", encoding="utf-8").read())
