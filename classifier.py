"""Email classification using Gemini AI."""
import os
import json
import httpx
from google import genai

# Valid categories for non-crap emails
CATEGORIES = ["work", "finance", "personal", "travel", "receipts", "social", "newsletters", "promotions"]

CLASSIFICATION_PROMPT = """You are an expert email classifier. Analyze the following email and classify it.

Rules:
1. First determine if this is "crap" — meaning promotional junk, spam, marketing blasts, notification noise, or low-value automated emails that the user would want trashed.
2. If it IS crap, set is_crap=true and provide a short reason.
3. If it is NOT crap, assign it to exactly ONE of these categories:
   - work: Work-related emails, colleague communications, project updates, meeting invites
   - finance: Banking, bills, invoices, payment confirmations, financial statements
   - personal: Personal communications from real people, friends, family
   - travel: Flight confirmations, hotel bookings, itineraries, travel updates
   - receipts: Purchase receipts, order confirmations, shipping notifications
   - social: Social media notifications, LinkedIn, Facebook, etc.
   - newsletters: Subscribed newsletters and content digests that are NOT crap
   - promotions: Promotional emails that might still be useful (discounts the user might want)

Email details:
Subject: {subject}
From: {from_addr}
Date: {date}
Snippet: {snippet}

Respond with ONLY a JSON object, no markdown, no explanation:
{{"category": "<one of the categories above or null>", "is_crap": <true/false>, "crap_reason": "<short reason or null>", "confidence": <0.0 to 1.0>}}"""


def _get_client() -> genai.Client:
    api_key = os.environ.get("GEMINI_WORKSHOP_API_KEY")
    base_url = os.environ.get("GEMINI_WORKSHOP_BASE_URL")
    if not api_key:
        raise ValueError("GEMINI_WORKSHOP_API_KEY not set")
    return genai.Client(
        api_key=api_key,
        http_options={"api_version": "v1alpha", "base_url": base_url} if base_url else None,
    )


def classify_email(subject: str, from_addr: str, date: str, snippet: str) -> dict:
    """Classify a single email using Gemini AI.

    Returns dict with keys: category, is_crap, crap_reason, confidence
    """
    prompt = CLASSIFICATION_PROMPT.format(
        subject=subject[:200],
        from_addr=from_addr[:200],
        date=date[:100],
        snippet=snippet[:500],
    )

    client = _get_client()

    try:
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=prompt,
        )
        raw = response.text.strip()

        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
            if raw.endswith("```"):
                raw = raw[:-3]
            raw = raw.strip()

        result = json.loads(raw)

        # Validate
        category = result.get("category")
        if category and category not in CATEGORIES:
            category = None

        is_crap = bool(result.get("is_crap", False))
        if is_crap:
            category = None

        return {
            "category": category,
            "is_crap": is_crap,
            "crap_reason": result.get("crap_reason"),
            "confidence": float(result.get("confidence", 0.7)),
        }
    except json.JSONDecodeError as e:
        # Fallback: treat as unknown, not crap
        return {
            "category": None,
            "is_crap": False,
            "crap_reason": f"Invalid JSON response: {str(e)[:100]}",
            "confidence": 0.0,
        }
    except Exception as e:
        # Fallback: treat as unknown, not crap
        return {
            "category": None,
            "is_crap": False,
            "crap_reason": f"Classification error: {str(e)[:100]}",
            "confidence": 0.0,
        }


def classify_batch(emails: list[dict]) -> list[dict]:
    """Classify a batch of emails. Returns list of classification results."""
    results = []
    for email in emails:
        result = classify_email(
            subject=email.get("subject", ""),
            from_addr=email.get("from", ""),
            date=email.get("date", ""),
            snippet=email.get("snippet", ""),
        )
        result["message_id"] = email["id"]
        result["subject"] = email.get("subject", "")
        result["from"] = email.get("from", "")
        results.append(result)
    return results
