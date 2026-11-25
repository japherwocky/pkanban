// How wide each column on a board is drawn. A width is a view preference --
// the person looking, on this device -- so it lives in localStorage and never
// reaches the server: one person widening a column does not rearrange the
// board for everyone it is shared with, and a read-only viewer can resize too.
//
// One map for every board, keyed by column id, which is unique across boards.

export const DEFAULT_COLUMN_WIDTH = 300;
export const MIN_COLUMN_WIDTH = 200;
export const MAX_COLUMN_WIDTH = 800;
export const COLUMN_WIDTH_STEP = 20;
export const COLUMN_WIDTHS_KEY = 'pkanban.columnWidths';

export function clampColumnWidth(width) {
  return Math.round(Math.min(MAX_COLUMN_WIDTH, Math.max(MIN_COLUMN_WIDTH, width)));
}

// Anything on this origin can write localStorage, so only numeric column ids
// with finite widths come back, and those inside the limits.
export function loadColumnWidths() {
  let stored;
  try {
    stored = JSON.parse(localStorage.getItem(COLUMN_WIDTHS_KEY));
  } catch {
    return {};
  }
  if (!stored || typeof stored !== 'object' || Array.isArray(stored)) return {};
  const widths = {};
  for (const [id, width] of Object.entries(stored)) {
    if (/^\d+$/.test(id) && typeof width === 'number' && Number.isFinite(width)) {
      widths[id] = clampColumnWidth(width);
    }
  }
  return widths;
}

// The default width is stored as no entry, so a column put back to it leaves
// nothing behind. Pass null for a deleted column.
export function saveColumnWidth(columnId, width) {
  const widths = loadColumnWidths();
  if (width == null || clampColumnWidth(width) === DEFAULT_COLUMN_WIDTH) {
    delete widths[columnId];
  } else {
    widths[columnId] = clampColumnWidth(width);
  }
  try {
    localStorage.setItem(COLUMN_WIDTHS_KEY, JSON.stringify(widths));
  } catch {
    // Storage full or blocked: the width holds until the page reloads.
  }
}
