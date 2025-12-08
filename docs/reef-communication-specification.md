# Reef Communication System Specification

## Overview

The Reef system enables knowledge-first communication between Praval agents. Like how coral reefs facilitate communication between polyps through chemical and biological signals, this system allows agents to exchange structured knowledge through JSON message queues.

## Design Philosophy

Following Praval's coral ecosystem metaphor:

- **Reef** = The message queue network connecting all agents
- **Spores** = JSON messages containing knowledge, data, or requests  
- **Channels** = Named message channels within the reef
- **Agents** = Coral polyps that communicate through the reef

## Core Requirements

### 1. Knowledge-First Communication
- All communication must be structured JSON containing knowledge/data
- Messages should carry semantic meaning, not just commands
- Support for different knowledge types (facts, questions, discoveries, etc.)

### 2. Agent Discovery Integration
- Seamless integration with existing Praval registry system
- Agents can discover reef channels through the registry
- Dynamic subscription/unsubscription from reef channels

### 3. Multiple Communication Patterns
- **Point-to-Point**: Direct agent-to-agent knowledge sharing
- **Broadcast**: Knowledge sharing with all agents in a channel
- **Request-Response**: Structured knowledge queries and replies
- **Publish-Subscribe**: Topic-based knowledge distribution

### 4. Reliability and Performance
- Message persistence with configurable retention
- Automatic cleanup of expired messages
- Thread-safe operations for concurrent access
- Graceful handling of network failures

### 5. Simple API Surface
- Intuitive methods that match the reef metaphor
- Minimal configuration required for basic usage
- Advanced features available when needed

## @agent Decorator Integration (v0.7.16+)

### Default Channel Behavior

When using the `@agent` decorator with `broadcast()`:

```python
from praval import agent, broadcast

@agent("researcher", responds_to=["task"])
def researcher(spore):
    # broadcast() defaults to reef's "main" channel
    broadcast({"type": "result", "data": "..."})

    # Explicitly specify a different channel
    broadcast({"type": "private_update"}, channel="internal")
```

**Key behavior:**
- `broadcast()` without a channel parameter sends to the **"main"** channel
- All agents are subscribed to the "main" channel by default
- This enables simple agent chaining without explicit channel management

### The `responds_to` Filter

The `responds_to` parameter filters which messages an agent processes:

```python
@agent("writer", responds_to=["research_complete", "update_request"])
def writer(spore):
    # This agent ONLY processes messages where:
    # spore.knowledge["type"] in ["research_complete", "update_request"]
    msg_type = spore.knowledge.get("type")
    print(f"Processing: {msg_type}")
```

**Filter mechanism:**
1. Agent receives spore from reef
2. Checks `spore.knowledge.get("type")`
3. If type is in `responds_to` list → process message
4. If type is NOT in list → silently ignore

**Special cases:**
- `responds_to=None` (default): Agent receives ALL messages
- `responds_to=[]` (empty list): Agent receives NO messages

### Message Flow Diagram

```
start_agents(initial_data={"type": "task", "query": "..."})
                        |
                        v
                   [main channel]
                        |
        +---------------+---------------+
        |                               |
        v                               v
  [researcher]                    [analyzer]
  responds_to: ["task"]          responds_to: ["task"]
        |                               |
   broadcast()                     broadcast()
  type: "research_done"           type: "analysis_done"
        |                               |
        v                               v
                   [main channel]
                        |
                        v
                    [writer]
           responds_to: ["research_done",
                        "analysis_done"]
```

## API Specification

### Core Classes

#### Spore
```python
@dataclass
class Spore:
    """A knowledge-carrying message that flows through the reef."""
    id: str
    spore_type: SporeType  # KNOWLEDGE, REQUEST, RESPONSE, BROADCAST, NOTIFICATION
    from_agent: str
    to_agent: Optional[str]  # None for broadcasts
    knowledge: Dict[str, Any]  # The actual data payload
    created_at: datetime
    expires_at: Optional[datetime] = None
    priority: int = 5  # 1-10, higher = more urgent
    reply_to: Optional[str] = None  # For request-response patterns
    metadata: Dict[str, Any] = None
```

#### ReefChannel
```python
class ReefChannel:
    """A message channel within the reef."""
    
    def __init__(self, name: str, max_capacity: int = 1000)
    def send_spore(self, spore: Spore) -> bool
    def subscribe(self, agent_name: str, handler: Callable[[Spore], None]) -> None
    def unsubscribe(self, agent_name: str) -> None
    def get_spores_for_agent(self, agent_name: str, limit: int = 10) -> List[Spore]
    def cleanup_expired(self) -> int
```

