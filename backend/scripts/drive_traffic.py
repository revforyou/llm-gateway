"""Called by traffic-engine GitHub Action. Sends burst of synthetic requests."""
import os
import random
import time
import httpx

API_URL = os.environ["API_URL"]
DEMO_API_KEY = os.environ["DEMO_API_KEY"]
BURST_SIZE = int(os.environ.get("TRAFFIC_BURST_SIZE", "12"))

SAMPLE_PROMPTS = [
    "How do I reset my password?",
    "I can't log into my account.",
    "Where can I find my invoice?",
    "How do I cancel my subscription?",
    "What payment methods do you accept?",
    "I was charged twice this month, please help.",
    "How do I upgrade my plan?",
    "I need to speak with someone about a billing dispute.",
    "Can I get a refund for last month?",
    "How do I add a team member to my account?",
    "The app is not loading correctly on my phone.",
    "I forgot the email address associated with my account.",
    "How do I export my data?",
    "My API key is not working.",
    "I need to change my email address.",
]


def main():
    success = 0
    errors = 0
    for i in range(BURST_SIZE):
        prompt = random.choice(SAMPLE_PROMPTS)
        jitter = random.uniform(0.5, 2.0)
        time.sleep(jitter)
        try:
            r = httpx.post(
                f"{API_URL}/v1/chat",
                headers={"Authorization": f"Bearer {DEMO_API_KEY}"},
                json={"prompt": prompt},
                timeout=30.0,
            )
            r.raise_for_status()
            success += 1
            print(f"[{i+1}/{BURST_SIZE}] OK — {r.json()['data']['complexity']}")
        except Exception as e:
            errors += 1
            print(f"[{i+1}/{BURST_SIZE}] ERROR — {e}")

    print(f"\nDone: {success} ok, {errors} errors")


if __name__ == "__main__":
    main()
