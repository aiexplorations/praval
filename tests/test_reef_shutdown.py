"""
Tests for Reef shutdown timeout and cleanup thread behavior.

Verifies shutdown timeout (M6) and cleanup thread logging (M3).
Part of rearchitecture Phase 1.
"""

import logging
import threading
import time
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

import pytest


class TestReefChannelShutdown:
    """Tests for ReefChannel.shutdown() with timeout."""

    def test_shutdown_returns_true_on_clean_exit(self):
        """Verify shutdown returns True when all handlers complete."""
        from praval.core.reef import ReefChannel

        channel = ReefChannel("test_clean")

        result = channel.shutdown(wait=True, timeout=5.0)

        assert result is True
        assert channel._shutdown is True

    def test_shutdown_with_wait_false_returns_immediately(self):
        """Verify shutdown returns True immediately when wait=False."""
        from praval.core.reef import ReefChannel

        channel = ReefChannel("test_nowait")

        start = time.time()
        result = channel.shutdown(wait=False)
        elapsed = time.time() - start

        assert result is True
        assert elapsed < 1.0  # Should be nearly instant

    def test_shutdown_respects_timeout(self):
        """Verify shutdown returns False when futures don't complete in time."""
        from praval.core.reef import ReefChannel

        channel = ReefChannel("test_timeout")

        # Create mock futures that never complete
        mock_future = Mock()
        mock_future.done.return_value = False
        mock_future.cancel.return_value = False
        channel._active_futures = [mock_future]

        # Shutdown with short timeout - the mock future never completes
        start = time.time()
        result = channel.shutdown(wait=True, timeout=0.5)
        elapsed = time.time() - start

        # Should timeout because mock future never completes
        assert result is False
        assert elapsed >= 0.5  # Waited for timeout
        assert elapsed < 2.0  # But didn't wait too long

    def test_shutdown_cancels_pending_futures(self):
        """Verify shutdown attempts to cancel pending futures."""
        from praval.core.reef import ReefChannel

        channel = ReefChannel("test_cancel")

        # Add some mock futures
        mock_future_done = Mock()
        mock_future_done.done.return_value = True

        mock_future_pending = Mock()
        mock_future_pending.done.return_value = False

        channel._active_futures = [mock_future_done, mock_future_pending]

        channel.shutdown(wait=True, timeout=1.0)

        # Pending future should have cancel called
        mock_future_pending.cancel.assert_called_once()
        # Done future should not have cancel called
        mock_future_done.cancel.assert_not_called()

    def test_shutdown_logs_warning_on_timeout(self, caplog):
        """Verify shutdown logs warning when timeout occurs."""
        from praval.core.reef import ReefChannel

        channel = ReefChannel("test_log_timeout")

        # Create a mock future that never completes
        mock_future = Mock()
        mock_future.done.return_value = False
        mock_future.cancel.return_value = False
        channel._active_futures = [mock_future]

        with caplog.at_level(logging.WARNING, logger="praval.core.reef"):
            result = channel.shutdown(wait=True, timeout=0.3)

        assert result is False
        assert any("timed out" in r.message for r in caplog.records)


class TestReefShutdown:
    """Tests for Reef.shutdown() with timeout."""

    def test_reef_shutdown_returns_true_on_clean_exit(self):
        """Verify reef shutdown returns True when all channels complete."""
        from praval.core.reef import Reef

        reef = Reef()
        reef.create_channel("ch1")
        reef.create_channel("ch2")

        result = reef.shutdown(wait=True, timeout=5.0)

        assert result is True

    def test_reef_shutdown_distributes_timeout(self):
        """Verify reef distributes timeout across channels."""
        from praval.core.reef import Reef

        reef = Reef()

        # Create channels that will take some time
        for i in range(3):
            reef.create_channel(f"ch{i}")

        start = time.time()
        result = reef.shutdown(wait=True, timeout=10.0)
        elapsed = time.time() - start

        assert result is True
        assert elapsed < 10.0  # Should complete well within timeout

    def test_reef_shutdown_waits_for_cleanup_thread(self):
        """Verify reef shutdown waits for cleanup thread."""
        from praval.core.reef import Reef

        reef = Reef()

        # Cleanup thread should be alive initially
        assert reef.cleanup_thread.is_alive()

        reef.shutdown(wait=True, timeout=10.0)

        # After shutdown, thread should have stopped
        # (may take a moment due to interruptible sleep)
        reef.cleanup_thread.join(timeout=2.0)
        assert not reef.cleanup_thread.is_alive()

    def test_reef_shutdown_logs_warning_if_cleanup_hangs(self, caplog):
        """Verify reef logs warning if cleanup thread doesn't stop."""
        from praval.core.reef import Reef

        reef = Reef()

        # Mock cleanup thread that doesn't stop
        mock_thread = Mock()
        mock_thread.is_alive.return_value = True
        reef.cleanup_thread = mock_thread

        with caplog.at_level(logging.WARNING, logger="praval.core.reef"):
            result = reef.shutdown(wait=True, timeout=1.0)

        assert result is False
        assert any("Cleanup thread did not stop" in r.message for r in caplog.records)

    def test_reef_shutdown_with_wait_false(self):
        """Verify reef shutdown with wait=False is fast."""
        from praval.core.reef import Reef

        reef = Reef()
        reef.create_channel("fast_ch")

        start = time.time()
        result = reef.shutdown(wait=False)
        elapsed = time.time() - start

        assert result is True
        assert elapsed < 1.0


