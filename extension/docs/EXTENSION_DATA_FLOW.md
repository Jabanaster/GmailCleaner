# Extension data flow and retention boundary

## Architecture overview

```
Gmail API
  → MV3 service worker (Gmail OAuth token stays here, never forwarded)
  → minimized message metadata only
  → authenticated FastAPI classification endpoint (organizer JWT)
  → server-side Gemini classification
  → user-owned classification proposals
  → popup / side-panel UI
```

## Data sent for classification

The service worker requests Gmail's **metadata** representation only. It sends:

- Gmail message ID and thread ID
- Subject and From headers
- Received timestamp (from `internalDate`)
- Gmail-provided snippet (up to ~100 chars)
- Existing label IDs (e.g., `INBOX`, `UNREAD`)

It does **not** request or transmit:
- Full message body
- Attachments
- MIME parts beyond headers
- Any other metadata fields

Gemini is called only server-side. The extension never calls Gemini directly.

## Authentication separation

### Gmail token
- Held by Chrome Identity (`chrome.identity.getAuthToken`)
- Used only for `gmail.googleapis.com` and `www.googleapis.com` calls within the service worker
- **Never sent to the organizer backend**
- Not accessible to React popup/sidepanel/options pages (they send runtime messages to the service worker)

### Organizer access token
- Stored in `chrome.storage.session` — disappears when the browser session ends
- Used only as a Bearer token in requests to the organizer backend
- Short-lived (10-minute default TTL)
- Rotated via refresh when expired

### Organizer refresh token
- Stored in `chrome.storage.local` — persists across browser restarts
- Read only by service-worker modules (`backend-auth.ts`, `chrome-storage.ts`)
- React UI pages receive only connection status and safe session metadata — never the raw credential
- Changing the backend URL clears both organizer credentials automatically

## Token lifecycle and refresh

```
1. Access token present → use directly
2. Access token absent → attempt silent refresh
3. 401 response from backend → attempt exactly one refresh
4. Refresh succeeds → new access token stored in session, new refresh token stored locally
5. Refresh fails → credentials cleared, state becomes "expired"/"unpaired"
```

The `withBackendAuth()` helper enforces at most one retry per request. An infinite loop cannot occur.

## Refresh token rotation

Every successful refresh rotates the token:
- Old token hash is recorded in `extension_refresh_token_history`
- New hash replaces it in `extension_device_sessions`
- `rotation_counter` increments

**Reuse detection:** If a previously-seen token hash is presented again, the device session is immediately revoked and the event is recorded in `extension_audit_events`. No token values are stored in audit events — only hashes.

## Device revocation

From the dashboard, any paired device can be revoked. This sets `revoked_at` on the device session:
- New refresh attempts immediately fail (session row check)
- Existing short-lived access tokens may succeed until their TTL expires (by design — they are stateless JWTs)
- The extension detects the revoked state on the next `/api/extension/auth/me` call and clears credentials

## Persistence and deletion

| Data | Storage | Cleared when |
|---|---|---|
| Gmail access token | Chrome Identity (managed) | Chrome manages expiry/revocation |
| Organizer access token | `chrome.storage.session` | Browser session ends or explicit disconnect |
| Organizer refresh token | `chrome.storage.local` | Explicit disconnect, backend URL change, or revocation detected |
| Extension settings | `chrome.storage.local` | Never (unless factory reset) |
| Latest scan status | `chrome.storage.local` | Overwritten on next scan |
| Classification proposals | Transient in service worker | Not persisted by Phase 2 endpoint |

Dashboard scan history is stored in the application database under the dashboard user's email-based ownership, not under the extension device session.

## CORS behavior

The backend allows only explicitly configured origins:
- `ALLOWED_WEB_ORIGINS` — dashboard web origins
- `ALLOWED_EXTENSION_IDS` — each ID produces a `chrome-extension://<ID>` origin

Wildcard `*` CORS is forbidden. Unknown origins receive no `Access-Control-Allow-Origin` header. The extension's `host_permissions` in `manifest.json` controls which URLs `fetch()` may reach.

## Security limitations

Chrome local storage is not a hardware-backed secret store. A compromised browser profile, malware, or a compromised extension update may recover the refresh credential. The following server-side mitigations are required:

- Refresh token rotation on every use
- Reuse detection with immediate device revocation
- Short access token TTL (10 min default)
- Device revocation from dashboard
- Least-privilege scopes (`classify:submit`, `scan:create`, `scan:read`)
- Audit events for all auth failures and revocations

## No mutation in Phase 2

No Gmail mutation is available in the extension in Phase 2. No labels are written, no messages are archived, deleted, trashed, or marked read/unread. The read-only boundary is enforced at the manifest scope level (`gmail.readonly`) and in the absence of any mutation API calls in the source.
