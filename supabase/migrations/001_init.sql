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
  key_hash      text not null,
  key_prefix    text not null,
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
  provider            text not null,
  model_used          text not null,
  prompt_version      text not null default 'v1',
  tokens_in           int not null,
  tokens_out          int not null,
  cost_usd            numeric(12,8) not null,
  latency_ms          int not null,
  gateway_overhead_ms int not null,
  experiment_id       uuid,
  variant             text,
  created_at          timestamptz not null default now()
);

create table responses (
  id              uuid primary key default gen_random_uuid(),
  request_id      uuid not null references requests(id) on delete cascade,
  team_id         uuid not null,
  content         text not null,
  finish_reason   text,
  raw_response    jsonb,
  created_at      timestamptz not null default now()
);

-- ============ EVALUATION ============
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

-- ============ A/B EXPERIMENTS ============
create table experiments (
  id              uuid primary key default gen_random_uuid(),
  team_id         uuid not null references teams(id) on delete cascade,
  name            text not null,
  hypothesis      text,
  variant_a       jsonb not null,
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

-- ============ DRIFT ============
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

-- ============ AUDIT LOG ============
create table audit_log (
  id          uuid primary key default gen_random_uuid(),
  team_id     uuid not null,
  actor       text not null,
  action      text not null,
  resource    text not null,
  metadata    jsonb default '{}'::jsonb,
  created_at  timestamptz not null default now()
);

-- ============ DATASET ============
create table tickets_seed (
  id          uuid primary key default gen_random_uuid(),
  source      text not null default 'bitext-customer-support',
  intent      text,
  category    text,
  text        text not null,
  difficulty  text,
  created_at  timestamptz not null default now()
);
