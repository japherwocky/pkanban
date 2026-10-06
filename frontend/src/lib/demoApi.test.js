import { describe, it, expect, beforeEach } from 'vitest';
import { executeCommand, getDemoState, resetDemo } from './demoApi.js';

beforeEach(() => resetDemo());

const column = (state, id) => state.board.columns.find((c) => c.id === id);

describe('demoApi', () => {
  it('creates a card in the named column, and the state shows it', () => {
    const result = executeCommand('pkanban card create 2 Write the tests');
    expect(result.exitCode).toBe(0);
    expect(column(getDemoState(), 2).cards.map((c) => c.title)).toEqual(['Write the tests']);
  });

  it('refuses a card with no title or an unknown column, and changes nothing', () => {
    expect(executeCommand('pkanban card create 2').exitCode).toBe(1);
    expect(executeCommand('pkanban card create 99 Nowhere').exitCode).toBe(1);
    expect(getDemoState().board.columns.flatMap((c) => c.cards)).toHaveLength(3);
  });

  it('reset returns the board to its starting cards', () => {
    executeCommand('pkanban card create 1 Extra');
    executeCommand('reset');
    expect(column(getDemoState(), 1).cards).toHaveLength(1);
  });

  it('getDemoState hands out a copy, not the live state', () => {
    getDemoState().board.columns[0].cards.length = 0;
    expect(column(getDemoState(), 1).cards).toHaveLength(1);
  });

  it('fails an unknown command with exit code 1 and a message on stderr', () => {
    const result = executeCommand('frobnicate');
    expect(result.exitCode).toBe(1);
    expect(result.stderr).toContain('frobnicate');
  });
});
