#!/usr/bin/env python3
"""
Validation script for Praval Phase 1 implementation.

This script validates that the core components are working correctly
without requiring external API dependencies.
"""

import sys
import os
import tempfile
import shutil
from unittest.mock import Mock, patch

# Add src to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_basic_imports():
    """Test that basic imports work correctly."""
    print("✓ Testing basic imports...")
    
    try:
        from praval import Agent
        from praval.core.agent import AgentConfig
        from praval.core.storage import StateStorage
        from praval.core.exceptions import PravalError, ProviderError
        print("  ✓ All imports successful")
        return True
    except ImportError as e:
        print(f"  ✗ Import failed: {e}")
        return False

def test_storage_functionality():
    """Test storage functionality works correctly."""
    print("✓ Testing storage functionality...")
    
    try:
        from praval.core.storage import StateStorage
        
        # Create temporary directory for testing
        temp_dir = tempfile.mkdtemp()
        
        try:
            storage = StateStorage(temp_dir)
            
            # Test save and load
            conversation = [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there!"}
            ]
            
            storage.save("test_agent", conversation)
            loaded = storage.load("test_agent")
            
            assert loaded == conversation, "Loaded conversation doesn't match saved"
            
            # Test list agents
            agents = storage.list_agents()
            assert "test_agent" in agents, "Agent not found in list"
            
            # Test delete
            storage.delete("test_agent")
            assert storage.load("test_agent") is None, "Agent not deleted"
            
            print("  ✓ Storage functionality working correctly")
            return True
            
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
            
    except Exception as e:
        print(f"  ✗ Storage test failed: {e}")
        return False

def test_agent_configuration():
    """Test agent configuration functionality."""
    print("✓ Testing agent configuration...")
    
    try:
        from praval.core.agent import AgentConfig
        
        # Test default configuration
        config = AgentConfig()
        assert config.temperature == 0.7, "Default temperature incorrect"
        assert config.max_tokens == 1000, "Default max_tokens incorrect"
        
        # Test custom configuration
        config = AgentConfig(temperature=0.9, max_tokens=2000)
        assert config.temperature == 0.9, "Custom temperature not set"
        assert config.max_tokens == 2000, "Custom max_tokens not set"
        
        # Test validation
        try:
            AgentConfig(temperature=3.0)
            assert False, "Temperature validation failed"
        except ValueError:
            pass  # Expected
        
        try:
            AgentConfig(max_tokens=-100)
            assert False, "Max tokens validation failed"
        except ValueError:
            pass  # Expected
        
        print("  ✓ Configuration functionality working correctly")
        return True
        
    except Exception as e:
        print(f"  ✗ Configuration test failed: {e}")
        return False

def test_agent_with_mocked_provider():
    """Test agent functionality with mocked provider."""
    print("✓ Testing agent with mocked provider...")
    
    try:
        from praval import Agent
        
        # Mock the provider factory to avoid import issues
        with patch('praval.core.agent.ProviderFactory') as mock_factory:
            mock_provider = Mock()
            mock_provider.generate.return_value = "Mocked response"
            mock_factory.create_provider.return_value = mock_provider
            
            # Mock environment to have API key
            with patch.dict('os.environ', {'OPENAI_API_KEY': 'test_key'}):
                # Test basic agent creation and chat
                agent = Agent("test_assistant")
                
                assert agent.name == "test_assistant", "Agent name not set correctly"
                assert agent.persist_state is False, "Default persist_state incorrect"
                
                # Test chat functionality
                response = agent.chat("Hello")
                assert response == "Mocked response", "Chat response incorrect"
                assert len(agent.conversation_history) == 2, "Conversation history length incorrect"
                
                # Test conversation history structure
                assert agent.conversation_history[0]["role"] == "user"
                assert agent.conversation_history[0]["content"] == "Hello"
                assert agent.conversation_history[1]["role"] == "assistant"
                assert agent.conversation_history[1]["content"] == "Mocked response"
        
        print("  ✓ Agent functionality working correctly")
        return True
        
    except Exception as e:
        print(f"  ✗ Agent test failed: {e}")
        return False

def test_tool_registration():
    """Test tool registration functionality."""
    print("✓ Testing tool registration...")
    
    try:
        from praval import Agent
        
        # Mock the provider
        with patch('praval.core.agent.ProviderFactory') as mock_factory:
            mock_provider = Mock()
            mock_factory.create_provider.return_value = mock_provider
            
            with patch.dict('os.environ', {'OPENAI_API_KEY': 'test_key'}):
                agent = Agent("tool_agent")
                
                # Test tool registration
                @agent.tool
                def add_numbers(x: int, y: int) -> int:
                    """Add two numbers together"""
                    return x + y
                
                # Verify tool was registered
                assert "add_numbers" in agent.tools, "Tool not registered"
                
                tool_info = agent.tools["add_numbers"]
                assert tool_info["function"] == add_numbers, "Tool function not stored correctly"
                assert "Add two numbers together" in tool_info["description"], "Tool description not stored"
                
                # Test that function still works
                result = add_numbers(5, 3)
                assert result == 8, "Tool function doesn't work"
        
        print("  ✓ Tool registration working correctly")
        return True
        
    except Exception as e:
        print(f"  ✗ Tool registration test failed: {e}")
        return False

def test_persistent_agent():
    """Test persistent agent functionality."""
    print("✓ Testing persistent agent...")
    
    try:
        from praval import Agent
        
        temp_dir = tempfile.mkdtemp()
        
        try:
            with patch('praval.core.agent.ProviderFactory') as mock_factory:
                mock_provider = Mock()
                mock_provider.generate.return_value = "Persistent response"
                mock_factory.create_provider.return_value = mock_provider
                
                with patch('praval.core.storage.StateStorage') as mock_storage_class:
                    mock_storage = Mock()
                    mock_storage.load.return_value = None  # No existing state
                    mock_storage_class.return_value = mock_storage
                    
                    with patch.dict('os.environ', {'OPENAI_API_KEY': 'test_key'}):
                        # Create persistent agent
                        agent = Agent("persistent_agent", persist_state=True)
                        
                        assert agent.persist_state is True, "Persistence not enabled"
                        
                        # Test chat saves state
                        agent.chat("Test message")
                        
                        # Verify save was called
                        assert mock_storage.save.called, "State not saved after chat"
                        
                        # Verify save was called with correct arguments
                        mock_storage.save.assert_called_with("persistent_agent", agent.conversation_history)
        
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
        
        print("  ✓ Persistent agent working correctly")
        return True
        
    except Exception as e:
        print(f"  ✗ Persistent agent test failed: {e}")
        return False

def main():
    """Run all validation tests."""
    print("Praval Phase 1 Implementation Validation")
    print("=" * 40)
    
    tests = [
        test_basic_imports,
        test_storage_functionality,
        test_agent_configuration,
        test_agent_with_mocked_provider,
        test_tool_registration,
        test_persistent_agent,
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"  ✗ Test failed with exception: {e}")
    
    print("\n" + "=" * 40)
    print(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All validation tests passed! Praval Phase 1 implementation is working correctly.")
        return 0
    else:
        print("❌ Some tests failed. Please check the implementation.")
        return 1

if __name__ == "__main__":
    sys.exit(main())