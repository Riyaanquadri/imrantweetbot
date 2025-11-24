# app/src/llm_provider.py
"""
Groq-backed LLM provider for tweet generation and replies.

Uses the official groq.Client (sync). Keeps prompts explicit, low-temp defaults,
and a small retry/backoff for resilience.
"""

import os
import time
import logging
from typing import Optional
from groq import Client
from .config import Config
from .logger import logger

# Read config from env/config
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "gpt-oss-120b")
GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", Config.POST_INTERVAL_HOURS)) if False else float(os.getenv("LLM_TEMPERATURE", "0.45"))
MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "300"))

# Build client
_client = None
def _get_client():
    global _client
    if _client is None:
        if not GROQ_API_KEY:
            raise RuntimeError("GROQ_API_KEY not set in environment")
        _client = Client(api_key=GROQ_API_KEY, base_url=GROQ_BASE_URL)
    return _client

def _call_groq_chat(messages, max_tokens=MAX_TOKENS, temperature=TEMPERATURE, retries=2, backoff=1.5):
    """Call Groq chat completions with simple retry/backoff. Returns text."""
    client = _get_client()
    for attempt in range(retries + 1):
        try:
            resp = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            # Groq returns choices like OpenAI style
            if resp and getattr(resp, "choices", None):
                return resp.choices[0].message.content.strip()
            # Some endpoints may return text directly
            if hasattr(resp, "text"):
                return resp.text.strip()
            return str(resp)
        except Exception as e:
            logger.warning("Groq call failed (attempt %s): %s", attempt + 1, str(e))
            if attempt < retries:
                time.sleep(backoff ** (attempt + 1))
            else:
                logger.exception("Groq retries exhausted")
                raise

def _truncate_to_tweet(text: str) -> str:
    if len(text) <= 280:
        return text
    trunc = text[:275]
    last_sent = trunc.rsplit('.', 1)[0]
    if last_sent and len(last_sent) > 50:
        return (last_sent + '.').strip()[:280]
    return (trunc[:277] + '...').strip()

class LLMProvider:
    def __init__(self, model: Optional[str] = None, temperature: Optional[float] = None):
        self.model = model or GROQ_MODEL
        self.temperature = temperature if temperature is not None else TEMPERATURE

    def generate_tweet(self, context: str, tone: str = 'concise') -> str:
        """
        Generate a single tweet (<= 280 chars). The prompt explicitly forbids
        giving financial advice and asks for concise factual wording.
        """
        system = (
            "You are a concise assistant that drafts short (<=280 chars) tweets "
            "about crypto projects. Do NOT provide financial advice, do NOT give "
            "trading signals, and avoid unverifiable claims. Keep language factual."
        )
        user = (
            f"Context:\n{context}\n\n"
            "Task: Draft one concise tweet (single tweet, no threads) summarizing the above. "
            "If context includes pricing/returns claims, refuse to restate them and say 'check official sources'. "
            "End with 'Not financial advice.' if the tweet references investments."
        )
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        out = _call_groq_chat(messages, max_tokens=120, temperature=self.temperature)
        return _truncate_to_tweet(out.replace("\n", " "))

    def generate_reply(self, mention_text: str, tone: str = 'helpful') -> str:
        """
        Generate a concise reply (<=280 chars). Do not include URLs unless provided.
        """
        system = (
            "You are a polite assistant that composes short Twitter replies about crypto projects. "
            "Do NOT provide investment advice or make claims about guaranteed returns."
        )
        user = (
            f"Compose a {tone} reply to the mention below. Be concise, acknowledge the user, and offer a pointer to official channels when relevant.\n\n"
            f"Mention: \"{mention_text}\""
        )
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        out = _call_groq_chat(messages, max_tokens=120, temperature=self.temperature)
        return _truncate_to_tweet(out.replace("\n", " "))

# simple convenience for compatibility with previous code
def make_provider():
    return LLMProvider()
