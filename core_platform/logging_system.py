import threading
import time

class SystemLogger:
    def __init__(self, max_logs=250):
        self.logs = []
        self.lock = threading.Lock()
        self.max_logs = max_logs

    def log(self, message):
        timestamp = time.strftime("%H:%M:%S")
        formatted = f"[{timestamp}] {message}"
        print(formatted) # Output to terminal
        with self.lock:
            self.logs.append(formatted)
            if len(self.logs) > self.max_logs:
                self.logs.pop(0)

    def get_logs(self):
        with self.lock:
            return list(self.logs)

    def clear(self):
        with self.lock:
            self.logs.clear()

# Global logger singleton
sys_logger = SystemLogger()
