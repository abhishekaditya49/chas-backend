-- Remove fixed upper cap on declaration spend; spend is bounded by user's remaining CC.

alter table public.declarations
drop constraint if exists declarations_cc_spent_check;

alter table public.declarations
add constraint declarations_cc_spent_check
check (cc_spent >= 1);
