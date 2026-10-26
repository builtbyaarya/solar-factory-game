# Solar Factory: Survive to 2030

A browser game. You build a US solar or battery factory, then the real shocks arrive one quarter at a time: duty orders, tax-credit rules, grid connection waits, late tools, ramp-up problems, price crashes, a customer going bust. Twenty quarters from Q1 2026 to Q4 2030. At the end you get a result card to send to whoever told you it was easy.

Play it: https://builtbyaarya.github.io/solar-factory-game/ (GitHub Pages, from this repository's `index.html`).

## What is real and what is a game

- The duty rates are real and come from the open [US Solar Trade Tracker](https://github.com/builtbyaarya/us-solar-trade-tracker) dataset (CC BY 4.0): the India, Indonesia and Laos final determinations of 11 September 2026, the 2025 orders on Cambodia, Malaysia, Thailand and Vietnam, Section 201 and Section 301. Each shock card links its source.
- The tax-credit mechanics (45X amounts, the 2026 prohibited-foreign-entity rules, the 48E/45Y begin-construction deadline) follow SEIA's summary of the July 2025 law and the IRS 45X page.
- The grid wait, cancellation and capacity context come from Berkeley Lab's Queued Up, E2's Clean Economy Works tracker and SEIA's Solar Market Insight.
- Capex, unit costs, prices, build times, labour and incentive multipliers are rounded public benchmarks or plain assumptions. They are labelled as such in the game's "Assumptions and sources" screen, which is the authoritative list.

It is fun first and accurate second. It is not a model you should raise money on, and nothing here is legal, trade or investment advice.

## Research behind the numbers

The game's parameters are anchored where a public reference exists and labelled as assumptions where none does:

- Duty rates: the [US Solar Trade Tracker](https://github.com/builtbyaarya/us-solar-trade-tracker), which cites every Federal Register notice.
- Capex by stage: Powell et al. (2015), *The capital intensity of photovoltaics manufacturing*, Energy and Environmental Science 8, https://doi.org/10.1039/c5ee01509j, cross-checked with the DOE *Solar Photovoltaics Supply Chain Deep Dive Assessment* (2022).
- Cost structure: Woodhouse, Smith, Ramdas and Margolis (2019), NREL/TP-6A20-72134, https://doi.org/10.2172/1495719.
- Ramp-up: Terwiesch and Bohn (2001), https://doi.org/10.1016/S0925-5273(00)00045-1, and Bohn and Terwiesch (1999), https://doi.org/10.1016/s0272-6963(99)00014-5.
- What duties do to prices and location: Wang and Houde (2026), https://doi.org/10.1086/736763, and Gerarden, Bollinger, Gillingham and Xu (2025), NBER WP 34401.
- Tax credits: the Treasury 45X final rule (89 FR 85798) and SEIA's summary of the July 2025 law.
- Grid waits, cancellations and capacity: Berkeley Lab *Queued Up 2026*, E2 *Clean Economy Works*, SEIA/Wood Mackenzie *Solar Market Insight*.

## Assumptions

Every number the game uses, with its source, is in the `ASSUMPTIONS` table and the `SRC` map at the top of `index.html`, and is shown on screen from the intro and the result page. If a figure is wrong or stale, open an issue with the source and it will be fixed.

## Running it locally

It is one file with no build step. Open `index.html` in a browser, or serve the folder with any static server. The Archivo fonts are embedded in the file; the only thing fetched from outside is three.js r128 from cdnjs, and without it (or without WebGL) the page falls back to a flat 2D stack.

A shared link (`?seed=...&stage=...&state=...&sup=...&size=...&name=...`) replays the same sequence of shocks so two people can compare choices.

## Feasibility report

The result screen offers a PDF study of the run. The player types an email address and presses one button; the address and the run data (setup, choices, quarter ledger, shocks) are posted to a form. `python3 scripts/make_report.py request.txt out/` turns that text into `report.pdf`, a feasibility study (summary, site and configuration, capex and funding, schedule, unit economics, cash chart, risk register, sensitivities, assumptions with sources; LaTeX with pgfplots and booktabs needed) using only the run data and the game's own `SRC` and `ASSUMPTIONS` tables. The address is used once to send the report and is not kept. A shared link with `&c=<choices>&auto=1` replays a run exactly.

## Roadmap

See `ROADMAP.md`. The game grows one small piece at a time; each piece is tested before it lands.

## Licence

MIT. Data from the tracker is CC BY 4.0 and credited above.
