import { describe, it, expect, beforeEach, vi } from 'vitest';
import { get } from 'svelte/store';
import { render, screen, fireEvent, waitFor } from '@testing-library/svelte';

const navigate = vi.fn();
vi.mock('svelte-routing', () => ({ navigate: (...args) => navigate(...args) }));

import { planLimitNotice, showPlanLimit, dismissPlanLimit, describeLimit } from './planLimit.js';
import { PlanLimitError } from './api.js';
import PlanLimitModal from './PlanLimitModal.svelte';

const boardsLimit = () =>
  new PlanLimitError({
    error: 'plan_limit', limit: 'boards', max: 5, current: 5,
    detail: 'The free plan allows 5 boards and you own 5.',
  });

beforeEach(() => {
  dismissPlanLimit();
  navigate.mockClear();
});

describe('showPlanLimit', () => {
  it('shows a plan-limit error and tells the caller it did', () => {
    const e = boardsLimit();
    expect(showPlanLimit(e)).toBe(true);
    expect(get(planLimitNotice)).toBe(e);
  });

  it('leaves every other error for the caller to alert', () => {
    expect(showPlanLimit(new Error('Board not found'))).toBe(false);
    expect(showPlanLimit(null)).toBe(false);
    expect(showPlanLimit(undefined)).toBe(false);
    expect(get(planLimitNotice)).toBeNull();
  });

  it('recognises a plan limit by its code, not its class', () => {
    // api.js can be loaded twice (tests reset modules); instanceof would miss.
    expect(showPlanLimit({ code: 'plan_limit', message: 'full', limit: 'boards' })).toBe(true);
  });
});

describe('describeLimit', () => {
  it('names what ran out', () => {
    expect(describeLimit('boards')).toMatch(/board/i);
    expect(describeLimit('cards_per_board')).toMatch(/card/i);
    expect(describeLimit('something-new')).toBe('Plan limit reached');
  });
});

describe('PlanLimitModal', () => {
  it('renders nothing until there is a limit to report', () => {
    render(PlanLimitModal);
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('shows the server sentence under a heading naming the limit', async () => {
    render(PlanLimitModal);
    showPlanLimit(boardsLimit());

    expect(await screen.findByRole('dialog', { name: /board limit reached/i })).toBeInTheDocument();
    expect(screen.getByText('The free plan allows 5 boards and you own 5.')).toBeInTheDocument();
  });

  it('takes the user to their plan and closes', async () => {
    render(PlanLimitModal);
    showPlanLimit(boardsLimit());

    await fireEvent.click(await screen.findByRole('button', { name: /see your plan/i }));

    expect(navigate).toHaveBeenCalledWith('/settings/plan');
    expect(get(planLimitNotice)).toBeNull();
  });

  it('closes without navigating', async () => {
    render(PlanLimitModal);
    showPlanLimit(boardsLimit());

    await fireEvent.click(await screen.findByRole('button', { name: /^close$/i }));

    await waitFor(() => expect(get(planLimitNotice)).toBeNull());
    expect(navigate).not.toHaveBeenCalled();
  });
});
