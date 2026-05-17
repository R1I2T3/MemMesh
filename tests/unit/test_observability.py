import json
import logging
import pytest
from io import StringIO
from contextvars import copy_context
from utils.observability import (
    RequestContext,
    StepRecord,
    JSONFormatter,
    start_request,
    log_step,
    end_request,
    _request_ctx,
)


@pytest.fixture
def log_capture():
    handler = logging.StreamHandler(StringIO())
    handler.setFormatter(JSONFormatter())
    logger = logging.getLogger("observability_test")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    yield handler
    logger.removeHandler(handler)


@pytest.mark.unit
def test_json_formatter_outputs_valid_json():
    formatter = JSONFormatter()
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="", lineno=0,
        msg="test message", args=(), exc_info=None,
    )
    record.event = "test_event"
    record.request_id = "req-123"
    output = formatter.format(record)
    parsed = json.loads(output)
    assert "timestamp" in parsed
    assert "level" in parsed
    assert "event" in parsed
    assert parsed["event"] == "test_event"
    assert parsed["request_id"] == "req-123"


@pytest.mark.unit
def test_start_request_creates_context():
    ctx = start_request("POST", "/query")
    assert isinstance(ctx, RequestContext)
    assert ctx.request_id is not None
    assert len(ctx.request_id) > 0
    assert ctx.steps == []


@pytest.mark.unit
def test_log_step_records_start_and_end():
    ctx = start_request("POST", "/query")
    with log_step(ctx, "vector_search"):
        pass
    assert len(ctx.steps) == 1
    step = ctx.steps[0]
    assert step.name == "vector_search"
    assert step.end_time is not None
    assert step.end_time >= step.start_time


@pytest.mark.unit
def test_log_step_captures_metrics():
    ctx = start_request("POST", "/query")
    with log_step(ctx, "multi_hop", hops_taken=3, entities=5):
        pass
    step = ctx.steps[0]
    assert step.metrics["hops_taken"] == 3
    assert step.metrics["entities"] == 5


@pytest.mark.unit
def test_end_request_produces_summary():
    ctx = start_request("POST", "/query")
    with log_step(ctx, "vector_search"):
        pass
    summary = end_request(ctx, "ok", citation_count=3)
    assert summary["status"] == "ok"
    assert summary["citation_count"] == 3
    assert summary["total_duration_ms"] > 0
    assert summary["step_count"] == 1


@pytest.mark.unit
def test_request_context_propagates_via_contextvar():
    ctx = start_request("GET", "/health")
    retrieved = _request_ctx.get()
    assert retrieved is ctx
    assert retrieved.request_id == ctx.request_id
