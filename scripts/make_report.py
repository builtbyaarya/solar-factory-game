#!/usr/bin/env python3
"""Build the feasibility study (PDF) for one Solar Factory run.

Input: the text of a report-request email (the body the game puts in the mail), or a file holding it.
Output: <outdir>/report.tex and <outdir>/report.pdf (latexmk -pdf; needs a TeX install with pgfplots and booktabs).

    python3 scripts/make_report.py request.txt out/

The study is built only from the request lines the game wrote (setup, choices, ledger, shocks) and from the
SRC map, the ASSUMPTIONS table and the event list inside index.html, so every number in it is either the
player's own run or a cited game assumption. It never invents a figure. Sensitivities are arithmetic on the
recorded ledger, not a new simulation. No em dashes anywhere.

Structure: title block, 1 Summary, 2 Site and configuration, 3 Capital cost and funding, 4 Schedule,
5 Unit economics, 6 Risk register, 7 Sensitivities, 8 Assumptions and sources, disclaimer.
"""
import json, os, re, subprocess, sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "index.html"

PHASES = {"b": "build", "r": "ramp", "o": "operate"}
INTEREST = 0.09          # construction loan rate, a year (ASSUMPTIONS, Financing)
LOAN_SHARE = 0.40        # construction loan as a share of capex (ASSUMPTIONS, Financing)
EXTRA_LOAN_SHARE = 0.25  # the one further loan (ASSUMPTIONS, Financing)
CREDIT_PHASE_Q = 17      # ledger quarter from which the 45X credit is 75% (Q1 2030; ASSUMPTIONS, Section 45X)


# ----------------------------------------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------------------------------------
def tex(s):
    """Escape a string for LaTeX text. Em and en dashes are replaced, never passed through."""
    s = str(s)
    for a, b in [("\\", r"\textbackslash{}"), ("&", r"\&"), ("%", r"\%"), ("$", r"\$"), ("#", r"\#"), ("_", r"\_"),
                 ("{", r"\{"), ("}", r"\}"), ("~", r"\textasciitilde{}"), ("^", r"\textasciicircum{}")]:
        s = s.replace(a, b)
    return s.replace("—", ", ").replace("–", "-")


def money(x, dp=0):
    """$M with thousands separators; negative numbers get a real minus sign in math mode."""
    if x is None:
        return "n/a"
    s = f"{abs(x):,.{dp}f}"
    return (r"$-$" if x < 0 else "") + s


def usd(x, dp=0):
    """Dollar figure in $M for prose and two-column tables, with a real minus sign."""
    if x is None:
        return "n/a"
    return ("$-$" if x < 0 else "") + f"\\${abs(x):,.{dp}f}M"


def pctf(x, dp=0):
    return f"{x:.{dp}f}\\%"


def qname(i):
    """Ledger quarter number (1 = Q1 2026) to a label."""
    return f"Q{(i - 1) % 4 + 1} {2026 + (i - 1) // 4}"


def supname(name):
    """Supplier names as the game writes them, but readable mid-sentence ("a mix, with ..." not "A mix, with ...")."""
    return name[0].lower() + name[1:] if name.startswith("A ") else name


def norm_phrase(s):
    return re.sub(r"\s+", " ", s.strip().lower())


# ----------------------------------------------------------------------------------------------------------
# request parsing (tolerant: leading/trailing whitespace, email quoting, an extra Email: line)
# ----------------------------------------------------------------------------------------------------------
def parse_request(text):
    lines = []
    for raw in text.splitlines():
        l = raw.strip()
        l = re.sub(r"^(>\s?)+", "", l).strip()   # strip reply quoting
        lines.append(l)

    def get(key):
        for l in lines:
            if l.startswith(key + ":"):
                return l.split(":", 1)[1].strip()
        return ""

    req = {k: get(K) for k, K in [("run", "Run"), ("company", "Company"), ("setup", "Setup"), ("outcome", "Outcome"),
                                   ("choices", "Choices"), ("shocks", "Shocks"), ("email", "Email")]}
    # ledger: the column key is in the line itself, so columns are mapped by name, not position
    led_line = next((l for l in lines if l.startswith("Ledger")), "")
    key_m = re.match(r"Ledger\s*\(([^)]*)\)\s*:\s*(.*)$", led_line)
    if key_m:
        keys = [k.strip() for k in key_m.group(1).split(",")]
        body = key_m.group(2)
    else:
        keys = ["q", "phase", "cash", "debt", "price", "cost", "yield", "util", "profit", "book", "cred"]
        body = led_line.split(":", 1)[1] if ":" in led_line else ""
    names = ["q", "phase", "cash", "debt", "price", "cost", "yield", "util", "profit", "book", "cred"]
    col = {}
    for i, k in enumerate(keys):
        for n in names:
            if k.lower().startswith(n) and n not in col:
                col[n] = i
                break
    rows = []
    for item in [x for x in body.split(";") if x.strip()]:
        f = [x.strip() for x in item.split(",")]
        if len(f) < len(col):
            continue
        try:
            rows.append({
                "q": int(float(f[col["q"]])), "phase": PHASES.get(f[col["phase"]], f[col["phase"]]),
                "cash": float(f[col["cash"]]), "debt": float(f[col["debt"]]),
                "price": float(f[col["price"]]), "uc": float(f[col["cost"]]),
                "yield": float(f[col["yield"]]), "util": float(f[col["util"]]), "profit": float(f[col["profit"]]),
                "book": float(f[col["book"]]) if "book" in col else 0.0, "cred": float(f[col["cred"]]) if "cred" in col else 0.0})
        except (ValueError, KeyError):
            continue
    # the result screen records the final quarter a second time; keep the first copy
    seen, uniq = set(), []
    for r in rows:
        if r["q"] in seen:
            continue
        seen.add(r["q"]); uniq.append(r)
    uniq.sort(key=lambda r: r["q"])
    req["ledger"] = uniq
    m = re.search(r"seed=(\d+)", req["run"]); req["seed"] = m.group(1) if m else "?"
    for k in ["stage", "state", "sup", "size", "name"]:
        m = re.search(r"[?&]" + k + r"=([^&\s]+)", req["run"]); req[k] = m.group(1) if m else ""
    m = re.match(r"(.*?)\s*\(grade\s+([^)]+)\)", req["outcome"])
    req["outcome_head"] = m.group(1).strip() if m else req["outcome"].split(",")[0].strip()
    req["grade"] = m.group(2).strip() if m else "?"
    req["shock_list"] = [s.strip() for s in req["shocks"].split(";") if s.strip()]
    req["choice_list"] = [int(c) for c in req["choices"] if c.isdigit()]
    return req


