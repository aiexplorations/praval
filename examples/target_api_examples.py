# Praval Target API - Phase 1
# These examples show the desired simplicity and elegance

# Example 1: Absolute Simplest Usage
from praval import Agent

agent = Agent("assistant")
print(agent.chat("Hello, how are you?"))


# Example 2: Stateful Conversations
agent = Agent("personal_assistant", persist_state=True)
agent.chat("My name is Alice and I'm learning Python")
agent.chat("I'm particularly interested in web development")

# Later, even in a different session...
agent = Agent("personal_assistant", persist_state=True)
response = agent.chat("What am I learning about?")
# Agent remembers: "You're learning Python, specifically web development"


# Example 3: Using Tools
agent = Agent("researcher")

@agent.tool
def calculate(expression: str) -> float:
    """Safely evaluate a mathematical expression"""
    return eval(expression)

@agent.tool  
def get_date() -> str: