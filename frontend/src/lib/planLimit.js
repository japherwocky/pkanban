import { writable } from 'svelte/store';

// The plan-limit error the user should currently be told about, or null.
// PlanLimitModal, mounted once in App.svelte, renders it: the two places that
// can hit a limit (creating a board, creating a card) are far apart, and an
// alert() cannot carry an upgrade link.
export const planLimitNotice = writable(null);

// Call from a catch block. Returns true when `e` was a plan limit and has been
// shown, so the caller can skip its generic "Failed to ..." alert.
export function showPlanLimit(e) {
  if (e?.code !== 'plan_limit') return false;
  planLimitNotice.set(e);
  return true;
}

export function dismissPlanLimit() {
  planLimitNotice.set(null);
}

// What the limit was on, in words, for the modal's heading.
export function describeLimit(limit) {
  if (limit === 'boards') return 'Board limit reached';
  if (limit === 'cards_per_board') return 'Card limit reached';
  return 'Plan limit reached';
}
