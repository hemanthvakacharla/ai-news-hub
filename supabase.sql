-- Run once in Supabase: SQL Editor -> New query -> paste -> Run.
create table if not exists votes (
  item_id  text not null,
  voter_id text not null,
  v        text not null check (v in ('up','down')),
  at       timestamptz not null default now(),
  primary key (item_id, voter_id)          -- one vote per visitor per story
);
alter table votes enable row level security;
create policy "anyone can vote"        on votes for insert with check (true);
create policy "anyone can change vote" on votes for update using (true) with check (true);
create policy "anyone can remove vote" on votes for delete using (true);
-- Visitors never read raw rows, only the totals:
create or replace view vote_counts as
  select item_id,
         count(*) filter (where v = 'up')   as up,
         count(*) filter (where v = 'down') as down
  from votes group by item_id;
grant select on vote_counts to anon;
grant insert, update, delete on votes to anon;
