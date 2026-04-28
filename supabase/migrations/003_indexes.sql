create index on requests (team_id, created_at desc);
create index on requests (experiment_id) where experiment_id is not null;
create index requests_team_complexity on requests (team_id, complexity, created_at desc);
create index requests_team_model on requests (team_id, model_used, created_at desc);

create index on responses (request_id);
create index on responses (team_id, created_at desc);

create index on eval_scores (team_id, created_at desc);
create index on eval_scores (response_id);
create index eval_quality_window on eval_scores (team_id, created_at desc, quality_score);

create index assignments_experiment on experiment_assignments (experiment_id, variant);

create index on drift_events (team_id, created_at desc);
create index on audit_log (team_id, created_at desc);
create index on tickets_seed (category);
