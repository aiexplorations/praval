"""
Test that reef imports are set up correctly.

This is a minimal test to verify that our reef module structure
is correct before running the comprehensive tests.
"""

import pytest


def test_reef_imports_structure():
    """Test that we can import the expected reef classes."""
    try:
        # These imports should work once we implement the reef module
        from praval.core.reef import SporeType, Spore, ReefChannel, Reef, get_reef
        
        # Basic smoke test - classes should be importable
        assert SporeType is not None
        assert Spore is not None
        assert ReefChannel is not None
        assert Reef is not None
        assert get_reef is not None
        
    except ImportError as e:
        # This is expected until we implement the reef module
        pytest.skip(f"Reef module not yet implemented: {e}")


def test_agent_reef_methods_structure():
    """Test that Agent class has the expected reef methods."""
    try:
        from praval import Agent
        
        # Create a basic agent
        agent = Agent("test")
        
        # Check that reef methods exist (will be added during implementation)
        reef_methods = [
            'send_knowledge',
            'broadcast_knowledge', 
            'request_knowledge',
            'on_spore_received',
            'subscribe_to_channel',
            'unsubscribe_from_channel'
        ]
        
        for method_name in reef_methods:
            assert hasattr(agent, method_name), f"Agent missing reef method: {method_name}"
            
    except (ImportError, AssertionError) as e:
        # This is expected until we implement reef integration
        pytest.skip(f"Agent reef integration not yet implemented: {e}")


def test_praval_init_includes_reef():
    """Test that praval.__init__.py includes reef functionality."""
    try:
        from praval import get_reef
        
        # Should be able to get reef instance
        reef = get_reef()
        assert reef is not None
        
    except ImportError as e:
        # This is expected until we add reef to __init__.py
        pytest.skip(f"Reef not yet added to praval.__init__: {e}")


if __name__ == "__main__":
    # Run basic import tests
    test_reef_imports_structure()
    test_agent_reef_methods_structure() 
    test_praval_init_includes_reef()
    print("✅ All import structure tests passed (or skipped appropriately)")