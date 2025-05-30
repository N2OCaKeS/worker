import config
import os
import time
import threading
from flask import Flask, jsonify
import requests
from collections import Counter


metrics = Counter({str(code): 0 for code in config.TRACK_CODES} | {"other": 0, "error": 0})
lock = threading.Lock()
stop_event = threading.Event()

def categorize_code(code):
    """Преобразует код в строку: либо один из TRACK_CODES, либо 'other'"""
    code_str = str(code)
    if code_str in metrics and code_str not in ("other", "error"):
        return code_str
    return "other"

def worker_loop():
    session = requests.Session()
    while not stop_event.is_set():
        for url in config.TARGET_URLS:
            try:
                r = session.get(url, timeout=5)
                key = categorize_code(r.status_code)
            except Exception:
                key = "error"
            with lock:
                metrics[key] += 1

def run_load_test():
    threads = []
    for _ in range(config.THREADS):
        t = threading.Thread(target=worker_loop, daemon=True)
        t.start()
        threads.append(t)
    time.sleep(config.DURATION)
    stop_event.set()
    for t in threads:
        t.join()


# Старт теста в фоне
threading.Thread(target=run_load_test, daemon=True).start()

# Запускаем Flask
app = Flask(__name__)

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def report(path):
    with lock:
        return jsonify(metrics)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)        