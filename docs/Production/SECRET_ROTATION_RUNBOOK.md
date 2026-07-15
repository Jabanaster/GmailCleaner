# Secret Rotation Runbook — GmailCleaner

> **Status**: Pre-production beta.  
> **Last updated**: 2026-07-15

> [!IMPORTANT]
> Never print, log, or commit secret values. This runbook uses placeholder
> labels only. Secret values are never shown here.

---

## Secrets Managed

| Secret | Environment Variable | Rotation Impact |
|---|---|---|
| JWT signing secret | `JWT_SIGNING_SECRET` | All extension sessions invalidated immediately |
| OAuth token encryption key | `OAUTH_TOKEN_ENCRYPTION_KEY` | All stored OAuth tokens must be re-encrypted or re-authorized |
| Google OAuth client secret | `GOOGLE_OAUTH_CLIENT_SECRET` | All users must re-authorize via OAuth flow |
| Dashboard session secret | Derived from `JWT_SIGNING_SECRET` | All dashboard sessions invalidated |
| Database connection URL | `DBE91F0215_DATABASE_URL` | Requires restart with new URL |

---

## 1. Rotating `JWT_SIGNING_SECRET`

**Impact**: All extension access tokens and refresh tokens are immediately invalidated. Users will be logged out of the extension and must re-pair.

**Steps**:

1. Generate a new secret (≥ 32 characters):
   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```
2. Update the environment variable in your hosting dashboard (Render / Cloud Run).
3. Redeploy the service.
4. Notify users: *"Extension requires re-pairing after security update."*

---

## 2. Rotating `OAUTH_TOKEN_ENCRYPTION_KEY`

**Impact**: All stored OAuth tokens are encrypted with the old key. After rotation, existing tokens cannot be decrypted and users must re-authorize via Gmail OAuth.

> [!CAUTION]
> This is a destructive operation. All users will lose their stored OAuth
> session and must re-grant Gmail access. Plan accordingly.

**Steps**:

1. Generate a new Fernet key:
   ```bash
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```
2. **Optional**: Before rotating, use `DELETE /api/user/account` or direct DB commands to clear all `gmail_oauth_tokens` rows (users will need to re-authorize regardless).
3. Update `OAUTH_TOKEN_ENCRYPTION_KEY` in the hosting environment.
4. Redeploy.
5. All users will be prompted to re-authorize Gmail on next visit.

---

## 3. Rotating `GOOGLE_OAUTH_CLIENT_SECRET`

**Impact**: All in-progress OAuth flows fail. Existing stored tokens are unaffected (they do not require the client secret for API calls after exchange), but new authorizations and token refreshes will fail until the new secret is deployed.

**Steps**:

1. In **Google Cloud Console → APIs & Services → Credentials**, generate a new client secret.
2. Update `GOOGLE_OAUTH_CLIENT_SECRET` in your hosting environment.
3. Redeploy immediately (minimize window of failure).
4. Revoke the old client secret in Google Cloud Console after confirming the new one works.

---

## 4. Rotating the Database URL / Credentials

1. Create new database credentials in Neon / Render Postgres dashboard.
2. Update `DBE91F0215_DATABASE_URL` in the hosting environment.
3. Redeploy.
4. Revoke old credentials in the database provider.
5. Verify `/api/health` and scan status return 200.

---

## Post-Rotation Checklist

- [ ] Health check passes.
- [ ] OAuth login completes end-to-end.
- [ ] Extension pairs successfully (new pairing code).
- [ ] Dry-run scan completes.
- [ ] Old secret/credential revoked at source.
- [ ] Incident note filed if rotation was due to a breach or suspected exposure.