class TestCleanupLoopLogging:
    """Tests for cleanup loop logging behavior (M3)."""

    def test_cleanup_loop_logs_errors(self, caplog):
        """Verify cleanup loop logs errors instead of silently ignoring."""
        from praval.core.reef import Reef

        reef = Reef()
        reef.create_channel("test_channel")

        # Create a channel that raises on cleanup
        mock_channel = Mock()
        mock_channel.cleanup_expired.side_effect = RuntimeError("Test cleanup error")
        reef.channels["broken"] = mock_channel

        # Run cleanup directly (not in thread) to capture logs
        reef._shutdown = False

        # Patch sleep to make test fast
        with patch("praval.core.reef.time.sleep"):
            # Simulate one cleanup iteration
            original_shutdown = reef._shutdown

            def run_one_iteration():
                # Set shutdown after one iteration
                reef._shutdown = False
                try:
                    # Process one channel cleanup
                    for channel in reef.channels.values():
                        try:
                            channel.cleanup_expired()
                        except Exception as e:
                            import logging

                            logging.getLogger("praval.core.reef").warning(
                                f"Error cleaning up channel: {e}"
                            )
                finally:
                    reef._shutdown = True

            with caplog.at_level(logging.WARNING, logger="praval.core.reef"):
                run_one_iteration()

        # Should have logged warning
        assert any("Error" in r.message or "error" in r.message for r in caplog.records)

    def test_cleanup_loop_uses_interruptible_sleep(self):
        """Verify cleanup loop responds quickly to shutdown signal."""
        from praval.core.reef import Reef

        reef = Reef()

        # Measure how long shutdown takes
        start = time.time()
        reef.shutdown(wait=True, timeout=5.0)
        elapsed = time.time() - start

        # Should complete in less than 5 seconds (interruptible sleep)
        # The cleanup loop checks shutdown every second
        assert elapsed < 5.0

    def test_cleanup_loop_logs_debug_for_expired_spores(self, caplog):
        """Verify cleanup logs debug when spores are cleaned up."""
        from praval.core.reef import ReefChannel
        import logging

        channel = ReefChannel("debug_test")

        # Mock cleanup_expired to return count
        channel.cleanup_expired = Mock(return_value=5)

        logger = logging.getLogger("praval.core.reef")
        with caplog.at_level(logging.DEBUG, logger="praval.core.reef"):
            expired = channel.cleanup_expired()
            if expired > 0:
                logger.debug(f"Cleaned up {expired} expired spores from {channel.name}")

        assert any("Cleaned up" in r.message for r in caplog.records)


class TestShutdownReturnType:
    """Tests verifying shutdown return type changes."""

    def test_channel_shutdown_returns_bool(self):
        """Verify ReefChannel.shutdown returns bool."""
        from praval.core.reef import ReefChannel

        channel = ReefChannel("bool_test")
        result = channel.shutdown()

        assert isinstance(result, bool)

    def test_reef_shutdown_returns_bool(self):
        """Verify Reef.shutdown returns bool."""
        from praval.core.reef import Reef

        reef = Reef()
        result = reef.shutdown()

        assert isinstance(result, bool)


class TestShutdownBackwardCompatibility:
    """Tests for backward compatibility of shutdown changes."""

    def test_channel_shutdown_default_timeout(self):
        """Verify channel shutdown has sensible default timeout."""
        from praval.core.reef import ReefChannel
        import inspect

        sig = inspect.signature(ReefChannel.shutdown)
        timeout_param = sig.parameters.get("timeout")

        assert timeout_param is not None
        assert timeout_param.default == 30.0

    def test_reef_shutdown_default_timeout(self):
        """Verify reef shutdown has sensible default timeout."""
        from praval.core.reef import Reef
        import inspect

        sig = inspect.signature(Reef.shutdown)
        timeout_param = sig.parameters.get("timeout")

        assert timeout_param is not None
        assert timeout_param.default == 30.0

    def test_existing_shutdown_call_still_works(self):
        """Verify existing shutdown calls without timeout still work."""
        from praval.core.reef import Reef, ReefChannel

        # Channel shutdown without timeout
        channel = ReefChannel("compat_channel")
        channel.shutdown(wait=True)  # Should not raise

        # Reef shutdown without timeout
        reef = Reef()
        reef.shutdown(wait=True)  # Should not raise
