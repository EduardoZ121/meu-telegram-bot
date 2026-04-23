cat > start.py << 'STARTEOF'
#!/usr/bin/env python3
import os, sys, threading, time, traceback
from flask import Flask, jsonify

_app = Flask(__name__)
_status = {"phase": "bootstrap", "error": None, "traceback": None, "started_at": time.time()}

@_app.route("/")
def _root():
    return jsonify({"status": "ok", **_status})

@_app.route("/health")
def _health():
    code = 200 if _status["error"] is None else 500
    return jsonify(_status), code

@_app.route("/error")
def _error():
    tb = _status.get("traceback") or "No error."
    return f"<pre>{tb}</pre>", 200

def _run_flask():
    port = int(os.getenv("PORT", 10000))
    _app.run(host="0.0.0.0", port=port)

threading.Thread(target=_run_flask, daemon=True).start()
time.sleep(2)

try:
    with open("bot.py", "r", encoding="utf-8") as f:
        code = f.read()
    exec(compile(code, "bot.py", "exec"), {"__name__": "__main__"})
except Exception as e:
    _status["error"] = str(e)
    _status["traceback"] = traceback.format_exc()
    print(_status["traceback"])

while True:
    time.sleep(60)
STARTEOF
