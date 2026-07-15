-- Migration: Create recovery_action_logs table
CREATE TABLE IF NOT EXISTS recovery_action_logs (
    id SERIAL PRIMARY KEY,
    operation_batch_id INTEGER REFERENCES operation_batches(id),
    scan_run_id INTEGER REFERENCES scan_runs(id),
    user_email VARCHAR(255) NOT NULL,
    gmail_message_id VARCHAR(255) NOT NULL,
    recovery_action VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
