alter table teams enable row level security;
alter table api_keys enable row level security;
alter table requests enable row level security;
alter table responses enable row level security;
alter table eval_scores enable row level security;
alter table experiments enable row level security;
alter table experiment_assignments enable row level security;
alter table drift_events enable row level security;
alter table audit_log enable row level security;

-- Service role bypasses RLS automatically.
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
    exists (
      select 1 from experiments e
      where e.id = experiment_id
        and e.team_id = (auth.jwt() ->> 'team_id')::uuid
    )
  );

create policy "team_read_own_drift" on drift_events
  for select using (team_id = (auth.jwt() ->> 'team_id')::uuid);

create policy "team_read_audit" on audit_log
  for select using (team_id = (auth.jwt() ->> 'team_id')::uuid);
