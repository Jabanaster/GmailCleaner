# Limited Private Beta Plan — GmailCleaner v0.3.0-beta.1

> **Status**: Pre-release Beta Plan  
> **Last updated**: 2026-07-15

---

## 1. Private Beta Eligibility

- **Phase 1 (Initial)**: Limited to internal test accounts managed by developers.
- **Phase 2 (Expanded)**: Open to trusted, designated alpha/beta users who explicitly agree to run on non-critical mailboxes.
- **Strict Constraint**: No public or production launch is authorized. The application must not be made available outside the designated group until Google OAuth verification is complete.

---

## 2. Beta Safety Rules

1. **Dry-Run First**: Every user must execute a dry-run scan (Preview Scan) first to inspect how the AI classifies their messages before executing any live modifications.
2. **No Blind Live Scan Mutations**: Real labels or deletion changes to the inbox require explicit confirmation in the UI.
3. **Recovery Preview First**: Users must preview the logs of a scan run under the Recovery tab before triggering any rollback.
4. **Data Deletion Enforced**: Account deletion requests will instantly purge all stored pairing tokens, OAuth codes, and scan logs for that user from the database.

---

## 3. Beta Setup Checklist

- [ ] **Code Base**: Clone the repo from target tag `v0.3.0-beta.1` (Commit `a85be89` or master patch `28bae16`).
- [ ] **Env Config**: Copy `.env.example` to `.env` and fill in:
  - `GOOGLE_OAUTH_CLIENT_ID` (Web Application type)
  - `GOOGLE_OAUTH_CLIENT_SECRET`
  - `PUBLIC_API_BASE_URL=http://localhost:5274`
  - `ALLOWED_WEB_ORIGINS=http://localhost:5274`
- [ ] **Backend Start**: Run `uv sync` and launch via `uvicorn app:asgi --host 127.0.0.1 --port 5274`.
- [ ] **Dashboard Build**: Run `npm ci` and `npm run build`.
- [ ] **Extension Load**: Load the extension folder in Chrome via Developer Mode (`Load unpacked` targeting the `extension/dist/` build directory).

---

## 4. Beta Test Script

1. **Connect Dashboard**: Load `http://localhost:5274`, click **Connect Gmail Account**, and authenticate with the test account.
2. **Pair Extension**:
   - Click **Pair Extension** on the dashboard to copy a pairing code.
   - Open Extension options, paste the code, and click **Pair backend**.
3. **Run Dry-Run Scan**:
   - Go back to the dashboard.
   - Click **Preview Scan (Dry Run)**.
   - Verify the progress bar update and classification output list.
4. **Verify Operation Logs**: Click on the **History** tab and verify the logged dry-run records exist.
5. **Run Recovery Preview**: Go to the **Recovery** tab, click **Review** on the logged run, and check that the proposed labels and changes render correctly in a read-only list.
6. **Test Account Deletion**: Click **Disconnect** or trigger account deletion. Confirm that your local user data is cleanly wiped from the database.

---

## 5. Issue Tracking Categories

- **Blocker**: Security vulnerabilities, unhandled server crashes (500s), or database corruption.
- **Major**: Pairing breaks, scans fail to complete, or OAuth callback loop.
- **Minor**: CSS styling defects, alignment issues, or slow response times.
- **UX Polish**: Layout modifications, modal sizing, or button hover states.
- **Compliance/Deployment**: Missing build files, undocumented parameters, or installation failure.

---

## 6. Go / No-Go Criteria for Release

- [x] **Zero live Gmail mutations** during dry-run.
- [x] **Zero token exposure** in server logs or UI views.
- [x] **Secure session isolation** preventing cross-user data leakage.
- [x] Stable pairing code generation and token rotation.
- [x] Database cascade deletion verified for all user-specific data.

---

## 7. Next Milestones

1. **Private Beta Round 1**: Initial validation with one test Gmail account.
2. **Blocker resolution**: Resolve any critical issues surfaced in Round 1.
3. **Release `v0.3.0-beta.2`** (if code changes are required).
4. **OAuth Verification Prep**: Finalize policy documents and submit app for Google's restricted scopes audit.
5. **Chrome Web Store Submission**: Prep store assets and manifest configuration for review.
