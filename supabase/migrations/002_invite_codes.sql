-- Invite code redemption + whitelist access control

alter table public.users
  add column if not exists is_whitelisted boolean not null default false,
  add column if not exists invite_code_id uuid,
  add column if not exists whitelisted_at timestamptz;

create table if not exists public.invite_codes (
  id uuid primary key default gen_random_uuid(),
  code text not null unique check (code = upper(code)),
  assigned_email text,
  status text not null default 'active' check (status in ('active', 'expired', 'revoked')),
  redeemed_by_user_id uuid references public.users(id) on delete set null,
  redeemed_by_email text,
  redeemed_at timestamptz,
  expires_at timestamptz,
  welcome_title text not null default 'Welcome to Chas',
  welcome_message text not null default 'Your invite has been redeemed. Step into the chamber and declare your first joy.',
  theme text not null default 'dawn' check (theme in ('dawn', 'sunset', 'mint', 'ink')),
  notes text not null default '',
  created_by uuid references public.users(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conname = 'users_invite_code_id_fkey'
  ) then
    alter table public.users
      add constraint users_invite_code_id_fkey
      foreign key (invite_code_id) references public.invite_codes(id)
      on delete set null;
  end if;
end $$;

create index if not exists idx_invite_codes_status on public.invite_codes(status);
create index if not exists idx_invite_codes_assigned_email on public.invite_codes(assigned_email);

create or replace function public.touch_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

drop trigger if exists invite_codes_touch_updated_at on public.invite_codes;
create trigger invite_codes_touch_updated_at
  before update on public.invite_codes
  for each row execute function public.touch_updated_at();

create or replace function public.redeem_invite_code(
  p_user_id uuid,
  p_email text,
  p_code text
)
returns table(
  success boolean,
  reason text,
  invite_code_id uuid,
  invite_code text,
  theme text,
  welcome_title text,
  welcome_message text
)
language plpgsql
security definer
set search_path = public
as $$
declare
  v_user public.users%rowtype;
  v_invite public.invite_codes%rowtype;
  v_code text := upper(trim(coalesce(p_code, '')));
  v_email text := lower(trim(coalesce(p_email, '')));
begin
  if v_code = '' then
    return query
      select false, 'invalid_code', null::uuid, null::text, null::text, null::text, null::text;
    return;
  end if;

  select *
  into v_user
  from public.users
  where id = p_user_id
  for update;

  if not found then
    return query
      select false, 'user_not_found', null::uuid, null::text, null::text, null::text, null::text;
    return;
  end if;

  if v_user.is_whitelisted then
    return query
      select true, 'already_whitelisted', v_user.invite_code_id, null::text, null::text, null::text, null::text;
    return;
  end if;

  select *
  into v_invite
  from public.invite_codes
  where code = v_code
  for update;

  if not found then
    return query
      select false, 'invite_not_found', null::uuid, null::text, null::text, null::text, null::text;
    return;
  end if;

  if v_invite.status <> 'active' then
    return query
      select false, 'invite_not_active', v_invite.id, v_invite.code, v_invite.theme, v_invite.welcome_title, v_invite.welcome_message;
    return;
  end if;

  if v_invite.expires_at is not null and v_invite.expires_at <= now() then
    update public.invite_codes
    set status = 'expired'
    where id = v_invite.id;

    return query
      select false, 'invite_expired', v_invite.id, v_invite.code, v_invite.theme, v_invite.welcome_title, v_invite.welcome_message;
    return;
  end if;

  if v_invite.assigned_email is not null and lower(trim(v_invite.assigned_email)) <> v_email then
    return query
      select false, 'invite_email_mismatch', v_invite.id, v_invite.code, v_invite.theme, v_invite.welcome_title, v_invite.welcome_message;
    return;
  end if;

  update public.invite_codes
  set
    assigned_email = coalesce(v_invite.assigned_email, v_email),
    status = 'expired',
    redeemed_by_user_id = p_user_id,
    redeemed_by_email = v_email,
    redeemed_at = now()
  where id = v_invite.id;

  update public.users
  set
    is_whitelisted = true,
    invite_code_id = v_invite.id,
    whitelisted_at = now()
  where id = p_user_id;

  return query
    select true, 'redeemed', v_invite.id, v_invite.code, v_invite.theme, v_invite.welcome_title, v_invite.welcome_message;
end;
$$;

alter table public.invite_codes enable row level security;

revoke all on function public.redeem_invite_code(uuid, text, text) from public;
grant execute on function public.redeem_invite_code(uuid, text, text) to service_role;
