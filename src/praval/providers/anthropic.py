"""
Anthropic provider implementation for Praval framework.

Provides integration with Anthropic's Claude models through the
Messages API with support for conversation history and system messages.
"""

import os
from typing import List, Dict, Any, Optional

import anthropic
from ..core.exceptions import ProviderError


class AnthropicProvider:
    """
    Anthropic provider for LLM interactions.
    
    Handles communication with Anthropic's Claude models through the
    Messages API with proper system message handling.
    """
    
    def __init__(self, config):
        """
        Initialize Anthropic provider.
        
        Args:
            config: AgentConfig object with provider settings
            
        Raises:
            ProviderError: If Anthropic client initialization fails
        """
        self.config = config
        
        try:
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise ProviderError("ANTHROPIC_API_KEY environment variable not set")
                
            self.client = anthropic.Anthropic(api_key=api_key)
        except Exception as e:
            raise ProviderError(f"Failed to initialize Anthropic client: {str(e)}") from e
    
    def generate(
        self, 
        messages: List[Dict[str, str]], 
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """
        Generate a response using Anthropic's Messages API.
        
        Args:
            messages: Conversation history as list of message dictionaries
            tools: Optional list of available tools (not fully supported yet)
            
        Returns:
            Generated response as a string
            
        Raises:
            ProviderError: If API call fails
        """
        try:
            # Separate system messages from conversation messages
            system_message = self._extract_system_message(messages)
            conversation_messages = self._filter_conversation_messages(messages)
            
            # Prepare the API call parameters
            call_params = {
                "model": "claude-3-sonnet-20240229",
                "messages": conversation_messages,
                "temperature": self.config.temperature,
                "max_tokens": self.config.max_tokens
            }
            
            # Add system message if present
            if system_message:
                call_params["system"] = system_message
            
            # Make the API call
            response = self.client.messages.create(**call_params)
            
            # Extract the response content
            if response.content and len(response.content) > 0:
                # Anthropic returns content as a list of content blocks
                content_blocks = response.content
                if content_blocks[0].type == "text":
                    return content_blocks[0].text
            
            return ""
            
        except Exception as e:
            raise ProviderError(f"Anthropic API error: {str(e)}") from e
    
    def _extract_system_message(self, messages: List[Dict[str, str]]) -> Optional[str]:
        """
        Extract system message from conversation messages.
        
        Args:
            messages: List of conversation messages
            
        Returns:
            System message content if found, None otherwise
        """
        for message in messages:
            if message.get("role") == "system":
                return message.get("content", "")
        return None
    
    def _filter_conversation_messages(self, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """
        Filter out system messages to get conversation messages only.
        
        Args:
            messages: List of all messages including system messages
            
        Returns:
            List of conversation messages (user/assistant only)
        """
        conversation_messages = []
        
        for message in messages:
            role = message.get("role", "")
            if role in ["user", "assistant"]:
                conversation_messages.append({
                    "role": role,
                    "content": message.get("content", "")
                })
        
        return conversation_messages