from datetime import datetime
from unittest.mock import Mock, patch

from praval.observability.export.console_viewer import (
    ConsoleViewer,
    print_traces,
    show_recent_traces,
)
from praval.observability.export.otlp_exporter import (
    OTLPExporter,
    export_traces_to_otlp,
)


def test_console_viewer_displays_trace(capsys):
    viewer = ConsoleViewer(use_colors=False)
    spans = [
        {
            "span_id": "1",
            "trace_id": "t1",
            "name": "root",
            "kind": "INTERNAL",
            "duration_ms": 1.2,
            "status": "ok",
            "attributes": {},
            "events": [],
        }
    ]
    viewer.display_trace("t1", spans)
    out = capsys.readouterr().out
    assert "Trace: t1" in out
    assert "root" in out


def test_console_viewer_displays_tree_events_statuses_and_summary(capsys):
    viewer = ConsoleViewer(use_colors=False)
    spans = [
        {
            "span_id": "root",
            "trace_id": "trace",
            "name": "root",
            "kind": "SERVER",
            "duration_ms": 4.0,
            "status": "ERROR",
            "attributes": {"agent": "researcher"},
            "events": [
                {
                    "name": "exception",
                    "attributes": {"exception.type": "ValueError"},
                }
            ],
        },
        {
            "span_id": "child",
            "parent_span_id": "root",
            "trace_id": "trace",
            "name": "child",
            "kind": "CLIENT",
            "duration_ms": 0,
            "status": "UNSET",
            "attributes": {},
            "events": [{"name": "retry", "attributes": {}}],
        },
    ]

    viewer.display_traces(spans)
    viewer.display_summary(spans)
    output = capsys.readouterr().out

    assert "root" in output and "child" in output
    assert "ValueError" in output and "retry" in output
    assert "Errors: 1" in output
    assert "Average duration: 4.00ms" in output


def test_console_viewer_empty_paths(capsys):
    viewer = ConsoleViewer(use_colors=False)
    viewer.display_trace("missing", [])
    viewer.display_summary([])
    output = capsys.readouterr().out
    assert "No spans found" in output
    assert "No spans to display" in output


def test_print_traces_resolves_recent_trace_ids_and_convenience_wrapper(capsys):
    span = {
        "span_id": "s",
        "trace_id": "t",
        "name": "operation",
        "status": "OK",
        "duration_ms": 1.0,
    }
    store = Mock()
    store.get_recent_traces.return_value = ["t"]
    store.get_trace.return_value = [span]

    with patch("praval.observability.storage.get_trace_store", return_value=store):
        print_traces(summary_only=True, use_colors=False)
        print_traces(trace_ids=["t"], use_colors=False)

    output = capsys.readouterr().out
    assert "Trace Summary" in output
    assert "operation" in output
    assert store.get_trace.call_count == 2

    with patch("praval.observability.export.console_viewer.print_traces") as print_mock:
        show_recent_traces(limit=3, use_colors=False)
    print_mock.assert_called_once_with(limit=3, use_colors=False)


def test_print_traces_handles_no_recent_spans(capsys):
    store = Mock()
    store.get_recent_traces.return_value = []
    with patch("praval.observability.storage.get_trace_store", return_value=store):
        print_traces(use_colors=False)
    assert "No traces found" in capsys.readouterr().out


def test_otlp_exporter_build_payload():
    exporter = OTLPExporter("http://localhost")
    spans = [
        {
            "trace_id": "trace1",
            "span_id": "span1",
            "parent_span_id": None,
            "name": "op",
            "kind": "INTERNAL",
            "start_time": 1,
            "end_time": 2,
            "duration_ms": 1.0,
            "attributes": {"k": "v"},
            "events": [],
            "status": "ok",
            "status_message": "",
        }
    ]
    payload = exporter._build_otlp_payload(spans)
    assert payload["resourceSpans"]


def test_otlp_exporter_export_spans_success(monkeypatch):
    class Resp:
        status_code = 200
        text = "ok"

    class FakeRequests:
        @staticmethod
        def post(*args, **kwargs):
            return Resp()

    monkeypatch.setitem(__import__("sys").modules, "requests", FakeRequests)

    exporter = OTLPExporter("http://localhost")
    assert exporter.export_spans(
        [
            {
                "trace_id": "t",
                "span_id": "s",
                "name": "n",
                "kind": "INTERNAL",
                "start_time": 1,
                "end_time": 2,
                "duration_ms": 1.0,
                "attributes": {},
                "events": [],
                "status": "ok",
                "status_message": "",
            }
        ]
    )


