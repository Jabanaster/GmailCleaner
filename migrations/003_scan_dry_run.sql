-- Migration: Add dry_run column to scan_runs for scan orchestration preview
ALTER TABLE scan_runs ADD COLUMN IF NOT EXISTS dry_run BOOLEAN DEFAULT FALSE;
