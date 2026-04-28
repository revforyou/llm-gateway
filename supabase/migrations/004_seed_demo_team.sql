-- Demo team for public /demo page.
-- The UUID is fixed so env vars can reference it.
-- Run this after 001, 002, 003.

insert into teams (id, name, plan)
values ('00000000-0000-0000-0000-000000000001', 'Demo Team', 'free')
on conflict (id) do nothing;

-- Allow anonymous reads for the demo team (for public /demo page).
create policy "demo_team_public_requests" on requests
  for select using (team_id = '00000000-0000-0000-0000-000000000001'::uuid);

create policy "demo_team_public_responses" on responses
  for select using (team_id = '00000000-0000-0000-0000-000000000001'::uuid);

create policy "demo_team_public_evals" on eval_scores
  for select using (team_id = '00000000-0000-0000-0000-000000000001'::uuid);

create policy "demo_team_public_experiments" on experiments
  for select using (team_id = '00000000-0000-0000-0000-000000000001'::uuid);

create policy "demo_team_public_drift" on drift_events
  for select using (team_id = '00000000-0000-0000-0000-000000000001'::uuid);
