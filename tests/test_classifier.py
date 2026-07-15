import os
import pytest
from pydantic import ValidationError
import classifier as clf


class MockResponse:
    def __init__(self, text):
        self.text = text


class MockModels:
    def __init__(self, text):
        self.text = text
    def generate_content(self, model, contents):
        return MockResponse(self.text)


class MockClient:
    def __init__(self, text):
        self.models = MockModels(text)


def test_valid_classification_passes(monkeypatch):
    monkeypatch.setattr(clf, "_get_client", lambda: MockClient('{"category": "work", "is_crap": false, "crap_reason": null, "confidence": 0.95}'))
    
    res = clf.classify_email("Meeting details", "boss@corp.test", "2026-07-15", "Let's meet tomorrow.")
    assert res["category"] == "work"
    assert res["is_crap"] is False
    assert res["confidence"] == 0.95


def test_malformed_json_fallback_no_action(monkeypatch):
    monkeypatch.setattr(clf, "_get_client", lambda: MockClient('invalid json here'))
    
    res = clf.classify_email("Meeting details", "boss@corp.test", "2026-07-15", "Let's meet tomorrow.")
    assert res["category"] is None
    assert res["is_crap"] is False
    assert res["confidence"] == 0.0
    assert "Fallback" in res["crap_reason"]


def test_low_confidence_fallback_no_action(monkeypatch, monkeypatch_env_or_config):
    # Set threshold to 0.85
    monkeypatch.setattr(clf, "_get_min_confidence", lambda: 0.85)
    monkeypatch.setattr(clf, "_get_client", lambda: MockClient('{"category": "work", "is_crap": false, "crap_reason": null, "confidence": 0.75}'))
    
    res = clf.classify_email("Meeting details", "boss@corp.test", "2026-07-15", "Let's meet tomorrow.")
    assert res["category"] is None
    assert res["is_crap"] is False
    assert res["confidence"] == 0.0
    assert "below minimum threshold" in res["crap_reason"]


def test_unknown_category_fallback_no_action(monkeypatch):
    # Category "unknown_cat" is not in CATEGORIES
    monkeypatch.setattr(clf, "_get_client", lambda: MockClient('{"category": "unknown_cat", "is_crap": false, "crap_reason": null, "confidence": 0.90}'))
    
    res = clf.classify_email("Meeting details", "boss@corp.test", "2026-07-15", "Let's meet tomorrow.")
    assert res["category"] is None
    assert res["is_crap"] is False
    assert res["confidence"] == 0.0


def test_missing_fields_fallback_no_action(monkeypatch):
    # missing is_crap and category
    monkeypatch.setattr(clf, "_get_client", lambda: MockClient('{"confidence": 0.90}'))
    
    res = clf.classify_email("Meeting details", "boss@corp.test", "2026-07-15", "Let's meet tomorrow.")
    # Defaults in ClassificationOutput model are category=None, is_crap=False, crap_reason=None.
    # Since they have default values, it won't fail validation, but we can verify it correctly parses
    assert res["category"] is None
    assert res["is_crap"] is False
    assert res["confidence"] == 0.90


def test_contradictory_output_fallback_no_action(monkeypatch):
    # both is_crap = True and category = "work"
    monkeypatch.setattr(clf, "_get_client", lambda: MockClient('{"category": "work", "is_crap": true, "crap_reason": "Junk", "confidence": 0.95}'))
    
    res = clf.classify_email("Meeting details", "boss@corp.test", "2026-07-15", "Let's meet tomorrow.")
    assert res["category"] is None
    assert res["is_crap"] is False
    assert res["confidence"] == 0.0
    assert "Contradictory output" in res["crap_reason"]


def test_raw_email_body_prevention(monkeypatch):
    # Subject: "Super secret code"
    # Snippet: "Buy drugs cheap!"
    # If the response tries to leak the snippet inside crap_reason, sanitize it
    monkeypatch.setattr(clf, "_get_client", lambda: MockClient('{"category": null, "is_crap": true, "crap_reason": "Contains Buy drugs cheap!", "confidence": 0.95}'))
    
    res = clf.classify_email("Super secret code", "spam@spam.com", "2026-07-15", "Buy drugs cheap!")
    assert res["is_crap"] is True
    assert "Buy drugs cheap!" not in res["crap_reason"]
    assert "Junk content matched policy" in res["crap_reason"]


@pytest.fixture
def monkeypatch_env_or_config(monkeypatch):
    # Helper to prevent actual config file load errors
    pass
