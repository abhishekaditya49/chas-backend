-- Reset one invite code so it can be reused.
-- Run in Supabase SQL editor after replacing values below.
--
-- Options:
-- - v_clear_assigned_email: clears assigned_email on the invite code.
-- - v_revoke_redeemer_access: un-whitelists the user that redeemed this code.

do $$
declare
  v_code text := upper(trim('REPLACECODE'));
  v_clear_assigned_email boolean := false;
  v_revoke_redeemer_access boolean := false;
  v_invite_id uuid;
  v_redeemed_user_id uuid;
begin
  if v_code = '' or v_code = 'REPLACECODE' then
    raise exception 'Please replace v_code with a real invite code before running this script.';
  end if;

  select id, redeemed_by_user_id
  into v_invite_id, v_redeemed_user_id
  from public.invite_codes
  where code = v_code
  limit 1;

  if v_invite_id is null then
    raise exception 'Invite code not found: %', v_code;
  end if;

  if v_revoke_redeemer_access and v_redeemed_user_id is not null then
    update public.users
    set
      is_whitelisted = false,
      invite_code_id = null,
      whitelisted_at = null
    where id = v_redeemed_user_id;
  end if;

  update public.invite_codes
  set
    status = 'active',
    redeemed_by_user_id = null,
    redeemed_by_email = null,
    redeemed_at = null,
    assigned_email = case
      when v_clear_assigned_email then null
      else assigned_email
    end
  where id = v_invite_id;
end
$$;
