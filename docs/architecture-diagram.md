# Praval Framework Architecture

This document contains the comprehensive architecture diagram for the Praval framework, showing the relationships between all major components.

## Framework Architecture

```mermaid
graph TB
    %% User Interface Layer
    subgraph "User Interface Layer"
        UD[User Code/Decorators]
        API[Praval API]
        Examples[Examples & Applications]
    end
    
    %% Core Framework Layer
    subgraph "Core Framework Layer"
        subgraph "Agent System"
            Agent[Agent Class]
            Decorator[Agent Decorator]
            Registry[Agent Registry]
            Composition[Agent Composition]
        end
        
        subgraph "Communication System (Reef)"
            Reef[Reef Network]
            Spore[Spore Messages]
            Channels[ReefChannels]
            SecureReef[Secure Reef]
            SecureSpore[Secure Spores]
            Transport[Transport Layer]
        end
        
        subgraph "Memory System"
            MemMgr[Memory Manager]
            STM[Short-Term Memory]
            LTM[Long-Term Memory]
            Episodic[Episodic Memory]
            Semantic[Semantic Memory]
            EmbedStore[Embedded Store]
        end
        
        subgraph "Storage System"
            DataMgr[Data Manager]
            StorageReg[Storage Registry]
            BaseProvider[Base Provider]
        end
    end
    
    %% Provider Layer
    subgraph "LLM Provider Layer"
        ProviderFactory[Provider Factory]
        OpenAI[OpenAI Provider]
        Anthropic[Anthropic Provider]
        Cohere[Cohere Provider]
    end
    
    %% Storage Provider Layer
    subgraph "Storage Providers"
        FS[FileSystem]
        PG[PostgreSQL]
        Redis[Redis]
        S3[S3]
        Qdrant[Qdrant]
    end
    
    %% External Services Layer
    subgraph "External Services"
        OpenAIAPI[OpenAI API]
        AnthropicAPI[Anthropic API]
        CohereAPI[Cohere API]
        QdrantDB[(Qdrant DB)]
        PostgresDB[(PostgreSQL)]
        RedisDB[(Redis)]
        S3Store[(S3 Storage)]
    end
    
    %% User Interface connections
    UD --> API
    API --> Decorator
    API --> Agent
    API --> MemMgr
    API --> DataMgr
    Examples --> API
    
    %% Core Framework connections
    Decorator --> Agent
    Decorator --> Registry
    Decorator --> Reef
    Agent --> ProviderFactory
    Agent --> MemMgr
    Agent --> DataMgr
    Registry --> Agent
    Composition --> Agent
    Composition --> Registry
    
    %% Communication System connections
    Reef --> Spore
    Reef --> Channels
    SecureReef --> Reef
    SecureReef --> SecureSpore
    SecureSpore --> Spore
    Transport --> Reef
    Agent --> Reef
    
    %% Memory System connections
    MemMgr --> STM
    MemMgr --> LTM
    MemMgr --> Episodic
    MemMgr --> Semantic
    LTM --> EmbedStore
    EmbedStore --> Qdrant
    
    %% Storage System connections
    DataMgr --> StorageReg
    StorageReg --> BaseProvider
    BaseProvider --> FS
    BaseProvider --> PG
    BaseProvider --> Redis
    BaseProvider --> S3
    BaseProvider --> Qdrant
    
    %% Provider connections
    ProviderFactory --> OpenAI
    ProviderFactory --> Anthropic
    ProviderFactory --> Cohere
    
    %% External Service connections
    OpenAI --> OpenAIAPI
    Anthropic --> AnthropicAPI
    Cohere --> CohereAPI
    Qdrant --> QdrantDB
    PG --> PostgresDB
    Redis --> RedisDB
    S3 --> S3Store
    
    %% Styling
    classDef userLayer fill:#e1f5fe,stroke:#01579b,stroke-width:2px
    classDef coreLayer fill:#f3e5f5,stroke:#4a148c,stroke-width:2px
    classDef providerLayer fill:#e8f5e8,stroke:#1b5e20,stroke-width:2px
    classDef storageLayer fill:#fff3e0,stroke:#e65100,stroke-width:2px
    classDef externalLayer fill:#fce4ec,stroke:#880e4f,stroke-width:2px
    
    class UD,API,Examples userLayer
    class Agent,Decorator,Registry,Composition,Reef,Spore,Channels,SecureReef,SecureSpore,Transport,MemMgr,STM,LTM,Episodic,Semantic,EmbedStore,DataMgr,StorageReg,BaseProvider coreLayer
    class ProviderFactory,OpenAI,Anthropic,Cohere providerLayer
    class FS,PG,Redis,S3,Qdrant storageLayer
    class OpenAIAPI,AnthropicAPI,CohereAPI,QdrantDB,PostgresDB,RedisDB,S3Store externalLayer
```

## Component Descriptions

### User Interface Layer
- **User Code/Decorators**: Application code using Praval's decorator-based API
- **Praval API**: Main framework API exposed to users
- **Examples & Applications**: Sample applications demonstrating framework capabilities

### Core Framework Layer

#### Agent System
- **Agent Class**: Core agent implementation with LLM integration
- **Agent Decorator**: Pythonic `@agent` decorator for creating agents from functions
- **Agent Registry**: Discovery and management of agent instances
- **Agent Composition**: Orchestration and workflow management

#### Communication System (Reef)
- **Reef Network**: Message queue system inspired by coral reef communication
- **Spore Messages**: JSON-based knowledge-carrying messages
- **ReefChannels**: Named communication channels
- **Secure Reef**: Enterprise security layer for reef communication
- **Secure Spores**: Encrypted and authenticated spore messages
- **Transport Layer**: Pluggable transport mechanisms (AMQP, MQTT, STOMP)

#### Memory System
- **Memory Manager**: Unified interface coordinating all memory types
- **Short-Term Memory**: Fast working memory for immediate context
- **Long-Term Memory**: Persistent vector storage via Qdrant
- **Episodic Memory**: Conversation history and experience tracking
- **Semantic Memory**: Knowledge and fact storage
- **Embedded Store**: Vector embedding management

#### Storage System
- **Data Manager**: Unified interface for all storage operations
- **Storage Registry**: Registration and discovery of storage providers
- **Base Provider**: Abstract base class for storage implementations

### Provider Layers
- **Provider Factory**: Creates appropriate LLM provider instances
- **LLM Providers**: OpenAI, Anthropic, and Cohere integrations
- **Storage Providers**: Multiple backend implementations (PostgreSQL, Redis, S3, Qdrant, FileSystem)

### External Services
- External APIs and databases that providers connect to

## Key Design Patterns

1. **Coral Reef Metaphor**: Agents communicate through spores in reef channels, mimicking biological systems
2. **Decorator-Based API**: Simple agent decorator transforms functions into intelligent agents
3. **Multi-Provider Architecture**: Pluggable LLM and storage providers for flexibility
4. **Memory Hierarchy**: Multi-layered memory system from short-term to semantic storage
5. **Self-Organization**: Agents coordinate autonomously without central orchestration

## Data Flow

1. **User creates agents** using the agent decorator
2. **Agents communicate** through spores in reef channels
3. **Memory system** stores and retrieves context across interactions
4. **Storage system** persists data across multiple backends
5. **LLM providers** process requests and generate responses
6. **Results flow back** through the reef to requesting agents