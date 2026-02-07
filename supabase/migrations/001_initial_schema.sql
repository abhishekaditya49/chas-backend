-- CHAS initial schema
-- Generated from BACKEND.md specification.

create extension if not exists pgcrypto;

create table if not exists public.users (
  id uuid primary key references auth.users(id) on delete cascade,
  email text not null unique,
  display_name text not null,
  avatar_url text,
  created_at timestamptz not null default now()
);

create or replace function public.handle_new_user()
returns trigger as $$
begin
  insert into public.users (id, email, display_name, avatar_url)
  values (
    new.id,
    new.email,
    coalesce(new.raw_user_meta_data->>'full_name', split_part(new.email, '@', 1)),
    new.raw_user_meta_data->>'avatar_url'
  )
  on conflict (id) do nothing;
  return new;
end;
$$ language plpgsql security definer;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

create table if not exists public.communities (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  description text not null default '',
  invite_code text not null unique default encode(gen_random_bytes(4), 'hex'),
  daily_cc_budget integer not null default 100,
  created_by uuid not null references public.users(id),
  created_at timestamptz not null default now()
);
create index if not exists idx_communities_invite_code on public.communities(invite_code);

create table if not exists public.community_members (
  user_id uuid not null references public.users(id) on delete cascade,
  community_id uuid not null references public.communities(id) on delete cascade,
  role text not null default 'member' check (role in ('member', 'moderator', 'council')),
  joined_at timestamptz not null default now(),
  primary key (user_id, community_id, role)
);
create index if not exists idx_community_members_community on public.community_members(community_id);

create table if not exists public.cc_balances (
  user_id uuid not null references public.users(id) on delete cascade,
  community_id uuid not null references public.communities(id) on delete cascade,
  daily_budget integer not null default 100,
  spent_today integer not null default 0,
  remaining integer not null default 100,
  last_reset timestamptz not null default now(),
  debt integer not null default 0,
  primary key (user_id, community_id)
);

create table if not exists public.declarations (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete cascade,
  community_id uuid not null references public.communities(id) on delete cascade,
  title text not null,
  description text not null default '',
  cc_spent integer not null check (cc_spent >= 1 and cc_spent <= 20),
  image_url text,
  created_at timestamptz not null default now()
);
create index if not exists idx_declarations_community on public.declarations(community_id, created_at desc);

