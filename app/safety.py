# Very small safety module. Replace with robust classifiers before prod.
import re
from .logger import logger

PROFANITY = ["badword1", "badword2"]  # extend with a better list or external library
FIN_ADVICE_TERMS = ["buy now", "guarantee", "sure thing", "investment advice"]


def contains_profanity(text: str) -> bool:
    t = text.lower()
    return any(p in t for p in PROFANITY)


def contains_financial_advice(text: str) -> bool:
    t = text.lower()
    return any(f in t for f in FIN_ADVICE_TERMS)


def passes_safety(text: str) -> bool:
    if not text or len(text.strip()) < 5:
        logger.warning('Safety: text too short')
        return False
    if contains_profanity(text):
        logger.warning('Safety: profanity detected')
        return False
    if contains_financial_advice(text):
        logger.warning('Safety: possible financial advice detected')
        return False
    if len(text) > 280:
        logger.warning('Safety: text too long')
        return False
    return True
