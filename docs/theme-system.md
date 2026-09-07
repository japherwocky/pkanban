# Theme System

pkanban uses a comprehensive theming system built on Tailwind CSS v4 with CSS custom properties, supporting light/dark mode and a consistent 5-color brand palette.

## Architecture

### Files

| File | Purpose |
|------|---------|
| `frontend/src/theme.css` | CSS custom properties definition, Tailwind @theme integration |
| `frontend/src/lib/theme.js` | Theme state management (Svelte store) |
| `frontend/src/lib/ThemeToggle.svelte` | Theme toggle UI component |

## Color Palette

The theme uses 5 brand colors with semantic foreground (text) colors:

| Role | Light Mode | Dark Mode | Usage |
|------|-----------|-----------|-------|
| **Primary** | `#2563eb` (blue) | `#3b82f6` | Main actions, buttons, links |
| **Secondary** | `#64748b` (slate) | `#94a3b8` | Secondary text, borders |
| **Accent** | `#8b5cf6` (violet) | `#a78bfa` | Highlights, badges |
| **Success** | `#22c55e` (green) | `#4ade80` | Success states |
| **Error** | `#ef4444` (red) | `#f87171` | Error states, destructive actions |

### Semantic Colors

| Variable | Light | Dark | Usage |
|----------|-------|------|-------|
| `--color-background` | `#ffffff` | `#0f172a` | Page background |
| `--color-foreground` | `#0f172a` | `#f8fafc` | Primary text |
| `--color-muted` | `#f1f5f9` | `#1e293b` | Secondary backgrounds |
| `--color-muted-foreground` | `#64748b` | `#94a3b8` | Secondary text |
| `--color-border` | `#e2e8f0` | `#334155` | Borders |
| `--color-card` | `#ffffff` | `#1e293b` | Card backgrounds |
| `--color-card-foreground` | `#0f172a` | `#f8fafc` | Card text |

## Font

- **Font Family**: Inter (Google Fonts), fallback to system-ui
- Defined in `theme.css` as `--font-sans`

## Usage

### Using Theme Colors in Components

```svelte
<script>
  // Colors are available as CSS variables
</script>

<button class="bg-primary text-primary-foreground px-4 py-2 rounded">
  Primary Button
</button>

<div class="bg-muted text-muted-foreground p-4">
  Muted content
</div>

<div class="border border-border">
  With border
</div>
```

### Programmatic Theme Control

```javascript
import { theme } from '../lib/theme.js';

// Get current theme
let currentTheme;
theme.subscribe(t => currentTheme = t);

// Set specific theme
theme.setTheme('light');
theme.setTheme('dark');
theme.setTheme('system');

// Cycle through themes (light -> dark -> system -> light)
theme.cycleTheme();

// Initialize theme system (call once in root component)
theme.init();
```

### Theme Toggle Component

```svelte
<script>
  import ThemeToggle from '$lib/ThemeToggle.svelte';
</script>

<header>
  <h1>My App</h1>
  <ThemeToggle />
</header>
```

## Tailwind v4 Integration

The theme system uses Tailwind v4's `@theme` directive to map CSS variables to Tailwind utilities:

```css
@theme {
  --color-primary: var(--color-primary);
  --color-primary-foreground: var(--color-primary-foreground);
  /* ... other colors */
}

@variant dark (&:where(.dark, .dark *));
```

This allows using classes like `bg-primary`, `text-error`, `border-secondary` throughout the application.

## Dark Mode Implementation

Dark mode is implemented via the `.dark` class on `document.documentElement`:

```css
.dark {
  --color-primary: #3b82f6;
  --color-background: #0f172a;
  /* ... */
}
```

The theme store automatically:
1. Reads saved preference from localStorage
2. Detects system preference via `prefers-color-scheme`
3. Applies/removes the `.dark` class accordingly
4. Listens for system preference changes when in "system" mode

## Adding New Theme Colors

1. Add the color variable to both `:root` and `.dark` in `theme.css`:

```css
:root {
  --color-new-color: #123456;
}

.dark {
  --color-new-color: #654321;
}
```

2. Map it in the `@theme` block:

```css
@theme {
  --color-new-color: var(--color-new-color);
}
```

3. Use in components: `bg-new-color text-new-color-foreground`

## Best Practices

1. Always use semantic color names (primary, secondary, success, etc.) instead of hardcoded colors
2. Pair colors with their foreground variants (e.g., `bg-primary` with `text-primary-foreground`)
3. Use `text-muted-foreground` for secondary text, not hardcoded grays
4. Use `border-border` for all borders to maintain consistency
5. Use `bg-card` and `bg-muted` for component backgrounds
