from dotenv import load_dotenv
load_dotenv(".env")
import os
import json
import time
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.src.llm_provider import LLMProvider


def get_variant_tone_map():
    raw = os.getenv("AB_VARIANT_TONES", "control:concise")
    result = {}
    for part in raw.split(","):
        if ":" in part:
            key, val = part.split(":", 1)
            result[key.strip()] = val.strip()
    return result


def main():
    prov = LLMProvider()
    variants = [v.strip() for v in os.getenv("AB_VARIANTS", "control").split(",") if v.strip()]
    if not variants:
        variants = ["control"]
    tone_map = get_variant_tone_map()
    topic = os.getenv("TEST_TOPIC", "Solstice recent commits & testnet activity")
    out = {}
    os.makedirs("data", exist_ok=True)
    per_variant = int(os.getenv("LOCAL_GEN_COUNT", "50"))
    delay = float(os.getenv("LOCAL_GEN_DELAY", "0.15"))
    for variant in variants:
        tone = tone_map.get(variant, "concise")
        out[variant] = []
        for _ in range(per_variant):
            tweet = prov.generate_tweet(topic, tone=tone, variant=variant, recent_tweets=[])
            out[variant].append(tweet)
            time.sleep(delay)
    for variant in out:
        print("=== VARIANT:", variant, "TONE:", tone_map.get(variant, "concise"))
        for idx, text in enumerate(out[variant][:10]):
            print(f"{idx + 1}. {text}")
        print()
    with open("data/local_gen.json", "w", encoding="utf-8") as handle:
        json.dump(out, handle, indent=2)
    print("Saved full output to data/local_gen.json")


if __name__ == "__main__":
    main()
