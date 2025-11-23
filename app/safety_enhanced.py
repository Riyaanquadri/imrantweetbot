"""
Enhanced safety checks with layered filtering pipeline.

Filters:
1. Length check (max 280 chars)
2. Profanity detection
3. Financial advice detection
4. URL validation (prevents suspicious URLs)
5. Toxicity heuristics

All violations are logged for manual review.
"""
import re
from typing import List, Tuple
from .logger import logger

# Safety configuration
PROFANITY_KEYWORDS = [
    "badword1", "badword2", "offensive"
]

FINANCIAL_ADVICE_KEYWORDS = [
    "buy now", "sell now", "guaranteed", "sure thing", "investment advice",
    "guaranteed return", "will make you money", "can't lose", "easy profit",
    "pump", "dump", "moon", "to the moon"
]

SUSPICIOUS_URL_PATTERNS = [
    r'bit\.ly',
    r'tinyurl',
    r'short\.link',
]

TOXICITY_KEYWORDS = [
    "scam", "rug pull", "exit scam", "hack", "stolen"
]


class SafetyCheckResult:
    """Result of a safety check."""
    
    def __init__(self, passed: bool, flags: List[str] = None, details: str = ""):
        self.passed = passed
        self.flags = flags or []
        self.details = details
    
    def __repr__(self):
        return f"SafetyCheckResult(passed={self.passed}, flags={self.flags})"


def check_length(text: str) -> SafetyCheckResult:
    """Check if text is within Twitter's 280 character limit."""
    if len(text) <= 280:
        return SafetyCheckResult(passed=True)
    return SafetyCheckResult(
        passed=False,
        flags=["text_too_long"],
        details=f"Text is {len(text)} chars, max 280 allowed"
    )


def check_profanity(text: str) -> SafetyCheckResult:
    """Check for profanity or offensive language."""
    text_lower = text.lower()
    found = [kw for kw in PROFANITY_KEYWORDS if kw in text_lower]
    
    if found:
        return SafetyCheckResult(
            passed=False,
            flags=["profanity_detected"],
            details=f"Found profanity: {', '.join(found)}"
        )
    return SafetyCheckResult(passed=True)


def check_financial_advice(text: str) -> SafetyCheckResult:
    """Check for financial advice or investment recommendations."""
    text_lower = text.lower()
    found = [kw for kw in FINANCIAL_ADVICE_KEYWORDS if kw in text_lower]
    
    if found:
        return SafetyCheckResult(
            passed=False,
            flags=["financial_advice_detected"],
            details=f"Found financial advice keywords: {', '.join(found)}"
        )
    return SafetyCheckResult(passed=True)


def check_urls(text: str) -> SafetyCheckResult:
    """Check for suspicious URL patterns."""
    # Find all URLs
    url_pattern = r'https?://[^\s]+'
    urls = re.findall(url_pattern, text)
    
    if not urls:
        return SafetyCheckResult(passed=True)
    
    suspicious = []
    for url in urls:
        for pattern in SUSPICIOUS_URL_PATTERNS:
            if re.search(pattern, url, re.IGNORECASE):
                suspicious.append(url)
    
    if suspicious:
        return SafetyCheckResult(
            passed=False,
            flags=["suspicious_urls"],
            details=f"Found suspicious URLs: {', '.join(suspicious)}"
        )
    return SafetyCheckResult(passed=True)


def check_toxicity(text: str) -> SafetyCheckResult:
    """Check for potentially problematic claims about scams/hacks."""
    text_lower = text.lower()
    found = [kw for kw in TOXICITY_KEYWORDS if kw in text_lower]
    
    # Only flag if seems like making accusations without context
    if found and len(text) < 100:  # Short text making serious claims
        return SafetyCheckResult(
            passed=False,
            flags=["potential_toxicity"],
            details=f"Short text with serious accusations: {', '.join(found)}"
        )
    return SafetyCheckResult(passed=True)


def check_minimum_length(text: str) -> SafetyCheckResult:
    """Ensure text is not suspiciously short."""
    if len(text.strip()) < 5:
        return SafetyCheckResult(
            passed=False,
            flags=["text_too_short"],
            details="Text too short to be meaningful"
        )
    return SafetyCheckResult(passed=True)


# Pipeline of checks to run
SAFETY_CHECKS = [
    ("length", check_length),
    ("minimum_length", check_minimum_length),
    ("profanity", check_profanity),
    ("financial_advice", check_financial_advice),
    ("urls", check_urls),
    ("toxicity", check_toxicity),
]


def run_safety_checks(text: str) -> Tuple[bool, List[str]]:
    """
    Run all safety checks on text.
    
    Returns:
        Tuple of (passed: bool, flags: List[str])
    """
    all_flags = []
    
    for check_name, check_func in SAFETY_CHECKS:
        try:
            result = check_func(text)
            if not result.passed:
                all_flags.extend(result.flags)
                logger.warning(f"Safety check '{check_name}' failed: {result.details}")
        except Exception as e:
            logger.error(f"Error in safety check '{check_name}': {e}")
            # Conservative: treat error as failure
            all_flags.append(f"{check_name}_error")
    
    passed = len(all_flags) == 0
    return passed, all_flags


def passes_safety(text: str) -> bool:
    """Quick boolean check - does text pass all safety checks?"""
    passed, _ = run_safety_checks(text)
    return passed


def get_safety_flags(text: str) -> List[str]:
    """Get detailed list of flags if text fails safety checks."""
    _, flags = run_safety_checks(text)
    return flags
