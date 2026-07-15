# User Data Deletion Plan

- **Tokens**: Purge the user's stored OAuth credentials and active session states immediately upon account deletion or disconnect.
- **Logs & Classifications**: Automatically cascade delete entries in `scan_runs`, `email_classifications`, `operation_batches`, `email_action_logs`, and `recovery_action_logs` tied to the deleted user's email.
- **Audit confirmation**: Log data-purging completions in application diagnostics without storing identifiable user data.
