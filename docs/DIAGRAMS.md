# Diagram conventions

Every architecture diagram in this repository is generated with the same skill and the same style, so
that a student moving from one lab to the next reads the same visual language.

## Toolchain

Diagrams are authored as draw.io XML with the official AWS4 shape libraries and exported to PNG.

```bash
drawio --no-sandbox -x -f png -s 1.5 -o diagrams/labNN-architecture.png diagrams/labNN-architecture.drawio
shared/diagram-motion/render.sh NN-topic/diagrams/labNN-architecture.drawio
```

The second command writes the animated SVG that the README shows: the arrows of the flow draw in
step order with a glowing dot, the step badge pulses and its legend row lights up. The step order of
each diagram lives in `shared/diagram-motion/flows.json`. See
[shared/diagram-motion/README.md](../shared/diagram-motion/README.md).

## Files per lab

| File                                    | Purpose                                   |
|-----------------------------------------|-------------------------------------------|
| `NN-topic/diagrams/labNN-<name>.drawio` | Editable source, committed                |
| `NN-topic/diagrams/labNN-<name>.svg`    | Animated image referenced from the README |
| `NN-topic/diagrams/labNN-<name>.png`    | Static render, for slides and printing    |

The plain draw.io SVG export is not committed: every text label carries a PNG copy, which puts a
diagram past the 1024 KB pre-commit limit. `render.sh` drops those copies, so the animated SVG
weighs 25 to 220 KB.

## Size budget

Export at scale `1.5`. If the result exceeds 1000 KB, export at scale `1` instead. The pre-commit hook
`check-added-large-files --maxkb=1024` rejects anything larger.

## Style

The skill's AWS Reference Architecture style applies without modification:

- Title at 30px bold, subtitle at 16px, orange separator `#FF9900`, spanning the full width.
- Title reads `Lab NN - Topic`. Subtitle states what the architecture does in one line.
- Containers use the adaptive fills of the style guide, so diagrams stay readable in dark and light mode.
- Service icons are 48x48 inside category containers with their category tint.
- Numbered teal `#007CBD` badges mark the request flow, with the matching step legend in the right sidebar.

## Flows

A request flow is drawn as an architecture diagram with numbered step badges and the sidebar legend,
not as a separate sequence chart. This keeps one visual language across the course.

## Labs without cloud services

Labs that run locally on Docker use the same containers, typography and palette, with the general icon
set for Docker, proxies, caches and databases.

## Referencing a diagram

```markdown
![Lab NN architecture](diagrams/labNN-architecture.svg)

[Edit this diagram](diagrams/labNN-architecture.drawio)
```

The `alt` text is required: markdownlint rule `MD045` fails an image without it.
