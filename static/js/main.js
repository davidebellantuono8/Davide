'use strict';

// ── Tab switching ──────────────────────────────────────────────────────────
document.querySelectorAll('.nav-tab').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.nav-tab').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-section').forEach(s => {
      s.classList.remove('active');
      s.classList.add('hidden');
    });
    btn.classList.add('active');
    const target = document.getElementById('tab-' + btn.dataset.tab);
    target.classList.remove('hidden');
    target.classList.add('active');
  });
});

// ── Helpers ────────────────────────────────────────────────────────────────
function fmtMktCap(val) {
  if (!val) return '—';
  if (val >= 1e12) return '$' + (val / 1e12).toFixed(2) + 'T';
  if (val >= 1e9)  return '$' + (val / 1e9).toFixed(2) + 'B';
  if (val >= 1e6)  return '$' + (val / 1e6).toFixed(2) + 'M';
  return '$' + val.toLocaleString();
}

function fmtNum(val, decimals = 2, suffix = '') {
  if (val === null || val === undefined) return '—';
  return Number(val).toFixed(decimals) + suffix;
}

function show(id)  { document.getElementById(id).classList.remove('hidden'); }
function hide(id)  { document.getElementById(id).classList.add('hidden'); }
function setText(id, text) { document.getElementById(id).textContent = text; }

function renderPlotly(divId, jsonData) {
  const fig = JSON.parse(jsonData);
  Plotly.newPlot(divId, fig.data, fig.layout, { responsive: true, displayModeBar: false });
}

// ── RSI / Technical signals ────────────────────────────────────────────────
function buildSignals(data) {
  const signals = [];

  // RSI
  if (data.rsi !== null && data.rsi !== undefined) {
    if (data.rsi > 70)      signals.push({ label: `RSI ${data.rsi} — Overbought`, cls: 'bearish' });
    else if (data.rsi < 30) signals.push({ label: `RSI ${data.rsi} — Oversold`,   cls: 'bullish' });
    else                    signals.push({ label: `RSI ${data.rsi} — Neutral`,     cls: 'neutral' });
  }

  // Price vs 52W
  if (data.current_price && data.w52_high) {
    const pctFromHigh = ((data.current_price - data.w52_high) / data.w52_high * 100).toFixed(1);
    if (Math.abs(pctFromHigh) < 5)
      signals.push({ label: `Near 52W High (${pctFromHigh}%)`, cls: 'bullish' });
    else if (pctFromHigh < -30)
      signals.push({ label: `Far from 52W High (${pctFromHigh}%)`, cls: 'bearish' });
  }

  // Volatility
  if (data.volatility !== null) {
    if (data.volatility > 50)      signals.push({ label: `High Volatility (${data.volatility}%)`, cls: 'bearish' });
    else if (data.volatility < 20) signals.push({ label: `Low Volatility (${data.volatility}%)`,  cls: 'bullish' });
    else                           signals.push({ label: `Moderate Volatility (${data.volatility}%)`, cls: 'neutral' });
  }

  // Sharpe
  if (data.sharpe_ratio !== null) {
    if (data.sharpe_ratio > 1)       signals.push({ label: `Sharpe ${data.sharpe_ratio} — Good Risk/Return`, cls: 'bullish' });
    else if (data.sharpe_ratio < 0)  signals.push({ label: `Sharpe ${data.sharpe_ratio} — Negative Returns`,  cls: 'bearish' });
    else                             signals.push({ label: `Sharpe ${data.sharpe_ratio} — Moderate`,           cls: 'neutral' });
  }

  // P/E
  if (data.pe_ratio) {
    if (data.pe_ratio > 50)     signals.push({ label: `P/E ${data.pe_ratio.toFixed(1)} — Expensive`, cls: 'bearish' });
    else if (data.pe_ratio < 15) signals.push({ label: `P/E ${data.pe_ratio.toFixed(1)} — Value`,    cls: 'bullish' });
    else                         signals.push({ label: `P/E ${data.pe_ratio.toFixed(1)} — Fair`,      cls: 'neutral' });
  }

  const container = document.getElementById('signals');
  if (signals.length === 0) {
    container.innerHTML = '<p style="color:var(--muted)">No signals available.</p>';
    return;
  }
  container.innerHTML = '<div class="signals-grid">' +
    signals.map(s => `<span class="signal ${s.cls}">${s.label}</span>`).join('') +
    '</div>';
}

// ── Analyze form ───────────────────────────────────────────────────────────
document.getElementById('analyze-form').addEventListener('submit', async (e) => {
  e.preventDefault();

  const ticker = document.getElementById('ticker-input').value.trim();
  const period = document.getElementById('period-select').value;

  if (!ticker) return;

  hide('analyze-results');
  hide('analyze-error');
  show('analyze-loader');

  try {
    const res = await fetch('/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ticker, period }),
    });
    const data = await res.json();

    hide('analyze-loader');

    if (!res.ok) {
      document.getElementById('analyze-error').textContent = data.error || 'Unknown error';
      show('analyze-error');
      return;
    }

    // Populate company header
    setText('res-name',   data.name);
    setText('res-ticker', data.ticker);
    setText('res-sector', data.sector || '—');
    setText('res-price',  '$' + data.current_price);

    const changeEl = document.getElementById('res-change');
    const sign = data.price_change >= 0 ? '+' : '';
    changeEl.textContent = `${sign}${data.price_change} (${sign}${data.price_change_pct}%)`;
    changeEl.className = 'change ' + (data.price_change >= 0 ? 'positive' : 'negative');

    // KPIs
    setText('kpi-mktcap', fmtMktCap(data.market_cap));
    setText('kpi-pe',     fmtNum(data.pe_ratio));
    setText('kpi-fpe',    fmtNum(data.forward_pe));
    setText('kpi-pb',     fmtNum(data.pb_ratio));
    setText('kpi-eps',    fmtNum(data.eps));
    setText('kpi-div',    data.dividend_yield + '%');
    setText('kpi-beta',   fmtNum(data.beta));
    setText('kpi-52h',    '$' + data.w52_high);
    setText('kpi-52l',    '$' + data.w52_low);
    setText('kpi-vol',    data.volatility + '%');
    setText('kpi-sharpe', data.sharpe_ratio);
    setText('kpi-rsi',    data.rsi);

    // Charts
    renderPlotly('price-chart',  data.chart_json);
    renderPlotly('volume-chart', data.vol_chart_json);

    // Signals
    buildSignals(data);

    show('analyze-results');
  } catch (err) {
    hide('analyze-loader');
    document.getElementById('analyze-error').textContent = 'Network error: ' + err.message;
    show('analyze-error');
  }
});

// ── Compare form ───────────────────────────────────────────────────────────
document.getElementById('compare-form').addEventListener('submit', async (e) => {
  e.preventDefault();

  const tickers = document.getElementById('compare-input').value.trim();
  const period  = document.getElementById('compare-period').value;

  if (!tickers) return;

  hide('compare-results');
  hide('compare-error');
  show('compare-loader');

  try {
    const res = await fetch('/compare', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tickers, period }),
    });
    const data = await res.json();

    hide('compare-loader');

    if (!res.ok) {
      document.getElementById('compare-error').textContent = data.error || 'Unknown error';
      show('compare-error');
      return;
    }

    renderPlotly('compare-chart', data.chart_json);
    show('compare-results');
  } catch (err) {
    hide('compare-loader');
    document.getElementById('compare-error').textContent = 'Network error: ' + err.message;
    show('compare-error');
  }
});
