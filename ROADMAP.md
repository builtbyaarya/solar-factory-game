# Roadmap

One small piece per build, tested before it lands. Keep the game one file, keep every number sourced, keep it fun.

## Done
- v0.1 (21 Oct 2026): setup (stage, state, supplier, size), 20-quarter loop, 21 shock cards, economics, result card, share and replay links, assumptions screen.
- v0.2.0 (22 Oct 2026): keyboard play (piece 1).
- v0.3.0 (22 Oct 2026): Wafer Stack redesign and new footer.
- v0.3.1 (22 Oct 2026): studio look (light background, product-shot lighting).
- v0.3.2 (22 Oct 2026): proper wafer and stamp models.
- v0.4.0 (22 Oct 2026): the factory site builds up quarter by quarter, sun and shadows.
- v0.5.0 (22 Oct 2026): emailed feasibility report per run (scripts/make_report.py) and exact replay links.
- v0.6.0 (23 Oct 2026): the plant scene rebuilt, email box for report requests, full feasibility study format.
- v0.7.0 (26 Oct 2026): cash by quarter chart on the result card (piece 2).
- v0.7.1 (26 Oct 2026): report box posts to the form only (no personal address in the page); made public.

## Next pieces (in order)
1. [x] Keyboard play: number keys pick options, Enter advances; visible focus on the active card.
2. [x] A tiny end-of-run chart on the result card: cash by quarter, drawn on the canvas.
3. Three more shock cards from new public events (each with a source): a scope ruling, a state permitting delay, a tool vendor going bust.
4. Difficulty presets (Investor, Founder, Plant manager) that change starting cash and event weights.
5. Battery-specific cards: cathode material sourcing under the prohibited-foreign-entity rules; the storage demand upswing.
6. A "What the numbers were" screen after the result: the full ledger by quarter, downloadable as CSV.
7. Pull duty rates from the tracker's `data/tracker.json` at build time (a small script that rewrites the `DUTIES` block) so updates flow through automatically.
8. Accessibility pass: screen-reader labels on the plate and rail, colour-contrast audit, reduced-motion check.
9. Sound off by default, one optional click per quarter.
10. India version (separate `india/index.html`, generic: no real company names), reusing the engine with its own duty and incentive tables.

## Rules for every piece
- Fun first, accurate second, never a dashboard.
- Every new number has a public source in `SRC`.
- No real Indian company names, nothing political, no em dashes in copy.
- Test by replaying three seeds end to end before committing.
