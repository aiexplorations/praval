-- Initialize Praval database schema
-- This script creates the necessary tables for the storage demo

-- Create schema for business data
CREATE SCHEMA IF NOT EXISTS business;

-- Customers table for relational data demo
CREATE TABLE IF NOT EXISTS business.customers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    industry VARCHAR(100),
    revenue BIGINT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB
);

-- Sales metrics table
CREATE TABLE IF NOT EXISTS business.sales_metrics (
    id SERIAL PRIMARY KEY,
    period VARCHAR(20) NOT NULL,
    revenue BIGINT NOT NULL,
    growth_rate DECIMAL(5,4),
    customer_count INTEGER,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    details JSONB
);

-- Agent activity log table
CREATE TABLE IF NOT EXISTS business.agent_activities (
    id SERIAL PRIMARY KEY,
    agent_name VARCHAR(100) NOT NULL,
    activity_type VARCHAR(50) NOT NULL,
    description TEXT,
    data JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert sample data for the demo
INSERT INTO business.customers (name, email, industry, revenue, metadata) VALUES
('Acme Corporation', 'contact@acme.com', 'Technology', 1500000, '{"employees": 250, "founded": 2018}'),
('Global Systems Inc', 'hello@globalsystems.com', 'Finance', 2300000, '{"employees": 450, "founded": 2015}'),
('Innovation Labs', 'info@innovationlabs.com', 'Research', 875000, '{"employees": 120, "founded": 2020}'),
('TechFlow Solutions', 'admin@techflow.com', 'Technology', 1200000, '{"employees": 180, "founded": 2019}'),
('DataCorp Analytics', 'contact@datacorp.com', 'Analytics', 1800000, '{"employees": 320, "founded": 2017}')
ON CONFLICT (email) DO NOTHING;

INSERT INTO business.sales_metrics (period, revenue, growth_rate, customer_count, details) VALUES
('Q1_2024', 2500000, 0.15, 150, '{"top_product": "Enterprise Suite", "region": "North America"}'),
('Q2_2024', 2800000, 0.12, 175, '{"top_product": "Analytics Platform", "region": "Europe"}'),
('Q3_2024', 3100000, 0.11, 190, '{"top_product": "AI Tools", "region": "Asia Pacific"}'),
('Q4_2024', 3450000, 0.13, 220, '{"top_product": "Cloud Services", "region": "Global"}')
ON CONFLICT DO NOTHING;

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_customers_industry ON business.customers(industry);
CREATE INDEX IF NOT EXISTS idx_customers_revenue ON business.customers(revenue);
CREATE INDEX IF NOT EXISTS idx_sales_period ON business.sales_metrics(period);
CREATE INDEX IF NOT EXISTS idx_agent_activities_agent ON business.agent_activities(agent_name);
CREATE INDEX IF NOT EXISTS idx_agent_activities_type ON business.agent_activities(activity_type);

-- Create a view for dashboard data
CREATE OR REPLACE VIEW business.dashboard_summary AS
SELECT 
    COUNT(*) as total_customers,
    SUM(revenue) as total_revenue,
    AVG(revenue) as avg_revenue,
    COUNT(DISTINCT industry) as industries_served
FROM business.customers;

-- Grant permissions
GRANT ALL PRIVILEGES ON SCHEMA business TO praval;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA business TO praval;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA business TO praval;

-- Log initialization
INSERT INTO business.agent_activities (agent_name, activity_type, description, data) VALUES
('system', 'initialization', 'Database schema initialized for Praval storage demo', 
 '{"tables_created": ["customers", "sales_metrics", "agent_activities"], "sample_data": true}');

COMMIT;