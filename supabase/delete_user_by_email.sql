-- Delete one user and their related data by email.
-- Run in Supabase SQL editor after replacing the values below.
--
-- IMPORTANT:
-- - If `v_delete_owned_communities` is true, communities created by this user
--   are deleted as well (and dependent community data cascades).
-- - If false, script will fail when the user owns communities because
--   communities.created_by is required.

do $$
declare
  v_email text := lower(trim('replace-with-user-email@example.com'));
  v_user_id uuid;
  v_delete_owned_communities boolean := true;
begin
  if v_email = '' or v_email like 'replace-with-user-email%' then
    raise exception 'Please replace v_email with a real email before running this script.';
  end if;

  select id
  into v_user_id
  from auth.users
  where lower(email) = v_email
  limit 1;

  if v_user_id is null then
    raise exception 'No auth user found for email: %', v_email;
  end if;

  if v_delete_owned_communities then
    delete from public.communities
    where created_by = v_user_id;
  else
    if exists (select 1 from public.communities where created_by = v_user_id) then
      raise exception
        'User % owns one or more communities. Set v_delete_owned_communities=true or reassign ownership first.',
        v_email;
    end if;
  end if;

  -- If this user redeemed an invite, recycle that code.
  update public.invite_codes
  set
    status = 'active',
    redeemed_by_user_id = null,
    redeemed_by_email = null,
    redeemed_at = null,
    assigned_email = case
      when lower(coalesce(assigned_email, '')) = v_email then null
      else assigned_email
    end
  where redeemed_by_user_id = v_user_id;

  -- Deleting from auth.users cascades to public.users via FK.
  delete from auth.users
  where id = v_user_id;
end
$$;
