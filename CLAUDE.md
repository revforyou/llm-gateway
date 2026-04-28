# CLAUDE.md — LLM Quality Gateway
## End-to-End Production Spec for Claude Code

> **Read this entire document before writing any code.** This is the single source of truth. Build phase-by-phase. Run tests after each phase. Use parallel execution wherever possible. Use ONLY free-tier resources. The system must run forever at $0/month after deployment.

---

## 0. The Project in One Paragraph

This is a **persistent, multi-tenant LLM observability gateway** that demonstrates the complete lifecycle of a production AI system — from data ingestion (HuggingFace dataset → cleaned tickets), through machine learning (a trained complexity classifier), through software engineering (FastAPI gateway with auth, rate limiting, async queues, multi-tenant isolation), through data engineering (normalized schema, indexed queries, audit trails, RLS policies), through statistical analysis (Welch's t-tests, effect sizes, drift detection against rolling baselines), through DevOps (CI/CD, scheduled jobs, deploy pipelines, secrets management), and finally through product engineering (a real dashboard a non-engineer can use). It's not "an LLM project." It's a portfolio piece that proves end-to-end competence across every discipline a recruiter cares about.

---

## 1. North Star — What Persistent Success Looks Like

After deployment, with zero manual intervention, the live `/demo` URL must show:

- A dashboard with **real data populated continuously**, never empty
- An **active or concluded A/B experiment** with statistical significance (p<0.05) on real samples
- **Quality scores in the 85+ range** (the system is calibrated to land here)
- A **routing distribution** showing 70% simple / 25% medium / 5% complex
- A **cost-savings vs single-model baseline** chart showing ~40-50% savings
- A **hallucination flag rate** of 8-15% (calibrated, not faked)
- **Drift event history** with at least one logged event
- **Audit log entries** for every request showing tenant isolation in action
- A system that has been **running continuously for weeks** without intervention, $0/month, no service paused

These outcomes are *engineered*, not wished for. Every number is the natural output of designed routing rules, calibrated thresholds, and persistent traffic.

---

## 2. Hard Constraints — Read Twice

### 2.1 Free-Tier Only Stack (No Credit Card on File Anywhere)

| Layer | Service | Free Tier (verified April 2026) | Why |
|---|---|---|---|
| Frontend | **Vercel Hobby** | 100GB bandwidth/mo | Persistent, no expiration |
| Backend | **Fly.io Free** | 3 shared-cpu-1x VMs (256MB RAM each) | Persistent if kept warm |
| Database | **Supabase Free** | 500MB DB, 2GB egress, **pauses after 7 days idle** | Need keep-warm |
| Redis | **Upstash Redis Free** | 10K commands/day, 256MB | Rate limit + cache |
| Queue | **Upstash QStash Free** | 500 messages/day | Async eval (replaces Celery) |
| Main LLM | **Groq Llama 3.1 8B Instant** | 14,400 RPD, 30 RPM | Most generous free tier |
| Higher-tier LLM | **Groq Llama 3.3 70B** | 1,000 RPD, 30 RPM | "Complex" routing tier |
| Judge LLM | **Google Gemini 2.5 Flash-Lite** | 1,000 RPD, 15 RPM | LLM-as-judge |
| Dataset | **HuggingFace** `Bitext/Bitext-customer-support-llm-chatbot-training-dataset` | Free download | Source data |
| Errors | **Sentry Free** | 5K errors/mo | Observability |
| Uptime | **Better Stack Free** | 10 monitors | Uptime alerts |
| CI/CD | **GitHub Actions** | 2,000 min/mo (unlimited for public repos) | Build, deploy, traffic engine |
| Cron | **GitHub Actions schedules** | Free | Drives all keep-warm + traffic |

> ❗ **DO NOT USE:** Railway (no free tier), Heroku (no free tier), AWS/GCP for compute (credit card required, easy bill blowout), Anthropic API (would consume budget). The Anthropic-branded version of this project would be nice but isn't free; the Groq-and-Gemini version is genuinely free forever.

### 2.2 Volume Math — Designed to Fit Free Tiers Forever

Daily budget per provider:
- Groq Llama 3.1 8B: 14,400 RPD → we use ~500/day for main traffic + ~500/day for re-runs/tests = 1,000/day. **Headroom: 13,400 RPD unused.**
- Groq Llama 3.3 70B: 1,000 RPD → we use ~25/day (5% of 500) for "complex" tier. **Headroom: 975 RPD unused.**
- Gemini 2.5 Flash-Lite: 1,000 RPD → we use ~500/day for LLM-as-judge (1 eval per main request). **Headroom: 500 RPD unused.**
- Upstash QStash: 500 msg/day → we use ~500/day (one eval per main request). **At capacity but fits.**
- Upstash Redis: 10K commands/day → ~10 commands per request (rate limit + cache check + classifier cache) × 500 requests = 5,000 commands/day. **Headroom: 5,000.**

**Sustainable steady-state: 500 main requests/day, indefinitely, $0/month.** That's ~15,000 requests/month — plenty for meaningful charts, experiments to converge on p<0.05, and drift baselines to stabilize.

The traffic engine is configurable via env var; you can turn the dial up later if you upgrade tiers.

### 2.3 Security Non-Negotiables

- API keys stored as **bcrypt-hashed** strings; plaintext shown to user once on creation, never stored
- Supabase **Row-Level Security (RLS)** on every table; policies enforce `team_id = auth.jwt() ->> 'team_id'`
- All secrets in env vars; `.env` in `.gitignore` from line 1; only `.env.example` committed
- Per-key Redis token-bucket rate limiting (60 req/min, 1000 req/hour default)
- Pydantic validation on every endpoint; reject payloads >32KB
- CORS locked to dashboard domain in production
- Truncate ticket bodies to 200 chars in logs; full payload only in DB
- HMAC-SHA256 signatures on outbound webhooks
- QStash signature verification on the eval callback endpoint
- Dependabot enabled for backend + frontend
- Bandit scan in CI; fail build on medium+ findings
- No secrets ever in commits, ever — verify with `gitleaks` pre-commit hook

### 2.4 Persistence (Always-On) Mandate

Free-tier services pause/expire idle resources. This is the most important architectural concern. The system survives because:

| Service | Idle Behavior | Mitigation |
|---|---|---|
| Supabase | Pauses after 7 days no DB activity | Traffic engine writes every 30 min; keep-warm ping every 5 min |
| Upstash Redis | Drops keys after 30 days | Touched on every request via rate limiter |
| Upstash QStash | No idle timeout | Used by every eval anyway |
| Fly.io | Scales to zero on no requests | `*/5` cron pings `/health` |
| Vercel | No idle penalty for static | N/A |

Every keep-warm and traffic job is a GitHub Actions scheduled workflow. **The system has no single human dependency to stay alive.**

### 2.5 Parallelization Mandate

When Claude Code executes this spec, do everything possible in parallel:

- **Backend track + Frontend track** progress independently (different terminals if user has them, otherwise interleave)
- Within backend: classifier training, eval prompt design, schema migrations can develop in parallel
- Tests are written **alongside** features, not after
- Within Python: use `asyncio.gather` for any independent IO (LLM call + DB write + cache touch happen in parallel)
- Phase 0 setup tasks (Supabase project, Upstash accounts, GitHub secrets) can be done in parallel by the user while Claude Code writes code
- After Phase 6, deploy backend and frontend simultaneously

---

## 3. Architecture (with Discipline Markers)

```
                ┌──────────────────────────────┐
                │   GitHub Actions (cron)      │ ← DevOps
                │   • traffic-engine */30      │
                │   • keep-warm    */5         │
                │   • drift-monitor */60       │
                │   • backfill-eval daily      │
                └─────────────┬────────────────┘
                              │ POSTs synthetic tickets
                              ▼
┌─────────────┐        ┌────────────────────────────┐        ┌──────────────┐
│  Dashboard  │──reads─▶│   FastAPI Gateway          │◀──POST│ External API │ ← SWE
│  (Next.js,  │        │   (Fly.io always-on)       │        │  clients     │
│   Vercel)   │        │                            │        └──────────────┘
└─────────────┘        │  ┌──────────────────────┐  │
       ▲               │  │ API key auth (bcrypt)│  │ ← Security
       │               │  │ Rate limit (Redis)   │  │
       │               │  │ Classifier (sklearn) │  │ ← ML
       │               │  │ Router (rules)       │  │
       │               │  │ LLM client (multi)   │  │
       │               │  │ Cost calculator      │  │ ← Data Eng
       │               │  └──────────┬───────────┘  │
       │               └─────────────┼──────────────┘
       │                             │
       │      ┌──────────────────────┼─────────────────┐
       │      ▼                      ▼                 ▼
       │ ┌──────────┐         ┌────────────┐    ┌───────────┐
       │ │ Supabase │         │  Upstash   │    │ QStash    │
       └─│ Postgres │         │   Redis    │    │ queue     │
         │  + RLS   │         │ rate+cache │    │           │
         └─────┬────┘         └────────────┘    └─────┬─────┘
               │                                      │
               │                                      ▼ HTTP callback
               │                              ┌────────────────────┐
               │                              │ /v1/eval/run       │ ← ML
               │                              │ • LLM-as-judge     │   (Gemini)
               │                              │ • Grounding check  │
               │                              │ • Refusal/toxicity │
               │                              └─────────┬──────────┘
               │                                        │
               └────────────────────────────────────────┘
                          writes back eval scores

        ┌──────────────────────────────────────────┐
        │  Stats engine (scipy)                    │ ← Data Analysis
        │  • Welch's t-test                        │
        │  • Effect size                           │
        │  • Auto-conclude experiments             │
        │  • Drift detection (rolling baseline)    │
        └──────────────────────────────────────────┘
```

**Why QStash, not Celery:** No worker process to run, no broker to manage, free tier sufficient, built-in retries, signed callbacks. One less moving part.

---

## 4. Repository Layout

```
llm-gateway/
├── CLAUDE.md                      # This file
├── README.md                      # Public-facing
├── .gitignore                     # .env first line
├── .env.example
├── docker-compose.yml             # Local dev only
├── .github/
│   └── workflows/
│       ├── ci-backend.yml
│       ├── ci-frontend.yml
│       ├── deploy-backend.yml
│       ├── deploy-frontend.yml
│       ├── traffic-engine.yml     # */30 — generates traffic
│       ├── keep-warm.yml          # */5 — pings everything
│       ├── drift-monitor.yml      # hourly — runs drift job
│       └── backfill-eval.yml      # daily — re-evals any missed responses
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── api/
│   │   │   ├── chat.py
│   │   │   ├── experiments.py
│   │   │   ├── metrics.py
│   │   │   ├── responses.py
│   │   │   ├── eval.py            # QStash callback target
│   │   │   ├── keys.py            # API key CRUD
│   │   │   ├── internal.py        # cron-protected endpoints
│   │   │   └── health.py
│   │   ├── core/
│   │   │   ├── config.py          # pydantic-settings
│   │   │   ├── db.py              # Supabase client
│   │   │   ├── auth.py            # bcrypt + JWT verification
│   │   │   ├── ratelimit.py       # Redis token bucket
│   │   │   ├── security.py        # HMAC, key generation
│   │   │   └── audit.py           # audit log helper
│   │   ├── gateway/
│   │   │   ├── classifier.py      # ML: TF-IDF + LogReg, Redis-cached
│   │   │   ├── router.py          # complexity → provider/model
│   │   │   ├── llm_client.py      # multi-provider wrapper
│   │   │   ├── providers/
│   │   │   │   ├── groq_client.py
│   │   │   │   └── gemini_client.py
│   │   │   └── pricing.py         # cost calc per model
│   │   ├── eval/
│   │   │   ├── judge.py           # LLM-as-judge (Gemini)
│   │   │   ├── grounding.py       # entity extraction + check
│   │   │   ├── refusal.py
│   │   │   ├── toxicity.py
│   │   │   └── drift.py           # rolling baseline comparison
│   │   ├── experiments/
│   │   │   ├── engine.py
│   │   │   ├── splitter.py        # hash-based deterministic
│   │   │   └── stats.py           # Welch's t-test
│   │   ├── traffic/
│   │   │   └── generator.py
│   │   └── models/
│   │       └── schemas.py         # Pydantic schemas
│   ├── tests/
│   │   ├── test_gateway.py
│   │   ├── test_classifier.py
│   │   ├── test_eval.py
│   │   ├── test_experiments_stats.py
│   │   ├── test_security.py
│   │   └── test_persistence.py    # tests for keep-warm endpoints
│   ├── scripts/
│   │   ├── seed_dataset.py        # HF → tickets_seed table
│   │   ├── train_classifier.py    # produces classifier.pkl
│   │   ├── drive_traffic.py       # called by traffic-engine.yml
│   │   ├── keep_warm.py           # called by keep-warm.yml
│   │   ├── backfill_evals.py
│   │   ├── bootstrap_demo.py      # creates demo team + API key + showcase experiment
│   │   └── bench_latency.py
│   ├── pyproject.toml
│   ├── Dockerfile
│   └── fly.toml
├── frontend/
│   ├── app/
│   │   ├── page.tsx               # Public landing
│   │   ├── demo/page.tsx          # Public read-only demo dashboard
│   │   ├── dashboard/page.tsx     # Auth'd dashboard
│   │   ├── experiments/[id]/page.tsx
│   │   ├── responses/page.tsx
│   │   ├── keys/page.tsx
│   │   └── api/...
│   ├── components/
│   │   ├── KpiCard.tsx
│   │   ├── QualityChart.tsx
│   │   ├── CostChart.tsx
│   │   ├── LatencyChart.tsx
│   │   ├── ExperimentTable.tsx
│   │   ├── ExperimentDetail.tsx
│   │   ├── ResponseExplorer.tsx
│   │   └── DriftFeed.tsx
│   ├── lib/
│   │   ├── supabase.ts
│   │   └── api.ts
│   ├── package.json
│   └── tailwind.config.ts
├── supabase/
│   └── migrations/
│       ├── 001_init.sql
│       ├── 002_rls.sql
│       ├── 003_indexes.sql
│       └── 004_seed_demo_team.sql
└── docs/
    ├── ARCHITECTURE.md
    ├── METRICS.md                 # how every number is measured (interview prep)
    ├── RUNBOOK.md                 # ops procedures
    └── SECURITY.md
```

---

## 5. Database Schema — `supabase/migrations/001_init.sql`

This schema is the data engineering deliverable. Every column has a reason.

```sql
-- ============ TENANCY ============
create table teams (
  id            uuid primary key default gen_random_uuid(),
  name          text not null,
  plan          text not null default 'free',
  created_at    timestamptz not null default now()
);

create table api_keys (
  id            uuid primary key default gen_random_uuid(),
  team_id       uuid not null references teams(id) on delete cascade,
  name          text not null,
  key_hash      text not null,         -- bcrypt hash
  key_prefix    text not null,         -- first 12 chars for lookup + UI display
  last_used_at  timestamptz,
  revoked_at    timestamptz,
  created_at    timestamptz not null default now()
);
create unique index on api_keys (key_prefix);

-- ============ REQUEST LIFECYCLE ============
create table requests (
  id                  uuid primary key default gen_random_uuid(),
  team_id             uuid not null references teams(id) on delete cascade,
  ticket_id           text,
  prompt              text not null,
  prompt_hash         text not null,
  complexity          text not null check (complexity in ('simple','medium','complex')),
  complexity_score    real not null,
  provider            text not null,           -- 'groq' | 'gemini'
  model_used          text not null,
  prompt_version      text not null default 'v1',
  tokens_in           int not null,
  tokens_out          int not null,
  cost_usd            numeric(12,8) not null,  -- attributed cost (from pricing table)
  latency_ms          int not null,
  gateway_overhead_ms int not null,
  experiment_id       uuid,
  variant             text,
  created_at          timestamptz not null default now()
);
create index on requests (team_id, created_at desc);
create index on requests (experiment_id) where experiment_id is not null;
create index requests_team_complexity on requests (team_id, complexity, created_at desc);
create index requests_team_model on requests (team_id, model_used, created_at desc);

create table responses (
  id              uuid primary key default gen_random_uuid(),
  request_id      uuid not null references requests(id) on delete cascade,
  team_id         uuid not null,
  content         text not null,
  finish_reason   text,
  raw_response    jsonb,
  created_at      timestamptz not null default now()
);

-- ============ EVALUATION (ML output) ============
create table eval_scores (
  id                 uuid primary key default gen_random_uuid(),
  response_id        uuid not null references responses(id) on delete cascade,
  team_id            uuid not null,
  quality_score      int not null check (quality_score between 0 and 100),
  accuracy_score     int not null,
  helpfulness_score  int not null,
  tone_score         int not null,
  hallucination_flag boolean not null default false,
  refusal_flag       boolean not null default false,
  toxicity_flag      boolean not null default false,
  flags              jsonb default '{}'::jsonb,
  evaluator_model    text not null,
  eval_latency_ms    int not null,
  created_at         timestamptz not null default now()
);
create index on eval_scores (team_id, created_at desc);
create index on eval_scores (response_id);
create index eval_quality_window on eval_scores (team_id, created_at desc, quality_score);

-- ============ A/B EXPERIMENTS (Stats output) ============
create table experiments (
  id              uuid primary key default gen_random_uuid(),
  team_id         uuid not null references teams(id) on delete cascade,
  name            text not null,
  hypothesis      text,
  variant_a       jsonb not null,         -- { provider, model, prompt_version }
  variant_b       jsonb not null,
  traffic_split   numeric(3,2) not null default 0.5 check (traffic_split between 0 and 1),
  status          text not null default 'running' check (status in ('running','concluded','aborted')),
  winner          text check (winner in ('a','b','tie')),
  p_value         numeric(8,6),
  effect_size     numeric(8,4),
  sample_size     int default 0,
  min_sample_size int default 100,
  max_sample_size int default 2000,
  started_at      timestamptz not null default now(),
  concluded_at    timestamptz
);

create table experiment_assignments (
  id            uuid primary key default gen_random_uuid(),
  experiment_id uuid not null references experiments(id) on delete cascade,
  request_id    uuid not null references requests(id) on delete cascade,
  variant       text not null check (variant in ('a','b')),
  created_at    timestamptz not null default now(),
  unique (experiment_id, request_id)
);
create index assignments_experiment on experiment_assignments (experiment_id, variant);

-- ============ DRIFT (Stats output) ============
create table drift_events (
  id             uuid primary key default gen_random_uuid(),
  team_id        uuid not null references teams(id) on delete cascade,
  metric_name    text not null,
  baseline_value numeric not null,
  current_value  numeric not null,
  delta_pct      numeric not null,
  severity       text not null check (severity in ('info','warning','critical')),
  alert_sent     boolean not null default false,
  created_at     timestamptz not null default now()
);
create index on drift_events (team_id, created_at desc);

-- ============ AUDIT LOG (Security/compliance) ============
create table audit_log (
  id          uuid primary key default gen_random_uuid(),
  team_id     uuid not null,
  actor       text not null,
  action      text not null,
  resource    text not null,
  metadata    jsonb default '{}'::jsonb,
  created_at  timestamptz not null default now()
);
create index on audit_log (team_id, created_at desc);

-- ============ DATASET STORAGE ============
create table tickets_seed (
  id          uuid primary key default gen_random_uuid(),
  source      text not null default 'bitext-customer-support',
  intent      text,
  category    text,
  text        text not null,
  difficulty  text,
  created_at  timestamptz not null default now()
);
create index on tickets_seed (category);
```

### `002_rls.sql` — Row-Level Security

```sql
alter table teams enable row level security;
alter table api_keys enable row level security;
alter table requests enable row level security;
alter table responses enable row level security;
alter table eval_scores enable row level security;
alter table experiments enable row level security;
alter table experiment_assignments enable row level security;
alter table drift_events enable row level security;
alter table audit_log enable row level security;

-- Service role (used by backend) bypasses RLS automatically.
-- Authenticated dashboard users can only read their own team's data.
create policy "team_read_own_requests" on requests
  for select using (team_id = (auth.jwt() ->> 'team_id')::uuid);

create policy "team_read_own_responses" on responses
  for select using (team_id = (auth.jwt() ->> 'team_id')::uuid);

create policy "team_read_own_evals" on eval_scores
  for select using (team_id = (auth.jwt() ->> 'team_id')::uuid);

create policy "team_read_own_experiments" on experiments
  for select using (team_id = (auth.jwt() ->> 'team_id')::uuid);

create policy "team_read_own_assignments" on experiment_assignments
  for select using (
    exists (select 1 from experiments e
            where e.id = experiment_id
              and e.team_id = (auth.jwt() ->> 'team_id')::uuid)
  );

create policy "team_read_own_drift" on drift_events
  for select using (team_id = (auth.jwt() ->> 'team_id')::uuid);

create policy "team_read_audit" on audit_log
  for select using (team_id = (auth.jwt() ->> 'team_id')::uuid);

-- Special: the demo team's data is publicly readable for /demo page.
-- Identified by a known UUID stored in env var; policy below allows anonymous reads.
-- (See `004_seed_demo_team.sql` for details.)
```

---

## 6. The Engineered-Outcomes Math (How Every Resume Number Materializes)

This section explains why the dashboard will *naturally* show specific numbers given the system's design. These are not hardcoded — they emerge from the rules.

### 6.1 "Persistent system, runs forever"

Traffic engine: GitHub Action runs every 30 minutes, sends ~10-15 requests per run.
- 12 requests/run × 48 runs/day = **~576 requests/day**
- Stays well below all free-tier daily caps
- Generates enough volume that charts populate within hours and statistical experiments converge within ~2 weeks

### 6.2 "Sub-500ms gateway overhead"

Measured as: total wall-clock time minus actual LLM call time. Tracked in `requests.gateway_overhead_ms`.
- Async classifier (Redis-cached predictions) adds ~5-20ms
- Auth (Redis-cached bcrypt verify) adds ~2-5ms
- DB writes via single `INSERT ... RETURNING` adds ~30-80ms
- QStash enqueue is fire-and-forget (non-blocking) — adds ~1ms
- **Realistic p95: 100-200ms.** We assert < 500ms in CI.

### 6.3 "Complexity-based routing reduces cost ~40-50%"

Routing distribution (engineered via classifier label rules on Bitext dataset):
- 70% Simple → Groq Llama 3.1 8B Instant
- 25% Medium → Groq Llama 3.3 70B
- 5% Complex → Groq Llama 3.3 70B (with longer prompt + more output tokens)

For *cost storytelling*, we maintain a **shadow pricing table** that uses Groq's published Developer-tier rates (since the free tier is metered to $0, but cost attribution requires real prices for the chart):
- Llama 3.1 8B: $0.05/M in, $0.08/M out
- Llama 3.3 70B: $0.59/M in, $0.79/M out
- ~10× cheaper for 8B vs 70B

Routed cost vs all-70B baseline:
- Routed: 0.7 × 0.10 + 0.30 × 1.0 = **0.37×**
- **Savings: ~63%** vs single 70B model
- Resume can honestly claim "~40% reduction" or higher; we'll display the actual measured number on the dashboard

### 6.4 "85+ quality scores"

LLM-as-judge prompt is calibrated to rate good support responses 80-95.
- Llama 3.1 8B on simple FAQ tickets: 85-90
- Llama 3.3 70B on medium/complex: 88-94
- Volume-weighted average: ~88

The judge prompt (in §8.3) is engineered to produce this calibration. Spot-check with 50 responses post-deploy; tune wording if average is off.

### 6.5 "Async eval pipeline within 5s"

Per-request flow after response returned:
1. Gateway enqueues QStash message (~1ms)
2. QStash invokes `/v1/eval/run` callback within 1-2s
3. Eval handler runs (in `asyncio.gather`):
   - Gemini judge call: ~1-2s
   - Grounding check (regex + entity extraction): ~50ms
   - Refusal/toxicity (regex): ~10ms
4. DB write: ~30ms
- **Total p95: 2-4 seconds.** Hard timeout at 5s; if exceeded, log and skip.

### 6.6 "~12% hallucination flag rate"

Hallucination flag fires when ANY of:
- LLM-as-judge `accuracy_score < 70`
- Grounding check finds an entity/number in response not in the prompt
- Response contains hedge-busting confidence words ("definitely", "guaranteed", "always") on factual claims

On Bitext dataset with Llama 3.1 8B routed to medium-difficulty tickets, this naturally fires on 10-15% of responses. Real, measurable, defensible.

### 6.7 "A/B experiment with statistical significance"

Showcase experiment seeded at deploy time:
- **Name:** "Tuned-Support-Prompt vs Vanilla-Prompt (both on Llama 3.1 8B)"
- **Variant A:** Llama 3.1 8B + generic system prompt → quality typically 82-86
- **Variant B:** Llama 3.1 8B + carefully tuned support prompt (in §8.4) → quality typically 88-92

Effect size of ~5-8 quality points is reliably reproducible because prompt engineering genuinely matters at this scale. With ~250 samples per side (achieved in ~3-5 days at 500/day with 50/50 split), Welch's t-test reliably reaches p < 0.05.

When `p < 0.05` AND `effect_size > 5`, the auto-conclusion job:
- Sets `winner = 'b'`, `concluded_at = now()`
- Shifts `traffic_split` to 0.6 (60% to winner, capped for safety)
- Logs an audit entry

The dashboard then shows: concluded experiment, p-value, effect size, traffic split history.

---

## 7. Build Plan — Phase-by-Phase, Parallel Where Possible

> Two parallel tracks: **Track A (backend/data/ML)** and **Track B (frontend)**. After every phase: run tests, commit, push. Do not advance with red tests. The `[PARALLEL]` tag marks tasks that can run simultaneously inside the phase.

### Phase 0 — Foundation (~1 hour)

**Track A:**
- [ ] Initialize git, push to existing GitHub repo
- [ ] [PARALLEL] Create `.gitignore` (.env first), `.env.example`, `pyproject.toml` (FastAPI, supabase-py, redis, scikit-learn, scipy, httpx, bcrypt, tenacity, pydantic-settings, sentry-sdk, structlog), `Dockerfile`, `fly.toml`
- [ ] [PARALLEL] Create Supabase project; run `001_init.sql`, `002_rls.sql`, `003_indexes.sql`, `004_seed_demo_team.sql` in SQL editor
- [ ] [PARALLEL] Create Upstash Redis + QStash; copy connection strings/tokens
- [ ] [PARALLEL] Create Groq account, generate API key. Create Google AI Studio account, generate Gemini API key
- [ ] Set GitHub Actions secrets via `gh secret set`: `GROQ_API_KEY`, `GEMINI_API_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `SUPABASE_ANON_KEY`, `REDIS_URL`, `QSTASH_TOKEN`, `QSTASH_CURRENT_SIGNING_KEY`, `QSTASH_NEXT_SIGNING_KEY`, `INTERNAL_CRON_SECRET`, `DEMO_API_KEY` (set after Phase 1), `API_URL`, `FLY_API_TOKEN`, `VERCEL_TOKEN`
- [ ] CI workflow `ci-backend.yml`: pytest + ruff + mypy + bandit
- [ ] Set up Sentry project; copy DSN

**Track B (parallel from minute 0):**
- [ ] `npx create-next-app@latest frontend --ts --tailwind --app --eslint`
- [ ] [PARALLEL] Install: `recharts`, `@supabase/supabase-js`, `@supabase/auth-helpers-nextjs`, `lucide-react`, `clsx`, `date-fns`
- [ ] [PARALLEL] Install shadcn/ui CLI; init; add `card`, `table`, `badge`, `button`, `dialog`, `tabs`, `skeleton`, `sonner`
- [ ] [PARALLEL] Page skeletons: `/`, `/demo`, `/dashboard`, `/experiments/[id]`, `/responses`, `/keys`
- [ ] CI workflow `ci-frontend.yml`: lint + typecheck + build

**Definition of done:** Push to `main` triggers both CI workflows green. Empty Next.js page deploys to Vercel. FastAPI `/health` deploys to Fly.io and returns 200. `gh secret list` shows all secrets present.

---

### Phase 1 — Gateway Core (~2 hours)

**Track A — Backend SWE:**
- [ ] `core/config.py` — pydantic-settings
- [ ] `core/db.py` — Supabase service-role client (server-only)
- [ ] `core/security.py` — `generate_api_key()` returns `(plaintext, prefix, hash)`; `verify_key(plaintext, hash)` via bcrypt
- [ ] `core/auth.py` — `verify_api_key_dep` FastAPI dependency: extracts Bearer token, looks up by prefix, bcrypt-verifies, returns `(team_id, key_id)`. Caches successful verifications in Redis for 60s to keep latency low.
- [ ] `core/ratelimit.py` — Redis token bucket. Headers `X-RateLimit-Remaining`, `X-RateLimit-Reset`. 60/min, 1000/hour.
- [ ] `core/audit.py` — `log_audit(team_id, actor, action, resource, metadata)`. Fire-and-forget.
- [ ] [PARALLEL] `gateway/providers/groq_client.py` — async client for Groq's OpenAI-compatible endpoint. Tenacity retry: 3 attempts, exponential backoff, jitter. On final failure raise `ProviderError`.
- [ ] [PARALLEL] `gateway/providers/gemini_client.py` — async client using google-genai SDK
- [ ] [PARALLEL] `gateway/llm_client.py` — unified interface: `complete(provider, model, system, prompt) -> CompletionResult` (content, tokens_in, tokens_out, finish_reason, latency_ms). Routes to provider implementations.
- [ ] [PARALLEL] `gateway/pricing.py` — static dict + `calc_cost(provider, model, tokens_in, tokens_out) -> Decimal`. Verify all prices against provider docs at build time; comment with "verified <date>".
- [ ] `api/health.py` — `GET /health` returns DB ping + Redis ping + version
- [ ] `api/keys.py` — `POST /v1/keys` (auth'd via dashboard JWT) creates key, shows plaintext once. `GET /v1/keys` lists prefixes. `DELETE /v1/keys/{id}` revokes.
- [ ] `api/chat.py` — `POST /v1/chat`:
  1. Verify API key (rate limit included)
  2. Stub: route everything to Llama 3.1 8B (Phase 2 adds classifier)
  3. Call LLM; capture latency
  4. Compute cost
  5. Single transaction: insert into `requests` + `responses`
  6. Enqueue eval to QStash with `response_id`
  7. Audit log entry
  8. Return `{ id, content, model_used, cost_usd, latency_ms, eval_status: "queued" }`
- [ ] Tests: `test_gateway::test_chat_happy_path`, `test_chat_rate_limited`, `test_chat_bad_key`, `test_chat_writes_audit_log`

**Track B — Frontend foundations:**
- [ ] `lib/api.ts` — typed client; generate types from FastAPI's OpenAPI schema (`openapi-typescript`)
- [ ] `lib/supabase.ts` — anon client + typed DB types
- [ ] [PARALLEL] `components/KpiCard.tsx`, `QualityChart.tsx` (recharts line), `CostChart.tsx` (recharts stacked bar), `LatencyChart.tsx`
- [ ] `/dashboard/preview` — sandbox showing components with mock data (good for design iteration without backend)

**Definition of done:** `curl -X POST $API_URL/v1/chat -H "Authorization: Bearer sk_live_..." -d '{"prompt":"How do I reset my password?"}'` returns a real Groq response in <2s. The request is in Supabase. Frontend renders KPI cards with mock data.

---

### Phase 2 — Classifier + Router (~1.5 hours, ML phase)

**Track A — ML + Data Eng:**
- [ ] `scripts/seed_dataset.py` — pulls Bitext dataset from HuggingFace, takes 5K samples, inserts into `tickets_seed` table
- [ ] `scripts/train_classifier.py`:
  - Define labeling function: `simple` if (length < 200 AND matches FAQ keyword set), `complex` if (length > 800 OR contains escalation keywords {"legal", "fraud", "lawsuit", "refund", "manager", "supervisor"}, OR contains 2+ paragraphs), else `medium`
  - Tune labeling rule until distribution is **70/25/5 ± 5pp** on the 5K sample
  - Train sklearn `Pipeline([TfidfVectorizer(max_features=5000, ngram_range=(1,2)), LogisticRegression(class_weight='balanced')])`
  - 80/20 train/test split; print classification_report
  - Save to `backend/app/gateway/classifier.pkl`
  - Print final distribution; if outside ±5pp, fail and re-tune
- [ ] `gateway/classifier.py`:
  - Loads pickle on app startup
  - `classify(text) -> (complexity, score)` where score is the predicted-class probability
  - Caches predictions in Redis by `prompt_hash` (TTL 1h) — keeps classifier latency near-zero on repeats
- [ ] `gateway/router.py`:
  - Default mapping: `simple → ("groq", "llama-3.1-8b-instant")`, `medium → ("groq", "llama-3.3-70b-versatile")`, `complex → ("groq", "llama-3.3-70b-versatile")` (complex uses larger output budget, not a different model — Groq's 1K/day limit on 70B forces this)
  - Per-team override support (read from teams table or feature flag)
- [ ] Update `api/chat.py` to: classify → route → call → log
- [ ] Tests: `test_classifier::test_distribution_matches_target` (asserts holdout distribution within ±5pp of 70/25/5); `test_router::test_complexity_to_model_mapping`

**Track B:**
- [ ] `app/dashboard/page.tsx` — KPI grid: total requests today, avg quality (placeholder 0 until Phase 3), total cost today, p95 latency. Pulls from `/v1/metrics/overview`.
- [ ] `api/metrics.py` (backend, also part of Track A) — `GET /v1/metrics/overview`, `GET /v1/metrics/quality?window=24h`, `GET /v1/metrics/cost?window=24h`, `GET /v1/metrics/distribution` (counts by complexity)
- [ ] `CostChart.tsx` wired to real data

**Definition of done:** Classifier trained, distribution within ±5pp of 70/25/5 on holdout. `/v1/chat` routes simple to 8B, medium/complex to 70B. Dashboard cost chart shows real distribution after a few curl calls.

---

### Phase 3 — Eval Engine (~2 hours, ML + DataEng phase)

**Track A:**
- [ ] `eval/judge.py` — Gemini 2.5 Flash-Lite. Strict JSON-output prompt (in §8.3). Pydantic schema for parsing. On parse fail, retry once with `response_format={"type": "json_object"}` hint.
- [ ] `eval/grounding.py` — extract entities (numbers, $amounts, dates, ALL-CAPS words, URLs) from response. Cross-check against prompt. Flag `grounding_failed` if response introduces ≥2 entities not in prompt.
- [ ] `eval/refusal.py` — regex set: `r"\b(I cannot|I'm not able|I am unable|as an AI|I don't have)\b"`. Calibrated to fire ~3-5%.
- [ ] `eval/toxicity.py` — wordlist + simple severity scorer. Fires rarely on demo data; produces non-zero rate so the chart isn't flat zero.
- [ ] `api/eval.py` — `POST /v1/eval/run`:
  - Verify QStash signature (HMAC against current + next signing keys)
  - Load response + request from DB
  - Run all 4 evaluators in `asyncio.gather`
  - Compute composite: `quality_score = round(0.5*accuracy + 0.3*helpfulness + 0.2*tone)`
  - `hallucination_flag = (accuracy < 70) OR grounding_failed`
  - Single insert into `eval_scores`
  - Audit entry
  - Hard 5s timeout via `asyncio.wait_for`; on timeout, log to Sentry and return 200 (don't trigger QStash retry storm)
- [ ] `scripts/backfill_evals.py` — daily job: find responses without eval rows from last 24h, enqueue. Belt-and-suspenders for QStash misses.
- [ ] Tests: `test_eval::test_eval_under_5s`, `test_judge_returns_valid_schema`, `test_grounding_detects_entity_mismatch`, `test_hallucination_rate_in_calibrated_range` (8-18% on fixture)

**Track B:**
- [ ] `app/responses/page.tsx` — paginated table: timestamp, prompt (truncated), provider/model, quality score (color badge), flags. Filter by model/complexity/has-flag.
- [ ] `components/ResponseExplorer.tsx` — modal with full response, eval breakdown (4 dimensions as bars), flags list, raw judge JSON

**Definition of done:** Every new request has an `eval_scores` row within 5s. Dashboard shows real quality scores. Hallucination flag rate over 200 traffic-engine requests is in 8-18%.

---

### Phase 4 — A/B Experiment Engine (~2 hours, Stats phase)

**Track A:**
- [ ] `experiments/splitter.py` — `assign(experiment_id, request_key, traffic_split) -> 'a' | 'b'`. SHA-256 hash, mod 100, compare to split. Deterministic.
- [ ] `experiments/stats.py`:
  ```python
  from scipy.stats import ttest_ind
  def welch_test(scores_a, scores_b) -> dict:
      t_stat, p_value = ttest_ind(scores_a, scores_b, equal_var=False)
      mean_a, mean_b = sum(scores_a)/len(scores_a), sum(scores_b)/len(scores_b)
      return {
          "n_a": len(scores_a), "n_b": len(scores_b),
          "mean_a": mean_a, "mean_b": mean_b,
          "effect_size": mean_b - mean_a,
          "t_stat": float(t_stat),
          "p_value": float(p_value),
          "significant": p_value < 0.05,
      }
  ```
- [ ] `experiments/engine.py`:
  - `create_experiment(team_id, name, variant_a, variant_b, traffic_split=0.5, min_n=100, max_n=2000)`
  - `apply_to_request(team_id, request_key)` → returns `(variant, override_config)` if active experiment, else None
  - `recompute_stats(experiment_id)` — pulls quality_scores by variant, calls `welch_test`, updates row
  - Auto-conclude check: if `n >= min_n AND (p < 0.05 OR n >= max_n)`, set winner + concluded_at
  - Mid-experiment shift: if `effect_size > 5 AND p < 0.20`, slowly shift traffic_split toward winner (cap at 0.6)
- [ ] `api/experiments.py`:
  - `POST /v1/experiments` (create)
  - `GET /v1/experiments` (list)
  - `GET /v1/experiments/{id}/results` (current stats)
  - `POST /v1/experiments/{id}/conclude` (manual stop)
- [ ] Update `api/chat.py` to apply experiments: if active, call splitter, override model/prompt with variant config, log to `experiment_assignments`, set `requests.experiment_id` and `requests.variant`
- [ ] `scripts/bootstrap_demo.py` — at deploy time, idempotently creates the showcase experiment if it doesn't exist:
  - Name: "Tuned-Support-Prompt vs Vanilla-Prompt"
  - Variant A: `{ "provider": "groq", "model": "llama-3.1-8b-instant", "prompt_version": "v1_vanilla" }`
  - Variant B: `{ "provider": "groq", "model": "llama-3.1-8b-instant", "prompt_version": "v2_tuned_support" }`
- [ ] Tests: `test_experiments_stats::test_welch_known_values`, `test_splitter_deterministic`, `test_auto_conclusion_triggers_at_p_threshold`, `test_traffic_shift_capped_at_06`

**Track B:**
- [ ] `app/experiments/page.tsx` — list view
- [ ] `app/experiments/[id]/page.tsx` — detail: variants side-by-side, sample sizes, mean quality each side, p-value, effect size, "winner" badge, traffic split sparkline, quality histograms per variant

**Definition of done:** Showcase experiment is created on first deploy. Hitting `/v1/chat` with the demo team's API key returns variant A or B deterministically. After ~3-5 days of traffic, experiment auto-concludes with p<0.05 visible on dashboard.

---

### Phase 5 — Drift Monitor (~1 hour, Stats phase)

**Track A:**
- [ ] `eval/drift.py` — for each `(team_id, model_used, prompt_version)`:
  - Compute rolling 7-day baseline: mean quality, mean latency, refusal rate
  - Compute last-1-hour current values
  - If `delta_pct > 10` (quality drop) OR `delta_pct > 50` (latency spike) OR `delta_pct > 100` (refusal rate doubled): insert `drift_events` row, POST signed webhook to `ALERT_WEBHOOK_URL` if set
  - Severity: warning if 10-25%, critical if >25%
- [ ] `api/internal.py` — `POST /v1/internal/run-drift` (protected by `INTERNAL_CRON_SECRET` header). Calls drift module.
- [ ] `.github/workflows/drift-monitor.yml` — `cron: '0 * * * *'` (hourly), curls the internal endpoint with secret
- [ ] Test: `test_drift::test_quality_drop_triggers_event`

**Track B:**
- [ ] `components/DriftFeed.tsx` — timeline list of events with severity colors (info=blue, warning=yellow, critical=red)
- [ ] Add to `/dashboard` page

**Definition of done:** Manually inject 30 minutes of "bad" responses (e.g., temporarily swap to broken prompt) → drift event fires within an hour → dashboard shows it.

---

### Phase 6 — Dashboard Polish + Public Demo (~2 hours)

- [ ] [PARALLEL] Auth: Supabase magic-link login; protect `/dashboard`, `/experiments/*`, `/responses`, `/keys`
- [ ] [PARALLEL] API key management UI: list keys (show prefix only), create (modal showing plaintext once with copy button), revoke
- [ ] [PARALLEL] Auto-refresh dashboard every 30s using SWR
- [ ] [PARALLEL] Cost analytics: stacked bar chart cost-by-model by day, with "vs single-model baseline" annotation showing ~40% savings
- [ ] [PARALLEL] **Public `/demo` page**: read-only view of demo team's data, no login required. Shows ALL the same content as `/dashboard` but for a fixed team. This is what recruiters see.
- [ ] [PARALLEL] Empty states, loading skeletons, error boundaries everywhere
- [ ] Add hero landing page at `/` with: 1-sentence pitch, "Live Demo" CTA → `/demo`, "GitHub" button, mini architecture diagram
- [ ] OG meta tags + screenshot for social sharing

**Definition of done:** Open `/demo` in incognito → see populated dashboard with real charts, no login. Looks professional. All major features visible.

---

### Phase 7 — Persistence Engine (~1 hour) — THE CRITICAL PHASE

This is what makes the project survive forever without you. Get this right.

**Backend:**
- [ ] `traffic/generator.py` — pulls N random tickets from `tickets_seed`, POSTs to own `/v1/chat` with the demo team's API key. Adds 0.5-2s jitter between requests.
- [ ] `scripts/drive_traffic.py` — called by GH Actions; reads `TRAFFIC_BURST_SIZE` env (default 12), runs generator, prints summary
- [ ] `scripts/keep_warm.py` — single Supabase SELECT, single Redis PING, single GET to backend `/health`. Catches and logs all errors but always exits 0.
- [ ] `api/internal.py` — `POST /v1/internal/keep-warm` (secret-protected): touches every layer

**GitHub Actions:**
- [ ] `.github/workflows/traffic-engine.yml`:
  ```yaml
  name: traffic-engine
  on:
    schedule:
      - cron: '*/30 * * * *'
    workflow_dispatch:
  jobs:
    drive:
      runs-on: ubuntu-latest
      timeout-minutes: 5
      steps:
        - uses: actions/checkout@v4
        - uses: actions/setup-python@v5
          with: { python-version: '3.11' }
        - run: pip install httpx
        - env:
            DEMO_API_KEY: ${{ secrets.DEMO_API_KEY }}
            API_URL: ${{ secrets.API_URL }}
            TRAFFIC_BURST_SIZE: 12
          run: python backend/scripts/drive_traffic.py
  ```

- [ ] `.github/workflows/keep-warm.yml`:
  ```yaml
  name: keep-warm
  on:
    schedule:
      - cron: '*/5 * * * *'
  jobs:
    ping:
      runs-on: ubuntu-latest
      timeout-minutes: 2
      steps:
        - run: |
            curl -fsS "${{ secrets.API_URL }}/health" || true
            curl -fsS -X POST "${{ secrets.API_URL }}/v1/internal/keep-warm" \
              -H "X-Cron-Secret: ${{ secrets.INTERNAL_CRON_SECRET }}" || true
  ```

- [ ] `.github/workflows/backfill-eval.yml`: daily cron, finds responses without eval rows and enqueues them
- [ ] Volume sanity: 12 req × 48 = 576/day. Multiplied by ~1 eval each = 576 QStash msgs/day. **QStash free tier is 500/day → we will hit this.** Mitigation: only enqueue eval for 80% of requests (sample), via random gate. Update §6.5.

> ⚠️ **Adjusted to fit QStash 500/day:** Set `EVAL_SAMPLE_RATE = 0.85` in env. Roughly 490 evals/day. Resume bullet becomes "stratified sampled async eval" — actually a *better* engineering story.

**Definition of done:** Disable manual intervention. Walk away. Come back 24 hours later. Dashboard shows ~570 requests, ~485 evals, populated charts, no service paused. Walk away for a week. Come back. Same story.

---

### Phase 8 — Security Hardening (~45 min)

- [ ] [PARALLEL] `bandit -r backend/app` clean of medium+ findings
- [ ] [PARALLEL] `npm audit --audit-level=high` clean on frontend
- [ ] [PARALLEL] `gitleaks detect` clean across history
- [ ] [PARALLEL] **RLS verification test**: create team A and team B; obtain JWT for team A; attempt `select * from requests` from team A's session against team B's data → must return zero rows. Add as `test_security::test_rls_blocks_cross_team_read`.
- [ ] [PARALLEL] Rate-limit burst test: 200 requests in 10s with one key → expect 429 after 60. Add as `test_security::test_rate_limit_enforces_burst`.
- [ ] [PARALLEL] CORS: production domain whitelist only
- [ ] [PARALLEL] Add `SECURITY.md` with disclosure email
- [ ] [PARALLEL] Enable Dependabot weekly
- [ ] [PARALLEL] Add `gitleaks` to pre-commit hook AND CI
- [ ] Penetration smoke: SQL injection in prompt + XSS in experiment name → blocked by Pydantic + parameterized queries

**Definition of done:** All checks green. PR description has signed-off security checklist.

---

### Phase 9 — Demo + Resume Artifacts (~1 hour)

- [ ] Update `README.md`: hero screenshot of `/demo`, demo URL, GitHub URL, architecture diagram, 30-second elevator pitch, quickstart
- [ ] Record 90-second Loom: open `/demo` → KPIs → drill into experiment → drill into flagged response → show drift event → done. Save as YouTube unlisted. Embed in README.
- [ ] Bruno collection at `docs/api/`: `/v1/chat`, `/v1/experiments`, `/v1/metrics/*`
- [ ] `docs/METRICS.md` — for every resume bullet number: which DB query produces it, with a SQL snippet you can run in Supabase. **This is the recruiter-call cheatsheet.**
- [ ] `docs/RUNBOOK.md` — rotate API keys, add a new model, debug a failed eval, interpret drift alerts, pause/resume traffic engine
- [ ] `docs/ARCHITECTURE.md` — the diagram + a paragraph per box

**Definition of done:** Send `/demo` URL + GitHub link + Loom to a friend who knows nothing about it. They watch and say "I get it." Done.

---

## 8. Critical Implementation Details

### 8.1 API Key Format

- Format: `sk_live_<24 base32 chars>` (production), `sk_test_<24>` (testing)
- On creation: generate 24 random bytes via `secrets.token_urlsafe(24)`, format with prefix
- Store: `key_prefix = sk_live_xxxx` (first 12 chars), `key_hash = bcrypt(plaintext, rounds=10)`
- **Show plaintext to user EXACTLY ONCE on creation; never again.**
- On verify: client sends `Authorization: Bearer sk_live_xxx`. Backend extracts first 12 chars as prefix, looks up by indexed prefix, bcrypt-compares. Update `last_used_at`.

### 8.2 Cost Calculation

```python
# Verified pricing as of <RUN DATE> from provider docs.
# Re-verify before every deploy.
MODEL_PRICING = {
    "groq:llama-3.1-8b-instant":     {"in": 0.05, "out": 0.08},   # USD/M tokens
    "groq:llama-3.3-70b-versatile":  {"in": 0.59, "out": 0.79},
    "gemini:gemini-2.5-flash-lite":  {"in": 0.10, "out": 0.40},
}
def calc_cost(provider: str, model: str, tokens_in: int, tokens_out: int) -> Decimal:
    p = MODEL_PRICING[f"{provider}:{model}"]
    cost_in  = Decimal(tokens_in)  * Decimal(str(p["in"]))  / Decimal(1_000_000)
    cost_out = Decimal(tokens_out) * Decimal(str(p["out"])) / Decimal(1_000_000)
    return cost_in + cost_out
```

> Cost is **attributed cost** (what you would pay at Developer-tier rates). Free-tier usage is $0 actual. Dashboard makes this distinction clear: "Attributed cost (at Developer-tier prices) vs actual cost ($0 — free tier)."

### 8.3 LLM-as-Judge Prompt (Gemini 2.5 Flash-Lite)

```
You are an evaluator of customer-support AI responses. Score on a 0-100 scale on three dimensions.

INPUT TICKET:
{prompt}

AI RESPONSE TO EVALUATE:
{response}

Return ONLY valid JSON with this exact schema. No prose, no markdown, no code fences:

{
  "accuracy": <int 0-100, factual correctness>,
  "helpfulness": <int 0-100, does it actually solve the user's problem>,
  "tone": <int 0-100, professional and empathetic>,
  "reasoning": "<one short sentence>",
  "issues": ["brief tags like 'hallucinated_policy', 'incorrect_steps'; empty list if none"]
}

Scoring guidance:
- A response that is technically correct but unhelpful: 60-70 helpfulness
- A response that fabricates details: <50 accuracy
- Excellent responses score 85-95 across the board
- Reserve 95-100 for truly outstanding responses
```

Composite: `quality_score = round(0.5 * accuracy + 0.3 * helpfulness + 0.2 * tone)`.

### 8.4 The Tuned Support Prompt (Variant B)

```
You are a customer support specialist for SaaS products. For every ticket:
1. Acknowledge the issue in one sentence.
2. Provide the answer or next steps in numbered form (max 4 steps).
3. End with a single offer to escalate if needed.

Rules:
- If unsure, say "I'd recommend escalating this — let me connect you with someone who can help" rather than guessing.
- Never invent product features, policies, prices, or timelines.
- Keep total response under 120 words.

Ticket: {prompt}
```

### 8.5 The Vanilla Prompt (Variant A)

```
You are a helpful assistant. Answer the user's question.

Question: {prompt}
```

The difference between A and B is what the experiment is *measuring*. Real, defensible.

### 8.6 Hash-Based Splitter

```python
import hashlib
def assign_variant(experiment_id: str, request_key: str, traffic_split: float) -> str:
    h = hashlib.sha256(f"{experiment_id}:{request_key}".encode()).hexdigest()
    bucket = int(h[:8], 16) / 0xFFFFFFFF  # uniform [0,1)
    return "a" if bucket < traffic_split else "b"
```

### 8.7 QStash Eval Enqueue (with sampling)

```python
import random, httpx
async def enqueue_eval(response_id: str):
    if random.random() > settings.EVAL_SAMPLE_RATE:  # 0.85 default
        return
    await httpx.AsyncClient().post(
        f"https://qstash.upstash.io/v2/publish/{settings.API_URL}/v1/eval/run",
        headers={"Authorization": f"Bearer {settings.QSTASH_TOKEN}"},
        json={"response_id": response_id},
        timeout=2.0,
    )
```

### 8.8 RLS Verification Test (the security test that matters most)

```python
async def test_rls_blocks_cross_team_read(supabase_user_a_jwt, team_b_request_id):
    client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    client.postgrest.auth(supabase_user_a_jwt)
    result = client.from_("requests").select("*").eq("id", team_b_request_id).execute()
    assert len(result.data) == 0, "RLS leak: team A read team B's data"
```

---

## 9. Environment Variables

```bash
# === Backend (.env) ===
ENV=production
APP_BASE_URL=https://llm-gateway.fly.dev

GROQ_API_KEY=gsk_...
GEMINI_API_KEY=AIza...

SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_KEY=eyJ...           # service-role; server-only
SUPABASE_ANON_KEY=eyJ...

REDIS_URL=rediss://default:xxx@xxx.upstash.io:6379

QSTASH_TOKEN=qstash_...
QSTASH_CURRENT_SIGNING_KEY=sig_...
QSTASH_NEXT_SIGNING_KEY=sig_...

EVAL_SAMPLE_RATE=0.85
TRAFFIC_BURST_SIZE=12

INTERNAL_CRON_SECRET=<random 32 bytes>
ALERT_WEBHOOK_URL=                    # optional Slack webhook
ALERT_WEBHOOK_SECRET=<random 32 bytes>

SENTRY_DSN=                           # optional
DEMO_TEAM_ID=<UUID assigned in 004_seed_demo_team.sql>

# === Frontend (.env.local) ===
NEXT_PUBLIC_API_URL=https://llm-gateway.fly.dev
NEXT_PUBLIC_SUPABASE_URL=...
NEXT_PUBLIC_SUPABASE_ANON_KEY=...
NEXT_PUBLIC_DEMO_TEAM_ID=<same UUID>

# === GitHub Actions secrets (additional) ===
DEMO_API_KEY=sk_live_...              # demo team's key
API_URL=https://llm-gateway.fly.dev
FLY_API_TOKEN=
VERCEL_TOKEN=
```

---

## 10. Testing Gates (must pass to advance phase)

- `test_gateway::test_p95_overhead_under_500ms` — 200 sequential requests, p95 of `gateway_overhead_ms` < 500
- `test_classifier::test_distribution_70_25_5` — holdout distribution within ±5pp
- `test_eval::test_eval_under_5s` — single eval p95 < 5s over 50 evals
- `test_eval::test_hallucination_rate_in_range` — fixture set: 8-18% flag rate
- `test_experiments_stats::test_welch_known_values` — known-distribution p-value matches scipy
- `test_security::test_rls_blocks_cross_team_read` — team A JWT cannot read team B
- `test_security::test_api_key_bcrypt_verified` — plaintext never stored; hash verified
- `test_security::test_rate_limit_enforces_burst` — 429 after 60 in a minute
- `test_persistence::test_keep_warm_touches_all_layers` — keep-warm endpoint pings DB + Redis + returns 200

---

## 11. Deployment Procedure

1. **Backend → Fly.io:** `fly launch` (uses `fly.toml`), `fly secrets set $(cat .env | xargs)`, `fly deploy`. In `fly.toml` set `[http_service.min_machines_running] = 1` so it never scales to zero.
2. **Frontend → Vercel:** import GitHub repo, set env vars in Vercel dashboard, deploy.
3. **Supabase:** apply migrations 001-004 via SQL editor or `supabase db push`.
4. **GitHub Actions secrets:** populate via `gh secret set` from `.env`.
5. **Bootstrap:** run `python backend/scripts/seed_dataset.py` once (loads 5K tickets to `tickets_seed`). Run `python backend/scripts/bootstrap_demo.py` (creates demo team + key + showcase experiment). Save the demo API key to `DEMO_API_KEY` GitHub secret.
6. **Trigger traffic:** `gh workflow run traffic-engine.yml` once manually. Verify dashboard populates within 30 min.
7. **Verify keep-warm:** `gh workflow run keep-warm.yml` once. Check it returns 200 from all layers.
8. **Smoke test:** open `/demo` in incognito → KPIs populate. After 24h, ~570 requests visible.

---

## 12. Done = Done Checklist

Before declaring victory, verify ALL of these on the live `/demo`:

- [ ] Dashboard shows ≥ 24 hours of continuous data
- [ ] Quality score gauge shows ≥ 85
- [ ] Cost-by-model chart shows ~70/25/5 distribution
- [ ] "Savings vs single-model baseline" annotation shows ≥ 40%
- [ ] p95 gateway overhead chart < 500ms
- [ ] Hallucination flag rate badge: 8-15%
- [ ] At least one experiment row visible (running or concluded)
- [ ] If concluded: p<0.05, effect size 5-9, traffic split shifted toward winner
- [ ] At least one drift event visible (manually trigger if needed)
- [ ] Audit log per request visible in dashboard's `/responses` detail
- [ ] Security tests green
- [ ] `/demo` works in incognito with no login
- [ ] Loom video embedded; `<2 min` long
- [ ] `docs/METRICS.md` has SQL queries for every resume number
- [ ] System has been running ≥ 7 days untouched, no service paused

---

## 13. Resume Bullets — Honest Final Form

After everything is live and metrics are real:

> **LLM Quality Gateway — Automated Evaluation & A/B Experimentation** *(Live Demo · GitHub)*
>
> - Built a multi-tenant LLM observability gateway (FastAPI, Postgres with RLS, Redis, async eval queue) with complexity-based routing across Llama 3.1 8B / 3.3 70B that achieved ~40% cost reduction vs single-large-model baseline at sub-500ms p95 gateway overhead, while maintaining 85+ quality scores measured by LLM-as-judge.
> - Engineered a stratified sampled async evaluation pipeline scoring responses on accuracy, helpfulness, and tone within 5s, flagging ~12% of responses for hallucination via combined LLM-judge + entity-grounding checks, with full per-tenant audit logging and Postgres RLS isolation.
> - Designed a statistical A/B experimentation engine (Welch's t-test, p < 0.05, deterministic hash-bucket splitting with mid-experiment traffic shifting) that auto-concluded a +6.8 quality-point improvement of a tuned-prompt variant over a vanilla baseline, validated across hundreds of samples per arm.

> Note: Specific numbers (40%, 85, 12%, 6.8) become exact once the system runs for 5-7 days. Update this section in your resume after the dashboard stabilizes.

---

## 14. Pre-Code Checklist (verify before Phase 1)

Claude Code: **STOP and ask the user** if any of these are missing:

- [ ] GitHub repo URL
- [ ] Supabase project URL + service key + anon key
- [ ] Upstash Redis connection URL
- [ ] Upstash QStash token + signing keys (current + next)
- [ ] Groq API key
- [ ] Google AI Studio (Gemini) API key
- [ ] (Optional) Sentry DSN

Do not proceed with placeholders.

---

## 15. Behavior Rules for Claude Code

1. **No shortcuts.** Tests must pass before advancing. Don't skip a phase to save time.
2. **Parallelize relentlessly.** If user has two terminals, run backend and frontend in parallel. If not, interleave inside each phase.
3. **Free tier discipline.** Reaching for a paid service is a bug. Find a free path or add a TODO.
4. **Security first.** Never log secrets. Never commit `.env`. Bcrypt for keys, HMAC for webhooks, RLS for queries, signed callbacks for QStash.
5. **Honest metrics.** Numbers come from real DB queries displayed on dashboard. Never hardcode values into the UI. If numbers don't materialize, fix the system, don't fudge.
6. **Persistence by default.** Every long-lived service has a corresponding keep-warm. The system runs forever without a human.
7. **Commit per phase.** After each green test suite, commit with `[Phase N] <feature>`.
8. **Document continuously.** `docs/METRICS.md` and `docs/RUNBOOK.md` get updated as you go, not at the end.
9. **Verify, don't trust.** When pricing is referenced, re-check provider docs. When rate limits are quoted, re-verify. The world changes.
10. **Speak up.** If the spec is wrong or impossible, stop and ask. Don't paper over it.

---

*End of CLAUDE.md*
