from praval.observability.export.console_viewer import ConsoleViewer
from praval.observability.export.otlp_exporter import OTLPExporter


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
