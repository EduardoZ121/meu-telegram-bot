import os
import time
import threading
import traceback
from flask import Flask, jsonify

app = Flask(__name__)
status = {"error": None, "traceback": None}

@app.route("/")
def home():
    return jsonify({"status": "ok"})

@app.route("/error")
def error():
    return f"<pre>{status['traceback']}</pre>"

def run_flask():
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

threading.Thread(target=run_flask, daemon=True).start()
time.sleep(2)

try:
    with open("bot.py", "r", encoding="utf-8") as f:
        code = f.read()
    exec(compile(code, "bot.py", "exec"), {"__name__": "__main__"})
except Exception as e:
    status["error"] = str(e)
    status["traceback"] = traceback.format_exc()
    print(status["traceback"])

while True:
    time.sleep(60)
