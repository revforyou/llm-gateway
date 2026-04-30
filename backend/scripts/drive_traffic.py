"""Called by traffic-engine GitHub Action. Sends burst of synthetic requests."""
import os
import random
import time
import httpx

API_URL = os.environ["API_URL"]
DEMO_API_KEY = os.environ["DEMO_API_KEY"]
BURST_SIZE = int(os.environ.get("TRAFFIC_BURST_SIZE", "12"))

# Designed for 70% simple / 25% medium / 5% complex at runtime.
SIMPLE_PROMPTS = [
    "How do I reset my password?",
    "Where is my order? I placed it 3 days ago.",
    "What payment methods do you accept?",
    "How long does standard shipping take?",
    "Where can I track my refund?",
    "How do I unsubscribe from your newsletter?",
    "What are your customer service hours?",
    "Can I track my order online?",
    "What is your return policy timeframe?",
    "How do I recover my password?",
    "Where can I find my order confirmation?",
    "Do you accept credit cards?",
    "How long does delivery usually take?",
    "Can I get a copy of my invoice?",
    "How do I update my email address?",
]

MEDIUM_PROMPTS = [
    "I need to cancel my subscription before the next billing cycle.",
    "How do I change the shipping address for my current order?",
    "I want to upgrade my plan to the premium tier.",
    "I'm having trouble logging into my account after changing my email.",
    "How do I add a second user to my account?",
    "I need to update my payment method on file.",
    "Can you help me understand my latest invoice charges?",
    "I accidentally created two accounts — how do I merge them?",
    "How do I download my data before closing my account?",
    "I need to pause my subscription for one month.",
    "My discount code isn't working at checkout.",
    "I need to change the email address on my account.",
    "How do I switch from monthly to annual billing?",
]

COMPLEX_PROMPTS = [
    "I was charged twice this month and demand an immediate refund.",
    "I need to speak to a human agent about an unauthorized charge on my account.",
    "I want to file a formal complaint — this is completely unacceptable service.",
    "I've been charged for a service I cancelled three months ago. I need this escalated.",
    "There's a fraudulent transaction on my account and I need to speak with a manager.",
]


def weighted_prompt() -> str:
    r = random.random()
    if r < 0.70:
        return random.choice(SIMPLE_PROMPTS)
    elif r < 0.95:
        return random.choice(MEDIUM_PROMPTS)
    else:
        return random.choice(COMPLEX_PROMPTS)


def main():
    success = 0
    errors = 0
    dist: dict[str, int] = {"simple": 0, "medium": 0, "complex": 0}

    for i in range(BURST_SIZE):
        prompt = weighted_prompt()
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
            data = r.json()["data"]
            complexity = data.get("complexity", "?")
            dist[complexity] = dist.get(complexity, 0) + 1
            success += 1
            print(f"[{i+1}/{BURST_SIZE}] OK — {complexity} — {data['model_used']}")
        except Exception as e:
            errors += 1
            print(f"[{i+1}/{BURST_SIZE}] ERROR — {e}")

    print(f"\nDone: {success} ok, {errors} errors")
    print(f"Distribution: {dist}")


if __name__ == "__main__":
    main()
