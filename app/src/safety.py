# app/src/safety.py
"""Minimal safety checks. Replace/enhance for production (Perspective API / Detoxify)."""
import re
from typing import Tuple

PROFANITY = {"fuck", "shit", "bitch", "damn"}

FIN_ADVICE_TERMS = {
    "buy now",
    "guarantee",
    "sure thing",
    "guaranteed return",
    "financial advice",
    "invest now",
    "investment advice",
}

IGNORE_PHRASES = {
    "not financial advice",
    "not investment advice",
}

def contains_profanity(text: str) -> bool:
    t = text.lower()
    for p in PROFANITY:
        if re.search(rf"\\b{re.escape(p)}\\b", t):
            return True
    return False

def contains_financial_claim(text: str) -> bool:
    t = text.lower()
    for ig in IGNORE_PHRASES:
        if ig in t:
            return False
    return any(term in t for term in FIN_ADVICE_TERMS)

def passes_safety(text: str) -> Tuple[bool, str]:
    if not text or len(text.strip()) < 5:
        return False, "too_short"
    if len(text) > 280:
        return False, "too_long"
    if contains_profanity(text):
        return False, "profanity"
    if contains_financial_claim(text):
        return False, "financial_claim"
    return True, ""
