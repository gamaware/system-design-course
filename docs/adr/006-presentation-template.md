# ADR-006: Shared Presentation Template Architecture

## Status

Accepted

## Context

Each module in the course can include a reveal.js slide deck for in-class instruction.
The original approach embedded all CSS, JavaScript, and asset references directly inside
a single monolithic `index.html` per module. With 17 modules planned, duplicating the
theme, animation logic, and toggle controls across every presentation creates a
significant maintenance burden. A design change in the theme would require updating
every copy independently.

## Decision

### Shared assets directory

All reusable presentation code lives in `shared/presentation/`:

- **`theme.css`** -- Design tokens (CSS custom properties), reveal.js overrides, component
  styles (cards, grids, badges, stats), animations, accessibility, and print styles.
- **`presenter.js`** -- Particle canvas background, theme/language toggle, animated counters,
  slide element animations, SVG restart, expandable cards, and Reveal.js initialization.
- **`assets/`** -- AWS Architecture Icons (SVG) and database engine logos (PNG).

### No build step

Module presentations reference shared files via relative paths
(`../../shared/presentation/theme.css`). The architecture requires no bundler, no transpiler, and no
build step. Presentations work when opened directly from the filesystem (`file://`
protocol) without a development server.

### Starter template

A starter template lives in `docs/presentation-template/` with a minimal `index.html`
demonstrating the correct script loading order, bilingual content pattern, and component
usage. New module presentations are created by copying this template into the module's
`presentation/` directory.

### Configuration via `window.PRES_CONFIG`

Module-specific slides can override Reveal.js defaults (width, height, transition, etc.)
by setting `window.PRES_CONFIG` before `presenter.js` loads. The shared script merges
these overrides with sensible defaults.

## Alternatives Considered

- **Copy-per-module**: Each module gets its own copy of the CSS and JS. Rejected because
  maintenance burden grows linearly with module count and design drift is inevitable.
- **Symlinks**: Shared files symlinked into each module directory. Rejected because
  symlinks are fragile across platforms, break on Windows without developer mode, and
  add unnecessary git complexity.
- **Build step (webpack/vite)**: A bundler that compiles shared assets into each module.
  Rejected because it adds tooling complexity, breaks `file://` access, and requires
  Node.js as a dependency for what is otherwise static HTML content.

## Consequences

- A single source of truth for the presentation theme reduces maintenance to one file.
- All 17 modules share consistent styling, animations, and accessibility features.
- Presentations work on `file://` without a development server, though CDN
  dependencies (reveal.js, Google Fonts) require internet connectivity.
- Deployment and distribution must include the `shared/` directory alongside module
  directories to preserve relative path references.
- Module-specific styling goes in a local `slides.css` file, not in the shared theme.
