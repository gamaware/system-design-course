# Presentation Template

Starter template for creating bilingual reveal.js slide decks for the Scalable System Design
course. Includes dark/light theme toggling, English/Spanish language switching, animated particle
background, expandable cards, counter animations, and a consistent visual identity across all
modules.

## Quick Start

1. Copy the `docs/presentation-template/` directory into your module (e.g., `10-databases/presentation/`).
2. Rename nothing -- the file names `index.html`, `slides.css`, and `slides.js` are conventions
   used across all modules.
3. Update the `<title>` tag and the title slide content in `index.html` with your module name
   and number.
4. Add new `<section>` elements between the title slide and the Q&A slide.
5. Open `index.html` in a browser to test. No build step required -- everything loads from CDNs
   and relative paths.

## File Structure

| File | Purpose |
| --- | --- |
| `index.html` | Slide deck markup. Contains all `<section>` elements and loads shared + local assets. |
| `slides.css` | Module-specific styles. Empty by default. Use for custom diagram sizing or widgets. |
| `slides.js` | Module-specific JavaScript. Sets `window.PRES_CONFIG` to override Reveal.js defaults. |
| `../../shared/presentation/theme.css` | Shared theme with CSS variables, component styles, and animations. |
| `../../shared/presentation/presenter.js` | Shared engine: Reveal.js init, theme/lang toggle, particles, counters, animations. |

## Available CSS Classes

### Layout

| Class | Description |
| --- | --- |
| `grid-2` | Two-column grid with equal widths. |
| `grid-3` | Three-column grid with equal widths. |
| `grid-4` | 2x2 grid (two columns, items wrap). |
| `grid-6` | 3x2 grid (three columns, items wrap). |
| `side-by-side` | Two-column grid with 14px gap, useful for comparison layouts. |

### Cards

| Class | Description |
| --- | --- |
| `card` | Rounded container with surface background and border. Use `h4` for the title. |
| `stat-card` | Centered card for displaying a large number with a label below. |
| `expandable` | Add to a `card` to make it clickable. Hidden content goes in a child `expand-content` div. |

### Badges

| Class | Description |
| --- | --- |
| `badge` | Inline pill-shaped label. Combine with a color class. |
| `badge-blue` | Blue badge (primary color). |
| `badge-green` | Green badge (mint/success). |
| `badge-orange` | Orange badge (warning). |
| `badge-red` | Red badge (error/danger). |
| `badge-purple` | Purple badge. |

### Colored Borders

Add a left accent border to any card or element.

| Class | Description |
| --- | --- |
| `border-blue` | Blue left border (primary). |
| `border-green` | Green left border (mint). |
| `border-red` | Red left border (error). |
| `border-orange` | Orange left border (warning). |
| `border-purple` | Purple left border. |
| `border-gold` | Gold left border. |

### Statistics and Counters

Use `stat-card` with `stat-num` and `stat-label` spans. Add `data-counter` to animate the number
on slide entry.

| Attribute | Description |
| --- | --- |
| `data-counter` | Target number to animate to (required). |
| `data-suffix` | Text appended after the number (e.g., `%`, `ms`). |
| `data-prefix` | Text prepended before the number (e.g., `$`, `~`). |
| `data-decimals` | Number of decimal places (default `0`). |

### Animations

| Class | Description |
| --- | --- |
| `float-in` | Fade in + slide up. Elements animate sequentially with 100ms stagger. |
| `slide-in` | Fade in + slide from left. Elements animate sequentially with 80ms stagger. |

Animations trigger automatically when a slide becomes active. Add these classes to cards, list
items, or any element you want to animate on entry.

### Diagrams

| Class | Description |
| --- | --- |
| `diagram-container` | Centered flex container for SVG diagrams. Max width 700px, max height 380px. |

### Utilities

| Class | Description |
| --- | --- |
| `subtitle` | Muted text at 0.82em, used under headings. |
| `aws-icon` | Inline block with right margin for AWS service icons. |
| `qa-center` | Full-height centered flex container for the Q&A slide. |
| `iteso-footer` | Absolute-positioned footer text at the bottom-left of a slide. |
| `iteso-tag` | Small muted text for the ITESO course identifier. |

## Bilingual Pattern

Every user-visible text element must include both language spans:

```html
<h2>
  <span class="lang-en">English Title</span>
  <span class="lang-es">Titulo en Espanol</span>
</h2>
```

The active language is controlled by the `data-lang` attribute on `<html>`. The toggle button
in the top-right corner switches between `en` and `es`. CSS rules in `theme.css` hide the
inactive language span.

Use HTML entities for Spanish characters: `&oacute;` (o), `&ntilde;` (n), `&iquest;` (?),
`&iacute;` (i), `&uacute;` (u), `&eacute;` (e), `&aacute;` (a).

## Adding Slides

Insert new `<section>` elements inside the `<div class="slides">` container. Place them between
the title slide (slide 0) and the Q&A slide (last slide):

```html
<!-- ========== SLIDE N: TOPIC ========== -->
<section>
  <h2>
    <span class="lang-en">Slide Title</span>
    <span class="lang-es">Titulo de la Diapositiva</span>
  </h2>
  <!-- Slide content here -->
</section>
```

Use the comment banner pattern (`<!-- ========== SLIDE N: TOPIC ========== -->`) to keep slides
organized and easy to navigate in the source.
