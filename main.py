import os
import time
import threading
from flask import Flask, jsonify
import requests
from collections import defaultdict, Counter
from typing import Dict, List

# ===== НАСТРОЙКИ ТЕСТА (одинаковые на всех нодах) =====
TARGET_URLS = os.getenv("TARGET_URLS", "https://example.com").split(",")
THREADS = int(os.getenv("THREADS", "10"))
DURATION = int(os.getenv("DURATION", "60"))  # в секундах

TRACK_CODES = [
    100, 101,                 # Informational
    200, 201, 202, 204,       # Success
    301, 302, 304,            # Redirects
    400, 401, 403, 404, 408, 429,  # Client errors
    500, 502, 503, 504        # Server errors
]

# ===== СТРУКТУРА ДЛЯ ХРАНЕНИЯ РЕЗУЛЬТАТОВ =====
test_results = {
    "config": {
        "target_urls": TARGET_URLS,
        "threads": THREADS,
        "duration": DURATION,
        "track_codes": TRACK_CODES
    },
    "sites": {}  # {url: Counter()}
}
results_lock = threading.Lock()
current_site = None
stop_event = threading.Event()

app = Flask(__name__)

def categorize_code(code: int) -> str:
    """Преобразует код в строку: либо один из TRACK_CODES, либо 'other'"""
    code_str = str(code)
    if code_str in {str(c) for c in TRACK_CODES}:
        return code_str
    return "other"

def worker_loop(url: str):
    """Цикл нагрузки для одного URL"""
    session = requests.Session()
    
    # Инициализация счетчика для сайта
    with results_lock:
        if url not in test_results["sites"]:
            test_results["sites"][url] = Counter({str(code): 0 for code in TRACK_CODES} | {"other": 0, "error": 0})
    
    # Основной цикл запросов
    while not stop_event.is_set() and current_site == url:
        try:
            r = session.get(url, timeout=5)
            key = categorize_code(r.status_code)
        except Exception:
            key = "error"
        
        with results_lock:
            test_results["sites"][url][key] += 1

def run_load_test():
    """Запускает нагрузочное тестирование для каждого URL последовательно"""
    global current_site
    
    for url in TARGET_URLS:
        current_site = url
        stop_event.clear()
        
        print(f"Starting test for {url} for {DURATION} seconds")
        
        # Запускаем воркеры
        threads = []
        for _ in range(THREADS):
            t = threading.Thread(target=worker_loop, args=(url,), daemon=True)
            t.start()
            threads.append(t)
        
        # Ждем указанное время
        time.sleep(DURATION)
        
        # Останавливаем воркеры для этого URL
        stop_event.set()
        for t in threads:
            t.join()
        
        print(f"Completed test for {url}")

# Запускаем тест в фоновом потоке
threading.Thread(target=run_load_test, daemon=True).start()

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def report(path):
    """Возвращает текущую статистику"""
    with results_lock:
        # Создаем копию результатов для ответа
        response = {
            "config": test_results["config"],
            "current_site": current_site,
            "sites": {url: dict(counter) for url, counter in test_results["sites"].items()}
        }
        return jsonify(response)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)