# ----------------------------------------------------------------------------------------------------------
# game tables, read from index.html (never edited here)
# ----------------------------------------------------------------------------------------------------------
def game_tables(req):
    html = INDEX.read_text(encoding="utf-8")

    def block(pattern):
        m = re.search(pattern, html, re.S)
        return m.group(0) if m else ""

    src = block(r"const SRC = \{.*?\n\};")
    asm = block(r"const ASSUMPTIONS = \[.*?\n\];")
    stages = block(r"const STAGES = \[.*?\n\];")
    states = block(r"const STATES = \[.*?\n\];")
    sups = block(r"const SUPPLIERS = \[.*?\n\];")
    sizes = block(r"const SIZES = \[.*?\n\];")
    duties = block(r"const DUTIES = \{.*?\n\};")
    events = block(r"const EV = \[\];.*?(?=\n/\* =+\n\s*TURN ENGINE)")
    m = re.search(r"const fixedQ = \(([0-9.]+) \* unitsPerYear\)", html)
    fixed_rate = float(m.group(1)) if m else 0.005
    # The event options are resolved with a mock game state built from the run's setup, so the option labels
    # the player saw can be printed in the risk register. apply() is never called.
    js = "\n".join([src, asm, stages, states, sups, sizes, duties,
                    "const chance = () => true; const fmtM = (x) => ''; const pct = (x) => ''; const rng = () => 0.5;",
                    "const setTimeout = () => 0;",
                    events,
                    f"const req = {json.dumps({k: req[k] for k in ['stage', 'state', 'sup', 'size']})};",
                    r"""
const stage = STAGES.find(s => s.id === req.stage) || STAGES[0];
const state = STATES.find(s => s.id === req.state) || STATES[0];
const size = SIZES.find(s => String(s.id) === String(req.size)) || SIZES[0];
function mock(supId, q, phase) { const sup = SUPPLIERS.find(s => s.id === supId) || SUPPLIERS[0];
  // a permissive state: anything that can fire at this quarter and phase for some cash, yield or credibility does fire
  return { stage, state, sup, size, price: stage.price, cash: -1, capexTotal: 0, gridLeft: 1, yield: 0.6, q: q === undefined ? 5 : q, phase: phase || "build",
           unitsPerYear: size.mult * 1e9, fixedQ: 1, debtOffered: false, feocHit: false, crashes: 1, cred: 60 }; }
const EVENTS = {};
for (const e of EV) {
  const bySup = {};
  for (const s of SUPPLIERS) {
    const opts = typeof e.options === "function" ? e.options(mock(s.id)) : e.options;
    bySup[s.id] = opts.map(o => ({ label: o.label, hint: o.hint }));
  }
  const can = {};
  for (const ph of ["build", "ramp", "operate"]) {
    can[ph] = [];
    for (let q = 0; q < 24; q++) { let ok = true; try { ok = !!e.when(mock(req.sup, q, ph)); } catch (err) { ok = true; } can[ph].push(ok); }
  }
  EVENTS[e.id] = { id: e.id, title: e.title, src: e.src, options: bySup, can };
}
console.log(JSON.stringify({ SRC, ASSUMPTIONS, STAGES, STATES, SUPPLIERS, SIZES, DUTIES, EVENTS, fixed_rate: """ + str(fixed_rate) + " }));"])
    out = subprocess.run(["node", "-e", js], capture_output=True, text=True)
    if out.returncode != 0:
        # fall back to the data tables alone; the register then prints option numbers instead of labels
        js2 = "\n".join([src, asm, stages, states, sups, sizes, duties,
                         "console.log(JSON.stringify({SRC, ASSUMPTIONS, STAGES, STATES, SUPPLIERS, SIZES, DUTIES, EVENTS: {}, fixed_rate: " + str(fixed_rate) + "}));"])
        out = subprocess.run(["node", "-e", js2], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


# ----------------------------------------------------------------------------------------------------------
# derived figures (all from the ledger and the game's stated rules)
# ----------------------------------------------------------------------------------------------------------
def derive(req, g):
    stage = next((s for s in g["STAGES"] if s["id"] == req["stage"]), g["STAGES"][0])
    state = next((s for s in g["STATES"] if s["id"] == req["state"]), g["STATES"][0])
    sup0 = next((s for s in g["SUPPLIERS"] if s["id"] == req["sup"]), g["SUPPLIERS"][0])
    size = float(req["size"] or 1)
    L = req["ledger"]
    unit = stage["unit"]                       # GW or GWh
    w = "Wh" if unit == "GWh" else "W"
    U = size * 1e9                             # W or Wh a year at nameplate
    capex = stage["capex"] * U * (1 - state["incentive"]) / 1e6          # $M after incentive
    capex_gross = stage["capex"] * U / 1e6
    fixedQ = g["fixed_rate"] * U * state["labour"] / 1e6                 # $M a quarter
    wc = fixedQ * (stage["buildQ"] + state["gridQ"] + 2)
    debt0 = LOAN_SHARE * capex
    cash0 = capex + wc
    equity = cash0 - debt0
    d = {"stage": stage, "state": state, "sup0": sup0, "size": size, "unit": unit, "w": w, "U": U, "capex": capex,
         "capex_gross": capex_gross, "fixedQ": fixedQ, "wc": wc, "debt0": debt0, "cash0": cash0, "equity": equity}

    # final supplier: the Setup line carries the route at the end of the run
    m = re.search(r"input from (.+)$", req["setup"])
    d["sup_final_name"] = m.group(1).strip() if m else sup0["name"]
    d["sup_changed"] = norm_phrase(d["sup_final_name"]) != norm_phrase(sup0["name"])

    # per-quarter reconstruction of the cash bridge
    # The game flips the phase to "ramp" at the end of the last build quarter, so the first ramp row in the
    # ledger still carries build economics (capex, half fixed cost, no sales). econ_build marks that.
    prev_cash, prev_debt, prev_phase, capex_left = cash0, debt0, "build", capex
    for r in L:
        r["econ_build"] = prev_phase == "build"
        prev_phase = r["phase"]
        r["interest"] = r["debt"] * INTEREST / 4
        r["loan"] = max(0.0, r["debt"] - prev_debt)
        r["dcash"] = r["cash"] - prev_cash
        if r["econ_build"]:
            spend = min(capex_left, capex / stage["buildQ"]) if capex_left > 1e-9 else 0.0
            capex_left -= spend
            r["capex_spend"] = spend
            r["fixed"] = 0.5 * fixedQ
            r["op"] = 0.0
            r["event_cash"] = r["dcash"] + r["interest"] + spend + 0.5 * fixedQ - r["loan"]
        else:
            r["capex_spend"] = 0.0
            r["fixed"] = fixedQ
            r["op"] = r["profit"]
            r["event_cash"] = r["dcash"] + r["interest"] - r["profit"] - r["loan"]
        # production in the quarter, from the ledger's utilisation and yield
        r["units"] = U / 4 * r["util"] / 100 * r["yield"] / 100 if not r["econ_build"] else 0.0   # W or Wh
        cred_mult = 0.75 if r["q"] >= CREDIT_PHASE_Q else 1.0
        r["credit_c"] = stage["credit"] * 100 * cred_mult                                           # cents per unit
        r["gm_c"] = r["price"] - r["uc"]                                                             # cents per unit
        r["cm_c"] = r["gm_c"] + r["credit_c"]
        prev_cash, prev_debt = r["cash"], r["debt"]

    producing = [r for r in L if not r["econ_build"]]
    selling = [r for r in producing if r["units"] > 0]
    d["producing"], d["selling"] = producing, selling
    d["last"] = L[-1] if L else None
    d["worst"] = min(L, key=lambda r: r["cash"]) if L else None
    d["peak_debt"] = max((r["debt"] for r in L), default=debt0)
    d["cum_profit"] = sum(r["profit"] for r in L)
    d["interest_total"] = sum(r["interest"] for r in L)
    d["build_rows"] = [r for r in L if r["econ_build"]]
    d["first_ramp"] = next((r for r in L if r["phase"] == "ramp"), None)      # the quarter first product came off the line
    d["first_sale"] = producing[0] if producing else None
    d["first_operate"] = next((r for r in L if r["phase"] == "operate"), None)
    d["loans"] = [r for r in L if r["loan"] > 0.05]
    d["bankrupt"] = "bankrupt" in req["outcome_head"].lower()
    d["never_ran"] = not producing

    # implied 45X credit: reconcile the ledger's result with the game's profit rule
    imp, nom = [], []
    for r in selling:
        c = (r["profit"] + fixedQ) * 1e6 / r["units"] * 100 - r["gm_c"]      # cents per unit
        imp.append(c); nom.append(r["credit_c"])
    d["credit_implied"] = sum(imp) / len(imp) if imp else None
    d["credit_nominal"] = sum(nom) / len(nom) if nom else None               # same quarters, so the 2030 phase-down is in both
    # if the ledger says the credit was not being paid, carry that through to the margins, breakeven and sensitivities
    d["credit_lost"] = d["credit_implied"] is not None and d["credit_nominal"] > 1 and d["credit_implied"] < 0.6
    if d["credit_lost"]:
        for r in L:
            r["credit_c"] = 0.0
            r["cm_c"] = r["gm_c"]

    # breakeven utilisation at the final quarter's price, cost and yield
    last = d["last"]
    if last and not last["econ_build"] and last["yield"] > 0:
        den = U / 4 * last["yield"] / 100
        d["be_util"] = (fixedQ * 1e6) / (den * last["cm_c"] / 100) * 100 if last["cm_c"] > 0 else None
        d["be_util_nocredit"] = (fixedQ * 1e6) / (den * last["gm_c"] / 100) * 100 if last["gm_c"] > 0 else None
    else:
        d["be_util"] = d["be_util_nocredit"] = None

    # sensitivities: arithmetic on the recorded quarters
    def shift_price(k):
        return sum(r["units"] * k * r["price"] / 100 for r in selling) / 1e6
    def shift_yield(pts):
        return sum(U / 4 * r["util"] / 100 * pts / 100 * r["cm_c"] / 100 for r in selling) / 1e6
    sens = [("Price $-10\\%$ in every selling quarter", shift_price(-0.10)), ("Price $+10\\%$ in every selling quarter", shift_price(0.10)),
            ("Yield $-3$ points in every selling quarter", shift_yield(-3)), ("Yield $+3$ points in every selling quarter", shift_yield(3))]
    duty_titles = ["commerce publishes the india, indonesia and laos orders", "administrative review moves the southeast asia rates",
                   "a 15% tariff plus minimum import prices from 4 december 2026", "a circumvention inquiry names your import route"]
    duty_hits = [s for s in req["shock_list"] if norm_phrase(s) in duty_titles]
    d["duty_hits"] = duty_hits
    if duty_hits and selling:
        # material line estimated as unit cost less the game's conversion cost at the state labour multiplier
        conv_c = stage["conv"] * state["labour"] * 100
        def shift_mat(k):
            return sum(r["units"] * k * max(0.0, r["uc"] - conv_c) / 100 for r in selling) / 1e6
        # shift_mat(k) is the extra cost; the change in result is its negative
        sens += [("Material cost $-10\\%$ (duty line eased)", -shift_mat(-0.10)), ("Material cost $+10\\%$ (duty line tightened)", -shift_mat(0.10))]
        d["conv_c"] = conv_c
    d["sens"] = sens
    return d


# ----------------------------------------------------------------------------------------------------------
# risk register: shocks aligned to quarters, with the option label the player picked
# ----------------------------------------------------------------------------------------------------------
def risk_register(req, g, d):
    L = req["ledger"]
    shocks, choices = req["shock_list"], req["choice_list"]
    n_turns = len(L)
    quiet = max(0, n_turns - len(shocks))
    by_title = {norm_phrase(e["title"]): e for e in g.get("EVENTS", {}).values()}
    # A quarter without an event happens only when the event pool is empty (in practice early in the build, once
    # the equipment and grid events have fired). Shocks are listed in order, one per event quarter, so walk the
    # turns and, while quiet turns remain to be placed, treat a turn as quiet when the next shock's own firing
    # rule (its when() in index.html, evaluated on a permissive mock state) says it could not fire yet.
    sup_id = req["sup"] or "ilo"
    rows, k = [], 0
    loan_taken = False
    phase_at_turn = "build"
    for i, r in enumerate(L):
        this_phase, phase_at_turn = phase_at_turn, r["phase"]
        if k >= len(shocks):
            continue
        title = shocks[k]
        e = by_title.get(norm_phrase(title))
        if quiet > 0 and e and "can" in e and i < len(e["can"].get(this_phase, [])) and not e["can"][this_phase][i]:
            quiet -= 1
            continue
        choice = choices[i] if i < len(choices) else None
        label = None
        if e and choice is not None:
            opts = e["options"].get(sup_id) or next(iter(e["options"].values()), [])
            if 0 <= choice < len(opts):
                label = opts[choice]["label"]
            if e["id"] == "orders_ilo" and sup_id == "ilo":
                sup_id = {1: "dom", 2: "mix"}.get(choice, sup_id)
            elif e["id"] == "circumvention" and choice == 1:
                sup_id = "dom"
            elif e["id"] == "lender" and choice == 0:
                loan_taken = True
        ev_cash = r["event_cash"] if abs(r["event_cash"]) >= 0.15 else 0.0   # ledger rounding noise
        rows.append({"q": r["q"], "title": title, "decision": label or (f"option {choice + 1}" if choice is not None else "n/a"),
                     "event_cash": ev_cash, "dcash": r["dcash"], "src": (e or {}).get("src", [])})
        k += 1
    return rows, loan_taken


# ----------------------------------------------------------------------------------------------------------
# LaTeX
# ----------------------------------------------------------------------------------------------------------
PREAMBLE = r"""\documentclass[11pt,letterpaper]{article}
\usepackage[margin=1in]{geometry}
\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage{mathpazo}
\usepackage{microtype}
\usepackage{amsmath}
\usepackage{xcolor}
\definecolor{amber}{HTML}{FFB000}
\definecolor{rule}{HTML}{8A8A8E}
\definecolor{soft}{HTML}{6E6E73}
\usepackage{booktabs,array,longtable,enumitem,siunitx,xurl,fancyhdr,lastpage,titlesec,caption,float}
\usepackage{pgfplots}
\pgfplotsset{compat=1.18}
\usepackage[hidelinks]{hyperref}
\urlstyle{same}
\sisetup{group-separator={,},group-minimum-digits=4}
\captionsetup{font=small,labelfont=bf,skip=4pt}
\setlength{\LTpre}{10pt}\setlength{\LTpost}{8pt}
\setlength{\parskip}{5pt}
\setlength{\parindent}{0pt}
\linespread{1.06}
\titleformat{\section}{\large\bfseries}{\textcolor{amber}{\thesection}}{0.7em}{}
\titlespacing*{\section}{0pt}{16pt}{6pt}
\titleformat{\subsection}{\normalsize\bfseries}{\textcolor{amber}{\thesubsection}}{0.7em}{}
\titlespacing*{\subsection}{0pt}{10pt}{3pt}
\pagestyle{fancy}
\fancyhf{}
\renewcommand{\headrulewidth}{0.4pt}
\renewcommand{\headrule}{\vspace{-2pt}{\color{rule}\hrule width\headwidth height 0.4pt}}
\renewcommand{\footrulewidth}{0pt}
\fancyhead[L]{\small\textcolor{soft}{%COMPANY%}}
\fancyhead[R]{\small\textcolor{soft}{Feasibility study}}
\fancyfoot[C]{\small\textcolor{soft}{Page \thepage\ of \pageref{LastPage}}}
\setlist{nosep,leftmargin=1.4em}
\newcolumntype{L}[1]{>{\raggedright\arraybackslash}p{#1}}
\newcolumntype{R}[1]{>{\raggedleft\arraybackslash}p{#1}}
\begin{document}
"""


def chart(L):
    if not L:
        return ""
    cash = " ".join(f"({r['q']},{r['cash']:.1f})" for r in L)
    debt = " ".join(f"({r['q']},{r['debt']:.1f})" for r in L)
    xmax = max(21, L[-1]["q"] + 1)
    ymin = min(0, min(r["cash"] for r in L)) * 1.1
    ymax = max(max(r["cash"] for r in L), max(r["debt"] for r in L)) * 1.08
    return rf"""\begin{{figure}}[tbp]
\centering
\begin{{tikzpicture}}
\begin{{axis}}[width=\linewidth,height=70mm,
  xmin=0,xmax={xmax},ymin={ymin:.0f},ymax={ymax:.0f},
  xtick={{1,5,9,13,17}},xticklabels={{Q1 2026,Q1 2027,Q1 2028,Q1 2029,Q1 2030}},
  minor xtick={{1,...,{xmax - 1}}},
  ylabel={{\$M}},
  grid=major,grid style={{color=rule!25}},axis line style={{color=rule}},
  tick label style={{font=\footnotesize}},label style={{font=\footnotesize}},
  legend style={{font=\footnotesize,draw=none,fill=none,at={{(0.5,-0.14)}},anchor=north,legend columns=-1,/tikz/every even column/.append style={{column sep=12pt}}}},
  legend cell align=left]
\addplot[color=amber,line width=1.4pt,mark=*,mark size=1.3pt] coordinates {{{cash}}};
\addlegendentry{{Cash at quarter end}}
\addplot[color=rule,line width=0.9pt,dashed,mark=none] coordinates {{{debt}}};
\addlegendentry{{Debt outstanding}}
\addplot[color=black,line width=0.4pt,mark=none,forget plot] coordinates {{(0,0) ({xmax},0)}};
\end{{axis}}
\end{{tikzpicture}}
\caption{{Cash and debt by quarter, from the ledger. Cash below zero after the one extra loan has been offered is the game's bankruptcy test.}}\label{{fig:cash}}
\end{{figure}}
"""


def build_tex(req, g, d, register, loan_taken):
    L = req["ledger"]
    stage, state, sup0 = d["stage"], d["state"], d["sup0"]
    w, unit, size = d["w"], d["unit"], d["size"]
    last, worst = d["last"], d["worst"]
    today = date.today().strftime("%d %B %Y")
    company = tex(req["company"] or "The company")
    config = f"{size:g} {unit} {stage['name'].lower()}, {state['name']}, {stage['input']} from {supname(sup0['name'])}"
    n_q = len(L)
    fixedQ = d["fixedQ"]
    cents = f"cents per {w}"

    # ---- summary prose ---------------------------------------------------------------------------------
    if d["bankrupt"]:
        verdict = (f"The plant failed the game's cash test in {qname(last['q'])}: cash closed the quarter at {usd(last['cash'])} "
                   f"after the one extra loan had already been {'drawn' if loan_taken else 'offered and refused'}. "
                   f"The run ended after {n_q} of 20 quarters.")
    elif d["never_ran"]:
        verdict = "The plant reached Q4 2030 without producing. Every quarter in the ledger is a build quarter."
    else:
        verdict = (f"The plant reached Q4 2030 with {usd(last['cash'])} of cash against {usd(last['debt'])} of debt. "
                   f"Operating results summed to {'a profit' if d['cum_profit'] >= 0 else 'a loss'} of {usd(abs(d['cum_profit']))} over "
                   f"{len(d['producing'])} producing quarters. The game graded the run {tex(req['grade'])} ({tex(req['outcome_head'])}).")
    first_prod = f"First product came off the line at the end of {qname(d['first_ramp']['q'])}" if d["first_ramp"] else "The line never produced"
    plan_q = stage["buildQ"] + state["gridQ"]
    sched_line = (f"{first_prod}, against a plan of {stage['buildQ']} build quarters plus up to {state['gridQ']} waiting for grid service." if d["first_ramp"]
                  else f"The plan was {stage['buildQ']} build quarters plus up to {state['gridQ']} waiting for grid service.")
    low_line = f"The cash low point was {usd(worst['cash'])} in {qname(worst['q'])}." if worst else ""
    margin_line = ""
    if last and not last["econ_build"]:
        margin_line = (f"At the close the unit cost was {last['uc']:.1f} {cents} against a price of {last['price']:.1f}, "
                       f"a margin of {money(last['gm_c'], 1)} {cents} before the 45X credit and {money(last['cm_c'], 1)} with it."
                       if not d["credit_lost"] else
                       f"a margin of {money(last['gm_c'], 1)} {cents}; the ledger shows the 45X credit was not being paid (Section~\\ref{{sec:ue}}).")
    summary = f"{company} set out to build a {size:g} {unit} {tex(stage['name'].lower())} in {tex(state['name'])}, buying {tex(stage['input'])} from {tex(supname(sup0['name']))}. {verdict} {sched_line} {low_line} {margin_line}"

    # ---- key figures -----------------------------------------------------------------------------------
    key_rows = [
        ("Capex after state incentive", f"{usd(d['capex'])}"),
        ("Funding at start (equity / construction loan)", f"{usd(d['equity'])} / {usd(d['debt0'])}"),
        ("Peak debt", f"{usd(d['peak_debt'])}" + (f" (extra loan drawn {qname(d['loans'][0]['q'])})" if d["loans"] else "")),
        ("Final cash", f"{usd(last['cash'])} in {qname(last['q'])}" if last else "n/a"),
        ("Cumulative operating result", f"{usd(d['cum_profit'])} over {len(d['producing'])} producing quarters"),
        ("Utilisation in the final quarter", f"{last['util']:.0f}\\% at {last['yield']:.0f}\\% yield" if last and not last["econ_build"] else "not producing"),
        ("Outcome", f"{tex(req['outcome_head'])}, grade {tex(req['grade'])}"),
    ]
    key_table = "\n".join(f"{k} & {v} \\\\" for k, v in key_rows)

    # ---- site and configuration ------------------------------------------------------------------------
    site_rows = [
        ("Stage", f"{tex(stage['name'])}; {stage['buildQ']} planned build quarters; 45X credit {stage['credit'] * 100:g} {cents} produced"),
        ("Nameplate", f"{size:g} {unit} a year ({size:g}\\,billion {w} at 100\\% utilisation and yield)"),
        ("State", f"{tex(state['name'])}"),
        ("Industrial power", f"about {state['power']} cents per kWh (rounded EIA industrial average)"),
        ("Labour multiplier", f"{state['labour']:.2f} on conversion cost"),
        ("State incentive", f"{state['incentive'] * 100:.0f}\\% of capex"),
        ("Grid service wait", f"up to {state['gridQ']} quarters on the state's large-load queue"),
        ("Weather exposure", f"{state['weather'] * 100:.0f}\\% chance a season of storm damage per quarter"),
        ("Main input", f"{tex(stage['input'])}, from {tex(supname(sup0['name']))} (material multiplier {sup0['matMult']:.2f}; {'qualifies' if sup0['domestic'] else 'does not qualify'} for domestic-content rules)"),
    ]
    if d["sup_changed"]:
        site_rows.append(("Input route at close", f"{tex(supname(d['sup_final_name']))} (changed during the run; see the risk register)"))
    site_table = "\n".join(f"{k} & {v} \\\\" for k, v in site_rows)
    site_prose = (f"The run recorded a {tex(stage['name'].lower())} sized at {size:g} {unit} a year in {tex(state['name'])}, "
                  f"with {tex(stage['input'])} bought from {tex(supname(sup0['name']))}. The supplier sets the material multiplier on the cost line and which duty case "
                  f"can reach the plant; the state sets power price, labour cost, the incentive on capex and how long the utility takes to connect the plant. "
                  f"Every value in the table is a game assumption with its source in Section~\\ref{{sec:asm}}.")

    # ---- capital cost and funding ----------------------------------------------------------------------
    cap_rows = [
        ("Capex rate for the stage", f"{stage['capex'] * 100:g} {cents} of annual capacity"),
        ("Gross capex", f"{usd(d['capex_gross'])}"),
        ("State incentive", f"{state['incentive'] * 100:.0f}\\%, worth {usd(d['capex_gross'] - d['capex'])}"),
        ("Capex after incentive, $C$", f"{usd(d['capex'])}"),
        ("Construction loan, $D_0 = 0.4\\,C$", f"{usd(d['debt0'])} at 9\\% a year"),
        ("Fixed cost a quarter, $F$", f"{usd(fixedQ, 1)}"),
        ("Working capital, $F\\,(B + G + 2)$", f"{usd(d['wc'])} for {stage['buildQ']} build and {state['gridQ']} grid quarters plus two"),
        ("Opening cash, $C + F\\,(B + G + 2)$", f"{usd(d['cash0'])}"),
        ("Equity, opening cash less $D_0$", f"{usd(d['equity'])}"),
    ]
    if d["loans"]:
        for r in d["loans"]:
            cap_rows.append((f"Extra loan drawn in {qname(r['q'])}", f"{usd(r['loan'])} at 9\\% a year, taking debt to {usd(r['debt'])}"))
    cap_rows.append(("Peak debt", f"{usd(d['peak_debt'])}"))
    cap_rows.append(("Interest paid over the run", f"{usd(d['interest_total'], 1)}"))
    cap_table = "\n".join(f"{k} & {v} \\\\" for k, v in cap_rows)
    cap_prose = (f"Capex is the stage rate times nameplate, less the state incentive, and it is spent in equal parts over the planned build quarters. "
                 f"The game funds the project on day one: a construction loan equal to 40\\% of capex, and equity for the rest of capex plus working capital "
                 f"sized to cover the fixed cost through the build, the grid wait and two further quarters. Interest runs at 9\\% a year on the balance, "
                 f"charged each quarter; nothing is repaid during the run. If cash falls below three quarters of fixed cost a lender offers one further "
                 f"loan of 25\\% of capex. " +
                 (f"That offer was taken in {qname(d['loans'][0]['q'])}, which is the step in the debt line in Figure~\\ref{{fig:cash}}. " if d["loans"] else
                  ("The offer came and was refused, so debt stayed at the construction loan. " if (loan_taken is False and any(norm_phrase(s) == "a private credit fund calls" for s in req["shock_list"])) else
                   "The offer was never triggered, so debt stayed at the construction loan. ")) +
                 f"Fixed cost is the game's rule of {g['fixed_rate'] * 100:g} {cents} of nameplate a quarter times the state labour multiplier; it is charged at half rate during the build.")
    capex_math = r"""\begin{align}
C &= c_{\mathrm{cap}}\, U\,(1 - s) &&\text{capex after the incentive } s \\
D_0 &= 0.4\,C, \qquad E_0 = 0.6\,C + F\,(B + G + 2) &&\text{loan and equity at start} \\
F &= f\, U\, m_{\mathrm{lab}} &&\text{fixed cost a quarter}
\end{align}
where $c_{\mathrm{cap}}$ is the stage capex rate, $f = """ + f"{g['fixed_rate']:g}" + r"""$ \$ per """ + w + r""" of nameplate, $U$ the nameplate in """ + w + r""" a year, $B$ the planned build quarters, $G$ the grid wait and $m_{\mathrm{lab}}$ the state labour multiplier. All four are game assumptions (Section~\ref{sec:asm}, rows Capex, Financing, Build time and Labour)."""

    # ---- schedule --------------------------------------------------------------------------------------
    build_n = len(d["build_rows"])
    sched_rows = [("Planned build", f"{stage['buildQ']} quarters of capex spend"),
                  ("Planned grid wait", f"up to {state['gridQ']} quarters after the build"),
                  ("Build quarters in the ledger", f"{build_n} ({qname(L[0]['q'])} to {qname(d['build_rows'][-1]['q'])})" if d["build_rows"] else "none")]
    if d["first_ramp"]:
        sched_rows.append(("First product off the line", f"end of {qname(d['first_ramp']['q'])}, at {d['first_ramp']['yield']:.0f}\\% yield"))
        ramp_rows = [r for r in d["producing"] if r["phase"] == "ramp"]
        if d["first_sale"]:
            sched_rows.append(("First selling quarter", f"{qname(d['first_sale']['q'])}, at {d['first_sale']['util']:.0f}\\% utilisation"))
        sched_rows.append(("Ramp quarters with sales", f"{len(ramp_rows)}" + (f", yield {ramp_rows[0]['yield']:.0f}\\% to {ramp_rows[-1]['yield']:.0f}\\%" if ramp_rows else "")))
    if d["first_operate"]:
        sched_rows.append(("Steady operation (yield at or above 90\\%)", f"from {qname(d['first_operate']['q'])}"))
    else:
        sched_rows.append(("Steady operation", "not reached in the recorded quarters"))
    sched_rows.append(("Last recorded quarter", f"{qname(last['q'])} ({'bankrupt' if d['bankrupt'] else 'end of game'})"))
    sched_table = "\n".join(f"{k} & {v} \\\\" for k, v in sched_rows)
    slip = build_n - plan_q
    grid_shock = any(norm_phrase(s) == "the utility quotes the connection" for s in req["shock_list"])
    tools_shock = any(norm_phrase(s) == "your equipment ships late" for s in req["shock_list"])
    sched_prose = (f"The ledger shows {build_n} build quarters against a plan of {stage['buildQ']} plus up to {state['gridQ']} for the grid, "
                   + (f"so the build ran {slip} quarter{'s' if slip != 1 else ''} longer than the worst planned case. " if slip > 0 else
                      f"so the plant started {abs(slip)} quarter{'s' if abs(slip) != 1 else ''} inside the worst planned case. " if slip < 0 else
                      "which is the worst planned case exactly. ")
                   + ("Both the equipment delay and the utility's connection quote came up; the decisions on them are in the risk register and between them they set the start date. " if (tools_shock and grid_shock) else
                      "The equipment delay came up and the decision on it, in the risk register, set the start date. " if tools_shock else
                      "The utility's connection quote came up and the decision on it, in the risk register, set the start date. " if grid_shock else
                      "Neither the equipment nor the grid event came up in this run. ")
                   + (f"The game counts the quarter in which first product comes off the line as the last build quarter, so sales begin the quarter after, "
                      f"at {d['first_ramp']['yield']:.0f}\\% yield and 30\\% utilisation; the plant moves to steady operation once yield reaches 90\\%. "
                      if d["first_ramp"] else "")
                   + "Phase, yield and utilisation by quarter are in Table~\\ref{tab:ledger}.")

    # ---- ledger table ----------------------------------------------------------------------------------
    led_rows = "\n".join(
        f"{qname(r['q'])} & {r['phase']} & {money(r['cash'], 1)} & {money(r['debt'], 1)} & "
        + (f"{r['price']:.1f} & {r['uc']:.1f} & {r['yield']:.0f} & {r['util']:.0f} & {money(r['profit'], 1)}" if not r["econ_build"] else
           f"{r['price']:.1f} & {r['uc']:.1f} & {r['yield']:.0f} & -- & --" if r["yield"] > 0 else f"{r['price']:.1f} & {r['uc']:.1f} & -- & -- & --")
        + f" & {r['book']:.0f} \\\\" for r in L)

    # ---- unit economics --------------------------------------------------------------------------------
    ue_rows = "\n".join(
        f"{qname(r['q'])} & {r['price']:.1f} & {r['uc']:.1f} & {money(r['gm_c'], 1)} & {money(r['gm_c'] / r['price'] * 100 if r['price'] else 0)}\\% & {r['credit_c']:.1f} & {money(r['cm_c'], 1)} & {r['units'] / 1e9:.3f} & {money(r['profit'], 1)} \\\\"
        for r in d["producing"]) or "\\multicolumn{9}{l}{The plant never produced, so there are no selling quarters.} \\\\"
    if d["credit_implied"] is not None:
        nominal = d["credit_nominal"]
        diff = d["credit_implied"] - nominal
        if abs(diff) <= 0.6:
            cred_line = (f"Reconciling the ledger with this formula gives an implied credit of {d['credit_implied']:.1f} {cents} against the nominal "
                         f"{nominal:.1f} averaged over the same quarters, so the credit stayed in place and the fixed-cost rule holds for the recorded quarters.")
        elif d["credit_implied"] < 0.6:
            cred_line = (f"Reconciling the ledger with this formula gives an implied credit near zero ({d['credit_implied']:.1f} {cents}) against the nominal "
                         f"{nominal:.1f}, which points to the 45X credit being lost under the prohibited-foreign-entity rule; the ledger does not record that flag directly, "
                         f"so the credit is taken as zero in Table~\\ref{{tab:ue}}, the breakeven and the sensitivities.")
        else:
            cred_line = (f"Reconciling the ledger with this formula gives an implied credit of {d['credit_implied']:.1f} {cents} against the nominal "
                         f"{nominal:.1f}; the gap means something the ledger does not record moved (the credit flag, nameplate after a used-tools purchase, or a cap on utilisation).")
    else:
        cred_line = ""
    def be_fmt(x):
        return f"{x:.0f}\\%" if x <= 100 else f"above 100\\% ({x:.0f}\\%, so no utilisation breaks even)"
    if d["be_util"] is not None and last and d["credit_lost"]:
        be_line = f"At the final quarter's price, cost and yield the breakeven utilisation without the credit is {be_fmt(d['be_util'])}; the plant ran at {last['util']:.0f}\\%."
    elif d["be_util"] is not None and last:
        be_line = (f"At the final quarter's price, cost and yield the breakeven utilisation is {be_fmt(d['be_util'])} with the credit"
                   + (f" and {be_fmt(d['be_util_nocredit'])} without it" if d["be_util_nocredit"] is not None else " and there is none without it, since price does not cover unit cost")
                   + f"; the plant ran at {last['util']:.0f}\\%.")
    elif last and not last["econ_build"]:
        be_line = "At the final quarter's price and cost the contribution per unit is at or below zero, so no utilisation breaks even."
    else:
        be_line = "No breakeven can be stated because the plant never produced."
    ue_prose = (f"The game's cost line is material plus conversion per {w}, following the cost-of-goods-sold and minimum-sustainable-price method NREL uses "
                f"for module manufacturing. Material is the stage material cost times the supplier multiplier, and the duty events raise that multiplier; "
                f"conversion is the stage conversion cost times the state labour multiplier, moved by the events on wages and temporary power"
                + (f"; an ingot and wafer plant also pays {0.4:g} cents per {w} for each cent of power price above 7 cents per kWh. " if stage["id"] == "wafer" else ". ")
                + f"The ledger records price and unit cost at the close of each quarter, so the quarterly result in Table~\\ref{{tab:ledger}} can be rebuilt from them:")
    ue_math = r"""\begin{align}
Q_q &= \frac{U_q}{4}\; u_q\, y_q &&\text{units sold in the quarter} \\
g_q &= p_q - c_q, \qquad g^{+}_q = p_q - c_q + k_q &&\text{margin per unit, without and with the credit} \\
\pi_q &= Q_q\, g^{+}_q - F &&\text{operating result} \\
u^{*} &= \frac{F}{\tfrac{U}{4}\, y\, (p - c + k)} &&\text{breakeven utilisation}
\end{align}
$p_q$ and $c_q$ are the ledger's price and unit cost, $u_q$ and $y_q$ its utilisation and yield, $k_q$ the stage credit (""" + f"{stage['credit'] * 100:g} {cents}" + r""", 75\% of that from Q1 2030) and $F$ the fixed cost from Section~\ref{sec:cap}. """ + cred_line + " " + be_line

    # ---- risk register ---------------------------------------------------------------------------------
    reg_rows = "\n".join(
        f"{qname(r['q'])} & {tex(r['title'])} & {tex(r['decision'])} & {money(r['event_cash'], 1)} & {money(r['dcash'], 1)} \\\\"
        for r in register) or "\\multicolumn{5}{l}{No events recorded.} \\\\"
    reg_prose = ("Each row is one event the run met, in order, with the option taken. The decision column prints the option as the game showed it. "
                 "The event cash column is the part of the quarter's cash change the ledger cannot explain with capex, fixed cost, interest, "
                 "a loan draw or the operating result, so it is the cash the decision itself cost or brought in; a value near zero means the decision "
                 "acted on price, cost, yield, order book or schedule rather than on cash. The last column is the whole change in cash that quarter. "
                 "Rounding in the ledger (one decimal of \\$M) carries into both.")
    if len(register) < len(req["shock_list"]):
        reg_prose += f" {len(req['shock_list']) - len(register)} recorded event(s) could not be placed on a quarter and are listed by title only: " + \
                     tex("; ".join(req["shock_list"][len(register):])) + "."

    # ---- sensitivities ---------------------------------------------------------------------------------
    sens_rows = []
    for label, delta in d["sens"]:
        new_cash = last["cash"] + delta if last else None
        verdict_s = ("above zero" if new_cash >= 0 else "below zero") if new_cash is not None else ""
        sens_rows.append(f"{label} & {money(delta, 1)} & {money(new_cash, 1)} & {verdict_s} \\\\")
    sens_table = "\n".join(sens_rows)
    sens_prose = ("These are arithmetic on the recorded run, not a new simulation. Each case changes one input in every quarter where the plant sold product, "
                  "keeps the recorded utilisation, yield, interest and events, and adds the change in operating result to the final cash. "
                  "A price change moves revenue by $Q_q \\Delta p$; a yield change moves units sold by $\\tfrac{U}{4} u_q \\Delta y$ at the quarter's margin with credit"
                  + (f"; the material case moves the material line, taken as unit cost less the game's conversion cost of {d['conv_c']:.1f} {cents} at the state labour multiplier, by 10\\% in each selling quarter. "
                     if d.get("conv_c") is not None else ". ")
                  + "The game's bankruptcy test, the lender's trigger and the order-book drift are not re-run, so a case that lands above zero says only that the "
                  "closing cash would have been positive on this arithmetic.")

    # ---- assumptions and sources -----------------------------------------------------------------------
    src_keys = list(g["SRC"].keys())
    def cite(keys):
        return ", ".join(f"[{src_keys.index(k) + 1}]" for k in keys if k in src_keys)
    asm_rows = "\n".join(f"{tex(a[0])} & {tex(a[1])} & {cite(a[2])} \\\\ \\addlinespace[3pt]" for a in g["ASSUMPTIONS"])
    asm_rows += f"\n\\addlinespace[1pt] Fixed cost & {g['fixed_rate'] * 100:g} {cents} of nameplate a quarter times the state labour multiplier, half rate during the build (from the game engine) & {cite(['assumption'])} \\\\"
    src_items = "\n".join(f"\\item {tex(v['t'])}. \\url{{{v['u']}}}" for k, v in g["SRC"].items())

    tex_src = PREAMBLE.replace("%COMPANY%", company) + rf"""
% ---- title block ----
\begin{{center}}
{{\footnotesize\textcolor{{soft}}{{FEASIBILITY STUDY}}}}\\[6pt]
{{\LARGE\bfseries {company}}}\\[6pt]
{{\large {tex(config)}}}\\[10pt]
{{\small\textcolor{{soft}}{{{today}}}}}\\[2pt]
{{\small\textcolor{{soft}}{{Prepared from a recorded run of Solar Factory: Survive to 2030 (seed {tex(req['seed'])}, {n_q} quarters)}}}}
\end{{center}}
\vspace{{4pt}}
{{\color{{rule}}\hrule height 0.4pt}}
\vspace{{6pt}}

\section{{Summary}}\label{{sec:sum}}
{summary}

\begin{{small}}
\begin{{longtable}}{{@{{}}L{{0.48\linewidth}}L{{0.47\linewidth}}@{{}}}}
\caption{{Key figures (\$M unless stated)}}\label{{tab:key}} \\
\toprule
\endfirsthead
\toprule
\endhead
\bottomrule
\endfoot
{key_table}
\end{{longtable}}
\end{{small}}

\section{{Site and configuration}}
{site_prose}

\begin{{small}}
\begin{{longtable}}{{@{{}}L{{0.24\linewidth}}L{{0.71\linewidth}}@{{}}}}
\caption{{Configuration as recorded}} \\
\toprule
\endfirsthead
\toprule
\endhead
\bottomrule
\endfoot
{site_table}
\end{{longtable}}
\end{{small}}

\section{{Capital cost and funding}}\label{{sec:cap}}
{cap_prose}

{capex_math}

\begin{{small}}
\begin{{longtable}}{{@{{}}L{{0.42\linewidth}}L{{0.53\linewidth}}@{{}}}}
\caption{{Capital cost and funding}} \\
\toprule
\endfirsthead
\toprule
\endhead
\bottomrule
\endfoot
{cap_table}
\end{{longtable}}
\end{{small}}

{chart(L)}

\section{{Schedule}}
{sched_prose}

\begin{{small}}
\begin{{longtable}}{{@{{}}L{{0.42\linewidth}}L{{0.53\linewidth}}@{{}}}}
\caption{{Schedule, planned and recorded}} \\
\toprule
\endfirsthead
\toprule
\endhead
\bottomrule
\endfoot
{sched_table}
\end{{longtable}}
\end{{small}}

\begin{{footnotesize}}
\begin{{longtable}}{{@{{}}llrrrrrrrr@{{}}}}
\caption{{Quarterly ledger as recorded by the game. Cash and debt at quarter end, \$M; price and cost in {cents}; yield, utilisation and order book in percent; result is the quarter's operating result including the 45X credit.}}\label{{tab:ledger}} \\
\toprule
Quarter & Phase & Cash & Debt & Price & Cost & Yield & Util. & Result & Book \\
\midrule
\endfirsthead
\toprule
Quarter & Phase & Cash & Debt & Price & Cost & Yield & Util. & Result & Book \\
\midrule
\endhead
\bottomrule
\endfoot
{led_rows}
\end{{longtable}}
\end{{footnotesize}}

\section{{Unit economics}}\label{{sec:ue}}
{ue_prose}
{ue_math}

\begin{{footnotesize}}
\begin{{longtable}}{{@{{}}lrrrrrrrr@{{}}}}
\caption{{Unit economics by producing quarter. Price, cost, margins and credit in {cents}; units in {unit}; result in \$M.}}\label{{tab:ue}} \\
\toprule
Quarter & Price & Cost & Margin & Margin \% & Credit & Margin + credit & Units & Result \\
\midrule
\endfirsthead
\toprule
Quarter & Price & Cost & Margin & Margin \% & Credit & Margin + credit & Units & Result \\
\midrule
\endhead
\bottomrule
\endfoot
{ue_rows}
\end{{longtable}}
\end{{footnotesize}}

\section{{Risk register}}\label{{sec:reg}}
{reg_prose}

\begin{{small}}
\begin{{longtable}}{{@{{}}L{{0.09\linewidth}}L{{0.33\linewidth}}L{{0.31\linewidth}}R{{0.08\linewidth}}R{{0.08\linewidth}}@{{}}}}
\caption{{Events met and decisions taken, \$M}}\label{{tab:reg}} \\
\toprule
Quarter & Event & Decision taken & Event cash & Cash change \\
\midrule
\endfirsthead
\toprule
Quarter & Event & Decision taken & Event cash & Cash change \\
\midrule
\endhead
\bottomrule
\endfoot
{reg_rows}
\end{{longtable}}
\end{{small}}

\section{{Sensitivities}}
{sens_prose}

\begin{{small}}
\begin{{longtable}}{{@{{}}L{{0.46\linewidth}}rrl@{{}}}}
\caption{{Final cash under simple what-ifs, \$M. Recorded final cash: {money(last['cash'], 1) if last else 'n/a'} in {qname(last['q']) if last else ''}.}} \\
\toprule
Case & Change in result & Final cash & Closing position \\
\midrule
\endfirsthead
\toprule
Case & Change in result & Final cash & Closing position \\
\midrule
\endhead
\bottomrule
\endfoot
{sens_table}
\end{{longtable}}
\end{{small}}

\section{{Assumptions and sources}}\label{{sec:asm}}
Every number in this study is either a line of the recorded ledger or one of the game's stated assumptions below. The duty rates, credit rules and queue
statistics are public figures with their sources; capex, cost, price and ramp values are rounded benchmarks chosen to make the game playable.

\begin{{small}}
\begin{{longtable}}{{@{{}}L{{0.21\linewidth}}L{{0.60\linewidth}}L{{0.13\linewidth}}@{{}}}}
\caption{{Assumptions used by the game}} \\
\toprule
Item & Value used & Sources \\
\midrule
\endfirsthead
\toprule
Item & Value used & Sources \\
\midrule
\endhead
\bottomrule
\endfoot
{asm_rows}
\end{{longtable}}
\end{{small}}

\subsection{{Sources}}
\begin{{footnotesize}}
\begin{{enumerate}}[leftmargin=2em]
{src_items}
\end{{enumerate}}
\end{{footnotesize}}

\vspace{{10pt}}
{{\color{{rule}}\hrule height 0.4pt}}
\vspace{{6pt}}
{{\footnotesize\color{{soft}} {company} is a fictional company and this study describes a game run, not a real project. The figures are the game's rounded assumptions
and the player's recorded decisions. Not affiliated with or endorsed by any agency or source cited. Not legal, tax, trade or investment advice.
Code MIT; duty data CC BY 4.0 from the US Solar Trade Tracker. Replay this run: \url{{{req['run']}&c={req['choices']}}}}}
\end{{document}}
"""
    return tex_src


# ----------------------------------------------------------------------------------------------------------
def main():
    if len(sys.argv) < 3:
        print(__doc__); sys.exit(1)
    src, outdir = Path(sys.argv[1]), Path(sys.argv[2])
    outdir.mkdir(parents=True, exist_ok=True)
    text = src.read_text(encoding="utf-8") if src.exists() else sys.argv[1]
    req = parse_request(text)
    if not req["ledger"]:
        print("no ledger found in the request; cannot build a report"); sys.exit(2)
    g = game_tables(req)
    d = derive(req, g)
    register, loan_taken = risk_register(req, g, d)
    body = build_tex(req, g, d, register, loan_taken)
    assert "—" not in body, "em dash in report"
    (outdir / "report.tex").write_text(body, encoding="utf-8")
    r = subprocess.run(["latexmk", "-pdf", "-interaction=nonstopmode", "-halt-on-error", "-outdir=" + str(outdir), str(outdir / "report.tex")],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout[-3000:]); print(r.stderr[-1000:]); sys.exit(3)
    print("built", outdir / "report.pdf")


if __name__ == "__main__":
    main()
