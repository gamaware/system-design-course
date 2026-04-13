# Shared Presentation Assets

Shared CSS theme, JavaScript engine, and icon assets for all module slide decks.
Every module presentation references these files via relative paths, so no build
step or development server is required. Presentations work on `file://`.

## Files

| File | Purpose |
| --- | --- |
| `theme.css` | Design tokens, reveal.js overrides, component styles, animations, print styles |
| `presenter.js` | Particle canvas, theme/lang toggle, counters, animations, Reveal.js init |
| `assets/aws-icons/` | Official AWS Architecture Icons (48px SVG) organized by service category |
| `assets/db-logos/` | Database engine logos (96px PNG) from icons8.com |

## CSS Classes

### Layout

| Class | Description |
| --- | --- |
| `.grid-2` | Two-column grid with 10px gap |
| `.grid-3` | Three-column grid with 10px gap |
| `.grid-4` | Two-column grid (intended for 4 items in 2x2) with 10px gap |
| `.grid-6` | Three-column grid (intended for 6 items in 3x2) with 10px gap |
| `.side-by-side` | Two-column grid with 14px gap for side-by-side comparisons |

### Cards

| Class | Description |
| --- | --- |
| `.card` | Rounded surface container with border and padding |
| `.stat-card` | Centered card for numeric statistics |
| `.stat-num` | Large primary-colored number inside a stat-card |
| `.stat-label` | Small muted label below the stat number |
| `.expandable` | Card that expands/collapses on click (add to `.card`) |
| `.expand-content` | Hidden content inside an expandable card |

### Badges

| Class | Description |
| --- | --- |
| `.badge` | Base inline badge with rounded corners |
| `.badge-blue` | Blue badge (primary) |
| `.badge-green` | Green badge (mint/success) |
| `.badge-orange` | Orange badge (warning) |
| `.badge-red` | Red badge (error) |
| `.badge-purple` | Purple badge |

### Colored Borders

| Class | Description |
| --- | --- |
| `.border-green` | 4px left border in mint/success color |
| `.border-blue` | 4px left border in primary color |
| `.border-red` | 4px left border in error color |
| `.border-orange` | 4px left border in warning color |
| `.border-purple` | 4px left border in purple color |
| `.border-gold` | 4px left border in gold color |

### Animations

| Class | Description |
| --- | --- |
| `.float-in` | Element fades in and floats up on slide entry (staggered by index) |
| `.slide-in` | Element fades in and slides from left on slide entry (staggered by index) |

### Utilities

| Class | Description |
| --- | --- |
| `.subtitle` | Muted smaller text for subtitles |
| `.aws-icon` | Inline-block with right margin for AWS icon alignment |
| `.qa-center` | Flexbox centering for Q&A slides |
| `.iteso-footer` | Absolute-positioned muted footer text |
| `.iteso-tag` | Small muted text for ITESO branding |
| `.diagram-container` | Centered flex container for SVG diagrams (max 700x380) |

### Toggle Bar

| Class | Description |
| --- | --- |
| `.toggle-bar` | Fixed top-right container for theme/language buttons |
| `.toggle-btn` | Styled button for toggles |

## JS Functions

### Exposed on `window`

| Function | Description |
| --- | --- |
| `toggleTheme()` | Switches between dark and light themes, persists to `localStorage` |
| `toggleLang()` | Switches between `en` and `es` languages, persists to `localStorage` |
| `applyTheme(theme)` | Applies `'dark'` or `'light'` theme and updates the toggle button icon |
| `initParticles()` | Initializes or restarts the particle canvas animation |

### Internal (called automatically on slide change)

| Function | Description |
| --- | --- |
| `animateSlideElements(slide)` | Triggers `.float-in` and `.slide-in` animations on the given slide |
| `triggerCounters(slide)` | Starts animated counters for elements with `data-counter` attribute |
| `restartSVGAnimations(slide)` | Restarts inline SVG `<animate>` elements on the given slide |
| `animateCounter(el, target, suffix, prefix, decimals, duration)` | Animates a number from 0 to target |

## Data Attributes for Counters

Add these attributes to any element to create an animated counter:

| Attribute | Required | Description |
| --- | --- | --- |
| `data-counter` | Yes | Target number to count up to |
| `data-suffix` | No | Text appended after the number (e.g., `%`, `ms`) |
| `data-prefix` | No | Text prepended before the number (e.g., `$`, `~`) |
| `data-decimals` | No | Number of decimal places (default: `0`) |

Example:

```html
<span class="stat-num" data-counter="99.9" data-suffix="%" data-decimals="1">0</span>
```

## `window.PRES_CONFIG`

Set `window.PRES_CONFIG` in your module's `slides.js` (before `presenter.js` loads)
to override Reveal.js defaults:

```javascript
window.PRES_CONFIG = {
  width: 960,           // default: 960
  height: 600,          // default: 600
  margin: 0.04,         // default: 0.04
  center: false,        // default: false
  hash: true,           // default: true
  transition: 'slide',  // default: 'slide'
  transitionSpeed: 'default',
  controls: true,       // default: true
  progress: true,       // default: true
  slideNumber: true,    // default: true
  overview: true,       // default: true
  touch: true,          // default: true
};
```

Only include properties you want to override. The defaults above are applied
automatically if `window.PRES_CONFIG` is not set or is missing a property.

## Bilingual Pattern

All visible text should include both English and Spanish spans. The active language
is controlled by `data-lang` on the `<html>` element. CSS rules in `theme.css` hide
the inactive language.

```html
<h2>
  <span class="lang-en">English Title</span>
  <span class="lang-es">Titulo en Espanol</span>
</h2>
```

The toggle button calls `toggleLang()` which switches `data-lang` between `en` and
`es` and persists the choice in `localStorage` under the key `pres-lang`.

## Script Loading Order

The loading order in `index.html` is critical:

```text
1. slides.js          -- Module-specific logic and window.PRES_CONFIG
2. reveal.js (CDN)    -- Reveal.js library (must load before presenter.js)
3. presenter.js       -- Initializes Reveal with config and sets up all features
```

`presenter.js` calls `Reveal.initialize()`, so it must load after the Reveal.js
library. Module-specific `slides.js` must load before `presenter.js` so that
`window.PRES_CONFIG` is available at initialization time.

## Creating a New Module Presentation

1. Copy `docs/presentation-template/` into your module directory as `presentation/`.
2. Update the `<title>` tag and title slide content.
3. Add your slides between the title slide and the Q&A slide.
4. Create a `slides.js` file for module-specific logic (can be empty).
5. Optionally create a `slides.css` file for module-specific styles.
6. Reference shared assets with relative paths: `../../shared/presentation/`.
