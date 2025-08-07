-- PostgreSQL initialization script for Praval
-- Optional database for structured data storage

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Agent metadata table
CREATE TABLE IF NOT EXISTS agents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL UNIQUE,
    description TEXT,
    system_message TEXT,
    config JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Agent sessions table
CREATE TABLE IF NOT EXISTS agent_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id UUID REFERENCES agents(id),
    session_name VARCHAR(255),
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP,
    metadata JSONB DEFAULT '{}'
);

-- Memory metadata table (references to Qdrant)
CREATE TABLE IF NOT EXISTS memory_metadata (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id UUID REFERENCES agents(id),
    memory_id VARCHAR(255) NOT NULL, -- References Qdrant point ID
    memory_type VARCHAR(50) NOT NULL,
    importance REAL DEFAULT 0.5,
    tags TEXT[],
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    access_count INTEGER DEFAULT 1
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_agents_name ON agents(name);
CREATE INDEX IF NOT EXISTS idx_memory_agent_id ON memory_metadata(agent_id);
CREATE INDEX IF NOT EXISTS idx_memory_type ON memory_metadata(memory_type);
CREATE INDEX IF NOT EXISTS idx_memory_importance ON memory_metadata(importance);
CREATE INDEX IF NOT EXISTS idx_memory_created_at ON memory_metadata(created_at);

-- Update timestamp function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger for agents table
CREATE TRIGGER update_agents_updated_at 
    BEFORE UPDATE ON agents 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();