# Google OAuth environment setup

## Development (Unpacked Extension)

### Dashboard OAuth client

1. In Google Cloud Console → **APIs & Services → Credentials**, create a **Web application** OAuth client.
2. Add an authorized redirect URI exactly matching your local setup:
   ```
   http://localhost:5173/api/gmail/oauth/callback
   ```
   (Adjust port if your Vite dev server uses a different one.)
3. Copy the **Client ID** and **Client Secret** into your `.env`:
   ```
   GOOGLE_OAUTH_CLIENT_ID=<client-id>
   GOOGLE_OAUTH_CLIENT_SECRET=<client-secret>
   ```
4. Add your developer Google account as a **test user** on the OAuth consent screen.

### Extension OAuth client (separate client)

1. Create a **Chrome Extension** OAuth client in the same Google Cloud project.
2. Enter the unpacked extension's ID in the **Extension ID** field.
3. Copy the **Client ID** (public identifier — no secret is used by extensions) into `manifest.json`:
   ```json
   "oauth2": {
     "client_id": "<client-id>.apps.googleusercontent.com",
     "scopes": ["https://www.googleapis.com/auth/gmail.readonly"]
   }
   ```
4. Rebuild the extension: `npm run build`
5. Reload the unpacked extension in `chrome://extensions`
6. Add the extension ID to the backend `.env`:
   ```
   ALLOWED_EXTENSION_IDS=<extension-id>
   ```
7. Add your developer account as a **test user** on the consent screen (same account can be used for both clients).

### Stabilizing the extension ID

An unpacked extension's ID is derived from its key. If you reload from a different location, the ID changes. To stabilize it:

1. After first load, go to `chrome://extensions` → click **Details** → note the ID
2. Open the extension's internal state, export the public key, and add it to `manifest.json` as a `"key"` field
3. Alternatively, use the same directory consistently — the ID stays stable as long as the directory doesn't change

### Consent screen status

Keep the consent screen in **Testing** status during development. Only named test users can complete the OAuth flow in Testing mode. The `gmail.readonly` scope is restricted.

## Production

Use a separate Google Cloud project and separate OAuth clients for production:

- **Dashboard:** Web application client with production HTTPS redirect URI
- **Extension:** Chrome Extension client with the published store extension ID

`PUBLIC_API_BASE_URL` must use HTTPS. `ALLOWED_EXTENSION_IDS` must contain the production store extension ID. `ALLOWED_WEB_ORIGINS` must contain the production dashboard origin.

`gmail.readonly` is a restricted Gmail scope. Sending Gmail-derived message metadata (subjects, senders, snippets) to a backend may require a Google security assessment before public release. Review the current Google Workspace API User Data Policy before submitting for OAuth verification.

Do not request `gmail.modify` until mutation features are user-visible, explicitly approved, tested, and ready for verification. Phase 2 remains strictly read-only.

## Scope policy

| Scope | Where used | Notes |
|---|---|---|
| `gmail.readonly` | Extension only (via `chrome.identity`) | Never forwarded to backend |
| `gmail.modify` (dashboard) | Dashboard backend, existing scan routes | Not available to extension |

The extension Gmail token stays inside Chrome Identity. It is never sent to the organizer backend. The backend receives only an organizer access JWT derived from the pairing workflow.
