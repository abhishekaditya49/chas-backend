-- Remove fixed minimum stake and enforce one active tip-to-tip per proposer/community.

alter table public.tip_to_tip_proposals
drop constraint if exists tip_to_tip_proposals_stake_amount_check;

alter table public.tip_to_tip_proposals
add constraint tip_to_tip_proposals_stake_amount_check
check (stake_amount >= 1);

with ranked_active as (
  select
    id,
    row_number() over (
      partition by community_id, proposer_id
      order by created_at desc, id desc
    ) as rn
  from public.tip_to_tip_proposals
  where status = 'active'
)
update public.tip_to_tip_proposals p
set status = 'expired'
from ranked_active r
where p.id = r.id
  and r.rn > 1;

create unique index if not exists idx_tip_to_tip_one_active_per_proposer
  on public.tip_to_tip_proposals (community_id, proposer_id)
  where status = 'active';
