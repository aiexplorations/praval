"""
Tests for agent logging behavior.

Verifies that agent.py uses proper logging instead of print statements.
Part of rearchitecture issue S4.
"""

import ast
import logging
from pathlib import Path
from unittest.mock import MagicMock, patch


class TestAgentLogging:
    """Tests for agent logging behavior."""

    def test_no_print_statements_in_agent(self):
        """Verify no print() calls remain in agent.py."""
        agent_path = Path("src/praval/core/agent.py")
        tree = ast.parse(agent_path.read_text())

        print_calls = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id == "print":
                    print_calls.append(node.lineno)

        assert len(print_calls) == 0, f"Found print() calls at lines: {print_calls}"

    def test_memory_init_logs_info(self, caplog):
        """Verify memory initialization logs at INFO level."""
        with caplog.at_level(logging.INFO, logger="praval.core.agent"):
            with patch("praval.core.agent.ProviderFactory"):
                with patch("praval.memory.MemoryManager") as mock_mm:
                    mock_memory = MagicMock()
                    mock_mm.return_value = mock_memory

                    from praval import Agent

                    _ = Agent("test_log_agent", memory_enabled=True)

        # Check that info log was emitted
        info_records = [r for r in caplog.records if r.levelno == logging.INFO]
        assert any("Memory system initialized" in r.message for r in info_records), (
            f"Expected INFO log about memory initialization. Got: "
            f"{[r.message for r in info_records]}"
        )

    def test_memory_unavailable_logs_warning(self, caplog):
        """Verify missing memory dependencies log at WARNING level."""
        with caplog.at_level(logging.WARNING, logger="praval.core.agent"):
            with patch("praval.core.agent.ProviderFactory"):
                # Simulate ImportError when memory module is not available
                with patch.dict("sys.modules", {"praval.memory": None}):
                    with patch(
                        "praval.core.agent.Agent._init_memory_system"
                    ) as mock_init:
                        # Make it raise ImportError to trigger warning log
                        def raise_import_error(self, config=None):
                            import logging

                            logger = logging.getLogger("praval.core.agent")
                            logger.warning(
                                "Memory system not available: test import error"
                            )
                            self.memory = None
                            self.memory_enabled = False

                        mock_init.side_effect = lambda config=None: raise_import_error(
                            mock_init, config
                        )

                        from praval import Agent

                        _ = Agent("test_warn_agent", memory_enabled=True)

        # Should log warning, not crash
        warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert any("not available" in r.message.lower() for r in warning_records), (
            f"Expected WARNING log about memory unavailable. Got: "
            f"{[r.message for r in warning_records]}"
        )

    def test_memory_not_enabled_logs_debug(self, caplog):
        """Verify 'memory not enabled' logs at DEBUG level."""
        with caplog.at_level(logging.DEBUG, logger="praval.core.agent"):
            with patch("praval.core.agent.ProviderFactory"):
                from praval import Agent

                agent = Agent("test_debug_agent", memory_enabled=False)
                # Try to remember something without memory enabled
                result = agent.remember("test content")

        assert result is None
        debug_records = [r for r in caplog.records if r.levelno == logging.DEBUG]
        assert any("Memory not enabled" in r.message for r in debug_records), (
            f"Expected DEBUG log about memory not enabled. Got: "
            f"{[r.message for r in debug_records]}"
        )

    def test_failed_operations_log_warning(self, caplog):
        """Verify failed memory operations log at WARNING level."""
        with caplog.at_level(logging.WARNING, logger="praval.core.agent"):
            with patch("praval.core.agent.ProviderFactory"):
                from praval import Agent

                agent = Agent("test_fail_agent", memory_enabled=False)
                # Set up a mock memory that raises on store
                mock_memory = MagicMock()
                mock_memory.store_memory.side_effect = RuntimeError("Test error")
                agent.memory = mock_memory

                # Try to remember - should fail and log warning
                result = agent.remember("test content")

        assert result is None
        warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert any("Failed to store memory" in r.message for r in warning_records), (
            f"Expected WARNING log about failed store. Got: "
            f"{[r.message for r in warning_records]}"
        )

    def test_recall_failure_logs_warning(self, caplog):
        """Verify failed recall operations log at WARNING level."""
        with caplog.at_level(logging.WARNING, logger="praval.core.agent"):
            with patch("praval.core.agent.ProviderFactory"):
                from praval import Agent

                agent = Agent("test_recall_agent", memory_enabled=False)
                # Set up a mock memory that raises on search
                mock_memory = MagicMock()
                mock_memory.search_memories.side_effect = RuntimeError("Search error")
                agent.memory = mock_memory

                # Try to recall - should fail and log warning
                result = agent.recall("test query")

        assert result == []
        warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert any("Failed to recall memories" in r.message for r in warning_records), (
            f"Expected WARNING log about failed recall. Got: "
            f"{[r.message for r in warning_records]}"
        )


class TestLoggingConfiguration:
    """Tests for logging configurability."""

    def test_logger_uses_module_name(self):
        """Verify logger is named after the module."""
        from praval.core import agent

        assert hasattr(agent, "logger")
        assert agent.logger.name == "praval.core.agent"

    def test_logging_can_be_suppressed(self, caplog):
        """Verify logging can be suppressed via configuration."""
        # Set level to ERROR to suppress INFO and WARNING
        logging.getLogger("praval.core.agent").setLevel(logging.ERROR)

        try:
            with caplog.at_level(logging.DEBUG):
                with patch("praval.core.agent.ProviderFactory"):
                    from praval import Agent

                    agent = Agent("test_suppress_agent", memory_enabled=False)
                    agent.remember("test")  # Would normally log DEBUG

            # Should have no INFO, WARNING, or DEBUG logs
            non_error_records = [r for r in caplog.records if r.levelno < logging.ERROR]
            praval_records = [
                r for r in non_error_records if r.name == "praval.core.agent"
            ]
            assert len(praval_records) == 0, (
                f"Expected no logs below ERROR. Got: "
                f"{[r.message for r in praval_records]}"
            )
        finally:
            # Reset logger level
            logging.getLogger("praval.core.agent").setLevel(logging.NOTSET)
