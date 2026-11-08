# Visuals requests

Append-only. Each builder writes under its own heading (docs/visuals-spec.md 4.6).

## Requests to CORE

### STUDIO

- STUDIO, `components/shared/ChartFrame.tsx`: optional `headingLevel?: 3 | 4` prop (default 3) for the title element. Why: in the Studio each chart sits under a section `<h3>` ("Effect", "How blinded it was", "Design fixes"), so the frame's `<h3>` title is a sibling of its own section heading in the outline. Workaround: none needed visually; the outline is just flat.
- STUDIO, `components/shared/ChartParts.tsx`: a non-recharts tooltip helper for hand-written SVG (position + sentence, tap/outside/scroll close). Why: `ChartTooltip` is recharts-payload shaped. Workaround: `components/studio/PointTip.tsx` renders a `div.chart-tooltip` so the look matches.

