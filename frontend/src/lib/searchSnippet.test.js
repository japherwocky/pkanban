import { describe, it, expect } from 'vitest';
import { highlightSegments } from './searchSnippet.js';

describe('highlightSegments', () => {
  it('splits a snippet into plain and matched runs', () => {
    expect(highlightSegments('cards still \x02count\x03 toward the \x02limit\x03.')).toEqual([
      { text: 'cards still ', match: false },
      { text: 'count', match: true },
      { text: ' toward the ', match: false },
      { text: 'limit', match: true },
      { text: '.', match: false },
    ]);
  });

  it('returns nothing for a card without a description', () => {
    expect(highlightSegments(null)).toEqual([]);
    expect(highlightSegments('')).toEqual([]);
  });

  it('leaves text without markers alone', () => {
    expect(highlightSegments('<b>not markup</b>')).toEqual([
      { text: '<b>not markup</b>', match: false },
    ]);
  });

  it('survives markers that do not pair up', () => {
    expect(highlightSegments('a \x02b')).toEqual([
      { text: 'a ', match: false },
      { text: 'b', match: true },
    ]);
    expect(highlightSegments('a\x03 b')).toEqual([{ text: 'a b', match: false }]);
  });
});
