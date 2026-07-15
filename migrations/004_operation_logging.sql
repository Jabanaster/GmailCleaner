-- Migration: Add operation logging tables
CREATE TABLE IF NOT EXISTS operation_batches (
    id SERIAL PRIMARY KEY,
    user_email VARCHAR(255) NOT NULL,
    scan_run_id INTEGER REFERENCES scan_runs(id),
    dry_run BOOLEAN DEFAULT FALSE,
    status VARCHAR(20) DEFAULT 'running',
    created_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    total_processed INTEGER DEFAULT 0,
    total_failed INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS email_action_logs (
    id SERIAL PRIMARY KEY,
    operation_batch_id INTEGER REFERENCES operation_batches(id),
    scan_run_id INTEGER REFERENCES scan_runs(id),
    user_email VARCHAR(255) NOT NULL,
    gmail_message_id VARCHAR(255) NOT NULL,
    planned_action VARCHAR(50),
    executed_action VARCHAR(50),
    category VARCHAR(50),
    confidence REAL,
    pre_label_ids TEXT,
    post_label_ids TEXT,
    archived_before BOOLEAN DEFAULT FALSE,
    trashed_before BOOLEAN DEFAULT FALSE,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
