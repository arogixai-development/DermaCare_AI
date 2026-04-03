-- DermaCare AI - PostgreSQL Schema
-- Database initialization script for production deployment

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- ============================================
-- Users Table
-- ============================================
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE,
    hashed_password VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    is_admin BOOLEAN DEFAULT FALSE,
    token_version INTEGER DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP WITH TIME ZONE,
    CONSTRAINT users_username_length CHECK (LENGTH(username) >= 3)
);

-- Indexes for users
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at DESC);

-- ============================================
-- Case Records Table
-- ============================================
CREATE TABLE IF NOT EXISTS case_records (
    id SERIAL PRIMARY KEY,
    case_id VARCHAR(100) UNIQUE NOT NULL,
    user_id VARCHAR(100) NOT NULL,
    timestamp VARCHAR(50) NOT NULL,
    
    -- Patient Demographics
    patient_age INTEGER,
    geographic_region VARCHAR(100),
    skin_phototype VARCHAR(50) DEFAULT 'UNKNOWN',
    occupation VARCHAR(200),
    
    -- Clinical Presentation
    complaint TEXT NOT NULL,
    lesion TEXT,
    symptoms TEXT,
    tests TEXT,
    
    -- Lesion Details
    lesion_history TEXT,
    history_duration VARCHAR(100),
    change_pattern VARCHAR(200),
    previous_biopsies TEXT,
    
    -- AI Analysis Results
    diagnoses_list JSONB,
    reasoning TEXT,
    soap_note JSONB,
    treatment_list JSONB,
    lesion_analysis JSONB,
    recommended_tests JSONB,
    
    -- Metadata
    status VARCHAR(50) DEFAULT 'completed',
    ai_model VARCHAR(100),
    monte_carlo_enabled BOOLEAN DEFAULT FALSE,
    inference_time_seconds FLOAT,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT case_patient_age_range CHECK (patient_age >= 0 AND patient_age <= 120)
);

