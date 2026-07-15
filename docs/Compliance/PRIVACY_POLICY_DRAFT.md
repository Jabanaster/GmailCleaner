# Privacy Policy (Draft)

**Note: This is a draft for developmental purposes and does not constitute formal legal advice.**

## 1. What Data GmailCleaner Accesses
GmailCleaner accesses Gmail message metadata (sender, recipient, subject, headers, and dates) and message bodies via the `https://www.googleapis.com/auth/gmail.readonly` scope.

## 2. What Data is Stored
- **OAuth Credentials**: Encrypted OAuth access and refresh tokens.
- **Classification Metadata**: Senders, subjects, classifications, classification reasons, confidence levels, and classification timestamps are stored in the database for dashboard history and review queues.
- **Message Content**: **GmailCleaner does not permanently store the content of email bodies.** Email body text is fetched transiently to classify messages and is discarded immediately after classification.

## 3. How Data is Used
- To sort your inbox into predefined categories (e.g. news, newsletters, receipts).
- To detect bulk sender list memberships and suggest trashing junk.
- To display scan summaries and allow undo/recovery of classification decisions.
- GmailCleaner adheres strictly to the **Google API Services User Data Policy**, including the **Limited Use** requirements.

## 4. How Users Can Revoke Access & Request Deletion
- Users can disconnect their Gmail accounts directly through the dashboard.
- Disconnecting purges local database tokens, classifications history, and device sessions associated with that user.
- Alternatively, access can be revoked at any time via the Google Account Security settings pane.
