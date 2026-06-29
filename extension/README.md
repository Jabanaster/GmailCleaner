# Google Email Organizer — Chrome Extension

A Manifest V3 Chrome extension that provides a read-only Gmail classification preview using the organizer backend.

## Scope

The extension requests only `gmail.readonly`. No Gmail mutation methods (`modify`, `delete`, `trash`, `archive`, `mark as read`) are implemented or called. This remains the boundary for Phase 2.

## Building

```powershell
npm install
npm run typecheck   # Type check
npm test            # Unit tests
npm run build       # Production bundle → dist/
```

## Loading in Chrome (Development)

1. Open `chrome://extensions`
2. Enable **Developer mode** (toggle top-right)
3. Click **Load unpacked**
4. Select the `extension/dist` directory
5. Copy the **Extension ID** shown on the card (e.g., `abcdefghijklmnopabcdefghijklmnop`)

## OAuth Configuration

### 1. Create a Chrome Extension OAuth client

In your Google Cloud Console project:

1. Go to **APIs & Services → Credentials → Create Credentials → OAuth client ID**
2. Choose **Chrome Extension** as the application type
3. Enter your extension's ID in the **Extension ID** field
4. Copy the **Client ID** (ends in `.apps.googleusercontent.com`) — this is a public identifier
5. Do **not** copy or use the client secret — Chrome extensions do not use client secrets

### 2. Update manifest.json

Replace the placeholder in `manifest.json`:

```json
"oauth2": {
  "client_id": "YOUR_ACTUAL_CLIENT_ID.apps.googleusercontent.com",
  "scopes": ["https://www.googleapis.com/auth/gmail.readonly"]
}
```

After editing, rebuild: `npm run build`, then reload the unpacked extension in Chrome.

### 3. Configure the backend allowlist

Add your extension ID to the backend `.env`:

```
ALLOWED_EXTENSION_IDS=abcdefghijklmnopabcdefghijklmnop
```

Restart the backend after changing this.

### 4. OAuth consent screen

Keep the consent screen in **Testing** mode during development. Add each developer's Google account as a test user. The `gmail.readonly` scope is a restricted scope — a production release requires OAuth verification.

See [docs/OAUTH_ENVIRONMENTS.md](docs/OAUTH_ENVIRONMENTS.md) for full environment guidance.

## Settings

The extension options page (`Options` link in Chrome extension card) allows configuring:

- **Backend URL** — the organizer API base URL (e.g., `http://localhost:5273`)
- **Scan limit** — maximum messages to fetch per preview scan (1–50)
- **Dry run mode** — display proposals without any actions

## Pairing Workflow

1. Log in to the dashboard at the configured backend URL
2. Generate a one-time pairing code (valid 10 minutes)
3. Open extension options → enter backend URL + pairing code → click **Pair**
4. The extension stores an organizer session — the popup and side panel show **Paired** state

## Data Flow

```
Gmail API → service worker (Gmail token stays here)
  → minimized metadata (subject, from, snippet, label IDs)
  → authenticated FastAPI endpoint
  → server-side Gemini classifier
  → classification proposals
  → popup / side panel UI
```

Gmail OAuth tokens are **never sent to the backend**. The organizer access token is stored in `chrome.storage.session` (cleared on browser session end). The rotating refresh token is in `chrome.storage.local`.

## Token Behavior

| Token | Storage | Lifetime | Notes |
|---|---|---|---|
| Gmail access token | Chrome Identity (managed) | ~1 hour | Never forwarded to backend |
| Organizer access token | `chrome.storage.session` | 10 min | Cleared when browser closes |
| Organizer refresh token | `chrome.storage.local` | 30 days | Rotates on every use |

## Security Notes

- Backend URL must use HTTPS in production; HTTP is allowed only for `localhost`/`127.0.0.1` development
- Changing the backend URL automatically clears all organizer credentials
- Refresh token reuse (replay attack) triggers immediate device session revocation on the backend
- The extension verifies `access_token` and `refresh_token` fields are present before storing any credentials
