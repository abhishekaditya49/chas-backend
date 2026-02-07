-- WARNING: Destructive operation.
-- This clears CHAS application data and all Supabase auth users.
-- Run from Supabase SQL Editor only when you want a full reset.

do $$
declare
  table_name text;
begin
  foreach table_name in array array[
    'jashn_celebrations',
    'jashn_e_chas',
    'sunset_entries',
    'election_votes',
    'elections',
    'notifications',
    'ledger_entries',
    'tip_to_tip_votes',
    'tip_to_tip_proposals',
    'borrow_requests',
    'chat_messages',
    'witnesses',
    'declarations',
    'cc_balances',
    'community_members',
    'communities',
    'invite_codes',
    'users'
  ]
  loop
    if to_regclass(format('public.%I', table_name)) is not null then
      execute format('truncate table public.%I restart identity cascade', table_name);
    end if;
  end loop;
end
$$;

-- Remove auth users so you can sign up fresh again.
delete from auth.users;
