import time
import threading

# Global log storage
service_logs = {
    "llama": [],
    "whisper": [],
    "download": [],
    "tts": []
}

logs_lock = threading.Lock()

def add_log(service: str, message: str):
    with logs_lock:
        logs = service_logs.get(service, [])
        logs.append(f"[{time.strftime('%H:%M:%S')}] {message}")
        if len(logs) > 100:
            logs.pop(0)
        service_logs[service] = logs

def get_service_logs(service: str):
    with logs_lock:
        return service_logs.get(service, [])

def capture_output(service: str, process):
    """Monitor a subprocess and capture its stdout/stderr to the log system."""
    def monitor():
        for line in iter(process.stdout.readline, b''):
            if line:
                add_log(service, line.decode('utf-8', errors='ignore').strip())
        process.stdout.close()
    
    thread = threading.Thread(target=monitor, daemon=True)
    thread.start()
    return thread
