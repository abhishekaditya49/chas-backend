-- Ensure tip-to-tip proposal status updates are emitted via Supabase Realtime.

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
      and c.relname = 'tip_to_tip_proposals'
  ) then
    alter publication supabase_realtime add table public.tip_to_tip_proposals;
  end if;
end;
$$;
