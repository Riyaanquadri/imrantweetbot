"""
OpenAI-backed LLM provider.

This implementation uses the OpenAI Chat Completions API (openai package).
It provides two main methods:
 - generate_tweet(context, tone): returns a tweet-ready string <= 280 chars
 - generate_reply(mention_text): returns a reply-ready string <= 280 chars

Important safety notes (you must enforce in production):
 - Always run a safety classifier on generated text before posting (the project has a minimal safety module).
 - Use temperature=0.3-0.8 depending on desired creativity. Lower reduces hallucination risk.
 - Keep prompts focused and include explicit "no financial advice" instructions.

Replace MODEL with your preferred OpenAI chat model that you have access to (gpt-4o-mini, gpt-4o, gpt-4, gpt-3.5-turbo, etc.).
"""
from typing import Optional
import openai
import time
from .config import Config
from .logger import logger

# Configure OpenAI API key
openai.api_key = Config.OPENAI_API_KEY

# Default model - change if needed
MODEL = "gpt-4o-mini" if True else "gpt-3.5-turbo"

class LLMProvider:
    def __init__(self, model: str = MODEL, temperature: float = 0.5):
        self.model = model
        self.temperature = temperature

    def _call_openai(self, messages, max_tokens=150, retry=2, backoff=1.5):
        """Call OpenAI chat completion with minimal retry/backoff."""
        for attempt in range(retry + 1):
            try:
                resp = openai.ChatCompletion.create(
                    model=self.model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=self.temperature,
                    n=1,
                )
                # The response text may be in different places depending on model wrapper
                return resp.choices[0].message.content.strip()
            except Exception as e:
                logger.warning('OpenAI call failed (attempt %s): %s', attempt + 1, str(e))
                if attempt < retry:
                    sleep_for = backoff ** (attempt + 1)
                    time.sleep(sleep_for)
                else:
                    logger.exception('OpenAI calls exhausted')
                    raise

    def _truncate_to_tweet(self, text: str) -> str:
        if len(text) <= 280:
            return text
        # prefer truncating to last sentence boundary before 275 chars
        trunc = text[:275]
        last_sent = trunc.rsplit('.', 1)[0]
        if last_sent and len(last_sent) > 50:
            return (last_sent + '.').strip()[:280]
        return (trunc[:277] + '...').strip()

    def generate_tweet(self, context: str, tone: str = 'concise') -> str:
        """Generate a single tweet (<=280 chars) using OpenAI.

        The prompt explicitly forbids giving financial advice and asks for concise, factual language.
        """
        system = (
            "You are an assistant that drafts short, factual, and clear tweets about crypto projects. "
            "You must NOT provide financial advice or recommendations, and you must not make unverifiable claims. "
            "Keep the tweet within 280 characters. Add 'Not financial advice.' when relevant."
        )
        user = (
            f"Draft a {tone} tweet (single tweet) summarizing the following context for followers who track the project:\n\n"
            f"{context}\n\n"
            "Be precise and avoid sensational language. Do NOT include private or leaked info. "
            "If the context includes a claim about price or returns, refuse to state it and instead advise to check official sources."
        )

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user}
        ]

        try:
            out = self._call_openai(messages, max_tokens=120)
        except Exception:
            logger.exception('OpenAI failed; falling back to template')
            return self._truncate_to_tweet(f"Update: {context} — follow official channels. Not financial advice.")

        tweet = self._truncate_to_tweet(out.replace('\n', ' '))
        return tweet

    def generate_reply(self, mention_text: str, tone: str = 'helpful') -> str:
        """Generate a reply to a mention.

        We include the mention's text in the prompt and ask for a concise, polite response. Replies should not be longer than 280 chars.
        """
        system = (
            "You are an assistant that composes polite, concise Twitter replies about crypto projects. "
            "Do NOT provide investment advice or make claims about guaranteed returns. Keep within 280 characters."
        )
        user = (
            f"Compose a {tone} reply to this mention while being factual and concise. Include a short acknowledgement and a useful pointer if appropriate. "
            f"Mention text: \"{mention_text}\"\n\n"
            "Do not include any URLs unless explicitly supplied."
        )
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user}
        ]

        try:
            out = self._call_openai(messages, max_tokens=120)
        except Exception:
            logger.exception('OpenAI failed for reply; falling back to template')
            return self._truncate_to_tweet(f"Thanks for the mention! We appreciate your interest. Not financial advice.")

        reply = self._truncate_to_tweet(out.replace('\n', ' '))
        return reply
