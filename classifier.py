"""Email classification using Gemini AI."""
import os
import json
from google import genai
from pydantic import BaseModel, field_validator, model_validator

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


class ClassificationOutput(BaseModel):
    category: str | None = None
    is_crap: bool = False
    crap_reason: str | None = None
    confidence: float = 0.0

    @field_validator("category")
    @classmethod
    def validate_category(cls, v):
        if v is not None and v not in CATEGORIES:
            raise ValueError(f"Category {v} is not a valid category")
        return v

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v):
        if not (0.0 <= v <= 1.0):
            raise ValueError("Confidence must be between 0.0 and 1.0")
        return v

    @model_validator(mode="after")
    def validate_contradictions(self) -> "ClassificationOutput":
        if self.is_crap and self.category is not None:
            raise ValueError("Contradictory output: is_crap=True and category set")
        return self


def _get_client() -> genai.Client:
    api_key = os.environ.get("GEMINI_WORKSHOP_API_KEY")
    base_url = os.environ.get("GEMINI_WORKSHOP_BASE_URL")
    if not api_key:
        raise ValueError("GEMINI_WORKSHOP_API_KEY not set")
    return genai.Client(
        api_key=api_key,
        http_options={"api_version": "v1alpha", "base_url": base_url} if base_url else None,
    )


def _get_min_confidence() -> float:
    try:
        from config import load_settings
        return load_settings().min_classification_confidence
    except Exception:
        # Fallback to env or default
        try:
            return float(os.getenv("MIN_CLASSIFICATION_CONFIDENCE", "0.80"))
        except Exception:
            return 0.80


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

    try:
        client = _get_client()
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

        # Enforce Pydantic validation
        validated = ClassificationOutput(**result)

        # Check confidence threshold
        min_conf = _get_min_confidence()
        if validated.confidence < min_conf:
            raise ValueError(f"Confidence {validated.confidence} is below minimum threshold {min_conf}")

        # Sanitize crap_reason to prevent storing raw email content
        crap_reason = validated.crap_reason
        if crap_reason:
            if (snippet and snippet in crap_reason) or (subject and subject in crap_reason):
                crap_reason = "Junk content matched policy"

        return {
            "category": validated.category,
            "is_crap": validated.is_crap,
            "crap_reason": crap_reason,
            "confidence": validated.confidence,
        }
    except Exception as e:
        # Fallback: treat as unknown, not crap (NO_ACTION)
        return {
            "category": None,
            "is_crap": False,
            "crap_reason": f"Fallback: {str(e)[:100]}",
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
