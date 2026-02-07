-- Atomic CC transfer for borrow approvals + realtime publication wiring.

create or replace function public.transfer_cc_for_borrow(
  p_lender_id uuid,
  p_borrower_id uuid,
  p_community_id uuid,
  p_amount integer
)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
  if p_amount < 1 then
    raise exception 'INVALID_AMOUNT';
  end if;

  update public.cc_balances
  set
    remaining = remaining - p_amount,
    spent_today = spent_today + p_amount
  where
    user_id = p_lender_id
    and community_id = p_community_id
    and remaining >= p_amount;

  if not found then
    raise exception 'INSUFFICIENT_CC';
  end if;

  update public.cc_balances
  set
    remaining = remaining + p_amount,
    debt = debt + p_amount
  where
    user_id = p_borrower_id
    and community_id = p_community_id;

  if not found then
    raise exception 'BORROWER_BALANCE_NOT_FOUND';
  end if;
end;
$$;

do $$
declare
  realtime_pub_oid oid;
begin
  select oid into realtime_pub_oid
  from pg_publication
  where pubname = 'supabase_realtime';

  if realtime_pub_oid is null then
    return;
  end if;

  if not exists (
    select 1
    from pg_publication_rel pr
    join pg_class c on c.oid = pr.prrelid
    join pg_namespace n on n.oid = c.relnamespace
    where pr.prpubid = realtime_pub_oid
      and n.nspname = 'public'
      and c.relname = 'chat_messages'
  ) then
    alter publication supabase_realtime add table public.chat_messages;
  end if;

  if not exists (
    select 1
    from pg_publication_rel pr
    join pg_class c on c.oid = pr.prrelid
    join pg_namespace n on n.oid = c.relnamespace
    where pr.prpubid = realtime_pub_oid
      and n.nspname = 'public'
      and c.relname = 'cc_balances'
  ) then
    alter publication supabase_realtime add table public.cc_balances;
  end if;

  if not exists (
    select 1
    from pg_publication_rel pr
    join pg_class c on c.oid = pr.prrelid
    join pg_namespace n on n.oid = c.relnamespace
    where pr.prpubid = realtime_pub_oid
      and n.nspname = 'public'
      and c.relname = 'notifications'
  ) then
    alter publication supabase_realtime add table public.notifications;
  end if;

  if not exists (
    select 1
    from pg_publication_rel pr
    join pg_class c on c.oid = pr.prrelid
    join pg_namespace n on n.oid = c.relnamespace
    where pr.prpubid = realtime_pub_oid
      and n.nspname = 'public'
      and c.relname = 'borrow_requests'
  ) then
    alter publication supabase_realtime add table public.borrow_requests;
  end if;

  if not exists (
    select 1
    from pg_publication_rel pr
    join pg_class c on c.oid = pr.prrelid
    join pg_namespace n on n.oid = c.relnamespace
    where pr.prpubid = realtime_pub_oid
      and n.nspname = 'public'
      and c.relname = 'tip_to_tip_votes'
  ) then
    alter publication supabase_realtime add table public.tip_to_tip_votes;
  end if;

  if not exists (
    select 1
    from pg_publication_rel pr
    join pg_class c on c.oid = pr.prrelid
    join pg_namespace n on n.oid = c.relnamespace
    where pr.prpubid = realtime_pub_oid
      and n.nspname = 'public'
      and c.relname = 'election_votes'
  ) then
    alter publication supabase_realtime add table public.election_votes;
  end if;
end;
$$;
