import os
import json
import httpx
from typing import Optional, List

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "gpt-oss-120b")
DEFAULT_TEMP = float(os.getenv("LLM_TEMPERATURE", "0.6"))
DEFAULT_TOP_P = float(os.getenv("LLM_TOP_P", "0.9"))
DEFAULT_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "140"))
GROQ_ENDPOINT = os.getenv("GROQ_API_URL", "https://api.groq.com/openai/v1/chat/completions")


class LLMProvider:
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or GROQ_API_KEY
        self.model = model or GROQ_MODEL
        if not self.api_key:
            raise RuntimeError("GROQ_API_KEY is required in env or provided to LLMProvider")
        self._client = httpx.Client(timeout=30.0)

    def _call_chat(self, messages, temperature=DEFAULT_TEMP, top_p=DEFAULT_TOP_P, max_tokens=DEFAULT_MAX_TOKENS):
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": float(temperature),
            "top_p": float(top_p),
            "max_tokens": int(max_tokens),
            "n": 1,
        }
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        r = self._client.post(GROQ_ENDPOINT, headers=headers, json=payload)
        r.raise_for_status()
        return r.json()

    def _build_prompt_messages(self, topic: str, tone: str = "concise", variant: Optional[str] = None, recent_tweets: Optional[List[str]] = None, retrieved_facts: Optional[List[str]] = None):
        sys_lines = [
            "You are a concise, technically accurate crypto engineer writing short high-value social posts called 'xeets'.",
            f"Tone: {tone}",
            "Constraints: no financial advice, avoid unverifiable claims, output ONLY the tweet text, <= 220 chars."
        ]
        if variant:
            sys_lines.insert(1, f"A/B variant: {variant}")
        if retrieved_facts:
            sys_lines.append("Relevant facts (do not hallucinate beyond these):")
            for f in retrieved_facts[:5]:
                sys_lines.append(f"- {f}")
        if recent_tweets:
            sys_lines.append("Avoid repeating these recent tweets:")
            for t in recent_tweets[:5]:
                sys_lines.append(f"- {t}")

        system = {"role": "system", "content": "\n".join(sys_lines)}
        # small few-shot examples; swap with your best examples
        examples = [
            {"role": "user", "content": "TYPE: announcement\nTONE: concise\nINSTRUCTIONS: one sentence, one stat or developer action, one hashtag.\n\nTopic: Solstice commit cadence increased.\n"},
            {"role": "assistant", "content": "Project update: recent commits and testnet activity — devs, pull the latest to test the flares module. #Solstice"},
            {"role": "user", "content": "TYPE: advantage\nTONE: authoritative\nINSTRUCTIONS: one line, express benefit to developers, include CTA.\n\nTopic: lower settlement latency.\n"},
            {"role": "assistant", "content": "Solstice v2 reduces settlement latency to ~0.4s (3x). Devs: upgrade nodes to v2 to gain lower confirmations. Read: docs.solstice.org #Solstice"},
        ]
        messages = [system] + examples + [{"role": "user", "content": f"Write a single tweet about: {topic}"}]
        return messages

    def generate_tweet(self, topic: str, tone: str = "concise", variant: Optional[str] = None, recent_tweets: Optional[List[str]] = None, retrieved_facts: Optional[List[str]] = None, temperature: Optional[float] = None, top_p: Optional[float] = None, max_tokens: Optional[int] = None) -> str:
        temp = temperature if temperature is not None else DEFAULT_TEMP
        tp = top_p if top_p is not None else DEFAULT_TOP_P
        mt = max_tokens if max_tokens is not None else DEFAULT_MAX_TOKENS
        messages = self._build_prompt_messages(topic, tone=tone, variant=variant, recent_tweets=recent_tweets, retrieved_facts=retrieved_facts)
        resp = self._call_chat(messages, temperature=temp, top_p=tp, max_tokens=mt)
        try:
            # Groq/OpenAI-like response shape
            choice = resp.get("choices", [{}])[0]
            content = choice.get("message", {}).get("content") or choice.get("text")
            if content is None and "data" in resp:
                # some wrappers return resp["data"][0]["message"]["content"]
                data = resp["data"]
                if isinstance(data, list) and data:
                    content = data[0].get("message", {}).get("content")
        except Exception:
            content = None
        return (content or "").strip().replace("\n", " ")

    def generate_paraphrase(self, text: str, temperature: Optional[float] = 0.75, top_p: Optional[float] = 0.95, max_tokens: Optional[int] = 140) -> str:
        """
        Produce one paraphrase of `text`. Keep facts intact; change phrasing.
        """
        messages = [
            {"role":"system","content":"You are an expert paraphraser. Produce one concise paraphrase that preserves facts and meaning, <=140 chars. Output only the paraphrase."},
            {"role":"user","content": f"Paraphrase: {text}"}
        ]
        resp = self._call_chat(messages, temperature=temperature, top_p=top_p, max_tokens=max_tokens)
        try:
            choice = resp.get("choices", [{}])[0]
            out = choice.get("message", {}).get("content") or choice.get("text")
        except Exception:
            out = None
        return (out or "").strip().replace("\n", " ")
