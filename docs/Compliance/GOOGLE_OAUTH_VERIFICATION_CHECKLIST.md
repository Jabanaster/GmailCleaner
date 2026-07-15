# Google OAuth Verification Checklist

## 1. Restricted Gmail Scope Inventory
- Scope: `https://www.googleapis.com/auth/gmail.readonly`
- Justification: Used to read emails and headers for classification. Allows the AI engine to categorise and suggest cleanups without editing or writing messages.

## 2. Demo Video Checklist
- [ ] Show the OAuth login process starting from the app homepage.
- [ ] Ensure the browser address bar is visible, showing the full client ID.
- [ ] Show consent screen displaying the app name matching GCP project credentials.
- [ ] Explain how user data is read-only, classified, and shown in the dashboard.
- [ ] Demonstrate dry-runs, review queues, and recovery tab capabilities.

## 3. Domain Verification Checklist
- [ ] Verify ownership of the app's domain in Google Search Console.
- [ ] Add the verified domain under the GCP console Authorized Domains section.
- [ ] Set redirect URIs matching the HTTPS verified domain.
