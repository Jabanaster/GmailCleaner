# Environment and Secret Management

- Store all API credentials (`GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, `OAUTH_TOKEN_ENCRYPTION_KEY`) in environment variables.
- Never commit `.env` or local secrets to repository history.
- Run validation checks on app startup to fail-fast if required environment parameters are missing.
