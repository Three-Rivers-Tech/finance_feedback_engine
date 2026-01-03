-- ============================================================================
-- Finance Feedback Engine PostgreSQL Initialization Script
-- Executed on first PostgreSQL container startup
-- ============================================================================

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Create schema version table for Alembic
CREATE TABLE IF NOT EXISTS alembic_version (
    version_num VARCHAR(32) NOT NULL,
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Grant privileges to ffe_user
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO ffe_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO ffe_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO ffe_user;

GRANT ALL PRIVILEGES ON DATABASE ffe TO ffe_user;
GRANT ALL PRIVILEGES ON SCHEMA public TO ffe_user;

-- Log initialization complete
SELECT 'Finance Feedback Engine PostgreSQL database initialized successfully' AS status;