#### Reef
```python
class Reef:
    """The message queue network connecting all agents."""
    
    def create_channel(self, name: str, max_capacity: int = 1000) -> ReefChannel
    def get_channel(self, name: str) -> Optional[ReefChannel]
    
    def send(self, from_agent: str, to_agent: Optional[str], 
             knowledge: Dict[str, Any], **options) -> str
    
    def broadcast(self, from_agent: str, knowledge: Dict[str, Any], 
                  channel: str = "main") -> str
    
    def request(self, from_agent: str, to_agent: str, 
                request: Dict[str, Any], **options) -> str
    
    def reply(self, from_agent: str, to_agent: str, 
              response: Dict[str, Any], reply_to_spore_id: str, 
              **options) -> str
    
    def subscribe(self, agent_name: str, handler: Callable[[Spore], None],
                  channel: str = "main") -> None
```

### Agent Integration

#### Enhanced Agent Class
```python
class Agent:
    # Existing methods...
    
    def send_knowledge(self, to_agent: str, knowledge: Dict[str, Any], 
                      channel: str = "main") -> str
    
    def broadcast_knowledge(self, knowledge: Dict[str, Any], 
                           channel: str = "main") -> str
    
    def request_knowledge(self, from_agent: str, request: Dict[str, Any], 
                         timeout: int = 30) -> Optional[Dict[str, Any]]
    
    def on_spore_received(self, spore: Spore) -> None
    
    def subscribe_to_channel(self, channel_name: str) -> None
    def unsubscribe_from_channel(self, channel_name: str) -> None
```

## Usage Examples

### Basic Knowledge Sharing
```python
from praval import Agent, get_reef

# Create agents
researcher = Agent("researcher", system_message="You research topics deeply")
analyzer = Agent("analyzer", system_message="You analyze data patterns")

# Register agents (existing Praval functionality)
register_agent(researcher)
register_agent(analyzer)

# Share knowledge between agents
researcher.send_knowledge("analyzer", {
    "topic": "machine_learning_trends",
    "findings": ["transformer_architectures_dominant", "multimodal_growth"],
    "confidence": 0.85,
    "sources": ["arxiv_papers", "industry_reports"]
})
```

### Request-Response Pattern
```python
# Agent requests knowledge from another
response = researcher.request_knowledge("analyzer", {
    "query": "analyze_patterns",
    "data_type": "research_papers",
    "filter": "last_6_months"
})

print(f"Analysis result: {response}")
```

### Broadcast Knowledge Discovery
```python
# Broadcast discovery to all agents
researcher.broadcast_knowledge({
    "discovery": "new_architecture_breakthrough",
    "details": "...",
    "significance": "high",
    "applications": ["nlp", "computer_vision"]
})
```

### Multi-Channel Communication
```python
reef = get_reef()

# Create specialized channels
reef.create_channel("research", max_capacity=500)
reef.create_channel("alerts", max_capacity=100)

# Agents can subscribe to specific channels
researcher.subscribe_to_channel("research")
analyzer.subscribe_to_channel("alerts")
```

## Implementation Requirements

### 1. Thread Safety
- All operations must be thread-safe using appropriate locking
- Concurrent message sending/receiving should work without data corruption
- Background cleanup should not interfere with active operations

### 2. Performance Characteristics
- O(1) message sending
- O(log n) message retrieval for targeted messages
- Configurable memory limits to prevent unbounded growth
- Automatic cleanup of expired messages

### 3. Error Handling
- Graceful handling of network failures
- Retry mechanisms for critical messages
- Logging of communication errors
- Circuit breaker pattern for failing agents

### 4. Testing Requirements
- Unit tests for all core classes
- Integration tests with the Agent system
- Performance tests for high message volumes
- Concurrency tests for thread safety
- Error condition tests

### 5. Configuration
- Global network configuration through environment variables
- Per-current configuration options
- Agent-specific communication preferences
- Message retention policies

## Advanced Features (v0.7.18+)

The following features are available with optional dependencies:

1. **Network Distribution** - Multi-process/distributed communication via AMQP (RabbitMQ), MQTT, or STOMP protocols. Install with `pip install praval[secure]`
2. **Message Encryption** - End-to-end encryption using PyNaCl with key management. Available through `SecureReef` class
3. **Transport Abstraction** - Protocol-agnostic message transport supporting multiple backends

## Current Limitations

1. **Persistence Across Process Restarts** - Messages are in-memory only for the default Reef
2. **Complex Routing** - Simple direct and broadcast patterns only
3. **Message Ordering Guarantees** - Best-effort delivery

## Success Criteria

1. Agents can seamlessly discover and communicate with each other
2. Knowledge sharing happens through structured JSON messages
3. Multiple communication patterns work reliably
4. System integrates cleanly with existing Praval registry
5. Performance remains good with hundreds of agents and thousands of messages
6. API is intuitive and matches the coral/ocean metaphor
7. Comprehensive test coverage (>90%)

## Migration Strategy

1. Implement core Reef system with comprehensive tests
2. Add communication methods to existing Agent class  
3. Update registry to support reef channel discovery
4. Provide examples and documentation
5. Maintain backward compatibility with existing Agent functionality

This specification provides the foundation for implementing knowledge-first agent communication while staying true to Praval's coral ecosystem philosophy.