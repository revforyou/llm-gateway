-- Add judge_confidence to eval_scores.
-- The eval pipeline records whether the LLM-as-judge returned parseable JSON
-- ("high") or fell back to default scores after a parse failure ("low").
-- Low-confidence scores are excluded from dashboard aggregates and from the
-- weekly classifier retrain feedback signal.
--
-- This column is written by app/api/eval.py and read by app/api/metrics.py
-- and scripts/retrain_from_feedback.py. Without it, every eval insert fails
-- and /v1/metrics/public returns 500.

alter table eval_scores
  add column if not exists judge_confidence text not null default 'high'
  check (judge_confidence in ('high', 'low'));

create index if not exists eval_scores_judge_confidence
  on eval_scores (team_id, judge_confidence, created_at desc);
