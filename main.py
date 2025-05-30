import os
import time
import threading
from flask import Flask, jsonify
import requests
from collections import defaultdict, Counter
from typing import Dict, List

app = Flask(__name__)

# Конфигурация из переменных окружения
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

# Глобальные структуры для хранения метрик
all_metrics = {
    "current_site": None,
    "sites": {},  # {url: {"metrics": Counter, "start_time": float, "end_time": float}}
    "aggregated": Counter(),
    "active_workers": 0
}
metrics_lock = threading.Lock()
stop_event = threading.Event()

def categorize_code(code: int) -> str:
    """Преобразует код в строку: либо один из TRACK_CODES, либо 'other'"""
    code_str = str(code)
    if code_str in {str(c) for c in TRACK_CODES}:
        return code_str
    return "other"

def worker_loop(url: str):
    """Цикл нагрузки для одного URL"""
    session = requests.Session()
    
    with metrics_lock:
        all_metrics["sites"][url] = {
            "metrics": Counter({str(code): 0 for code in TRACK_CODES} | {"other": 0, "error": 0}),
            "start_time": time.time(),
            "end_time": None
        }
        all_metrics["active_workers"] += 1
    
    try:
        while not stop_event.is_set() and all_metrics["current_site"] == url:
            try:
                r = session.get(url, timeout=5)
                key = categorize_code(r.status_code)
            except Exception:
                key = "error"
            
            with metrics_lock:
                all_metrics["sites"][url]["metrics"][key] += 1
                all_metrics["aggregated"][key] += 1
    
    finally:
        with metrics_lock:
            all_metrics["sites"][url]["end_time"] = time.time()
            all_metrics["active_workers"] -= 1

def run_load_test():
    """Запускает нагрузочное тестирование для каждого URL последовательно"""
    for url in TARGET_URLS:
        with metrics_lock:
            all_metrics["current_site"] = url
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
        
        # Ждем завершения всех воркеров
        while True:
            with metrics_lock:
                if all_metrics["active_workers"] == 0:
                    break
            time.sleep(0.1)
        
        print(f"Completed test for {url}")

# Запускаем тест в фоновом потоке
threading.Thread(target=run_load_test, daemon=True).start()

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def report(path):
    """Возвращает текущую статистику"""
    with metrics_lock:
        # Формируем детализированный отчет
        report = {
            "current_site": all_metrics["current_site"],
            "sites": {},
            "aggregated": dict(all_metrics["aggregated"]),
            "timestamp": time.time()
        }
        
        # Добавляем детали по каждому сайту
        for url, data in all_metrics["sites"].items():
            site_report = {
                "metrics": dict(data["metrics"]),
                "start_time": data["start_time"],
                "end_time": data["end_time"],
                "duration": (data["end_time"] - data["start_time"]) if data["end_time"] else None
            }
            report["sites"][url] = site_report
        
        return jsonify(report)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)