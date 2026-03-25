"""
API Logging & Monitoring - DermaCare AI
=====================================
Comprehensive request/response logging and performance monitoring.
"""
import time
import logging
import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from collections import defaultdict
from pathlib import Path
import threading

logger = logging.getLogger("DermaCare_AI.api_logging")

BASE_DIR = Path(__file__).parent.parent.parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

API_LOG_FILE = LOG_DIR / "api_requests.log"
ERROR_LOG_FILE = LOG_DIR / "errors.log"
PERF_LOG_FILE = LOG_DIR / "performance.log"


class RequestLogger:
    """Thread-safe request logging."""
    
    def __init__(self):
        self._lock = threading.Lock()
        self._request_count = 0
        self._error_count = 0
        self._total_duration = 0.0
        self._endpoint_stats = defaultdict(lambda: {"count": 0, "errors": 0, "total_time": 0.0})
    
    def log_request(self, method: str, path: str, status_code: int, 
                   duration_ms: float, user: Optional[str] = None,
                   ip: Optional[str] = None, error: Optional[str] = None):
        """Log an API request."""
        with self._lock:
            self._request_count += 1
            self._total_duration += duration_ms
            
            endpoint = f"{method} {path}"
            self._endpoint_stats[endpoint]["count"] += 1
            self._endpoint_stats[endpoint]["total_time"] += duration_ms
            
            if status_code >= 400 or error:
                self._error_count += 1
                self._endpoint_stats[endpoint]["errors"] += 1
            
            log_entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "method": method,
                "path": path,
                "status": status_code,
                "duration_ms": round(duration_ms, 2),
                "user": user,
                "ip": ip,
                "error": error
            }
            
            self._write_log(API_LOG_FILE, log_entry)
            
            if error or status_code >= 500:
                self._write_log(ERROR_LOG_FILE, log_entry)
    
    def log_performance(self, endpoint: str, duration_ms: float, 
                       cache_hit: bool = False):
        """Log performance metrics."""
        perf_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "endpoint": endpoint,
            "duration_ms": round(duration_ms, 2),
            "cache_hit": cache_hit
        }
        self._write_log(PERF_LOG_FILE, perf_entry)
    
    def _write_log(self, filepath: Path, entry: Dict[str, Any]):
        """Write log entry to file."""
        try:
            with open(filepath, 'a', encoding='utf-8') as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            logger.error(f"Failed to write log: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current statistics."""
        with self._lock:
            avg_duration = self._total_duration / self._request_count if self._request_count > 0 else 0
            error_rate = (self._error_count / self._request_count * 100) if self._request_count > 0 else 0
            
            return {
                "total_requests": self._request_count,
                "total_errors": self._error_count,
                "error_rate_percent": round(error_rate, 2),
                "avg_duration_ms": round(avg_duration, 2),
                "endpoints": dict(self._endpoint_stats)
            }
    
    def reset_stats(self):
        """Reset statistics."""
        with self._lock:
            self._request_count = 0
            self._error_count = 0
            self._total_duration = 0.0
            self._endpoint_stats.clear()


request_logger = RequestLogger()


class PerformanceMonitor:
    """Monitor API performance metrics."""
    
    def __init__(self):
        self._timings = defaultdict(list)
        self._lock = threading.Lock()
    
    def record_timing(self, endpoint: str, duration_ms: float):
        """Record timing for an endpoint."""
        with self._lock:
            timings = self._timings[endpoint]
            timings.append(duration_ms)
            
            if len(timings) > 100:
                timings.pop(0)
    
    def get_percentile(self, endpoint: str, percentile: int) -> float:
        """Get percentile timing for endpoint."""
        with self._lock:
            timings = sorted(self._timings.get(endpoint, [0]))
            if not timings:
                return 0.0
            
            idx = int(len(timings) * percentile / 100)
            return timings[min(idx, len(timings) - 1)]
    
    def get_stats(self, endpoint: str) -> Dict[str, float]:
        """Get timing statistics for endpoint."""
        with self._lock:
            timings = self._timings.get(endpoint, [])
            if not timings:
                return {"count": 0, "min": 0, "max": 0, "avg": 0, "p50": 0, "p95": 0, "p99": 0}
            
            return {
                "count": len(timings),
                "min": round(min(timings), 2),
                "max": round(max(timings), 2),
                "avg": round(sum(timings) / len(timings), 2),
                "p50": round(self.get_percentile(endpoint, 50), 2),
                "p95": round(self.get_percentile(endpoint, 95), 2),
                "p99": round(self.get_percentile(endpoint, 99), 2)
            }


performance_monitor = PerformanceMonitor()


class ErrorTracker:
    """Track and categorize errors."""
    
    def __init__(self):
        self._errors = defaultdict(int)
        self._lock = threading.Lock()
    
    def track_error(self, error_type: str, message: str):
        """Track an error occurrence."""
        with self._lock:
            key = f"{error_type}: {message[:100]}"
            self._errors[key] += 1
    
    def get_top_errors(self, limit: int = 10) -> list:
        """Get most frequent errors."""
        with self._lock:
            sorted_errors = sorted(self._errors.items(), key=lambda x: x[1], reverse=True)
            return [{"error": k, "count": v} for k, v in sorted_errors[:limit]]


error_tracker = ErrorTracker()


def log_api_request(method: str, path: str, status_code: int,
                   duration_ms: float, user: Optional[str] = None,
                   ip: Optional[str] = None, error: Optional[str] = None):
    """Convenience function to log API request."""
    request_logger.log_request(method, path, status_code, duration_ms, user, ip, error)
    performance_monitor.record_timing(path, duration_ms)
    
    if error:
        error_tracker.track_error(type(error).__name__ if hasattr(error, '__class__') else 'Unknown', str(error))


def get_api_stats() -> Dict[str, Any]:
    """Get API statistics."""
    return request_logger.get_stats()


def get_endpoint_stats(endpoint: str) -> Dict[str, float]:
    """Get statistics for specific endpoint."""
    return performance_monitor.get_stats(endpoint)


def get_error_summary() -> list:
    """Get error summary."""
    return error_tracker.get_top_errors()