def test_otlp_exporter_export_spans_failure(monkeypatch):
    class Resp:
        status_code = 500
        text = "fail"

    class FakeRequests:
        @staticmethod
        def post(*args, **kwargs):
            return Resp()

    monkeypatch.setitem(__import__("sys").modules, "requests", FakeRequests)

    exporter = OTLPExporter("http://localhost")
    assert (
        exporter.export_spans(
            [
                {
                    "trace_id": "t",
                    "span_id": "s",
                    "name": "n",
                    "kind": "INTERNAL",
                    "start_time": 1,
                    "end_time": 2,
                    "duration_ms": 1.0,
                    "attributes": {},
                    "events": [],
                    "status": "ok",
                    "status_message": "",
                }
            ]
        )
        is False
    )


def test_otlp_exporter_empty_batch_and_request_exception(monkeypatch):
    exporter = OTLPExporter("http://localhost")
    assert exporter.export_spans([]) is True

    class FakeRequestException(Exception):
        pass

    class FakeRequests:
        RequestException = FakeRequestException

        @staticmethod
        def post(*args, **kwargs):
            raise FakeRequestException("collector unavailable")

    monkeypatch.setitem(__import__("sys").modules, "requests", FakeRequests)
    assert exporter.export_spans([{"trace_id": "t"}]) is False


def test_otlp_conversion_covers_types_timestamps_events_and_invalid_hex():
    exporter = OTLPExporter("http://localhost")
    attributes = exporter._attributes_to_otlp(
        {"bool": True, "int": 2, "float": 1.5, "text": "value"}
    )
    assert {next(iter(item["value"])) for item in attributes} == {
        "boolValue",
        "intValue",
        "doubleValue",
        "stringValue",
    }

    now = datetime.now()
    assert exporter._datetime_to_unix_nano(1.5) == 1_500_000_000
    assert exporter._datetime_to_unix_nano(now) > 0
    assert exporter._datetime_to_unix_nano(now.isoformat()) > 0
    assert exporter._datetime_to_unix_nano("invalid") == 0
    assert exporter._datetime_to_unix_nano(None) == 0
    assert exporter._hex_to_base64("") == ""
    assert exporter._hex_to_base64("not-hex") == "not-hex"

    converted = exporter._span_to_otlp(
        {
            "trace_id": "00" * 16,
            "span_id": "01" * 8,
            "parent_span_id": "02" * 8,
            "name": "operation",
            "kind": "CLIENT",
            "start_time": now,
            "end_time": now.isoformat(),
            "status": "ERROR",
            "events": [{"name": "retry", "timestamp": 1, "attributes": {"count": 1}}],
        }
    )
    assert converted["kind"] == 3
    assert converted["status"]["code"] == 2
    assert converted["events"][0]["name"] == "retry"


def test_export_traces_to_otlp_resolves_recent_ids_and_batches(monkeypatch):
    spans = [{"trace_id": "t", "span_id": str(index)} for index in range(101)]
    store = Mock()
    store.get_recent_traces.return_value = ["t"]
    store.get_trace.return_value = spans
    exported = []

    monkeypatch.setattr("praval.observability.storage.get_trace_store", lambda: store)
    monkeypatch.setattr(
        OTLPExporter,
        "export_spans",
        lambda self, batch: exported.append(list(batch)) or True,
    )

    assert export_traces_to_otlp("http://collector") is True
    assert [len(batch) for batch in exported] == [100, 1]


def test_export_traces_to_otlp_empty_and_failed_batch(monkeypatch):
    store = Mock()
    store.get_recent_traces.return_value = []
    monkeypatch.setattr("praval.observability.storage.get_trace_store", lambda: store)
    assert export_traces_to_otlp("http://collector") is True

    store.get_recent_traces.return_value = ["t"]
    store.get_trace.return_value = [{"trace_id": "t", "span_id": "s"}]
    monkeypatch.setattr(OTLPExporter, "export_spans", lambda self, batch: False)
    assert export_traces_to_otlp("http://collector") is False
