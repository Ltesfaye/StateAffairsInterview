import logging
import json
import sys
import uuid
import os
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, Optional

class JsonFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging"""
    
    STANDARD_ATTRS = {
        'name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 'filename',
        'module', 'exc_info', 'exc_text', 'stack_info', 'lineno', 'funcName',
        'created', 'msecs', 'relativeCreated', 'thread', 'threadName',
        'processName', 'process', 'message', 'extra_data', 'trace_id'
    }

    def __init__(self, service_name: str):
        super().__init__()
        self.service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "service": self.service_name,
            "message": record.getMessage(),
            "logger": record.name,
        }

        # Include trace_id if present
        if hasattr(record, "trace_id"):
            log_data["trace_id"] = record.trace_id
        
        # Include any other extra fields passed via extra={...}
        for key, value in record.__dict__.items():
            if key not in self.STANDARD_ATTRS and not key.startswith('_'):
                log_data[key] = value
        
        # Support for legacy extra_data dict
        if hasattr(record, "extra_data") and isinstance(record.extra_data, dict):
            log_data.update(record.extra_data)

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)

def get_logger(name: str, service_name: str = "stateaffair-worker") -> logging.Logger:
    """Get a configured JSON logger"""
    logger = logging.getLogger(name)
    
    # Avoid duplicate handlers
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = JsonFormatter(service_name)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
        
    return logger

def setup_logger(level: str = "INFO", log_file: Optional[Path] = None) -> logging.Logger:
    """Compatibility shim for old setup_logger calls"""
    return get_logger("root", service_name="migration-shim")

def generate_trace_id() -> str:
    """Generate a unique correlation ID for tracking tasks across services"""
    return str(uuid.uuid4())