create table if not exists public.witnesses (
  user_id uuid not null references public.users(id) on delete cascade,
  declaration_id uuid not null references public.declarations(id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key (user_id, declaration_id)
);
create index if not exists idx_witnesses_declaration on public.witnesses(declaration_id);

create table if not exists public.chat_messages (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete cascade,
  community_id uuid not null references public.communities(id) on delete cascade,
  content text,
  type text not null check (type in ('message', 'declaration', 'borrow_request', 'tip_to_tip', 'system')),
  reference_id uuid,
  created_at timestamptz not null default now()
);
create index if not exists idx_chat_messages_community on public.chat_messages(community_id, created_at);

create table if not exists public.borrow_requests (
  id uuid primary key default gen_random_uuid(),
  borrower_id uuid not null references public.users(id) on delete cascade,
  lender_id uuid not null references public.users(id) on delete cascade,
  community_id uuid not null references public.communities(id) on delete cascade,
  amount integer not null check (amount >= 1),
  reason text not null,
  status text not null default 'pending' check (status in ('pending', 'approved', 'declined')),
  created_at timestamptz not null default now()
);
create index if not exists idx_borrow_requests_community on public.borrow_requests(community_id);

create table if not exists public.tip_to_tip_proposals (
  id uuid primary key default gen_random_uuid(),
  proposer_id uuid not null references public.users(id) on delete cascade,
  community_id uuid not null references public.communities(id) on delete cascade,
  title text not null,
  description text not null default '',
  stake_amount integer not null check (stake_amount >= 50),
  deadline timestamptz not null,
  status text not null default 'pending' check (status in ('pending', 'active', 'completed', 'expired')),
  created_at timestamptz not null default now()
);
create index if not exists idx_tip_to_tip_community on public.tip_to_tip_proposals(community_id);
create index if not exists idx_tip_to_tip_status on public.tip_to_tip_proposals(status) where status in ('pending', 'active');

create table if not exists public.tip_to_tip_votes (
  proposal_id uuid not null references public.tip_to_tip_proposals(id) on delete cascade,
  user_id uuid not null references public.users(id) on delete cascade,
  vote text not null check (vote in ('accept', 'decline')),
  created_at timestamptz not null default now(),
  primary key (proposal_id, user_id)
);

create table if not exists public.ledger_entries (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete cascade,
  community_id uuid not null references public.communities(id) on delete cascade,
  type text not null check (type in ('declaration', 'borrow_given', 'borrow_received', 'tip_to_tip', 'daily_reset', 'expired')),
  amount integer not null,
  description text not null,
  reference_id uuid,
  created_at timestamptz not null default now()
);
create index if not exists idx_ledger_user_community on public.ledger_entries(user_id, community_id, created_at desc);

create table if not exists public.notifications (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete cascade,
  community_id uuid not null references public.communities(id) on delete cascade,
  type text not null check (type in ('witnessed', 'borrow_request', 'borrow_approved', 'borrow_declined', 'tip_to_tip', 'jashn_e_chas', 'election', 'system')),
  title text not null,
  body text not null,
  read boolean not null default false,
  created_at timestamptz not null default now()
);
create index if not exists idx_notifications_user on public.notifications(user_id, read, created_at desc);

create table if not exists public.elections (
  id uuid primary key default gen_random_uuid(),
  community_id uuid not null references public.communities(id) on delete cascade,
  title text not null,
  status text not null default 'active' check (status in ('active', 'completed')),
  winner_id uuid references public.users(id),
  created_at timestamptz not null default now(),
  ends_at timestamptz not null
);
create index if not exists idx_elections_community on public.elections(community_id);

create table if not exists public.election_votes (
  election_id uuid not null references public.elections(id) on delete cascade,
  voter_id uuid not null references public.users(id) on delete cascade,
  candidate_id uuid not null references public.users(id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key (election_id, voter_id)
);

create table if not exists public.sunset_entries (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete cascade,
  community_id uuid not null references public.communities(id) on delete cascade,
  unspent_cc integer not null,
  date date not null,
  created_at timestamptz not null default now(),
  unique (user_id, community_id, date)
);

create table if not exists public.jashn_e_chas (
  id uuid primary key default gen_random_uuid(),
  community_id uuid not null references public.communities(id) on delete cascade,
  week_start date not null,
  week_end date not null,
  honored_user_id uuid references public.users(id),
  total_declarations integer not null default 0,
  total_cc_spent integer not null default 0,
  created_at timestamptz not null default now(),
  unique (community_id, week_start)
);

create table if not exists public.jashn_celebrations (
  jashn_id uuid not null references public.jashn_e_chas(id) on delete cascade,
  user_id uuid not null references public.users(id) on delete cascade,
  message text not null,
  created_at timestamptz not null default now(),
  primary key (jashn_id, user_id)
);

-- RLS
alter table public.users enable row level security;
alter table public.communities enable row level security;
alter table public.community_members enable row level security;
alter table public.cc_balances enable row level security;
alter table public.declarations enable row level security;
alter table public.witnesses enable row level security;
alter table public.chat_messages enable row level security;
alter table public.borrow_requests enable row level security;
alter table public.tip_to_tip_proposals enable row level security;
alter table public.tip_to_tip_votes enable row level security;
alter table public.ledger_entries enable row level security;
alter table public.notifications enable row level security;
alter table public.elections enable row level security;
alter table public.election_votes enable row level security;
alter table public.sunset_entries enable row level security;
alter table public.jashn_e_chas enable row level security;
alter table public.jashn_celebrations enable row level security;

create or replace function public.is_community_member(cid uuid)
returns boolean as $$
  select exists (
    select 1 from public.community_members
    where user_id = auth.uid() and community_id = cid
  );
$$ language sql security definer stable;

create policy "read_users" on public.users for select using (true);
create policy "update_own_user" on public.users for update using (auth.uid() = id);

create policy "read_own_communities" on public.communities for select using (public.is_community_member(id));
create policy "create_community" on public.communities for insert with check (auth.uid() = created_by);

create policy "read_community_members" on public.community_members for select using (public.is_community_member(community_id));
create policy "join_community" on public.community_members for insert with check (auth.uid() = user_id);

create policy "read_own_balance" on public.cc_balances for select using (auth.uid() = user_id);

create policy "read_community_declarations" on public.declarations for select using (public.is_community_member(community_id));
create policy "create_declaration" on public.declarations for insert with check (auth.uid() = user_id and public.is_community_member(community_id));

create policy "read_witnesses" on public.witnesses for select using (true);
create policy "create_witness" on public.witnesses for insert with check (auth.uid() = user_id);

create policy "read_chat" on public.chat_messages for select using (public.is_community_member(community_id));
create policy "send_chat" on public.chat_messages for insert with check (auth.uid() = user_id and public.is_community_member(community_id));

create policy "read_borrows" on public.borrow_requests for select using (public.is_community_member(community_id));
create policy "create_borrow" on public.borrow_requests for insert with check (auth.uid() = borrower_id and public.is_community_member(community_id));
create policy "respond_borrow" on public.borrow_requests for update using (auth.uid() = lender_id);

create policy "read_tip_to_tip" on public.tip_to_tip_proposals for select using (public.is_community_member(community_id));
create policy "create_tip_to_tip" on public.tip_to_tip_proposals for insert with check (auth.uid() = proposer_id and public.is_community_member(community_id));

create policy "read_votes" on public.tip_to_tip_votes for select using (true);
create policy "cast_vote" on public.tip_to_tip_votes for insert with check (auth.uid() = user_id);

create policy "read_own_ledger" on public.ledger_entries for select using (auth.uid() = user_id);

create policy "read_own_notifications" on public.notifications for select using (auth.uid() = user_id);
create policy "update_own_notifications" on public.notifications for update using (auth.uid() = user_id);

create policy "read_elections" on public.elections for select using (public.is_community_member(community_id));

create policy "read_election_votes" on public.election_votes for select using (true);
create policy "cast_election_vote" on public.election_votes for insert with check (auth.uid() = voter_id);

create policy "read_sunset" on public.sunset_entries for select using (public.is_community_member(community_id));

create policy "read_jashn" on public.jashn_e_chas for select using (public.is_community_member(community_id));

create policy "read_celebrations" on public.jashn_celebrations for select using (true);
create policy "add_celebration" on public.jashn_celebrations for insert with check (auth.uid() = user_id);
