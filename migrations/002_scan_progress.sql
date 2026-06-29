-- Migration: Add total_emails column to scan_runs for progress tracking
ALTER TABLE scan_runs ADD COLUMN IF NOT EXISTS total_emails INTEGER DEFAULT 0;
