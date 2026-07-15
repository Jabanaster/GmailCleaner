# Logging and Redaction Policy

- **PII Scrubbing**: Scrub email addresses, subject lines, message body text, and OAuth tokens from application stdout logs.
- Logging should strictly track operational metrics, category outcomes, execution times, and sanitized error messages.
- Any unexpected payload fields sent to classification engines must be validated and sanitized prior to parsing.
