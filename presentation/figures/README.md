# StockBench PPT Figure Generator

Generate static 16:9 PNG figures for the presentation pages.

## Setup

Dependencies are installed in this directory with npm.

```bash
cd presentation/figures
npm install
npx playwright install chromium
```

## Render

Render the current sample pages:

```bash
npm run render
```

Render selected pages:

```bash
npm run render 06 14
```

Outputs:

```text
output/page-06.png
output/page-14.png
```

Pages are laid out on a 1920 × 1080 CSS canvas and exported with 2× device scale factor as 3840 × 2160 PNGs. Figures intentionally omit PPT-level titles, page numbers, source strips, and right-corner metadata; each image contains only the core static chart.

Style constraints:

- Chinese text uses a Heiti-style font without extra artificial bolding.
- Use flat solid colors only; do not use gradients.
- Keep information density low and make the most important chart elements large.
