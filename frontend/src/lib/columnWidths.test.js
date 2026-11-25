import { describe, it, expect, vi, afterEach } from 'vitest';
import {
  clampColumnWidth,
  COLUMN_WIDTHS_KEY,
  DEFAULT_COLUMN_WIDTH,
  loadColumnWidths,
  MAX_COLUMN_WIDTH,
  MIN_COLUMN_WIDTH,
  saveColumnWidth,
} from './columnWidths.js';

const stored = () => JSON.parse(localStorage.getItem(COLUMN_WIDTHS_KEY));

afterEach(() => vi.restoreAllMocks());

describe('column widths', () => {
  it('clamps to the limits and rounds', () => {
    expect(clampColumnWidth(10)).toBe(MIN_COLUMN_WIDTH);
    expect(clampColumnWidth(5000)).toBe(MAX_COLUMN_WIDTH);
    expect(clampColumnWidth(333.6)).toBe(334);
  });

  it('saves and loads a width per column', () => {
    saveColumnWidth(10, 420);
    saveColumnWidth(20, 260);
    expect(loadColumnWidths()).toEqual({ 10: 420, 20: 260 });
  });

  it('stores the default as no entry at all', () => {
    saveColumnWidth(10, 420);
    saveColumnWidth(10, DEFAULT_COLUMN_WIDTH);
    expect(stored()).toEqual({});
  });

  it('forgets a deleted column', () => {
    saveColumnWidth(10, 420);
    saveColumnWidth(20, 500);
    saveColumnWidth(10, null);
    expect(stored()).toEqual({ 20: 500 });
  });

  it('starts empty from nothing, or from junk', () => {
    expect(loadColumnWidths()).toEqual({});
    for (const junk of ['not json', '[400]', '"wide"', 'null', '42']) {
      localStorage.setItem(COLUMN_WIDTHS_KEY, junk);
      expect(loadColumnWidths()).toEqual({});
    }
  });

  it('keeps only numeric ids with finite widths, inside the limits', () => {
    // A string, not JSON.stringify: in an object literal __proto__ sets the
    // prototype instead of making a key.
    localStorage.setItem(
      COLUMN_WIDTHS_KEY,
      '{"10": 9999, "20": 5, "30": "400", "40": null, "abc": 400, "__proto__": 400, "50": 450}',
    );
    expect(loadColumnWidths()).toEqual({ 10: MAX_COLUMN_WIDTH, 20: MIN_COLUMN_WIDTH, 50: 450 });
  });

  it('survives storage that refuses to write', () => {
    vi.spyOn(localStorage, 'setItem').mockImplementation(() => {
      throw new Error('QuotaExceededError');
    });
    expect(() => saveColumnWidth(10, 400)).not.toThrow();
  });
});
