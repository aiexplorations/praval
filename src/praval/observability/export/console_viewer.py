"""
Console trace viewer for debugging and local development.

Displays traces in a tree format showing:
- Span hierarchy (parent-child relationships)
- Timing information
- Errors and events
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class ConsoleViewer:
    """Console viewer for displaying traces in terminal."""

    def __init__(self, use_colors: bool = True):
        """Initialize console viewer.

        Args:
            use_colors: Whether to use ANSI colors in output
        """
        self.use_colors = use_colors

        # ANSI color codes
        self.RESET = "\033[0m" if use_colors else ""
        self.BOLD = "\033[1m" if use_colors else ""
        self.DIM = "\033[2m" if use_colors else ""
        self.GREEN = "\033[32m" if use_colors else ""
        self.RED = "\033[31m" if use_colors else ""
        self.YELLOW = "\033[33m" if use_colors else ""
        self.BLUE = "\033[34m" if use_colors else ""
        self.CYAN = "\033[36m" if use_colors else ""

    def display_trace(self, trace_id: str, spans: List[Dict[str, Any]]) -> None:
        """Display a single trace in tree format.

        Args:
            trace_id: Trace ID
            spans: List of spans in the trace
        """
        if not spans:
            print(f"No spans found for trace {trace_id}")
            return

        print(f"\n{self.BOLD}Trace: {trace_id}{self.RESET}")
        print(f"{self.DIM}{'─' * 80}{self.RESET}\n")

        # Build span hierarchy
        span_map = {s["span_id"]: s for s in spans}
        root_spans = [s for s in spans if not s.get("parent_span_id")]

        # Display each root span and its children
        for root in root_spans:
            self._display_span_tree(root, span_map, depth=0)

        print()

    def display_traces(self, spans: List[Dict[str, Any]]) -> None:
        """Display multiple traces grouped by trace_id.

        Args:
            spans: List of spans from potentially multiple traces
        """
        # Group by trace_id
        trace_groups: Dict[str, List[Dict]] = {}
        for span in spans:
            trace_id = span.get("trace_id")
            if trace_id:
                if trace_id not in trace_groups:
                    trace_groups[trace_id] = []
                trace_groups[trace_id].append(span)

        # Display each trace
        for trace_id, trace_spans in trace_groups.items():
            self.display_trace(trace_id, trace_spans)

    def _display_span_tree(
        self, span: Dict[str, Any], span_map: Dict[str, Dict], depth: int = 0
    ) -> None:
        """Recursively display span and its children.

        Args:
            span: Span to display
            span_map: Map of span_id to span
            depth: Current depth in tree
        """
        indent = "  " * depth
        branch = "└─ " if depth > 0 else ""

        # Span name and kind
        name = span.get("name", "unknown")
        kind = span.get("kind", "INTERNAL")
        duration = span.get("duration_ms", 0)
        status = span.get("status", "ok")

        # Color based on status
        if status == "error":
            status_color = self.RED
        elif status == "ok":
            status_color = self.GREEN
        else:
            status_color = self.YELLOW

        # Format timing
        duration_str = f"{duration:.2f}ms" if duration else "?"

        # Print span line
        print(
            f"{indent}{branch}{self.BOLD}{name}{self.RESET} "
            f"{self.DIM}[{kind}]{self.RESET} "
            f"{status_color}{status}{self.RESET} "
            f"{self.CYAN}{duration_str}{self.RESET}"
        )

        # Print attributes if any
        attributes = span.get("attributes", {})
        if attributes:
            for key, value in attributes.items():
                print(f"{indent}  {self.DIM}├─ {key}: {value}{self.RESET}")

        # Print events if any
        events = span.get("events", [])
        if events:
            for event in events:
                event_name = event.get("name", "event")
                event_attrs = event.get("attributes", {})

                # Highlight exceptions
                if "exception" in event_name.lower():
                    event_color = self.RED
                else:
                    event_color = self.YELLOW

                print(
                    f"{indent}  {self.DIM}├─ {event_color}⚡ {event_name}{self.RESET}"
                )

                # Print event attributes
                for key, value in event_attrs.items():
                    print(f"{indent}  {self.DIM}│  {key}: {value}{self.RESET}")

        # Find and display children
        span_id = span.get("span_id")
        children = [s for s in span_map.values() if s.get("parent_span_id") == span_id]

        for child in children:
            self._display_span_tree(child, span_map, depth + 1)

    def display_summary(self, spans: List[Dict[str, Any]]) -> None:
        """Display summary statistics for traces.

        Args:
            spans: List of spans
        """
        if not spans:
            print("No spans to display")
            return

        # Calculate statistics
        total_spans = len(spans)
        trace_ids = set(s.get("trace_id") for s in spans if s.get("trace_id"))
        total_traces = len(trace_ids)

        error_spans = [s for s in spans if s.get("status") == "error"]
        error_count = len(error_spans)

        durations = [s.get("duration_ms", 0) for s in spans if s.get("duration_ms")]
        avg_duration = sum(durations) / len(durations) if durations else 0

        # Display summary
        print(f"\n{self.BOLD}Trace Summary{self.RESET}")
        print(f"{self.DIM}{'─' * 80}{self.RESET}")
        print(f"Total traces: {self.CYAN}{total_traces}{self.RESET}")
        print(f"Total spans: {self.CYAN}{total_spans}{self.RESET}")
        print(f"Errors: {self.RED}{error_count}{self.RESET}")
        print(f"Average duration: {self.CYAN}{avg_duration:.2f}ms{self.RESET}")
        print()


def print_traces(
    trace_ids: Optional[List[str]] = None,
    limit: int = 10,
    summary_only: bool = False,
    use_colors: bool = True,
) -> None:
    """Print traces from local storage to console.

    Args:
        trace_ids: Optional list of specific trace IDs to display (None = recent)
        limit: Maximum number of traces to display (default: 10)
        summary_only: If True, only show summary statistics
        use_colors: Whether to use ANSI colors in output

    Example:
        # Show last 10 traces
        print_traces()

        # Show specific trace
        print_traces(trace_ids=["abc123..."])

        # Show summary only
        print_traces(summary_only=True)
    """
    from ..storage import get_trace_store

    store = get_trace_store()
    viewer = ConsoleViewer(use_colors=use_colors)

    # Get spans
    if trace_ids:
        spans = []
        for trace_id in trace_ids:
            spans.extend(store.get_trace(trace_id))
    else:
        spans = store.get_recent_traces(limit=limit)

    if not spans:
        print("No traces found")
        return

    # Display results
    if summary_only:
        viewer.display_summary(spans)
    else:
        viewer.display_traces(spans)
        viewer.display_summary(spans)


def show_recent_traces(limit: int = 5, use_colors: bool = True) -> None:
    """Show the most recent traces (convenience function).

    Args:
        limit: Number of recent traces to show
        use_colors: Whether to use ANSI colors
    """
    print_traces(limit=limit, use_colors=use_colors)
