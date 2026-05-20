# LLM Quality Gateway

**Production-grade LLM observability platform** with complexity-based routing, async evaluation pipelines, A/B experimentation, and multi-tenant API key auth — built on FastAPI, Next.js 14, Supabase, and Upstash. Fully deployed on free-tier infrastructure with zero ongoing cost.

---

## What It Does

Most teams send every prompt to the same model. This gateway classifies each request by complexity, routes it to the cheapest model that can handle it, and asynchronously scores every response with an LLM-as-judge evaluator — giving you quality metrics, cost attribution, and A/B experiment results without adding latency to the critical path.

**Live demo:** [llm-gateway-lemon.vercel.app/demo](https://llm-gateway-lemon.vercel.app/demo)  
**API:** [llm-gateway-6xsv.onrender.com/health](https://llm-gateway-6xsv.onrender.com/health)

---

## Architecture

```
Client Request
      │
      ▼
┌─────────────────────────────────────────────────┐
│               FastAPI Gateway (Render)           │
│                                                 │
│  1. Auth: bcrypt API key verify (Redis-cached)  │
│  2. Rate limit: token bucket (Upstash Redis)    │
│  3. Classify: TF-IDF + LogReg complexity model  │
│  4. Route: simple → 8B │ medium/complex → 70B  │
│  5. Call: Groq Llama 3.1/3.3                   │
│  6. Log: Supabase (requests + responses)        │
│  7. Enqueue: QStash async eval job              │
└─────────────────────────────────────────────────┘
      │                          │
      ▼                          ▼
  Response                 QStash Queue
  (< 500ms added             │
   overhead)                 ▼
                    ┌──────────────────┐
                    │  Eval Pipeline   │
                    │                  │
                    │  Gemini Flash    │
                    │  ├ quality score │
                    │  ├ hallucination │
                    │  ├ refusal flag  │
                    │  └ toxicity flag │
                    │                  │
                    │  → Supabase      │
                    └──────────────────┘
```

---

## Key Engineering Decisions

### 1. Hybrid Complexity Classifier

A two-stage classifier avoids the latency of calling an LLM to classify complexity:

1. **Rule-based fast path** — keyword matching catches unambiguous complex cases (fraud, billing disputes, escalation requests) in microseconds
2. **TF-IDF + Logistic Regression fallback** — trained on the Bitext customer support dataset (27k examples), classifies simple vs. medium with ~88% accuracy

The trained model ships as `classifier.pkl` committed to the repo. No cold-start retraining on Render.

```
simple  → llama-3.1-8b-instant   (~$0.05/M tokens)
medium  → llama-3.3-70b-versatile (~$0.59/M tokens)
complex → llama-3.3-70b-versatile + priority routing
```

Result: ~40% cost reduction vs. always routing to 70B.

### 2. Async Eval Pipeline (No Added Latency)

The eval pipeline runs entirely off the critical path:

1. Response returns to client immediately
2. `asyncio.create_task()` fires a QStash publish (non-blocking, 5s timeout)
3. QStash delivers to `/v1/eval/run` with retry logic
4. Gemini 2.5 Flash-Lite scores: `quality = 0.5×accuracy + 0.3×helpfulness + 0.2×tone`
5. Flags hallucinations, refusals, and toxicity in parallel via `asyncio.gather()`
6. Writes to `eval_scores` table in Supabase

85% of requests are sampled for eval (configurable). A nightly backfill job catches any that failed.

### 3. A/B Experimentation Engine

SHA-256 hash of `(team_id + experiment_id + request_id)` for deterministic, reproducible assignment — same request always goes to the same variant. No sticky sessions needed.

Auto-concludes experiments when sample size is reached using **Welch's t-test** (unequal variance):
- `p < 0.05` → declare winner
- `|effect_size| < 0.02` → call it a tie
- Stores p-value, effect size, and winner in Supabase for audit trail

### 4. Multi-Tenant Auth

- API keys are `sha256(random_bytes(32))` with a 12-char prefix for lookup
- Stored as **bcrypt hashes** — plaintext shown once on creation, never stored
- Auth results cached in Redis for 60s to avoid re-hashing on every request
- Per-team rate limiting: 60 req/min + 1000 req/hr via Redis pipeline (atomic increment + expire)

### 5. Zero-Cost Persistent Deployment

The entire stack runs forever on free tiers:

| Service | Free Limits | How We Stay Within |
|---|---|---|
| Render | 750h/month, spins down after 15min idle | GitHub Actions pings `/health` every 5 min |
| Supabase | 500MB, pauses after 7 days idle | Same keep-warm hits DB on every ping |
| Upstash Redis | 10k commands/day | Auth cache + rate limit only (< 200 commands/request) |
| Upstash QStash | 500 messages/day | 85% sample rate + burst of 12 every 30 min = ~340/day |
| Groq | 14,400 tokens/min | Traffic engine throttled to 12 req/30min |
| Gemini | 1,500 req/day | Eval sample rate caps usage |
| Vercel | Unlimited hobby | Static + server components, no serverless functions abuse |

---

## Stack

**Backend:** Python 3.11 · FastAPI · Pydantic Settings · Supabase (Postgres) · Upstash Redis · Upstash QStash · Groq SDK · Gemini API · scikit-learn · scipy · bcrypt · tenacity · structlog · Sentry

**Frontend:** Next.js 14 · TypeScript · Tailwind CSS 4 · Recharts · SWR · shadcn/ui

**Infra:** Render (backend) · Vercel (frontend) · Supabase (DB + auth) · GitHub Actions (cron)

---

## Database Schema

Seven tables with Row-Level Security on every one:

```
teams               — multi-tenant root
api_keys            — bcrypt-hashed keys, prefix-indexed
requests            — every gateway call with complexity + cost + latency
responses           — LLM output, linked to request
eval_scores         — quality/hallucination/refusal/toxicity per response
experiments         — A/B test config with hypothesis + traffic split
experiment_assignments — deterministic variant assignment log
drift_events        — statistical drift alerts (PSI-based)
audit_log           — append-only action log per team
```

Service role key used server-side (bypasses RLS). Dashboard queries use team-scoped JWT (RLS enforced).

---

## GitHub Actions Automation

| Workflow | Schedule | Purpose |
|---|---|---|
| `keep-warm` | every 5 min | Pings `/health` + keep-warm endpoint to prevent Render/Supabase sleep |
| `traffic-engine` | every 30 min | Sends 12 realistic prompts (70% simple / 25% medium / 5% complex) |
| `backfill-eval` | daily 3am UTC | Catches any evals that failed or were missed during the day |
| `ci-backend` | on push to `backend/**` | Runs pytest — no real secrets needed, conftest sets all defaults |

All cron workflows gated on `vars.BACKEND_DEPLOYED == 'true'` so they don't run before the backend is live.

---

## Local Development

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp ../.env.example ../.env  # fill in your keys
uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

```bash
# Run tests (no real secrets needed)
cd backend && pytest tests/ -v

# Bootstrap demo team + API key (run once after deploy)
SUPABASE_URL=... SUPABASE_SERVICE_KEY=... python backend/scripts/bootstrap_demo.py

# Drive traffic manually
DEMO_API_KEY=sk_live_... API_URL=https://... python backend/scripts/drive_traffic.py
```

---

## API Reference

```
GET  /health                          # {"status":"ok","db":"ok","redis":"ok"}
GET  /v1/metrics/public               # Demo team metrics, no auth required

POST /v1/chat                         # Main gateway endpoint
  Authorization: Bearer sk_live_...
  {"prompt": "my subscription renewal failed"}
  → {"id":"...","content":"...","model_used":"llama-3.1-8b-instant",
     "complexity":"simple","cost_usd":0.000012,"latency_ms":312,"eval_status":"queued"}

GET  /v1/metrics/overview             # 24h stats for your team
GET  /v1/metrics/distribution         # Complexity breakdown (7 days)
GET  /v1/experiments                  # Active A/B experiments
POST /v1/keys                         # Create new API key
```

All responses: `{"data": {...}, "error": null}` or `{"data": null, "error": {"code":"...","message":"..."}}`

---

## What I'd Add With More Time

- **Streaming responses** — SSE endpoint for real-time token streaming
- **Prompt versioning** — store and diff prompt templates, tie eval scores to versions  
- **Cost forecasting** — linear regression on rolling 7-day spend to project monthly cost
- **Webhook alerts** — POST to Slack/Discord when quality drops below threshold or drift detected
- **Fine-tuned classifier** — replace TF-IDF with a small BERT fine-tuned on domain data
- **Feedback loop** — use eval scores as training signal to continuously improve routing thresholds
