"""
Cohere provider implementation for Praval framework.

Provides integration with Cohere's chat models through their
Chat API with support for conversation history.
"""

import os
from typing import List, Dict, Any, Optional

import cohere
from ..core.exceptions import ProviderError


class CohereProvider:
    """
    Cohere provider for LLM interactions.
    
    Handles communication with Cohere's chat models through the
    Chat API with conversation history support.
    """
    
    def __init__(self, config):
        """
        Initialize Cohere provider.
        
        Args:
            config: AgentConfig object with provider settings
            
        Raises:
            ProviderError: If Cohere client initialization fails
        """
        self.config = config
        
        try:
            api_key = os.getenv("COHERE_API_KEY")
            if not api_key:
                raise ProviderError("COHERE_API_KEY environment variable not set")
                
            self.client = cohere.Client(api_key)
        except Exception as e:
            raise ProviderError(f"Failed to initialize Cohere client: {str(e)}") from e
    
    def generate(
        self, 
        messages: List[Dict[str, str]], 
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """
        Generate a response using Cohere's Chat API.
        
        Args:
            messages: Conversation history as list of message dictionaries
            tools: Optional list of available tools (not fully supported yet)
            
        Returns:
            Generated response as a string
            
        Raises:
            ProviderError: If API call fails
        """
        try:
            # Extract the current user message and chat history
            current_message, chat_history = self._prepare_chat_format(messages)
            
            # Prepare the API call parameters
            call_params = {
                "message": current_message,
                "temperature": self.config.temperature,
                "max_tokens": self.config.max_tokens
            }
            
            # Add chat history if available
            if chat_history:
                call_params["chat_history"] = chat_history
            
            # Add system message as preamble if present
            system_message = self._extract_system_message(messages)
            if system_message:
                call_params["preamble"] = system_message
            
            # Make the API call
            response = self.client.chat(**call_params)
            
            # Extract the response text
            return response.text if hasattr(response, 'text') else ""
            
        except Exception as e:
            raise ProviderError(f"Cohere API error: {str(e)}") from e
    
    def _prepare_chat_format(self, messages: List[Dict[str, str]]) -> tuple[str, List[Dict[str, str]]]:
        """
        Prepare messages in Cohere's chat format.
        
        Cohere expects the current user message separately from chat history.
        
        Args:
            messages: List of conversation messages
            
        Returns:
            Tuple of (current_message, chat_history)
        """
        # Filter out system messages for conversation
        conversation_messages = [
            msg for msg in messages 
            if msg.get("role") in ["user", "assistant"]
        ]
        
        if not conversation_messages:
            return "", []
        
        # The last message should be the current user message
        current_message = ""
        chat_history = []
        
        if conversation_messages:
            # Get the last user message as current message
            last_message = conversation_messages[-1]
            if last_message.get("role") == "user":
                current_message = last_message.get("content", "")
                
                # Convert previous messages to chat history format
                for i, msg in enumerate(conversation_messages[:-1]):
                    role = msg.get("role", "")
                    content = msg.get("content", "")
                    
                    if role == "user":
                        chat_history.append({"role": "USER", "message": content})
                    elif role == "assistant":
                        chat_history.append({"role": "CHATBOT", "message": content})
            else:
                # If last message is not from user, treat it as continuation
                current_message = "Please continue."
                
                # Convert all messages to chat history
                for msg in conversation_messages:
                    role = msg.get("role", "")
                    content = msg.get("content", "")
                    
                    if role == "user":
                        chat_history.append({"role": "USER", "message": content})
                    elif role == "assistant":
                        chat_history.append({"role": "CHATBOT", "message": content})
        
        return current_message, chat_history
    
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