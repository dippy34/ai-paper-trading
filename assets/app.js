/* AI Trading Showdown dashboard. Plain JS, no build step.
 *
 * Code + docs are served from this site. Each bot's books live on that bot's own
 * git branch, so they're read from raw.githubusercontent.com (add ?source=local to
 * read ./bots/<id>/ instead when previewing locally).
 */
(() => {
  "use strict";

  const params = new URLSearchParams(location.search);
  const LOCAL = params.get("source") === "local";
  const TZ = "America/New_York";
  const MINUS = "−";

  const S = { config: null, bots: {}, journals: {}, docs: {}, chartMode: "equity", tradeFilter: "all", tradeSearch: "" };
  let lastFetchSig = "";

  // ------------------------------------------------------------------ dom helpers
  function h(tag, attrs, ...kids) {
    const el = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v == null || v === false) continue;
      if (k === "class") el.className = v;
      else if (k === "style") el.setAttribute("style", v);
      else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
      else el.setAttribute(k, v === true ? "" : v);
    }
    for (const kid of kids.flat()) {
      if (kid == null || kid === false) continue;
      el.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
    }
    return el;
  }
  const svgNS = "http://www.w3.org/2000/svg";
  function s(tag, attrs, ...kids) {
    const el = document.createElementNS(svgNS, tag);
    for (const [k, v] of Object.entries(attrs || {})) if (v != null) el.setAttribute(k, v);
    for (const kid of kids.flat()) if (kid != null) el.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
    return el;
  }

  // ------------------------------------------------------------------ formatting
  const usd = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const usd0 = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
  const money = (v) => (v < 0 ? MINUS : "") + usd.format(Math.abs(v));
  const money0 = (v) => (v < 0 ? MINUS : "") + usd0.format(Math.abs(v));
  const signed = (v, f = money) => (v > 0.004 ? "+" : v < -0.004 ? MINUS : "") + f(Math.abs(v)).replace(MINUS, "");
  const pct = (v, d = 2) => (v == null || !isFinite(v) ? "–" : (v > 0.0005 ? "+" : v < -0.0005 ? MINUS : "") + Math.abs(v).toFixed(d) + "%");
  const tone = (v) => (v > 0.004 ? "up" : v < -0.004 ? "down" : "");
  const compactUsd = (v) => {
    const a = Math.abs(v);
    const str = a >= 1e6 ? (a / 1e6).toFixed(2).replace(/\.?0+$/, "") + "M" : a >= 1e3 ? (a / 1e3).toFixed(a >= 1e5 ? 0 : 1).replace(/\.0$/, "") + "k" : a.toFixed(0);
    return (v < 0 ? MINUS : "") + "$" + str;
  };
  const qtyFmt = (q) => (Math.abs(q) >= 1000 ? Math.round(q).toLocaleString("en-US") : Number(q.toFixed(4)).toString());
  const etParts = (d) => Object.fromEntries(
    new Intl.DateTimeFormat("en-US", { timeZone: TZ, year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", weekday: "short", hourCycle: "h23" })
      .formatToParts(d).map((p) => [p.type, p.value])
  );
  const etDateStr = (d) => { const p = etParts(d); return `${p.year}-${p.month}-${p.day}`; };
  const fmtDay = (iso, opts = { weekday: "short", month: "short", day: "numeric" }) =>
    new Date(iso + "T12:00:00Z").toLocaleDateString("en-US", { ...opts, timeZone: "UTC" });
  const fmtTime = (ts) => new Date(ts).toLocaleTimeString("en-US", { timeZone: TZ, hour: "numeric", minute: "2-digit" }) + " ET";
  const esc = (t) => String(t).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  // ------------------------------------------------------------------ theme
  function initTheme() {
    let saved = null;
    try { saved = localStorage.getItem("theme"); } catch (e) { /* storage blocked */ }
    if (saved === "light" || saved === "dark") document.documentElement.dataset.theme = saved;
    document.getElementById("theme-toggle").addEventListener("click", () => {
      const cur = document.documentElement.dataset.theme || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
      const next = cur === "dark" ? "light" : "dark";
      document.documentElement.dataset.theme = next;
      try { localStorage.setItem("theme", next); } catch (e) { /* ignore */ }
      route();
    });
  }

  // ------------------------------------------------------------------ data
  async function fetchText(url) {
    try {
      const r = await fetch(url, { cache: "no-cache" });
      return r.ok ? await r.text() : null;
    } catch (e) {
      return null;
    }
  }
  async function fetchJSON(url, fallback) {
    const t = await fetchText(url);
    if (t == null) return fallback;
    try { return JSON.parse(t); } catch (e) { return fallback; }
  }
  function botUrl(id, path) {
    if (LOCAL) return `bots/${id}/${path}`;
    const b = S.config.bots[id];
    const bust = Math.floor(Date.now() / 60000);
    return `https://raw.githubusercontent.com/${S.config.repo}/refs/heads/${encodeURI(b.branch)}/bots/${id}/${path}?t=${bust}`;
  }

  async function loadBots() {
    const ids = Object.keys(S.config.bots);
    const results = await Promise.all(ids.map(async (id) => {
      const [portfolio, trades, equity, journalIndex, memory] = await Promise.all([
        fetchJSON(botUrl(id, "portfolio.json"), null),
        fetchJSON(botUrl(id, "trades.json"), []),
        fetchJSON(botUrl(id, "equity.json"), []),
        fetchJSON(botUrl(id, "journal/index.json"), []),
        fetchText(botUrl(id, "memory.md")),
      ]);
      return [id, { id, meta: S.config.bots[id], portfolio, trades, equity, journalIndex, memory }];
    }));
    const sig = JSON.stringify(results.map(([, b]) => [b.trades.length, b.equity.length, b.journalIndex.length, b.portfolio && b.portfolio.updated]));
    const changed = sig !== lastFetchSig;
    lastFetchSig = sig;
    S.bots = Object.fromEntries(results);
    return changed;
  }

  // ------------------------------------------------------------------ derived numbers
  const startCash = () => Number(S.config.competition.starting_cash);
  const color = (id) => `var(--${id === "risky" ? "rocket" : "turtle"})`;

  function botStats(b) {
    const start = startCash();
    const eq = b.equity || [];
    const last = eq[eq.length - 1];
    const equity = last ? last.equity : start;
    const closed = b.trades.filter((t) => t.realized_pnl != null);
    const wins = closed.filter((t) => t.realized_pnl > 0).length;
    let peak = start, maxDd = 0;
    for (const e of eq) {
      peak = Math.max(peak, e.equity);
      maxDd = Math.min(maxDd, (e.equity / peak - 1) * 100);
    }
    const lastDate = last ? last.date : null;
    const prevClose = [...eq].reverse().find((e) => e.label === "close" && e.date < (lastDate || ""));
    const ref = prevClose ? prevClose.equity : start;
    const best = closed.reduce((m, t) => (m == null || t.realized_pnl > m.realized_pnl ? t : m), null);
    return {
      equity, last,
      pnl: equity - start,
      ret: (equity / start - 1) * 100,
      dayChange: equity - ref,
      dayPct: (equity / ref - 1) * 100,
      cash: last ? last.cash : start,
      leverage: last && last.leverage != null ? last.leverage : 0,
      trades: b.trades.length,
      winRate: closed.length ? (wins / closed.length) * 100 : null,
      closedCount: closed.length,
      maxDd,
      realized: b.portfolio ? b.portfolio.realized_pnl : 0,
      best,
      status: b.portfolio ? b.portfolio.status : "waiting",
      positions: last ? Object.keys(last.positions || {}).length : 0,
    };
  }

  function timeline() {
    // Evenly spaced "session" axis: Start, then each (date, label) snapshot in time order.
    const keys = new Map();
    for (const b of Object.values(S.bots)) {
      for (const e of b.equity || []) {
        const k = `${e.date}|${e.label}`;
        const prev = keys.get(k);
        if (!prev || e.ts < prev.ts) keys.set(k, { key: k, date: e.date, label: e.label, ts: e.ts });
      }
    }
    const pts = [...keys.values()].sort((a, b) => (a.ts < b.ts ? -1 : 1));
    const start = startCash();
    const series = {};
    for (const [id, b] of Object.entries(S.bots)) {
      const byKey = new Map((b.equity || []).map((e) => [`${e.date}|${e.label}`, e]));
      series[id] = pts.map((p) => (byKey.has(p.key) ? byKey.get(p.key).equity : null));
    }
    let spy0 = null;
    const bench = pts.map((p) => {
      for (const b of Object.values(S.bots)) {
        const e = (b.equity || []).find((x) => `${x.date}|${x.label}` === p.key && x.benchmark);
        if (e) { if (spy0 == null) spy0 = e.benchmark; return start * (e.benchmark / spy0); }
      }
      return null;
    });
    // Prepend the common starting point.
    const startPt = { key: "start", date: S.config.competition.start_date, label: "start", ts: null };
    return {
      points: [startPt, ...pts],
      series: Object.fromEntries(Object.entries(series).map(([id, v]) => [id, [start, ...v]])),
      bench: [start, ...bench],
    };
  }

  function phaseInfo() {
    const c = S.config.competition;
    const now = new Date();
    const today = etDateStr(now);
    const days = (a, b) => {
      let n = 0;
      for (let d = new Date(a + "T12:00:00Z"); d <= new Date(b + "T12:00:00Z"); d.setUTCDate(d.getUTCDate() + 1)) {
        const wd = d.getUTCDay();
        if (wd !== 0 && wd !== 6) n++;
      }
      return n;
    };
    const total = days(c.start_date, c.end_date);
    const p = etParts(now);
    const [wh, wm] = c.wake_time_et.split(":").map(Number);
    // Next wake-up: today if it's a weekday before wake time, else the next weekday.
    let next = null;
    for (let i = 0; i < 8; i++) {
      const d = new Date(today + "T12:00:00Z");
      d.setUTCDate(d.getUTCDate() + i);
      const iso = d.toISOString().slice(0, 10);
      const wd = d.getUTCDay();
      if (wd === 0 || wd === 6 || iso < c.start_date || iso > c.end_date) continue;
      if (i === 0 && (Number(p.hour) > wh || (Number(p.hour) === wh && Number(p.minute) >= wm))) continue;
      next = iso;
      break;
    }
    const finalClose = Object.values(S.bots).some((b) => (b.equity || []).some((e) => e.date === c.end_date && e.label === "close"));
    let phase = "live";
    if (today < c.start_date) phase = "upcoming";
    else if (today > c.end_date || finalClose) phase = "finished";
    const dayNum = phase === "upcoming" ? 0 : days(c.start_date, today < c.end_date ? today : c.end_date);
    const wakeLabel = new Date(`2000-01-01T${c.wake_time_et}:00Z`).toLocaleTimeString("en-US", { timeZone: "UTC", hour: "numeric", minute: "2-digit" });
    return { phase, total, dayNum, next, wakeLabel, today };
  }

  // ------------------------------------------------------------------ chart
  function renderChart(container) {
    const tl = timeline();
    const ids = Object.keys(S.bots);
    const mode = S.chartMode;
    const start = startCash();
    const conv = (v) => (v == null ? null : mode === "equity" ? v : (v / start - 1) * 100);
    const lines = [
      ...ids.map((id) => ({ id, name: `${S.bots[id].meta.emoji} ${S.bots[id].meta.name}`, short: S.bots[id].meta.name, color: color(id), vals: tl.series[id].map(conv), width: 2 })),
      { id: "bench", name: "S&P 500 (SPY)", short: "S&P 500", color: "var(--bench)", vals: tl.bench.map(conv), width: 1.5 },
    ];
    container.textContent = "";
    if (tl.points.length < 2) {
      container.append(h("div", { class: "chart-empty" }, "📉📈 The chart starts after the bots' first trading session. Check back after the first wake-up!"));
      return;
    }
    const W = Math.max(320, Math.round(container.clientWidth || 800));
    const narrow = W < 560;
    const H = narrow ? 240 : 300;
    const m = { l: narrow ? 46 : 60, r: narrow ? 12 : 92, t: 14, b: 28 };
    const iw = W - m.l - m.r, ih = H - m.t - m.b;
    const all = lines.flatMap((l) => l.vals).filter((v) => v != null);
    const base = mode === "equity" ? start : 0;
    let lo = Math.min(base, ...all), hi = Math.max(base, ...all);
    const span = hi - lo || (mode === "equity" ? start * 0.01 : 1);
    lo -= span * 0.08; hi += span * 0.08;
    const step = niceStep((hi - lo) / 5);
    lo = Math.floor(lo / step) * step; hi = Math.ceil(hi / step) * step;
    const n = tl.points.length;
    const x = (i) => m.l + (n === 1 ? iw / 2 : (i / (n - 1)) * iw);
    const y = (v) => m.t + ih - ((v - lo) / (hi - lo)) * ih;
    const fmtY = mode === "equity" ? compactUsd : (v) => (v > 0 ? "+" : v < 0 ? MINUS : "") + Math.abs(v).toFixed(step < 1 ? 1 : 0) + "%";

    const svg = s("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": "Account value over time for each trader and the S&P 500", tabindex: "0" });
    for (let v = lo; v <= hi + step / 2; v += step) {
      svg.append(s("line", { class: "gridline", x1: m.l, x2: W - m.r, y1: y(v), y2: y(v) }));
      svg.append(s("text", { class: "tick", x: m.l - 8, y: y(v) + 4, "text-anchor": "end" }, fmtY(v)));
    }
    svg.append(s("line", { class: "baseline", x1: m.l, x2: W - m.r, y1: y(base), y2: y(base) }));
    // x ticks: first point of each date, thinned to fit.
    const firsts = [];
    tl.points.forEach((p, i) => { if (i > 0 && (!firsts.length || tl.points[firsts[firsts.length - 1]].date !== p.date)) firsts.push(i); });
    const minGap = narrow ? 52 : 64;
    let lastX = -Infinity;
    svg.append(s("text", { class: "tick", x: x(0), y: H - 8, "text-anchor": "start" }, "Start"));
    lastX = x(0) + 20;
    for (const i of firsts) {
      if (x(i) - lastX < minGap) continue;
      svg.append(s("text", { class: "tick", x: x(i), y: H - 8, "text-anchor": "middle" }, fmtDay(tl.points[i].date, { month: "short", day: "numeric" })));
      lastX = x(i);
    }
    // lines (benchmark first so the bots draw on top)
    const ordered = [lines[lines.length - 1], ...lines.slice(0, -1)];
    for (const l of ordered) {
      let d = "", pen = false;
      l.vals.forEach((v, i) => {
        if (v == null) return;
        d += `${pen ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`;
        pen = true;
      });
      svg.append(s("path", { d, fill: "none", stroke: l.color, "stroke-width": l.width, "stroke-linejoin": "round", "stroke-linecap": "round" }));
    }
    // end dots + direct labels (dropped where they would collide; legend + tooltip carry identity)
    const ends = lines.map((l) => {
      let i = l.vals.length - 1;
      while (i >= 0 && l.vals[i] == null) i--;
      return i >= 0 ? { l, i, v: l.vals[i], yy: y(l.vals[i]) } : null;
    }).filter(Boolean);
    for (const e of ends) {
      svg.append(s("circle", { cx: x(e.i), cy: e.yy, r: 4, fill: e.l.color, stroke: "var(--surface)", "stroke-width": 2 }));
    }
    if (!narrow) {
      const shown = ends.filter((e) => !ends.some((o) => o !== e && Math.abs(o.yy - e.yy) < 26 && (e.l.id === "bench" || o.l.id !== "bench")));
      for (const e of shown) {
        svg.append(s("text", { class: "endlabel", x: x(e.i) + 9, y: e.yy - 2 }, e.l.short));
        svg.append(s("text", { class: "tick", x: x(e.i) + 9, y: e.yy + 11 }, mode === "equity" ? compactUsd(e.v) : fmtY(e.v)));
      }
    }
    // hover layer: crosshair snaps to the nearest snapshot, one tooltip lists every series
    const cross = s("line", { class: "crosshair", y1: m.t, y2: m.t + ih, visibility: "hidden" });
    const hoverDots = lines.map((l) => s("circle", { r: 4, fill: l.color, stroke: "var(--surface)", "stroke-width": 2, visibility: "hidden" }));
    svg.append(cross, ...hoverDots);
    const tip = h("div", { class: "tooltip", hidden: true });
    let cur = null;
    const show = (i) => {
      cur = i;
      const p = tl.points[i];
      cross.setAttribute("x1", x(i)); cross.setAttribute("x2", x(i)); cross.setAttribute("visibility", "visible");
      tip.textContent = "";
      tip.append(h("div", { class: "t-date" }, p.key === "start" ? `Start · ${fmtDay(p.date)}` : `${fmtDay(p.date)} · ${p.label === "close" ? "market close" : p.label === "morning" ? "after morning trades" : p.label}`));
      lines.forEach((l, j) => {
        const v = l.vals[i];
        if (v == null) { hoverDots[j].setAttribute("visibility", "hidden"); return; }
        hoverDots[j].setAttribute("cx", x(i)); hoverDots[j].setAttribute("cy", y(v)); hoverDots[j].setAttribute("visibility", "visible");
        const shownVal = mode === "equity" ? `${money0(v)} (${pct((v / start - 1) * 100)})` : pct(v);
        tip.append(h("div", { class: "t-row" }, h("span", { class: "t-name" }, h("span", { class: "key", style: `--k:${l.color}` }), l.name), h("b", {}, shownVal)));
      });
      tip.hidden = false;
      const box = container.getBoundingClientRect();
      const px = (x(i) / W) * box.width;
      const tw = tip.offsetWidth;
      tip.style.left = `${Math.min(Math.max(0, px + 12 + tw > box.width ? px - tw - 12 : px + 12), Math.max(0, box.width - tw))}px`;
      tip.style.top = `${m.t}px`;
    };
    const hide = () => { cur = null; tip.hidden = true; cross.setAttribute("visibility", "hidden"); hoverDots.forEach((d) => d.setAttribute("visibility", "hidden")); };
    svg.addEventListener("pointermove", (ev) => {
      const r = svg.getBoundingClientRect();
      const px = ((ev.clientX - r.left) / r.width) * W;
      const i = Math.round(((px - m.l) / iw) * (n - 1));
      show(Math.max(0, Math.min(n - 1, i)));
    });
    svg.addEventListener("pointerleave", hide);
    svg.addEventListener("blur", hide);
    svg.addEventListener("focus", () => show(n - 1));
    svg.addEventListener("keydown", (ev) => {
      if (ev.key === "ArrowLeft") { show(Math.max(0, (cur ?? n - 1) - 1)); ev.preventDefault(); }
      if (ev.key === "ArrowRight") { show(Math.min(n - 1, (cur ?? 0) + 1)); ev.preventDefault(); }
    });
    container.append(svg, tip);
  }

  function niceStep(raw) {
    const p = Math.pow(10, Math.floor(Math.log10(raw)));
    const f = raw / p;
    return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10) * p;
  }

  function chartTable() {
    const tl = timeline();
    const ids = Object.keys(S.bots);
    const rows = tl.points.map((p, i) => h("tr", {},
      h("td", {}, p.key === "start" ? "Start" : `${fmtDay(p.date)} · ${p.label}`),
      ids.map((id) => h("td", { class: "r" }, tl.series[id][i] == null ? "–" : money(tl.series[id][i]))),
      h("td", { class: "r" }, tl.bench[i] == null ? "–" : money(tl.bench[i])),
    ));
    return h("details", { class: "table-view" },
      h("summary", {}, "Show the numbers as a table"),
      h("div", { class: "table-wrap" }, h("table", {},
        h("thead", {}, h("tr", {}, h("th", {}, "Snapshot"), ids.map((id) => h("th", { class: "r" }, S.bots[id].meta.name)), h("th", { class: "r" }, "S&P 500 equivalent"))),
        h("tbody", {}, rows))));
  }

  // ------------------------------------------------------------------ views
  function viewScoreboard() {
    const ids = Object.keys(S.bots);
    const stats = Object.fromEntries(ids.map((id) => [id, botStats(S.bots[id])]));
    const ph = phaseInfo();
    const started = ids.some((id) => S.bots[id].equity.length || S.bots[id].trades.length);
    const [a, b] = ids;
    const diff = stats[a].equity - stats[b].equity;
    const leader = Math.abs(diff) < 0.005 ? null : diff > 0 ? a : b;

    let bannerText;
    if (!started) {
      bannerText = [h("span", { class: "big" }, "⏰"), h("div", {}, h("strong", {}, "Both traders are asleep, waiting for their first wake-up call."),
        h("div", { class: "ink2" }, ph.next ? `First bell: ${fmtDay(ph.next)} at ${ph.wakeLabel} ET. They wake up at the same moment and can't see each other's work.` : ""))];
    } else if (!leader) {
      bannerText = [h("span", { class: "big" }, "🤝"), h("strong", {}, "Dead even so far.")];
    } else {
      const lb = S.bots[leader].meta;
      bannerText = [h("span", { class: "big" }, ph.phase === "finished" ? "🏆" : lb.emoji),
        h("div", {}, h("strong", {}, `${lb.name} ${ph.phase === "finished" ? "wins" : "leads"} by ${money(Math.abs(diff))}`),
          h("div", { class: "ink2" }, ph.phase === "finished" ? "Final results are in." : ph.next ? `Next wake-up: ${fmtDay(ph.next)} at ${ph.wakeLabel} ET.` : ""))];
    }

    const cards = ids.map((id) => {
      const bot = S.bots[id], st = stats[id], meta = bot.meta;
      const isLeader = leader === id;
      return h("article", { class: "card bot-card", style: `--c:${color(id)}` },
        h("div", { class: "bot-head" },
          h("span", { class: "bot-emoji", "aria-hidden": "true" }, meta.emoji),
          h("div", {}, h("div", { class: "bot-name" }, `${meta.name}`), h("div", { class: "bot-tag" }, `${id === "risky" ? "The risky one" : "The safe one"} · ${meta.tagline}`)),
          isLeader ? h("span", { class: "crown" }, ph.phase === "finished" ? "🏆 Winner" : "👑 Leading") : st.status === "bankrupt" ? h("span", { class: "crown" }, "💀 Busted") : null),
        h("div", { class: "hero" }, money(st.equity)),
        h("div", { class: `hero-delta ${tone(st.pnl)}` }, `${signed(st.pnl)} (${pct(st.ret)})`, h("span", { class: "muted" }, " all-time")),
        h("div", { class: "stats" },
          stat("Since last close", h("span", { class: tone(st.dayChange) }, `${signed(st.dayChange, money0)} (${pct(st.dayPct)})`)),
          stat("Cash", money0(st.cash)),
          stat("Leverage", `${st.leverage.toFixed(2)}x`),
          stat("Trades", `${st.trades}`),
          stat("Win rate", st.winRate == null ? "–" : `${st.winRate.toFixed(0)}% of ${st.closedCount}`),
          stat("Max drawdown", pct(st.maxDd, 1)),
        ));
    });

    const chartBox = h("div", { class: "chart" });
    const seg = h("div", { class: "seg", role: "group", "aria-label": "Chart units" },
      ["equity", "return"].map((mde) => h("button", { type: "button", class: S.chartMode === mde ? "on" : "", onclick: () => { S.chartMode = mde; route(); } }, mde === "equity" ? "$ value" : "% return")));
    const legend = h("div", { class: "legend" },
      ids.map((id) => h("span", {}, h("span", { class: "key", style: `--k:${color(id)}` }), `${S.bots[id].meta.emoji} ${S.bots[id].meta.name}`)),
      h("span", {}, h("span", { class: "key", style: "--k:var(--bench)" }), "S&P 500 (SPY), same $100k"));

    const app = document.getElementById("app");
    app.textContent = "";
    app.append(
      h("section", { class: "card banner" }, bannerText),
      h("section", { class: "versus" }, cards),
      h("section", { class: "card chart-card" },
        h("div", { class: "chart-head" }, h("h3", {}, "Account value"), seg),
        legend, chartBox, chartTable()),
      h("h2", { class: "section" }, "Open positions", h("span", { class: "muted" }, "as of each trader's latest snapshot")),
      h("section", { class: "versus" }, ids.map((id) => positionsCard(id))),
      h("h2", { class: "section" }, "Latest trades", h("a", { href: "#/trades" }, "see all →")),
      tradesTable(allTrades().slice(0, 8)),
    );
    requestAnimationFrame(() => renderChart(chartBox));
  }

  function stat(label, value) {
    return h("div", { class: "stat" }, h("div", { class: "label" }, label), h("div", { class: "value" }, value));
  }

  function positionsCard(id) {
    const bot = S.bots[id];
    const last = bot.equity[bot.equity.length - 1];
    const port = bot.portfolio || { positions: {} };
    const pos = last ? last.positions || {} : {};
    const equity = last ? last.equity : startCash();
    const rows = Object.entries(pos).sort((a, b) => Math.abs(b[1].value) - Math.abs(a[1].value)).map(([sym, p]) => {
      const avg = port.positions && port.positions[sym] ? port.positions[sym].avg_price : null;
      const pnl = avg != null ? (p.price - avg) * p.qty : null;
      const pnlPct = avg ? ((p.price / avg - 1) * 100) * (p.qty < 0 ? -1 : 1) : null;
      return h("tr", {},
        h("td", {}, h("span", { class: "sym" }, sym), p.qty < 0 ? h("span", { class: "badge short", style: "margin-left:6px" }, "short") : null),
        h("td", { class: "r" }, qtyFmt(p.qty)),
        h("td", { class: "r" }, avg != null ? money(avg) : "–"),
        h("td", { class: "r" }, money(p.price)),
        h("td", { class: "r" }, money0(p.value)),
        h("td", { class: `r ${tone(pnl || 0)}` }, pnl == null ? "–" : `${signed(pnl, money0)}`, h("br"), h("small", {}, pct(pnlPct, 1))),
        h("td", { class: "r" }, equity > 0 ? `${((Math.abs(p.value) / equity) * 100).toFixed(1)}%` : "–"));
    });
    return h("section", { class: "card pos-card", style: `--c:${color(id)}` },
      h("h3", {}, h("span", { class: "dot" }), `${bot.meta.emoji} ${bot.meta.name}`),
      rows.length
        ? h("div", { class: "table-wrap" }, h("table", {},
          h("thead", {}, h("tr", {}, ["Symbol", "Qty", "Avg cost", "Price", "Value", "P&L", "Weight"].map((t, i) => h("th", { class: i ? "r" : "" }, t)))),
          h("tbody", {}, rows)))
        : h("p", { class: "empty" }, last ? "All cash. 💵" : "No positions yet."));
  }

  function allTrades() {
    return Object.values(S.bots).flatMap((b) => b.trades.map((t) => ({ ...t, bot: b.id }))).sort((a, b) => (a.ts < b.ts ? 1 : -1));
  }

  function tradesTable(trades) {
    if (!trades.length) return h("p", { class: "card empty" }, "No trades yet. The first orders go in at the first wake-up.");
    return h("div", { class: "card table-wrap" }, h("table", {},
      h("thead", {}, h("tr", {}, ["When", "Trader", "Side", "Symbol", "Qty", "Fill", "Amount", "Realized", "Why"].map((t, i) => h("th", { class: [4, 5, 6, 7].includes(i) ? "r" : "" }, t)))),
      h("tbody", {}, trades.map((t) => {
        const meta = S.bots[t.bot] ? S.bots[t.bot].meta : { name: t.bot, emoji: "" };
        return h("tr", {},
          h("td", { class: "num", style: "white-space:nowrap" }, fmtDay(t.date, { month: "short", day: "numeric" }), h("br"), h("small", { class: "muted" }, fmtTime(t.ts))),
          h("td", {}, h("span", { class: "who", style: `--c:${color(t.bot)}` }, h("span", { class: "dot" }), meta.name)),
          h("td", {}, h("span", { class: `badge ${t.side}` }, t.side)),
          h("td", {}, h("span", { class: "sym", title: t.name || "" }, t.symbol)),
          h("td", { class: "r" }, qtyFmt(t.qty)),
          h("td", { class: "r" }, money(t.price)),
          h("td", { class: "r" }, money0(t.notional)),
          h("td", { class: `r ${t.realized_pnl == null ? "" : tone(t.realized_pnl)}` }, t.realized_pnl == null ? "–" : signed(t.realized_pnl, money0)),
          h("td", { class: "reason" }, t.reason));
      }))));
  }

  function viewTrades() {
    const app = document.getElementById("app");
    const ids = Object.keys(S.bots);
    const all = allTrades();
    const filtered = all.filter((t) => (S.tradeFilter === "all" || t.bot === S.tradeFilter)
      && (!S.tradeSearch || t.symbol.includes(S.tradeSearch.toUpperCase()) || (t.reason || "").toLowerCase().includes(S.tradeSearch.toLowerCase())));
    const totals = ids.map((id) => {
      const ts = all.filter((t) => t.bot === id);
      const vol = ts.reduce((a, t) => a + t.notional, 0);
      const real = ts.reduce((a, t) => a + (t.realized_pnl || 0), 0);
      return h("span", { class: "who", style: `--c:${color(id)}` }, h("span", { class: "dot" }), `${S.bots[id].meta.name}: ${ts.length} trades · ${money0(vol)} traded · realized ${signed(real, money0)}`);
    });
    const search = h("input", { type: "search", placeholder: "Filter symbol or reason", value: S.tradeSearch, "aria-label": "Filter trades" });
    search.addEventListener("input", () => {
      S.tradeSearch = search.value;
      const pos = search.selectionStart;
      viewTrades();
      const again = document.querySelector(".filters input");
      again.focus(); again.setSelectionRange(pos, pos);
    });
    app.textContent = "";
    app.append(
      h("div", { class: "filters" },
        h("div", { class: "seg", role: "group", "aria-label": "Trader" },
          [["all", "Both"], ...ids.map((id) => [id, `${S.bots[id].meta.emoji} ${S.bots[id].meta.name}`])].map(([k, label]) =>
            h("button", { type: "button", class: S.tradeFilter === k ? "on" : "", onclick: () => { S.tradeFilter = k; viewTrades(); } }, label))),
        search),
      h("p", { class: "note", style: "display:flex;gap:18px;flex-wrap:wrap" }, totals),
      h("div", { style: "height:12px" }),
      tradesTable(filtered),
      h("p", { class: "note" }, "Fills are the live Yahoo Finance price plus/minus 0.05% slippage. \"Realized\" is profit or loss locked in when a position is sold or covered."));
  }

  async function loadJournals(dates) {
    const jobs = [];
    for (const d of dates) for (const id of Object.keys(S.bots)) {
      const k = `${id}|${d}`;
      if (!(k in S.journals) && S.bots[id].journalIndex.includes(d)) {
        jobs.push(fetchText(botUrl(id, `journal/${d}.md`)).then((t) => { S.journals[k] = t; }));
      }
    }
    await Promise.all(jobs);
  }

  async function viewJournals() {
    const app = document.getElementById("app");
    const ids = Object.keys(S.bots);
    const dates = [...new Set(ids.flatMap((id) => S.bots[id].journalIndex))].sort().reverse();
    app.textContent = "";
    app.append(h("p", { class: "note", style: "margin-top:20px" }, "Every trading day each AI writes a journal: how it read the market, what it did and why, and how it feels about it. They wake up at the same time and write these independently. Neither can read the other's."));
    if (!dates.length) { app.append(h("p", { class: "card empty", style: "margin-top:16px" }, "No journal entries yet.")); return; }
    const holder = h("div", {}, h("p", { class: "loading" }, "Loading journals…"));
    app.append(holder);
    await loadJournals(dates);
    holder.textContent = "";
    for (const d of dates) {
      holder.append(h("section", { class: "day-block" },
        h("div", { class: "day-title" }, fmtDay(d, { weekday: "long", month: "long", day: "numeric" })),
        h("div", { class: "side-by-side" }, ids.map((id) => {
          const t = S.journals[`${id}|${d}`];
          const meta = S.bots[id].meta;
          return h("article", { class: `card entry ${t ? "" : "missing"}`, style: `--c:${color(id)}` },
            h("div", { class: "entry-head" }, meta.emoji, ` ${meta.name}`),
            t ? markdown(t, `bots/${id}/journal/`) : h("p", {}, "No entry this day."));
        }))));
    }
  }

  function viewBrains() {
    const app = document.getElementById("app");
    const ids = Object.keys(S.bots);
    app.textContent = "";
    app.append(
      h("p", { class: "note", style: "margin-top:20px" }, "Each trader keeps a private memory file it rereads every morning: theses, watchlists, lessons, grudges against specific stocks. This is the only knowledge it carries from day to day, and it's never shared with the other bot."),
      h("div", { class: "side-by-side", style: "margin-top:16px" }, ids.map((id) => {
        const b = S.bots[id];
        return h("article", { class: "card entry", style: `--c:${color(id)}` },
          h("div", { class: "entry-head" }, `${b.meta.emoji} ${b.meta.name}'s memory`),
          b.memory ? markdown(b.memory, `bots/${id}/`) : h("p", { class: "muted" }, "Empty. This fills in after the first wake-up."),
          h("p", { class: "note" }, h("a", { href: `#/docs/${b.meta.persona}` }, `Read ${b.meta.name}'s persona and rules →`)));
      })));
  }

  async function viewDocs(path) {
    const docs = S.config.docs;
    path = path || docs[0].path;
    const app = document.getElementById("app");
    const nav = h("nav", { class: "card docs-nav", "aria-label": "Documentation" },
      docs.map((d) => h("a", { href: `#/docs/${d.path}`, class: d.path === path ? "active" : "" }, d.title)));
    const body = h("article", { class: "card doc-body" }, h("p", { class: "loading" }, "Loading…"));
    app.textContent = "";
    app.append(h("div", { class: "docs-layout" }, nav, body));
    if (!(path in S.docs)) S.docs[path] = await fetchText(path);
    body.textContent = "";
    const text = S.docs[path];
    if (text == null) body.append(h("p", { class: "empty" }, `Couldn't load ${path}.`));
    else body.append(markdown(text, path.includes("/") ? path.slice(0, path.lastIndexOf("/") + 1) : ""));
    body.append(h("p", { class: "note" }, h("a", { href: `https://github.com/${S.config.repo}/blob/${S.config.code_branch}/${path}` }, "View this file on GitHub →")));
    window.scrollTo(0, 0);
  }

  // ------------------------------------------------------------------ markdown
  function resolvePath(baseDir, rel) {
    const parts = (baseDir + rel).split("/");
    const out = [];
    for (const p of parts) { if (p === "..") out.pop(); else if (p !== "." && p !== "") out.push(p); }
    return out.join("/");
  }

  function markdown(text, baseDir) {
    const div = h("div", { class: "md" });
    if (window.marked && window.DOMPurify) {
      div.innerHTML = window.DOMPurify.sanitize(window.marked.parse(text, { gfm: true, breaks: false }));
    } else {
      div.innerHTML = `<pre>${esc(text)}</pre>`;
    }
    const docPaths = new Set(S.config.docs.map((d) => d.path));
    for (const a of div.querySelectorAll("a[href]")) {
      const href = a.getAttribute("href");
      if (/^(https?:|mailto:|#)/.test(href)) { if (/^https?:/.test(href)) a.target = "_blank"; continue; }
      const [p, frag] = href.split("#");
      const resolved = resolvePath(baseDir, p);
      if (docPaths.has(resolved)) a.setAttribute("href", `#/docs/${resolved}`);
      else { a.setAttribute("href", `https://github.com/${S.config.repo}/blob/${S.config.code_branch}/${resolved}${frag ? "#" + frag : ""}`); a.target = "_blank"; }
    }
    return div;
  }

  // ------------------------------------------------------------------ router
  function route() {
    const hash = location.hash.replace(/^#\/?/, "");
    const [tab, ...rest] = hash.split("/");
    const name = ["scoreboard", "trades", "journals", "brains", "docs"].includes(tab) ? tab : "scoreboard";
    for (const a of document.querySelectorAll(".tabs a")) a.classList.toggle("active", a.dataset.tab === name);
    if (name === "trades") viewTrades();
    else if (name === "journals") viewJournals();
    else if (name === "brains") viewBrains();
    else if (name === "docs") viewDocs(decodeURIComponent(rest.join("/")));
    else viewScoreboard();
  }

  function renderHeader() {
    const c = S.config.competition;
    const ph = phaseInfo();
    document.getElementById("comp-name").textContent = c.name;
    let sub;
    if (ph.phase === "upcoming") sub = `Starts ${fmtDay(c.start_date)} · $${(c.starting_cash / 1000).toFixed(0)}k each`;
    else if (ph.phase === "finished") sub = `🏁 Finished ${fmtDay(c.end_date)} · ${ph.total} trading days`;
    else sub = `Day ${ph.dayNum} of ${ph.total} · ${fmtDay(c.start_date, { month: "short", day: "numeric" })} – ${fmtDay(c.end_date, { month: "short", day: "numeric" })} · $${(c.starting_cash / 1000).toFixed(0)}k each`;
    document.getElementById("comp-sub").textContent = sub;
    document.getElementById("data-source").textContent = LOCAL ? " Data: local files." : " Data refreshes every few minutes.";
  }

  async function boot() {
    initTheme();
    S.config = await fetchJSON("config.json", null);
    if (!S.config) {
      document.getElementById("app").textContent = "Couldn't load config.json.";
      return;
    }
    await loadBots();
    renderHeader();
    route();
    window.addEventListener("hashchange", route);
    let rw = innerWidth;
    window.addEventListener("resize", () => {
      if (Math.abs(innerWidth - rw) < 40) return;
      rw = innerWidth;
      const box = document.querySelector(".chart");
      if (box) renderChart(box);
    });
    setInterval(async () => {
      if (document.hidden) return;
      const changed = await loadBots();
      renderHeader();
      const tab = (location.hash.replace(/^#\/?/, "").split("/")[0]) || "scoreboard";
      if (changed && ["scoreboard", "trades", "brains"].includes(tab)) route();
    }, 5 * 60 * 1000);
  }

  // marked/DOMPurify load with `defer` before this script; boot after DOM is ready either way.
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();
