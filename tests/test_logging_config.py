"""Structured JSON-lines logging — real formatter, real root-logger wiring."""

from __future__ import annotations

import json
import logging

from libs.logging_config import JSONLinesFormatter, configure_logging


def make_record(msg: str = "hello", **extra) -> logging.LogRecord:
    record = logging.LogRecord(
        name="incidentsherpa.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=msg,
        args=(),
        exc_info=None,
    )
    for key, value in extra.items():
        setattr(record, key, value)
    return record


class TestJSONLinesFormatter:
    def test_emits_one_parseable_json_line_with_core_fields(self):
        line = JSONLinesFormatter().format(make_record("alert received"))
        assert "\n" not in line
        entry = json.loads(line)
        assert entry["level"] == "INFO"
        assert entry["logger"] == "incidentsherpa.test"
        assert entry["msg"] == "alert received"
        assert entry["timestamp"].endswith("+00:00")  # UTC ISO-8601

    def test_extra_fields_become_structured_keys(self):
        line = JSONLinesFormatter().format(
            make_record("screened", incident_id="inc-1", latency_ms=42.5)
        )
        entry = json.loads(line)
        assert entry["incident_id"] == "inc-1"
        assert entry["latency_ms"] == 42.5

    def test_unserialisable_extra_never_kills_the_line(self):
        line = JSONLinesFormatter().format(make_record("odd", weird=object()))
        assert "odd" in json.loads(line)["msg"]

    def test_exception_info_is_included(self):
        try:
            raise ValueError("boom")
        except ValueError:
            import sys

            record = make_record("failed")
            record.exc_info = sys.exc_info()
        entry = json.loads(JSONLinesFormatter().format(record))
        assert "ValueError: boom" in entry["exc_info"]

    def test_message_interpolation_uses_record_args(self):
        record = logging.LogRecord(
            "n", logging.WARNING, __file__, 1, "pipeline failed for %s", ("inc-9",), None
        )
        assert json.loads(JSONLinesFormatter().format(record))["msg"] == (
            "pipeline failed for inc-9"
        )


class TestConfigureLogging:
    def _our_handlers(self) -> list[logging.Handler]:
        return [
            h
            for h in logging.getLogger().handlers
            if getattr(h, "_incidentsherpa_json", False)
        ]

    def test_idempotent_single_handler(self):
        before = self._our_handlers()
        try:
            configure_logging()
            configure_logging()
            configure_logging()
            assert len(self._our_handlers()) == 1
        finally:
            for handler in self._our_handlers():
                if handler not in before:
                    logging.getLogger().removeHandler(handler)

    def test_level_from_env(self, monkeypatch):
        monkeypatch.setenv("LOG_LEVEL", "debug")
        root = logging.getLogger()
        previous_level = root.level
        before = self._our_handlers()
        try:
            configure_logging()
            assert root.level == logging.DEBUG
        finally:
            root.setLevel(previous_level)
            for handler in self._our_handlers():
                if handler not in before:
                    logging.getLogger().removeHandler(handler)
