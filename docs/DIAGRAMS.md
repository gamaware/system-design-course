# Diagram conventions

Every architecture diagram in this repository is generated with the same skill and the same style, so
that a student moving from one lab to the next reads the same visual language.

## Toolchain

Diagrams are authored as draw.io XML with the official AWS4 shape libraries and exported to PNG.

```bash
drawio --no-sandbox -x -f png -s 1.5 -o diagrams/labNN-architecture.png diagrams/labNN-architecture.drawio
```

## Files per lab

| File                                    | Purpose                                   |
|-----------------------------------------|-------------------------------------------|
| `NN-topic/diagrams/labNN-<name>.drawio` | Editable source, committed                |
| `NN-topic/diagrams/labNN-<name>.png`    | Rendered image referenced from the README |

SVG is not committed. draw.io embeds every icon as base64, so a diagram carrying a dozen service icons
lands past the 1024 KB pre-commit limit, as measured on the diagrams in this repository.

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
![Lab NN architecture](diagrams/labNN-architecture.png)

[Edit this diagram](diagrams/labNN-architecture.drawio)
```

The `alt` text is required: markdownlint rule `MD045` fails an image without it.