-- Indexes for case_records
CREATE INDEX IF NOT EXISTS idx_cases_case_id ON case_records(case_id);
CREATE INDEX IF NOT EXISTS idx_cases_user_id ON case_records(user_id);
CREATE INDEX IF NOT EXISTS idx_cases_timestamp ON case_records(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_cases_status ON case_records(status);
CREATE INDEX IF NOT EXISTS idx_cases_complaint_trgm ON case_records USING GIN(complaint gin_trgm_ops);

-- ============================================
-- Diagnosis Logs Table (Audit Trail)
-- ============================================
CREATE TABLE IF NOT EXISTS diagnosis_logs (
    id SERIAL PRIMARY KEY,
    case_id VARCHAR(100) NOT NULL,
    user_id VARCHAR(100) NOT NULL,
    
    -- Request Data
    request_data JSONB NOT NULL,
    llm_prompt TEXT,
    raw_response TEXT,
    
    -- Response Data
    parsed_response JSONB,
    parsing_success BOOLEAN DEFAULT FALSE,
    
    -- Performance Metrics
    inference_time_ms INTEGER,
    total_time_ms INTEGER,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign Key
    CONSTRAINT fk_case_record FOREIGN KEY (case_id) REFERENCES case_records(case_id) ON DELETE CASCADE
);

-- Indexes for diagnosis_logs
CREATE INDEX IF NOT EXISTS idx_logs_case_id ON diagnosis_logs(case_id);
CREATE INDEX IF NOT EXISTS idx_logs_user_id ON diagnosis_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_logs_created_at ON diagnosis_logs(created_at DESC);

-- ============================================
-- Drug Database Table (Optional Local Cache)
-- ============================================
CREATE TABLE IF NOT EXISTS drug_database (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) UNIQUE NOT NULL,
    generic_name VARCHAR(200),
    category VARCHAR(100),
    interactions JSONB,
    side_effects JSONB,
    contraindications JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for drug_database
CREATE INDEX IF NOT EXISTS idx_drugs_name ON drug_database(name);
CREATE INDEX IF NOT EXISTS idx_drugs_category ON drug_database(category);

-- ============================================
-- API Request Logs (Security & Monitoring)
-- ============================================
CREATE TABLE IF NOT EXISTS api_logs (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(100),
    endpoint VARCHAR(200) NOT NULL,
    method VARCHAR(10) NOT NULL,
    status_code INTEGER,
    response_time_ms INTEGER,
    ip_address VARCHAR(45),
    user_agent TEXT,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for api_logs
CREATE INDEX IF NOT EXISTS idx_api_logs_user_id ON api_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_api_logs_endpoint ON api_logs(endpoint);
CREATE INDEX IF NOT EXISTS idx_api_logs_created_at ON api_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_api_logs_status ON api_logs(status_code);

-- ============================================
-- Rate Limiting Table (Persistent)
-- ============================================
CREATE TABLE IF NOT EXISTS rate_limit_data (
    id SERIAL PRIMARY KEY,
    identifier VARCHAR(255) UNIQUE NOT NULL,
    attempt_count INTEGER DEFAULT 0,
    first_attempt TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_attempt TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    locked_until TIMESTAMP WITH TIME ZONE,
    successful_logins INTEGER DEFAULT 0
);

-- Indexes for rate_limit_data
CREATE INDEX IF NOT EXISTS idx_rate_limit_identifier ON rate_limit_data(identifier);
CREATE INDEX IF NOT EXISTS idx_rate_limit_locked ON rate_limit_data(locked_until) WHERE locked_until IS NOT NULL;

-- ============================================
-- Refresh Tokens Table
-- ============================================
CREATE TABLE IF NOT EXISTS refresh_tokens (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR(255) NOT NULL UNIQUE,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    revoked BOOLEAN DEFAULT FALSE,
    revoked_at TIMESTAMP WITH TIME ZONE
);

-- Indexes for refresh_tokens
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user_id ON refresh_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_hash ON refresh_tokens(token_hash);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_expires ON refresh_tokens(expires_at);

-- ============================================
-- Functions and Triggers
-- ============================================

-- Auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply trigger to case_records
DROP TRIGGER IF EXISTS update_case_records_updated_at ON case_records;
CREATE TRIGGER update_case_records_updated_at
    BEFORE UPDATE ON case_records
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Auto-update updated_at timestamp for drugs
DROP TRIGGER IF EXISTS update_drug_database_updated_at ON drug_database;
CREATE TRIGGER update_drug_database_updated_at
    BEFORE UPDATE ON drug_database
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- Default Admin User
-- ============================================
INSERT INTO users (username, email, hashed_password, is_admin, is_active)
VALUES (
    'arogixai@gmail.com',
    'arogixai@gmail.com',
    -- Default password: Arogix9345@ (hashed with bcrypt)
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.FRDhN3hX5F4EK',
    TRUE,
    TRUE
) ON CONFLICT (username) DO NOTHING;

-- ============================================
-- Grant Permissions
-- ============================================
-- Note: These will be set based on the actual DB_USER from environment

-- ============================================
-- Comments
-- ============================================
COMMENT ON TABLE users IS 'User accounts for authentication';
COMMENT ON TABLE case_records IS 'Clinical case records with AI diagnosis results';
COMMENT ON TABLE diagnosis_logs IS 'Audit trail of all AI diagnosis requests';
COMMENT ON TABLE drug_database IS 'Local cache of drug information and interactions';
COMMENT ON TABLE api_logs IS 'API request logs for security monitoring';
COMMENT ON TABLE rate_limit_data IS 'Persistent rate limiting data';
COMMENT ON TABLE refresh_tokens IS 'Refresh token storage for JWT';

-- ============================================
-- Partitioning Setup (Optional for large scale)
-- ============================================
-- For future scaling, consider partitioning:
-- - case_records by month (timestamp)
-- - api_logs by day (created_at)
-- - diagnosis_logs by month (created_at)

COMMENT ON DATABASE IS 'DermaCare AI - Dermatology Clinical Decision Support System';
