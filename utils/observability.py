import json
import logging
import time
import uuid
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class StepRecord:
    name: str
    start_time: float
    end_time: Optional[float] = None
    metrics: dict = field(default_factory=dict)


@dataclass
class RequestContext:
    request_id: str
    start_time: float
    method: str
    path: str
    steps: list = field(default_factory=list)


_request_ctx: ContextVar[Optional[RequestContext]] = ContextVar("request_ctx", default=None)


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "message": record.getMessage(),
        }
        if hasattr(record, "event"):
            log_data["event"] = record.event
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id
        if hasattr(record, "duration_ms"):
            log_data["duration_ms"] = record.duration_ms
        if hasattr(record, "step"):
            log_data["step"] = record.step
        for key in ("hops_taken", "entities_expanded", "result_count", "citation_count", "status", "step_count", "total_duration_ms"):
            if hasattr(record, key):
                log_data[key] = getattr(record, key)
        return json.dumps(log_data)


def _configure_json_logging():
    """Configure the root logger to use JSONFormatter. Safe to call multiple times."""
    root = logging.getLogger()
    for h in root.handlers:
        if isinstance(h.formatter, JSONFormatter):
            return
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    root.addHandler(handler)
    root.setLevel(logging.INFO)


def start_request(method: str, path: str) -> RequestContext:
    ctx = RequestContext(
        request_id=str(uuid.uuid4()),
        start_time=time.time(),
        method=method,
        path=path,
    )
    _request_ctx.set(ctx)
    logger = logging.getLogger(__name__)
    extra = {"event": "request_start", "request_id": ctx.request_id}
    logger.info("Request started", extra=extra)
    return ctx


class _StepContextManager:
    def __init__(self, ctx: RequestContext, name: str, **metrics):
        self.ctx = ctx
        self.name = name
        self.metrics = metrics

    def __enter__(self):
        self.start = time.time()
        logger = logging.getLogger(__name__)
        extra = {"event": "step_start", "request_id": self.ctx.request_id, "step": self.name}
        logger.info(f"Step started: {self.name}", extra=extra)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        end = time.time()
        duration_ms = round((end - self.start) * 1000, 2)
        record = StepRecord(
            name=self.name,
            start_time=self.start,
            end_time=end,
            metrics=self.metrics,
        )
        self.ctx.steps.append(record)
        logger = logging.getLogger(__name__)
        extra = {
            "event": "step_end",
            "request_id": self.ctx.request_id,
            "step": self.name,
            "duration_ms": duration_ms,
        }
        extra.update(self.metrics)
        if "result_count" in self.metrics:
            extra["result_count"] = self.metrics["result_count"]
        logger.info(f"Step ended: {self.name}", extra=extra)
        return False


def log_step(ctx: RequestContext, name: str, **metrics) -> _StepContextManager:
    return _StepContextManager(ctx, name, **metrics)


def end_request(ctx: RequestContext, status: str, **metrics) -> dict:
    total_ms = round((time.time() - ctx.start_time) * 1000, 2)
    summary = {
        "request_id": ctx.request_id,
        "status": status,
        "total_duration_ms": total_ms,
        "step_count": len(ctx.steps),
    }
    summary.update(metrics)
    logger = logging.getLogger(__name__)
    extra = {"event": "request_end", "request_id": ctx.request_id, "status": status, "total_duration_ms": total_ms, "step_count": len(ctx.steps)}
    extra.update(metrics)
    logger.info("Request ended", extra=extra)
    return summary
