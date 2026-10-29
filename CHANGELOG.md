# Changelog

## v0.8.0 (2026-10-29)
Three new shock cards (piece 3), each tied to a public source. A scope ruling application names your product (imported inputs only): Commerce has 30 days to open the inquiry and 120 days to rule, extendable to 300, and an in-scope ruling brings deposits back to the day it opened (19 CFR 351.225). The state air permit stalls (during the build): based on a South Carolina solar plant whose air permit had no decision date months after comments closed. Your tool vendor goes bust: based on Meyer Burger's US units filing Chapter 11 in June 2025. New entries in the SRC map and three new rows in the ASSUMPTIONS table, with links. The Ledger line format is unchanged. Because the shock deck is bigger, a seed shared before this version may now deal a different set of shocks. Tested by replaying three seeds by click, one run by keyboard, the reduced-motion and no-WebGL fallbacks, and each new card's text, options and timing directly.

## v0.7.1 (2026-10-26)
Ready to go public. The report box now only posts to the request form; the old fallback that opened your mail app with a personal address in it is gone, and if the post fails the page asks you to press the button again. No gameplay change, no new numbers.

## v0.7.0 (2026-10-26)
Cash chart. The result card now carries a small chart of your cash at the close of each quarter, drawn on the card canvas from the run's own ledger: an amber line with a soft fill, a dashed zero line, and the high and low marked above it. It shows up in the saved and shared PNG too. No new numbers, so no change to the SRC map or ASSUMPTIONS table, and the Ledger line in the report email is unchanged. Tested by replaying three seeds by click, one run by keyboard, and the reduced-motion and no-WebGL fallbacks.

## v0.6.0 (2026-10-23)
The plant. The site scene is rebuilt so it reads as a cell or module plant: a long hall with a clean facade and an entrance canopy, a row of sawtooth roof monitors, cladding that slides on panel by panel, an electrical substation with transformers and a bus structure that energises when the grid connects, a parking apron, a truck dock with trailers that arrive as utilisation rises, rooftop PV in neat strings once operating, and a site boundary. Each piece lands with weight (ease and settle, shadows with it). The cash stack still sits on the dock and every shock still happens there. About 15k triangles, one instanced draw per material, no post-processing. Report requests now go through an email box on the result screen: type an address, press one button, no mail app; if the post fails the mail app opens with the same request as before. `scripts/make_report.py` now writes a full feasibility study (summary, site and configuration, capex and funding, schedule, unit economics with typeset formulas, a cash chart, a risk register of the shocks met and the decisions taken, sensitivities, assumptions with sources). No change to the game rules, numbers, events, SRC map or ASSUMPTIONS table.

## v0.5.0 (2026-10-22)
Feasibility report. The result screen now offers a PDF study of your run: pressing the button opens your mail app with the run's data in the message (setup, choices, quarter ledger, shocks); a reply comes back with the report. `scripts/make_report.py` builds that PDF (LaTeX) from the request text and the game's own SRC and ASSUMPTIONS tables, so every figure in it is either the player's run or a cited assumption. A run can also be replayed exactly with `&c=<choices>&auto=1` on the shared link. Footer notes that an address is used once to reply and not kept. No gameplay change.

## v0.4.1 (2026-10-22)
Animation fixes: new wafers now drop in from just above the stack instead of from the sky, wafers that slide off tumble toward the viewer and bounce once on the dock, and the sun is a small disc with slow rays in the top corner.

## v0.4.0 (2026-10-22)
The site: the scene is now your factory being built. The slab goes down in Q1, then the steel, the walls, the roof with its skylights; the power line and substation arrive when the grid connects; rooftop solar goes on once you are operating. A sun crosses the sky from Q1 2026 to Q4 2030 and everything casts real shadows. The cash stack now sits on the loading dock and takes the shocks as before. Bankruptcy greys the site out. No gameplay change.

## v0.3.2 (2026-10-22)
New models: wafers are now true pseudo-squares (a square cut from a round ingot, arc corners) with a bevelled rim that catches the light, a cell finger-and-busbar pattern on the top face, and the duty stamp is a rounded amber puck instead of a box. About 220 triangles per wafer, still one instanced draw. No gameplay change.

## v0.3.1 (2026-10-22)
Studio look: light grey studio background, the wafer stack lit like a product shot (key light, rim light, soft contact shadow), white cards with soft shadows, pill buttons, centred copy. Archivo only (the Archivo Black file is no longer embedded). Same stack behaviour, same rules and numbers.

## v0.3.0 (2026-10-22)
Wafer Stack redesign: the blue cell background and the stat panels are gone. One stack of thin silicon wafers floats in a flat, deep scene; its height is your cash, and shocks act on it (a duty stamp presses it down, a price crash slides the top wafers off, a storm rains on it, a loan drops new wafers on one by one, yield gains polish it, bankruptcy collapses it, surviving to 2030 turns it slowly in warm light). Six stats are now one quiet line with details on tap. Archivo is embedded in the file (no Google Fonts); three.js r128 from cdnjs is the only external load. Reduced-motion shows a still stack; without WebGL the page falls back to a flat 2D stack. The result card carries a still render of the final stack. New footer. No change to the game rules, numbers, events, SRC map or ASSUMPTIONS table.

## v0.2.0 (2026-10-22)
Keyboard play: number keys 1 to 9 pick an option, Enter moves on to the next quarter. Each option shows its key, the active card lights up in amber when it has focus, and focus moves to the next thing to press. Tested by replaying three seeds by click and one run by keyboard only. No new numbers.

## v0.1.1 (2026-10-21)
Assumptions screen now cites the research behind capex, cost structure, ramp-up and duty pass-through (Powell 2015; Woodhouse et al. 2019; Terwiesch and Bohn 2001; Wang and Houde 2026; Gerarden et al. 2025; Treasury 45X final rule). No gameplay change.

## v0.1 (2026-10-21)
First playable version: four stages, six states, four supplier routes, three sizes, twenty quarters, twenty-one shock cards with sources, result card, share and replay links, assumptions screen.
