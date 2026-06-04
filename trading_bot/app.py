from flask import Flask, render_template_string, jsonify, request
import threading
import time
import sys, uuid, os, json
from datetime import datetime
import pandas as pd
from nse_scanner import scan_all as scan_market
from papa_scanner import scan_all_papa
from backtest import get_daily_picks

app = Flask(__name__)
scans = {}

BASE_CSS = """
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif; background:#0f172a; color:#e2e8f0; padding:20px; }
.container { max-width:1500px; margin:0 auto; }
h1 { font-size:2rem; margin-bottom:4px; background:linear-gradient(135deg,#22d3ee,#818cf8); -webkit-background-clip:text; -webkit-text-fill-color:transparent; }
.subtitle { color:#94a3b8; margin-bottom:24px; font-size:14px; }
.tabs { display:flex; gap:4px; margin-bottom:24px; background:#1e293b; border-radius:12px; padding:4px; }
.tab { padding:10px 24px; border-radius:8px; border:none; background:transparent; color:#94a3b8; font-size:14px; font-weight:600; cursor:pointer; transition:all 0.2s; text-decoration:none; }
.tab:hover { color:#e2e8f0; }
.tab.active { background:linear-gradient(135deg,#22d3ee,#818cf8); color:#0f172a; }
.hero { background:linear-gradient(135deg,rgba(34,211,238,0.05),rgba(129,140,248,0.05)); border:1px solid #334155; border-radius:16px; padding:32px; text-align:center; margin-bottom:24px; }
.hero h2 { font-size:1.3rem; margin-bottom:8px; }
.hero p { color:#94a3b8; font-size:13px; max-width:650px; margin:0 auto 20px; line-height:1.6; }
.scan-btn { padding:14px 48px; border-radius:12px; border:none; background:linear-gradient(135deg,#22d3ee,#818cf8); color:#0f172a; font-weight:700; cursor:pointer; font-size:16px; transition:all 0.2s; letter-spacing:0.3px; }
.scan-btn:hover { transform:translateY(-1px); opacity:0.95; }
.scan-btn:disabled { opacity:0.4; cursor:not-allowed; transform:none; }
.overlay { display:none; position:fixed; top:0; left:0; right:0; bottom:0; background:rgba(15,23,42,0.92); z-index:999; justify-content:center; align-items:center; flex-direction:column; }
.overlay.show { display:flex; }
.loader { width:60px; height:60px; border:4px solid #334155; border-top:4px solid #818cf8; border-radius:50%; animation:spin 0.8s linear infinite; }
.loader-text { margin-top:20px; color:#e2e8f0; font-size:18px; font-weight:600; }
.loader-sub { margin-top:6px; color:#64748b; font-size:13px; }
.scan-progress { margin-top:24px; width:400px; }
.scan-progress-track { width:100%; height:8px; background:#1e293b; border-radius:4px; overflow:hidden; }
.scan-progress-bar { height:100%; width:0%; background:linear-gradient(90deg,#22d3ee,#818cf8); border-radius:4px; transition:width 0.3s ease; }
.scan-stats { display:flex; justify-content:space-between; margin-top:10px; font-size:13px; color:#64748b; }
.scan-stats .num { color:#e2e8f0; font-weight:600; }
@keyframes spin { 0%{transform:rotate(0deg)} 100%{transform:rotate(360deg)} }
.results { display:none; }
.results.show { display:block; }
.summary-cards { display:grid; grid-template-columns:repeat(auto-fill,minmax(170px,1fr)); gap:10px; margin-bottom:20px; }
.summary-card { background:#1e293b; border:1px solid #334155; border-radius:12px; padding:14px; text-align:center; }
.summary-card .label { font-size:10px; color:#64748b; text-transform:uppercase; letter-spacing:0.5px; }
.summary-card .value { font-size:20px; font-weight:700; margin-top:4px; }
.dot-big { font-size:26px; letter-spacing:3px; }
table { width:100%; border-collapse:collapse; margin-bottom:16px; background:#1e293b; border-radius:12px; overflow:hidden; font-size:12px; }
th { text-align:left; padding:9px 10px; background:#334155; font-weight:600; font-size:10px; text-transform:uppercase; letter-spacing:0.05em; color:#94a3b8; }
td { padding:9px 10px; border-top:1px solid #334155; }
tr:hover td { background:#1a2332; }
.text-right { text-align:right; }
.dot-display { display:inline-flex; gap:2px; font-size:16px; padding:2px 6px; border-radius:4px; background:#0f172a; }
.sig-STRONG_BUY { color:#86efac; background:#166534; padding:2px 8px; border-radius:20px; font-weight:600; font-size:10px; white-space:nowrap; }
.sig-BUY { color:#a3e635; background:#14532d; padding:2px 8px; border-radius:20px; font-weight:600; font-size:10px; white-space:nowrap; }
.sig-HOLD { color:#fde047; background:#713f12; padding:2px 8px; border-radius:20px; font-weight:600; font-size:10px; white-space:nowrap; }
.sig-SELL { color:#fca5a5; background:#7f1d1d; padding:2px 8px; border-radius:20px; font-weight:600; font-size:10px; white-space:nowrap; }
.sig-AVOID { color:#fecaca; background:#991b1b; padding:2px 8px; border-radius:20px; font-weight:600; font-size:10px; white-space:nowrap; }
.sig-WAIT { color:#94a3b8; background:#334155; padding:2px 8px; border-radius:20px; font-weight:600; font-size:10px; white-space:nowrap; }
.sig-ALERT { color:#fde047; background:#78350f; padding:2px 8px; border-radius:20px; font-weight:600; font-size:10px; white-space:nowrap; }
.score-bar { height:3px; border-radius:2px; margin-top:3px; background:#1e293b; overflow:hidden; }
.score-bar-fill { height:100%; border-radius:2px; }
.grade-bar { display:flex; height:22px; border-radius:4px; overflow:hidden; margin-top:8px; }
.grade-seg { display:flex; align-items:center; justify-content:center; font-size:9px; font-weight:700; color:#0f172a; }
.gear-badge { display:inline-block; padding:1px 8px; border-radius:10px; font-size:10px; font-weight:600; white-space:nowrap; }
.timestamp { color:#64748b; font-size:12px; margin-top:12px; text-align:center; }
.disclaimer { margin-top:24px; padding:16px; border-radius:8px; background:#1e293b; border:1px solid #334155; font-size:12px; color:#64748b; text-align:center; line-height:1.6; }
.cheat-sheet { background:#1e293b; border:1px solid #334155; border-radius:12px; padding:20px; margin-top:24px; }
.cheat-sheet h3 { color:#f59e0b; font-size:14px; margin-bottom:12px; }
.cheat-sheet .dot-row { display:flex; align-items:center; gap:12px; padding:5px 0; font-size:12px; border-bottom:1px solid #0f172a; }
.cheat-sheet .dot-row:last-child { border-bottom:none; }
.cheat-sheet .dot-desc { color:#94a3b8; font-size:11px; }
.col-g { color:#4ade80; } .col-y { color:#fde047; } .col-r { color:#f87171; }
.checklist-popup { display:none; position:fixed; top:50%; left:50%; transform:translate(-50%,-50%); background:#1e293b; border:1px solid #334155; border-radius:16px; padding:24px; z-index:1000; max-width:500px; width:90%; max-height:80vh; overflow-y:auto; }
.checklist-popup.show { display:block; }
.checklist-popup h3 { margin-bottom:12px; color:#f59e0b; }
.checklist-popup .item { padding:6px 0; border-bottom:1px solid #0f172a; font-size:13px; display:flex; align-items:center; gap:8px; }
.checklist-popup .item:last-child { border-bottom:none; }
.checklist-overlay { display:none; position:fixed; top:0; left:0; right:0; bottom:0; background:rgba(0,0,0,0.6); z-index:999; }
.checklist-overlay.show { display:block; }
.chk-yes { color:#4ade80; } .chk-no { color:#f87171; }
.check-col { cursor:pointer; text-decoration:underline dotted #64748b; }
.methods-box { background:#0f172a; border:1px solid #334155; border-radius:12px; padding:16px; margin-bottom:20px; font-size:12px; line-height:1.7; }
.methods-box strong { color:#f59e0b; }
.papa-hero { background:linear-gradient(135deg,rgba(245,158,11,0.05),rgba(249,115,22,0.05)); border:1px solid #334155; border-radius:16px; padding:32px; text-align:center; margin-bottom:24px; }
.papa-hero h2 { color:#f59e0b; }
.papa-btn { background:linear-gradient(135deg,#f59e0b,#f97316); }
.papa-h1 { background:linear-gradient(135deg,#f59e0b,#f97316); -webkit-background-clip:text; -webkit-text-fill-color:transparent; }

/* Sortable tables */
.data-table th.sortable { cursor:pointer; user-select:none; }
.data-table th.sortable:hover { background:#334155; }
.data-table th.sort-asc::after { content:" ▲"; font-size:10px; }
.data-table th.sort-desc::after { content:" ▼"; font-size:10px; }

/* Filter bar */
.filter-bar { display:flex; gap:8px; margin-bottom:12px; flex-wrap:wrap; align-items:center; }
.filter-bar input, .filter-bar select {
    background:#1e293b; border:1px solid #334155; border-radius:6px;
    padding:5px 10px; color:#e2e8f0; font-size:12px; outline:none;
}
.filter-bar input:focus, .filter-bar select:focus { border-color:#3b82f6; }
.filter-bar label { color:#94a3b8; font-size:11px; display:flex; align-items:center; gap:4px; white-space:nowrap; }

/* Column toggle dropdown */
.col-toggle { position:relative; display:inline-block; }
.col-toggle-btn { background:#1e293b; border:1px solid #334155; border-radius:6px; padding:5px 10px; color:#94a3b8; font-size:12px; cursor:pointer; }
.col-toggle-btn:hover { border-color:#3b82f6; }
.col-toggle-menu { display:none; position:absolute; top:100%; right:0; background:#1e293b; border:1px solid #334155; border-radius:8px; padding:8px; z-index:100; min-width:160px; margin-top:4px; }
.col-toggle-menu label { display:flex; align-items:center; gap:6px; padding:3px 6px; font-size:12px; color:#e2e8f0; cursor:pointer; white-space:nowrap; }
.col-toggle-menu label:hover { background:#334155; border-radius:4px; }
.col-toggle-menu input[type=checkbox] { accent-color:#3b82f6; }
.col-toggle.open .col-toggle-menu { display:block; }

/* Portfolio sidebar */
.sidebar { width:300px; min-width:300px; background:#1e293b; border-radius:12px; padding:16px; height:fit-content; max-height:calc(100vh - 40px); overflow-y:auto; position:sticky; top:20px; }
.sidebar h3 { font-size:14px; color:#f59e0b; margin-bottom:12px; }
.sidebar .sect { margin-bottom:14px; padding-bottom:12px; border-bottom:1px solid #334155; }
.sidebar .sect:last-child { border-bottom:none; margin-bottom:0; }
.hold-form { display:grid; grid-template-columns:1fr 1fr; gap:6px; margin-bottom:8px; }
.hold-form input { background:#0f172a; border:1px solid #334155; border-radius:6px; padding:6px 8px; color:#e2e8f0; font-size:12px; outline:none; }
.hold-form input:focus { border-color:#3b82f6; }
.hold-form .full { grid-column:span 2; }
.hold-form button { grid-column:span 2; background:linear-gradient(135deg,#22d3ee,#818cf8); border:none; border-radius:6px; padding:7px; color:#0f172a; font-weight:600; font-size:12px; cursor:pointer; }
.hold-form button:hover { opacity:0.9; }
.hold-card { background:#0f172a; border:1px solid #334155; border-radius:8px; padding:10px; margin-bottom:8px; font-size:11px; position:relative; }
.hold-card .hs { font-size:14px; font-weight:700; }
.hold-card .hst { display:grid; grid-template-columns:1fr 1fr; gap:3px; margin-top:5px; color:#94a3b8; }
.hold-card .hst>div { display:flex; justify-content:space-between; }
.hold-card .hst .v { color:#e2e8f0; }
.hold-card .ha { margin-top:5px; padding:3px 8px; border-radius:4px; text-align:center; font-weight:600; font-size:10px; }
.hold-card .hx { position:absolute; top:3px; right:3px; background:transparent; border:none; color:#64748b; cursor:pointer; font-size:13px; padding:2px; line-height:1; }
.hold-card .hx:hover { color:#f87171; }
.adv-BUY { background:#14532d; color:#a3e635; }
.adv-HOLD { background:#713f12; color:#fde047; }
.adv-SELL { background:#7f1d1d; color:#fca5a5; }
.adv-WATCH { background:#1e3a5f; color:#93c5fd; }
.psum { font-size:11px; color:#94a3b8; }
.psum .pr { display:flex; justify-content:space-between; padding:2px 0; }
.psum .pr .v { color:#e2e8f0; font-weight:600; }
.psum .p-inv { color:#4ade80; }
.psum .p-pl { color:#fbbf24; }
@media (max-width:900px) { .sidebar { width:100%; min-width:100%; margin-bottom:16px; position:static; } .mflex { flex-direction:column; } }
"""

SIDEBAR_HTML = '''
<div class="sidebar" id="pfSidebar">
  <h3>💼 Portfolio</h3>
  <div class="sect" id="pfQuickSection">
    <div style="color:#64748b;font-size:11px;text-align:center;padding:10px 0">Quick add:</div>
    <div class="hold-form">
      <input type="text" id="pfSym" placeholder="Symbol" style="text-transform:uppercase" oninput="this.value=this.value.toUpperCase()">
      <input type="number" id="pfQty" placeholder="Qty" min="1">
      <input type="number" id="pfBuy" placeholder="Buy ₹" min="0" step="0.01" class="full">
      <button onclick="pfAdd()">+ Add Holding</button>
    </div>
  </div>
  <div style="text-align:center;padding:8px 0;border-top:1px solid #334155">
    <a href="/portfolio" style="color:#34d399;font-size:12px;text-decoration:none">💼 Full Portfolio →</a>
  </div>
</div>
<script>
// Quick-add from sidebar (uses same server-side storage)
let _pfQuick = [];
function pfAdd(){
  const s=document.getElementById('pfSym').value.trim().toUpperCase();
  const q=parseInt(document.getElementById('pfQty').value)||0;
  const b=parseFloat(document.getElementById('pfBuy').value)||0;
  if(!s||q<1){alert('Enter symbol and quantity');return;}
  fetch('/api/portfolio/holdings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({symbol:s,qty:q,buy_price:b})}).then(function(r){return r.json()}).then(function(d){
    if(d.error) alert(d.error); else {document.getElementById('pfSym').value='';document.getElementById('pfQty').value='';document.getElementById('pfBuy').value='';}
  });
}
</script>
'''

MARKET_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Stock Bot — Market Scanner</title>
<style>BODY_PLACEHOLDER</style>
</head>
<body>
<div class="container">
    <h1>Stock Bot</h1>
    <div class="subtitle">NSE Market Scanner & Analysis Suite</div>
    <div class="tabs">
        <a href="/" class="tab active">📊 Market Scanner</a>
        <a href="/papa" class="tab">🎯 Papa Approach</a>
        <a href="/both" class="tab">🤝 Both</a>
        <a href="/picks" class="tab">📈 Daily Picks</a>
        <a href="/portfolio" class="tab">💼 Portfolio</a>
    </div>
    <div style="display:flex;align-items:flex-start;gap:16px">
        SIDEBAR_PLACEHOLDER
        <div style="flex:1;min-width:0">
            <div class="hero">
                <h2>Scan All 2,300+ NSE Stocks</h2>
                <p>Every stock graded on 9 parameters: RSI, MACD, Bollinger Bands, Trend, Volume, Momentum, Volatility, Reversal, Upside. Ranked by composite score.</p>
                <button class="scan-btn" id="scanBtn" onclick="startScan()">⚡ Scan Entire Market</button>
            </div>
            <div class="overlay" id="overlay">
                <div class="loader"></div>
                <div class="loader-text" id="loaderText">Starting scan...</div>
                <div class="loader-sub" id="loaderSub">Fetching NSE stock list</div>
                <div class="scan-progress">
                    <div class="scan-progress-track"><div class="scan-progress-bar" id="progressBar"></div></div>
                    <div class="scan-stats">
                        <span id="progressPct">0%</span>
                        <span id="progressCount">0 / 2,376</span>
                        <span id="progressFound">Qualified: 0</span>
                        <span id="progressRate">0/s</span>
                    </div>
                </div>
            </div>
            <div class="results" id="results">
                <div class="summary-cards" id="summaryCards"></div>
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
            <span style="font-size:13px;color:#64748b">Top 25 shown</span>
            <button id="marketToggleBtn" onclick="mktShowAll=!mktShowAll;renderMarketTable()" style="background:#1e293b;color:#4ade80;border:1px solid #4ade80;border-radius:6px;padding:4px 12px;font-size:11px;cursor:pointer">Show All</button>
        </div>
        <div class="filter-bar" id="mktFilterBar" style="display:none">
            <label>🔍 <input type="text" id="mktS" placeholder="Symbol" size="8" oninput="filterMkt()"></label>
            <label>Grade <select id="mktG" onchange="filterMkt()"><option value="">All</option><option>A</option><option>B</option><option>C</option><option>D</option></select></label>
            <label>Signal <select id="mktSig" onchange="filterMkt()"><option value="">All</option><option>STRONG BUY</option><option>BUY</option><option>HOLD</option><option>NEUTRAL</option><option>CAUTION</option></select></label>
            <label>Risk <select id="mktR" onchange="filterMkt()"><option value="">All</option><option>Low</option><option>Medium</option><option>High</option></select></label>
            <div class="col-toggle"><button class="col-toggle-btn" onclick="this.parentNode.classList.toggle('open')">Columns ▾</button><div class="col-toggle-menu" id="mktColM"></div></div>
        </div>
        <table id="mktTbl">
            <thead><tr>
                <th class="sortable" data-idx="0">#</th><th class="sortable" data-idx="1">Symbol</th><th class="sortable text-right" data-idx="2">Price</th><th class="sortable" data-idx="3">Grade</th><th class="sortable text-right" data-idx="4">Score</th>
                <th class="sortable text-right" data-idx="5">RSI</th><th class="sortable" data-idx="6">Risk</th><th class="sortable text-right" data-idx="7">Upside</th><th class="sortable" data-idx="8">Signal</th><th class="sortable" data-idx="9">Factors</th>
            </tr></thead>
            <tbody id="rankingsBody"></tbody>
        </table>
        <div class="grade-dist" id="gradeDist"></div>
        <div class="timestamp" id="timestamp"></div>
    </div>
    <div class="disclaimer">
        <strong>⚠ Disclaimer:</strong> Educational only. Based on 9 technical parameters. Not investment advice.
    </div>
        </div>
    </div>
</div>
<script>
let scanId = null;
function startScan() {
    scanId = null;
    document.getElementById('scanBtn').disabled = true;
    document.getElementById('scanBtn').textContent = 'Scanning...';
    document.getElementById('overlay').classList.add('show');
    document.getElementById('results').classList.remove('show');
    document.getElementById('progressBar').style.width = '0%';
    document.getElementById('progressPct').textContent = '0%';
    document.getElementById('progressCount').textContent = '0 / 2,376';
    document.getElementById('progressFound').textContent = 'Qualified: 0';
    document.getElementById('progressRate').textContent = '0/s';
    fetch('/api/market/start',{method:'POST'}).then(r=>r.json()).then(d=>{scanId=d.scan_id;pollProgress();});
}
function pollProgress() {
    if(!scanId) return;
    fetch('/api/market/progress/'+scanId).then(r=>r.json()).then(d=>{
        if(d.error) return;
        const pct=d.total>0?Math.round((d.scanned/d.total)*100):0;
        document.getElementById('progressBar').style.width=pct+'%';
        document.getElementById('progressPct').textContent=pct+'%';
        document.getElementById('progressCount').textContent=d.scanned.toLocaleString()+' / '+d.total.toLocaleString();
        document.getElementById('progressFound').textContent='Qualified: '+d.qualified;
        document.getElementById('progressRate').textContent=d.rate.toFixed(1)+'/s';
        const msgs=['Scanning stocks...','Calculating RSI...','Analyzing MACD...','Checking Bollinger Bands...','Computing trends...','Grading...','Ranking...'];
        document.getElementById('loaderText').textContent=msgs[Math.floor(Math.random()*msgs.length)];
        document.getElementById('loaderSub').textContent=d.qualified+' qualified so far';
        if(d.status==='running') setTimeout(pollProgress,400);
        else if(d.status==='done') fetchResults('/api/market/results/'+scanId);
    }).catch(()=>setTimeout(pollProgress,500));
}
function fetchResults(url) {
    fetch(url).then(r=>r.json()).then(d=>{
        document.getElementById('progressBar').style.width='100%';
        document.getElementById('progressPct').textContent='100%';
        document.getElementById('loaderText').textContent='Complete!';
        setTimeout(()=>{
            document.getElementById('overlay').classList.remove('show');
            document.getElementById('scanBtn').disabled=false;
            document.getElementById('scanBtn').textContent='⚡ Scan Entire Market';
            renderMarketResults(d);
        },500);
    });
}
var mktShowAll = false, mktAllStocks = [], _mktRaw = [];
function renderMarketTable(){
    var stocks = mktShowAll ? mktAllStocks : mktAllStocks.slice(0, 25);
    document.getElementById('rankingsBody').innerHTML = stocks.map(function(r,i){
        var bc = r.score > 15 ? '#4ade80' : r.score > 8 ? '#fde047' : '#f87171';
        return '<tr><td>'+(i+1)+'</td><td><strong>'+r.symbol+'</strong></td><td class="text-right">₹'+(r.price||'').toLocaleString()+'</td><td style="color:'+(r.grade&&r.grade[0]==='A'?'#4ade80':r.grade&&r.grade[0]==='B'?'#22d3ee':r.grade&&r.grade[0]==='C'?'#fde047':'#f87171')+';font-weight:700">'+r.grade+'</td><td class="text-right">'+(r.score||'')+'<div class="score-bar"><div class="score-bar-fill" style="width:'+Math.min((r.score||0)/30*100,100)+'%;background:'+bc+'"></div></div></td><td class="text-right">'+(r.rsi||'-')+'</td><td style="color:'+(r.risk==='Low'?'#4ade80':r.risk==='Medium'?'#fde047':'#f87171')+'">'+r.risk+'</td><td class="text-right">'+(r.upside_pct?r.upside_pct+'%':'-')+'</td><td><span class="sig-'+r.signal.replace(' ','_')+'">'+r.signal+'</span></td><td style="font-size:11px;color:#94a3b8;max-width:250px">'+((r.factors||[]).slice(0,3).join('; '))+'</td></tr>';
    }).join('');
    document.getElementById('marketToggleBtn').textContent = mktShowAll ? 'Show Top 25' : 'Show All ('+mktAllStocks.length+')';
}
function renderMarketResults(d) {
    document.getElementById('results').classList.add('show');
    const stocks=d.stocks||[], gc=d.grade_counts||{}, top=stocks[0]||{};
    document.getElementById('summaryCards').innerHTML=
        '<div class="summary-card"><div class="label">Scanned</div><div class="value" style="color:#e2e8f0">'+(d.total||0).toLocaleString()+'</div></div>'+
        '<div class="summary-card"><div class="label">Qualified</div><div class="value" style="color:#4ade80">'+(d.qualified||0)+'</div></div>'+
        '<div class="summary-card"><div class="label">Top Grade</div><div class="value" style="color:#22d3ee">'+(top.grade||'-')+'</div></div>'+
        '<div class="summary-card"><div class="label">Top Stock</div><div class="value" style="color:#fb923c">'+(top.symbol||'-')+'</div></div>'+
        '<div class="summary-card"><div class="label">Top Score</div><div class="value" style="color:#fde047">'+(top.score||'-')+'</div></div>'+
        '<div class="summary-card"><div class="label">A+ to B</div><div class="value" style="color:#4ade80">'+((gc.A_plus||0)+(gc.A||0)+(gc.A_minus||0)+(gc.B_plus||0)+(gc.B||0)+(gc.B_minus||0))+'</div></div>';
    mktShowAll = false;
    _mktRaw = stocks;
    mktAllStocks = stocks;
    renderMarketTable();
    const gl=[{k:'A_plus',l:'A+',c:'#166534'},{k:'A',l:'A',c:'#22c55e'},{k:'A_minus',l:'A-',c:'#4ade80'},{k:'B_plus',l:'B+',c:'#22d3ee'},{k:'B',l:'B',c:'#0891b2'},{k:'B_minus',l:'B-',c:'#06b6d4'},{k:'C_plus',l:'C+',c:'#fde047'},{k:'C',l:'C',c:'#eab308'},{k:'C_minus',l:'C-',c:'#fb923c'},{k:'D',l:'D',c:'#f87171'},{k:'E',l:'E',c:'#991b1b'}];
    const tot=d.qualified||1; let gd='<h3 style="font-size:14px;margin-bottom:8px;color:#94a3b8">Grade Distribution</h3><div class="grade-bar">';
    const gl2=[]; for(const g of gl){const n=gc[g.k]||0;if(n>0){gd+='<div class="grade-seg" style="width:'+(n/tot*100).toFixed(1)+'%;background:'+g.c+'">'+(n>5?g.l:'')+'</div>';gl2.push({l:g.l,c:g.c,n});}}
    gd+='</div><div style="margin-top:8px;display:flex;gap:10px;flex-wrap:wrap;font-size:11px;color:#64748b">';
    for(const g of gl2) gd+='<span><span style="color:'+g.c+';font-weight:600">'+g.l+'</span>: '+g.n+'</span>';
    gd+='</div>'; document.getElementById('gradeDist').innerHTML=gd;
    document.getElementById('timestamp').textContent='Updated: '+(d.timestamp||'')+' | Scanned '+d.total+' stocks, '+d.qualified+' qualified';
    document.getElementById('mktFilterBar').style.display='flex';
    initMktSort(); initColToggle('mktTbl','mktColM');
}
// Sort/filter/col-select
var mktSortCol=-1,mktSortAsc=true;
function initMktSort(){document.querySelectorAll('#mktTbl th.sortable').forEach(function(t){t.onclick=function(){var i=parseInt(this.dataset.idx);if(mktSortCol===i)mktSortAsc=!mktSortAsc;else{mktSortCol=i;mktSortAsc=true;}document.querySelectorAll('#mktTbl th.sortable').forEach(function(x){x.classList.remove('sort-asc','sort-desc')});this.classList.add(mktSortAsc?'sort-asc':'sort-desc');filterMkt()}})}
function filterMkt(){var s=(document.getElementById('mktS').value||'').toUpperCase(),g=document.getElementById('mktG').value,sig=document.getElementById('mktSig').value,r=document.getElementById('mktR').value;var f=_mktRaw.filter(function(st){if(s&&!st.symbol.toUpperCase().includes(s))return false;if(g&&(!st.grade||!st.grade.startsWith(g)))return false;if(sig&&st.signal!==sig)return false;if(r&&st.risk!==r)return false;return true});if(mktSortCol>=0){var ks=['symbol','symbol','price','grade','score','rsi','risk','upside_pct','signal','signal'];f.sort(function(a,b){var k=ks[mktSortCol],av,bv;if(k==='price'||k==='score'||k==='rsi'||k==='upside_pct'){av=parseFloat(a[k])||0;bv=parseFloat(b[k])||0}else{var gm={A:5,B:4,C:3,D:2,E:1};if(k==='grade'){av=gm[(a.grade||'E')[0]]||1;bv=gm[(b.grade||'E')[0]]||1}else if(k==='risk'){av={Low:3,Medium:2,High:1}[a.risk]||0;bv={Low:3,Medium:2,High:1}[b.risk]||0}else if(k==='signal'){av=['CAUTION','NEUTRAL','HOLD','BUY','STRONG BUY'].indexOf(a.signal);bv=['CAUTION','NEUTRAL','HOLD','BUY','STRONG BUY'].indexOf(b.signal)}}return mktSortAsc?av-bv:bv-av})}mktAllStocks=f;var showAll=document.getElementById('marketToggleBtn').textContent.indexOf('Top 25')>=0;mktShowAll=!showAll;renderMarketTable()}
function initColToggle(tblId,menuId){var tbl=document.getElementById(tblId);if(!tbl)return;var headers=tbl.querySelectorAll('thead th');var menu=document.getElementById(menuId);menu.innerHTML='';headers.forEach(function(th,i){var txt=th.textContent.trim().replace(/[▲▼]/g,'').trim();if(!txt||txt==='#')return;var label=document.createElement('label');var cb=document.createElement('input');cb.type='checkbox';cb.checked=true;cb.onchange=function(){tbl.querySelectorAll('tr').forEach(function(tr){var td=tr.children[i];if(td)td.style.display=cb.checked?'':'none'})};label.appendChild(cb);label.appendChild(document.createTextNode(' '+txt));menu.appendChild(label)})}
</script>
</body>
</html>
"""

PAPA_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Stock Bot — Papa Approach</title>
<style>PAPA_CSS_PLACEHOLDER</style>
<style>
.papa-hero { background:linear-gradient(135deg,rgba(245,158,11,0.05),rgba(249,115,22,0.05)); border:1px solid #334155; border-radius:16px; padding:32px; text-align:center; margin-bottom:24px; }
.papa-hero h2 { color:#f59e0b; }
.papa-btn { background:linear-gradient(135deg,#f59e0b,#f97316); }
</style>
</head>
<body>
<div class="container">
    <h1 style="background:linear-gradient(135deg,#f59e0b,#f97316);-webkit-background-clip:text;-webkit-text-fill-color:transparent">Stock Bot</h1>
    <div class="subtitle">NSE Market Scanner & Papa Approach</div>
    <div class="tabs">
        <a href="/" class="tab">📊 Market Scanner</a>
        <a href="/papa" class="tab active">🎯 Papa Approach</a>
        <a href="/both" class="tab">🤝 Both</a>
        <a href="/picks" class="tab">📈 Daily Picks</a>
        <a href="/portfolio" class="tab">💼 Portfolio</a>
    </div>
    <div style="display:flex;align-items:flex-start;gap:16px">
        SIDEBAR_PLACEHOLDER
        <div style="flex:1;min-width:0">
            <div class="papa-hero">
                <h2>🎯 Papa Approach — D·V·M 3-Dot System</h2>
                <p><strong>Surendra Pal Rana (fuziwaiinvesting.com)</strong> — 11-point algorithmic checklist based on Trendlyne DVM methodology. Scans all NSE stocks for Durability • Valuation • Momentum with color dots 🟢🟡🔴. Tracks stock lifecycle from ICU → Recovery → Gear 1/2 → Peak → Sell.</p>
                <button class="scan-btn papa-btn" id="papaScanBtn" onclick="startPapaScan()">🎯 Run Papa Scan</button>
            </div>
    <div class="overlay" id="papaOverlay">
        <div class="loader" style="border-top-color:#f59e0b"></div>
        <div class="loader-text" id="papaLoaderText">Starting Papa scan...</div>
        <div class="loader-sub" id="papaLoaderSub">D·V·M scoring + 11-point checklist</div>
        <div class="scan-progress">
            <div class="scan-progress-track"><div class="scan-progress-bar" id="papaProgressBar" style="background:linear-gradient(90deg,#f59e0b,#f97316)"></div></div>
            <div class="scan-stats">
                <span id="papaProgressPct">0%</span>
                <span id="papaProgressCount">0 / 2,376</span>
                <span id="papaProgressFound">Qualified: 0</span>
                <span id="papaProgressRate">0/s</span>
            </div>
        </div>
    </div>
    <div class="results" id="papaResults">
        <div class="summary-cards" id="papaSummaryCards"></div>
        <div class="methods-box">
            <strong>D (Durability):</strong> 🟢&gt;55 🟡35-55 🔴&lt;35 &nbsp;|&nbsp;
            <strong>V (Valuation):</strong> 🟢&gt;50 🟡30-50 🔴&lt;30 &nbsp;|&nbsp;
            <strong>M (Momentum):</strong> 🟢&gt;60 🟡35-60 🔴&lt;35 &nbsp;|&nbsp;
            11-Point: Chart · P/E low · Mom 30→35 · RSI 30→35 · MFI 30→35 · MACD ↑ · Price/Vol/EMA · Stoch · CCI red · Will -100:-21 · Beta ok
        </div>
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
            <span style="font-size:13px;color:#64748b">Top 25 shown</span>
            <button id="papaToggleBtn" onclick="papaShowAll=!papaShowAll;renderPapaTable()" style="background:#1e293b;color:#4ade80;border:1px solid #4ade80;border-radius:6px;padding:4px 12px;font-size:11px;cursor:pointer">Show All</button>
        </div>
        <div class="filter-bar" id="papaFilterBar" style="display:none">
            <label>🔍 <input type="text" id="papaS" placeholder="Symbol" size="8" oninput="filterPapa()"></label>
            <label>Grade <select id="papaG" onchange="filterPapa()"><option value="">All</option><option>A</option><option>B</option><option>C</option><option>D</option></select></label>
            <label>Signal <select id="papaSig" onchange="filterPapa()"><option value="">All</option><option>STRONG BUY</option><option>BUY</option><option>HOLD</option><option>WAIT</option><option>ALERT</option><option>AVOID</option><option>SELL</option></select></label>
            <label>Gear <select id="papaGear" onchange="filterPapa()"><option value="">All</option><option>Gear 1</option><option>Gear 2</option><option>Ready</option><option>Top Gear</option><option>Critical</option><option>Recovery</option><option>Sell</option></select></label>
            <div class="col-toggle"><button class="col-toggle-btn" onclick="this.parentNode.classList.toggle('open')">Columns ▾</button><div class="col-toggle-menu" id="papaColM"></div></div>
        </div>
        <table id="papaTbl">
            <thead><tr>
                <th class="sortable" data-idx="0">#</th><th class="sortable" data-idx="1">Symbol</th><th class="sortable text-right" data-idx="2">Price</th><th class="sortable" data-idx="3">Grade</th><th class="sortable text-right" data-idx="4">Overall</th>
                <th class="sortable" data-idx="5">D·V·M</th><th class="sortable" data-idx="6">D</th><th class="sortable" data-idx="7">V</th><th class="sortable" data-idx="8">M</th><th class="sortable" data-idx="9">Class</th><th class="sortable" data-idx="10">Gear</th><th class="sortable" data-idx="11">Checks</th><th class="sortable" data-idx="12">Signal</th>
            </tr></thead>
            <tbody id="papaBody"></tbody>
        </table>
        <div class="grade-dist" id="papaGradeDist"></div>
        <div class="timestamp" id="papaTimestamp"></div>
    </div>
    <div class="cheat-sheet">
        <h3>📖 Papa Approach — Complete Dot Pattern Reference</h3>
        <div class="dot-row"><span class="dot-big">🟢🟢🟢</span> <span class="col-g">Gear 1 — Healthy</span> <span class="dot-desc">Durable company, good valuation, strong momentum. Entry zone.</span></div>
        <div class="dot-row"><span class="dot-big">🟡🟢🟢</span> <span class="col-g">Gear 1 — Healthy</span> <span class="dot-desc">Company recovering, good valuation, strong momentum. Entry after check.</span></div>
        <div class="dot-row"><span class="dot-big">🔴🟢🟢</span> <span class="col-g">Gear 1 — Healthy</span> <span class="dot-desc">Weak company but good value & momentum. Cautious entry.</span></div>
        <div class="dot-row"><span class="dot-big">🟢🟡🟢</span> <span class="col-y">Gear 2 — Running</span> <span class="dot-desc">Stock running up, valuation getting expensive. Hold.</span></div>
        <div class="dot-row"><span class="dot-big">🟡🟡🟢</span> <span class="col-y">Gear 2 — Running</span> <span class="dot-desc">Weakening company, expensive, strong momentum. Caution.</span></div>
        <div class="dot-row"><span class="dot-big">🔴🟡🟢</span> <span class="col-y">Gear 2 — Running</span> <span class="dot-desc">Weak, expensive, momentum strong. Risky hold.</span></div>
        <div class="dot-row"><span class="dot-big">🟢🔴🟢</span> <span class="col-y">Top Gear ⚠️</span> <span class="dot-desc">Strong company, overvalued, peak momentum. ALERT — prepare to exit!</span></div>
        <div class="dot-row"><span class="dot-big">🟡🔴🟢</span> <span class="col-y">Top Gear ⚠️</span> <span class="dot-desc">Weak company, overvalued, peak momentum. ALERT — exit soon!</span></div>
        <div class="dot-row"><span class="dot-big">🔴🔴🟢</span> <span class="col-y">Top Gear ⚠️</span> <span class="dot-desc">Bad company, overvalued, momentum still up. Last lap!</span></div>
        <div class="dot-row"><span class="dot-big">🟢🟢🟡</span> <span class="col-g">Pre-Entry Ready 🟢</span> <span class="dot-desc">Coming out of ICU. Durable, good value, momentum turning. BUY ZONE!</span></div>
        <div class="dot-row"><span class="dot-big">🟡🟢🟡</span> <span class="col-g">Pre-Entry Ready 🟢</span> <span class="dot-desc">Company recovering, good value, momentum turning. BUY if checks pass!</span></div>
        <div class="dot-row"><span class="dot-big">🔴🟢🟡</span> <span class="col-g">Pre-Entry Ready 🟢</span> <span class="dot-desc">Weak company, good value, momentum bottoming. Cautious buy.</span></div>
        <div class="dot-row"><span class="dot-big">🟢🟢🔴</span> <span class="col-r">Recovery Watch</span> <span class="dot-desc">Durable, cheap, no momentum. Wait for 🟢🟢🟡.</span></div>
        <div class="dot-row"><span class="dot-big">🟡🟢🔴</span> <span class="col-r">Recovery Watch</span> <span class="dot-desc">Company improving, cheap, no momentum. Wait for 🟡🟢🟡.</span></div>
        <div class="dot-row"><span class="dot-big">🟢🟡🔴</span> <span class="col-r">ICU Conscious</span> <span class="dot-desc">Durable but expensive & no momentum. Avoid.</span></div>
        <div class="dot-row"><span class="dot-big">🟡🟡🔴</span> <span class="col-r">ICU Conscious</span> <span class="dot-desc">Weakening company, expensive, no momentum. Avoid.</span></div>
        <div class="dot-row"><span class="dot-big">🟢🔴🟡</span> <span class="col-r">🚨 SELL NOW</span> <span class="dot-desc">Peak passed — momentum collapsing. SELL IMMEDIATELY!</span></div>
        <div class="dot-row"><span class="dot-big">🟡🔴🟡</span> <span class="col-r">🚨 SELL NOW</span> <span class="dot-desc">Post-peak crash. SELL IMMEDIATELY!</span></div>
        <div class="dot-row"><span class="dot-big">🟢🔴🔴</span> <span class="col-r">💀 Free Fall</span> <span class="dot-desc">Durable but overvalued & crashing. Do NOT buy.</span></div>
        <div class="dot-row"><span class="dot-big">🟡🔴🔴</span> <span class="col-r">💀 Free Fall</span> <span class="dot-desc">Weakening company crashing. Do NOT buy.</span></div>
        <div class="dot-row"><span class="dot-big">🔴🔴🔴</span> <span class="col-r">💀 ICU — Unconscious</span> <span class="dot-desc">Worst grade. Bad company, overvalued, crashing. AVOID!</span></div>
        <div style="margin-top:12px;padding-top:12px;border-top:1px solid #334155;font-size:11px;color:#64748b;line-height:1.6">
            <strong>Lifecycle:</strong> ICU (🔴🔴🔴) → Conscious (🟢🟡🔴) → Recovery Watch (🟢🟢🔴) → Pre-Entry Ready (🟢🟢🟡) → Gear 1 (🟢🟢🟢) → Gear 2 (🟢🟡🟢) → Top Gear (🟢🔴🟢) → SELL (🟢🔴🟡) → Free Fall (🔴🔴🔴)
        </div>
    </div>
    <div class="disclaimer">
        <strong>⚠ Disclaimer:</strong> Educational only. Based on Surendra Pal Rana's methodology (fuziwaiinvesting.com). Not investment advice.
    </div>
        </div>
    </div>
</div>
<div class="checklist-overlay" id="checklistOverlay" onclick="closeChecklist()"></div>
<div class="checklist-popup" id="checklistPopup"></div>
<script>
let papaScanId=null;
function startPapaScan(){
    papaScanId=null;
    document.getElementById('papaScanBtn').disabled=true;
    document.getElementById('papaScanBtn').textContent='Scanning...';
    document.getElementById('papaOverlay').classList.add('show');
    document.getElementById('papaResults').classList.remove('show');
    document.getElementById('papaProgressBar').style.width='0%';
    document.getElementById('papaProgressPct').textContent='0%';
    document.getElementById('papaProgressCount').textContent='0 / 2,376';
    document.getElementById('papaProgressFound').textContent='Qualified: 0';
    document.getElementById('papaProgressRate').textContent='0/s';
    fetch('/api/papa/start',{method:'POST'}).then(r=>r.json()).then(d=>{papaScanId=d.scan_id;pollPapaProgress();});
}
function pollPapaProgress(){
    if(!papaScanId) return;
    fetch('/api/papa/progress/'+papaScanId).then(r=>r.json()).then(d=>{
        if(d.error){console.error(d.error);return;}
        if(d.msg){
            document.getElementById('papaLoaderText').textContent=d.msg;
            document.getElementById('papaLoaderSub').textContent='';
        }else{
            const pct=d.total>0?Math.round((d.scanned/d.total)*100):0;
            document.getElementById('papaProgressBar').style.width=pct+'%';
            document.getElementById('papaProgressPct').textContent=pct+'%';
            document.getElementById('papaProgressCount').textContent=d.scanned.toLocaleString()+' / '+d.total.toLocaleString();
            document.getElementById('papaProgressFound').textContent='Qualified: '+d.qualified;
            document.getElementById('papaProgressRate').textContent=d.rate.toFixed(1)+'/s';
            const msgs=['Durability scoring...','Valuation check...','Momentum analysis...','Beta computation...','Stochastic/CCI/MFI...','11-point checklist...','Classifying dots...'];
            document.getElementById('papaLoaderText').textContent=msgs[Math.floor(Math.random()*msgs.length)];
            document.getElementById('papaLoaderSub').textContent=d.qualified+' qualified so far';
        }
        if(d.status==='running') setTimeout(pollPapaProgress,400);
        else if(d.status==='done') fetchPapaResults();
    }).catch(()=>setTimeout(pollPapaProgress,500));
}
function fetchPapaResults(){
    fetch('/api/papa/results/'+papaScanId).then(r=>r.json()).then(d=>{
        document.getElementById('papaProgressBar').style.width='100%';
        document.getElementById('papaProgressPct').textContent='100%';
        document.getElementById('papaLoaderText').textContent='Complete!';
        setTimeout(()=>{
            document.getElementById('papaOverlay').classList.remove('show');
            document.getElementById('papaScanBtn').disabled=false;
            document.getElementById('papaScanBtn').textContent='🎯 Run Papa Scan';
            renderPapaResults(d);
        },500);
    });
}
function gearColor(gl){
    if(gl<=1) return '#f87171';
    if(gl===2) return '#fb923c';
    if(gl===3) return '#fde047';
    if(gl===4) return '#4ade80';
    if(gl===5) return '#22d3ee';
    if(gl===6) return '#f59e0b';
    if(gl===7) return '#ef4444';
    return '#991b1b';
}
document.addEventListener('click',function(e){
    var td=e.target.closest('.check-col');
    if(td){var sym=td.getAttribute('data-symbol');var cl=td.getAttribute('data-checklist');if(sym&&cl){try{showChecklist(sym,JSON.parse(cl));}catch(ex){}}}
});
function showChecklist(symbol,cl){
    const keys=Object.keys(cl);
    let html='<h3>📋 '+symbol+' — 11-Point Checklist</h3>';
    keys.forEach(k=>{const pass=cl[k];html+='<div class="item"><span class="'+(pass?'chk-yes':'chk-no')+'">'+(pass?'✅':'❌')+'</span> <span>'+k+'</span></div>';});
    document.getElementById('checklistPopup').innerHTML=html;
    document.getElementById('checklistPopup').classList.add('show');
    document.getElementById('checklistOverlay').classList.add('show');
}
function closeChecklist(){
    document.getElementById('checklistPopup').classList.remove('show');
    document.getElementById('checklistOverlay').classList.remove('show');
}
var papaShowAll = false, papaAllStocks = [], _papaRaw = [];
function renderPapaTable(){
    var stocks = papaShowAll ? papaAllStocks : papaAllStocks.slice(0, 25);
    document.getElementById('papaBody').innerHTML = stocks.map(function(r,i){
        var gc2 = gearColor(r.gear_level);
        var gradeC = r.grade === 'A+' ? '#86efac' : r.grade === 'A' ? '#4ade80' : r.grade === 'B' ? '#22d3ee' : r.grade === 'C' ? '#fde047' : '#f87171';
        var checksColor = r.checks_passed >= 8 ? '#4ade80' : r.checks_passed >= 6 ? '#fde047' : '#f87171';
        var safeSymbol = (r.symbol||'').replace(/'/g,"\\'").replace(/"/g,"&quot;");
        var safeChecklist = JSON.stringify(r.checklist||{}).replace(/'/g,"\\'").replace(/"/g,"&quot;");
        return '<tr><td>'+(papaShowAll ? i+1 : i+1)+'</td><td><strong>'+(r.symbol||'')+'</strong>'+(r.sector?'<br><span style="font-size:9px;color:#64748b">'+r.sector.slice(0,12)+'</span>':'')+'</td><td class="text-right">₹'+(r.price||'').toLocaleString()+'</td><td style="color:'+gradeC+';font-weight:700">'+(r.grade||'')+'</td><td class="text-right"><strong>'+(r.overall_score||'')+'</strong><div class="score-bar"><div class="score-bar-fill" style="width:'+(r.overall_score||0)+'%;background:'+(r.overall_score>60?'#4ade80':r.overall_score>40?'#fde047':'#f87171')+'"></div></div></td><td><span class="dot-display">'+(r.dot_pattern||'---')+'</span></td><td>'+(r.d_score||'-')+'</td><td>'+(r.v_score||'-')+'</td><td>'+(r.m_score||'-')+'</td><td style="font-size:10px;color:#94a3b8;max-width:130px">'+(r.class_name||'-')+'</td><td><span class="gear-badge" style="background:'+gc2+'20;color:'+gc2+'">'+(r.gear_display||'-')+'</span></td><td style="color:'+checksColor+';font-weight:600;cursor:pointer" class="check-col" data-symbol="'+safeSymbol+'" data-checklist="'+safeChecklist+'">'+(r.checks_passed||'0')+'/'+(r.checks_total||'11')+'</td><td><span class="sig-'+r.signal.replace(' ','_')+'">'+(r.signal||'-')+'</span></td></tr>';
    }).join('');
    document.getElementById('papaToggleBtn').textContent = papaShowAll ? 'Show Top 25' : 'Show All ('+papaAllStocks.length+')';
}
function renderPapaResults(d){
    document.getElementById('papaResults').classList.add('show');
    const stocks=d.stocks||[], top=stocks[0]||{}, gc=d.grade_counts||{};
    document.getElementById('papaSummaryCards').innerHTML=
        '<div class="summary-card"><div class="label">Scanned</div><div class="value" style="color:#e2e8f0">'+(d.total||0).toLocaleString()+'</div></div>'+
        '<div class="summary-card"><div class="label">Qualified</div><div class="value" style="color:#4ade80">'+(d.qualified||0)+'</div></div>'+
        '<div class="summary-card"><div class="label">Top Grade</div><div class="value" style="color:#22d3ee">'+(top.grade||'-')+'</div></div>'+
        '<div class="summary-card"><div class="label">Top Stock</div><div class="value" style="color:#fb923c">'+(top.symbol||'-')+'</div></div>'+
        '<div class="summary-card"><div class="label">Top Dots</div><div class="value"><span class="dot-big">'+(top.dot_pattern||'---')+'</span></div></div>'+
        '<div class="summary-card"><div class="label">Top Class</div><div class="value" style="font-size:13px;color:#94a3b8">'+(top.class_label||'-')+'</div></div>'+
        '<div class="summary-card"><div class="label">Top Signal</div><div class="value" style="font-size:16px">'+(top.signal||'-')+'</div></div>';
    papaShowAll = false;
    _papaRaw = stocks;
    papaAllStocks = stocks;
    renderPapaTable();
    const gl=[{l:'A+',c:'#86efac'},{l:'A',c:'#4ade80'},{l:'B',c:'#22d3ee'},{l:'C',c:'#fde047'},{l:'D',c:'#f87171'}];
    const tot=d.qualified||1; let gd='<h3 style="font-size:14px;margin-bottom:8px;color:#94a3b8">Grade Distribution (11-Point Checklist)</h3><div class="grade-bar">';
    const gl2=[]; for(const g of gl){const n=gc[g.l]||0;if(n>0){gd+='<div class="grade-seg" style="width:'+(n/tot*100).toFixed(1)+'%;background:'+g.c+'">'+(n>5?g.l:'')+'</div>';gl2.push({l:g.l,c:g.c,n});}}
    gd+='</div><div style="margin-top:8px;display:flex;gap:10px;flex-wrap:wrap;font-size:11px;color:#64748b">';
    for(const g of gl2) gd+='<span><span style="color:'+g.c+';font-weight:600">'+g.l+'</span>: '+g.n+'</span>';
    gd+='</div>'; document.getElementById('papaGradeDist').innerHTML=gd;
    document.getElementById('papaTimestamp').textContent='Updated: '+(d.timestamp||'')+' | Scanned '+d.total+' stocks, '+d.qualified+' qualified';
    document.getElementById('papaFilterBar').style.display='flex';
    initPapaSort(); initColToggle('papaTbl','papaColM');
}
var papaSortCol=-1,papaSortAsc=true;
function initPapaSort(){document.querySelectorAll('#papaTbl th.sortable').forEach(function(t){t.onclick=function(){var i=parseInt(this.dataset.idx);if(papaSortCol===i)papaSortAsc=!papaSortAsc;else{papaSortCol=i;papaSortAsc=true;}document.querySelectorAll('#papaTbl th.sortable').forEach(function(x){x.classList.remove('sort-asc','sort-desc')});this.classList.add(papaSortAsc?'sort-asc':'sort-desc');filterPapa()}})}
function filterPapa(){var s=(document.getElementById('papaS').value||'').toUpperCase(),g=document.getElementById('papaG').value,sig=document.getElementById('papaSig').value,gear=document.getElementById('papaGear').value;var f=_papaRaw.filter(function(st){if(s&&!st.symbol.toUpperCase().includes(s))return false;if(g&&(!st.grade||!st.grade.startsWith(g)))return false;if(sig&&st.signal!==sig)return false;if(gear&&st.gear_display&&!st.gear_display.includes(gear))return false;return true});if(papaSortCol>=0){var ks=['symbol','symbol','price','grade','overall_score','dot_pattern','d_score','v_score','m_score','class_name','gear_level','checks_passed','signal'];f.sort(function(a,b){var k=ks[papaSortCol],av,bv;if(k==='price'||k==='overall_score'||k==='d_score'||k==='v_score'||k==='m_score'||k==='gear_level'||k==='checks_passed'){av=parseFloat(a[k])||0;bv=parseFloat(b[k])||0}else if(k==='grade'){av={A:5,B:4,C:3,D:2,E:1}[(a.grade||'E')[0]]||1;bv={A:5,B:4,C:3,D:2,E:1}[(b.grade||'E')[0]]||1}else if(k==='signal'){av=['SELL','AVOID','ALERT','WAIT','HOLD','BUY','STRONG BUY'].indexOf(a.signal);bv=['SELL','AVOID','ALERT','WAIT','HOLD','BUY','STRONG BUY'].indexOf(b.signal)}else{av=(a[k]||'').toString().toLowerCase();bv=(b[k]||'').toString().toLowerCase()}return papaSortAsc?av>bv?1:-1:av<bv?1:-1})}papaAllStocks=f;var showAll=document.getElementById('papaToggleBtn').textContent.indexOf('Top 25')>=0;papaShowAll=!showAll;renderPapaTable()}
</script>
</body>
</html>
"""

def process_scan(scan_id, scan_func):
    def progress_callback(scanned, total, qualified, errors=None):
        elapsed = time.time() - start_time[0]
        rate = scanned / elapsed if elapsed > 0 else 0
        update = {
            "scanned": scanned, "total": total,
            "qualified": qualified, "rate": round(rate, 1),
        }
        if isinstance(errors, str):
            update["msg"] = errors
            update["errors"] = 0
        else:
            update["errors"] = errors if errors is not None else 0
        scans[scan_id].update(update)
    start_time = [time.time()]
    try:
        results = scan_func(progress_callback=progress_callback)
        grade_counts = {}
        for r in results:
            g = r["grade"]
            grade_counts[g] = grade_counts.get(g, 0) + 1
        elapsed = time.time() - start_time[0]
        scans[scan_id].update({
            "status": "done",
            "results": {
                "stocks": results,
                "total": scans[scan_id]["total"],
                "qualified": len(results),
                "grade_counts": grade_counts,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            },
            "scanned": scans[scan_id]["total"],
            "qualified": len(results),
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        scans[scan_id].update({"status": "error", "error": str(e)})


BOTH_HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Stock Bot — Combined Scan</title>
<style>BODY_PLACEHOLDER</style>
<style>
.both-hero { background:linear-gradient(135deg,rgba(139,92,246,0.05),rgba(192,132,252,0.05)); border:1px solid #334155; border-radius:16px; padding:32px; text-align:center; margin-bottom:24px; }
.both-hero h2 { color:#a78bfa; }
.both-btn { background:linear-gradient(135deg,#7c3aed,#a78bfa); }
.both-h1 { background:linear-gradient(135deg,#7c3aed,#a78bfa); -webkit-background-clip:text; -webkit-text-fill-color:transparent; }
.badge-combined { display:inline-block; padding:2px 8px; border-radius:4px; font-size:11px; font-weight:600; }
.badge-combined.both-buy { background:#065f46; color:#6ee7b7; }
.badge-combined.both-strong { background:#065f46; color:#6ee7b7; }
.table-m ix { color:#94a3b8; font-size:12px; }
td .dot-row { display:flex; gap:3px; align-items:center; }
.summary-combined { display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:12px; margin-bottom:20px; }
.conviction-row { background:rgba(251,191,36,0.06) !important; border-left:3px solid #fbbf24; }
.summary-combined .card { background:#1e293b; border:1px solid #334155; border-radius:12px; padding:16px; text-align:center; }
.summary-combined .card .num { font-size:28px; font-weight:700; }
.summary-combined .card .lbl { font-size:12px; color:#94a3b8; margin-top:4px; }
</style>
</head>
<body>
<div class="container">
    <h1 class="both-h1">Stock Bot</h1>
    <div class="subtitle">NSE Market Scanner & Papa Approach</div>
    <div class="tabs">
        <a href="/" class="tab">📊 Market Scanner</a>
        <a href="/papa" class="tab">🎯 Papa Approach</a>
        <a href="/both" class="tab active">🤝 Both</a>
        <a href="/picks" class="tab">📈 Daily Picks</a>
        <a href="/portfolio" class="tab">💼 Portfolio</a>
    </div>
    <div style="display:flex;align-items:flex-start;gap:16px">
        SIDEBAR_PLACEHOLDER
        <div style="flex:1;min-width:0">
            <div class="both-hero">
                <h2>🤝 Combined Scan — Papa BUY + Market BUY</h2>
                <p>Stocks that are <strong>BUY</strong>+ in <strong>Papa Approach</strong> and <strong>HOLD</strong>+ in <strong>Market Scanner</strong> — the intersection of both screening systems. Runs both scans sequentially (~2 min).</p>
                <button class="scan-btn both-btn" id="bothScanBtn" onclick="startBothScan()">🤝 Run Combined Scan</button>
            </div>
            <div class="overlay" id="bothOverlay">
                <div class="loader" style="border-top-color:#a78bfa"></div>
                <div class="loader-text" id="bothLoaderText">Starting combined scan...</div>
            </div>
            <div id="bothResults" style="display:none;">
                <div class="summary-combined" id="bothSummary"></div>
                <div class="filter-bar" id="bothFilterBar" style="display:none">
                    <label>🔍 <input type="text" id="bothS" placeholder="Symbol" size="8" oninput="filterBoth()"></label>
                    <label>Mkt Signal <select id="bothMktSig" onchange="filterBoth()"><option value="">All</option><option>STRONG BUY</option><option>BUY</option><option>HOLD</option></select></label>
                    <label>Papa Signal <select id="bothPapaSig" onchange="filterBoth()"><option value="">All</option><option>STRONG BUY</option><option>BUY</option><option>WAIT</option><option>ALERT</option></select></label>
                    <div class="col-toggle"><button class="col-toggle-btn" onclick="this.parentNode.classList.toggle('open')">Columns ▾</button><div class="col-toggle-menu" id="bothColM"></div></div>
                </div>
                <div style="overflow-x:auto;">
                    <table id="bothTbl">
                        <thead>
                            <tr>
                                <th class="sortable" data-idx="0">Symbol</th>
                                <th class="sortable text-right" data-idx="1">Price</th>
                                <th class="sortable" data-idx="2">Sector</th>
                                <th class="sortable" data-idx="3">Mkt Sig</th>
                                <th class="sortable text-right" data-idx="4">Mkt Sc</th>
                                <th class="sortable" data-idx="5">Papa Sig</th>
                                <th class="sortable" data-idx="6">D·V·M</th>
                                <th class="sortable" data-idx="7">Checks</th>
                                <th class="sortable" data-idx="8">Grade</th>
                            </tr>
                        </thead>
                        <tbody id="bothTableBody"></tbody>
                    </table>
                </div>
                <div class="footer-text"><span id="bothCount"></span> stocks match both scanners</div>
            </div>
        </div>
    </div>
</div>
<script>
let bothPoll = null;
function startBothScan() {
    document.getElementById("bothOverlay").style.display = "flex";
    document.getElementById("bothResults").style.display = "none";
    document.getElementById("bothScanBtn").disabled = true;
    document.getElementById("bothScanBtn").textContent = "Scanning...";
    fetch("/api/both/start", { method:"POST" })
        .then(r => r.json())
        .then(d => {
            bothPoll = setInterval(() => pollBothProgress(d.scan_id), 500);
        });
}
function pollBothProgress(scanId) {
    fetch("/api/both/progress/" + scanId)
        .then(r => r.json())
        .then(d => {
            if (d.msg) {
                document.getElementById("bothLoaderText").innerHTML = d.msg.replace(/\\n/g, "<br>");
            } else {
                document.getElementById("bothLoaderText").innerHTML = `Scanning... ${d.scanned}/${d.total} | Qualified: ${d.qualified}`;
            }
            if (d.status === "done") {
                clearInterval(bothPoll);
                setTimeout(() => fetchBothResults(scanId), 200);
            } else if (d.status === "error") {
                clearInterval(bothPoll);
                document.getElementById("bothOverlay").style.display = "none";
                document.getElementById("bothScanBtn").disabled = false;
                document.getElementById("bothScanBtn").textContent = "🤝 Run Combined Scan";
                alert("Error: " + d.error);
            }
        });
}
function fetchBothResults(scanId) {
    fetch("/api/both/results/" + scanId)
        .then(r => r.json())
        .then(d => {
            document.getElementById("bothOverlay").style.display = "none";
            document.getElementById("bothScanBtn").disabled = false;
            document.getElementById("bothScanBtn").textContent = "🤝 Run Combined Scan";
            if (d.error) { alert(d.error); return; }
            renderBothResults(d);
        });
}
function renderBothResults(data) {
    const stocks = data.stocks || [];
    document.getElementById("bothResults").style.display = "block";

    let marketBuy = 0, marketStrong = 0;
    let papaBuy = 0, papaStrong = 0;
    stocks.forEach(s => {
        if (s.market_signal === "STRONG BUY") marketStrong++;
        else if (s.market_signal === "BUY") marketBuy++;
        if (s.papa_signal === "STRONG BUY") papaStrong++;
        else if (s.papa_signal === "BUY") papaBuy++;
    });

    document.getElementById("bothSummary").innerHTML = `
        <div class="card"><div class="num">${stocks.length}</div><div class="lbl">Combined Matches</div></div>
        <div class="card"><div class="num" style="color:#22c55e">${marketStrong+marketBuy}</div><div class="lbl">Market HOLD+</div></div>
        <div class="card"><div class="num" style="color:#f59e0b">${papaStrong+papaBuy}</div><div class="lbl">Papa BUY+</div></div>
    `;

    const tbody = document.getElementById("bothTableBody");
    tbody.innerHTML = stocks.map(s => {
        const gradeColor = {"A":"#22c55e","B":"#3b82f6","C":"#f59e0b","D":"#ef4444","E":"#94a3b8"}[s.papa_grade] || "#94a3b8";
        const dColor = s.d_color === "green" ? "#22c55e" : s.d_color === "yellow" ? "#eab308" : "#ef4444";
        const vColor = s.v_color === "green" ? "#22c55e" : s.v_color === "yellow" ? "#eab308" : "#ef4444";
        const mColor = s.m_color === "green" ? "#22c55e" : s.m_color === "yellow" ? "#eab308" : "#ef4444";
        const msig = s.market_signal === "STRONG BUY" ? '<span class="badge" style="background:#065f46;color:#6ee7b7">STRONG BUY</span>'
                   : s.market_signal === "BUY" ? '<span class="badge" style="background:#065f46;color:#6ee7b7">BUY</span>'
                   : '<span class="badge">'+s.market_signal+'</span>';
        const psig = s.papa_signal === "STRONG BUY" ? '<span class="badge" style="background:#065f46;color:#6ee7b7">STRONG BUY</span>'
                   : s.papa_signal === "BUY" ? '<span class="badge" style="background:#065f46;color:#6ee7b7">BUY</span>'
                   : '<span class="badge">'+s.papa_signal+'</span>';
        return `<tr>
            <td><strong>${s.symbol}</strong></td>
            <td>${s.price ? "₹" + s.price.toLocaleString() : "-"}</td>
            <td class="table-mix">${s.sector || "-"}</td>
            <td>${msig}</td>
            <td>${s.market_score ?? "-"}</td>
            <td>${psig}</td>
            <td><div class="dot-row"><span style="color:${dColor}">●</span><span style="color:${vColor}">●</span><span style="color:${mColor}">●</span></div></td>
            <td>${s.checks_passed ?? "-"}/${s.checks_total ?? 11}</td>
            <td><span class="badge" style="background:${gradeColor}20;color:${gradeColor}">${s.papa_grade || "-"}</span></td>
        </tr>`;
    }).join("");
    document.getElementById("bothCount").textContent = stocks.length;
    _bothRaw = stocks;
    document.getElementById('bothFilterBar').style.display='flex';
    initBothSort(); initColToggle('bothTbl','bothColM');
}
var _bothRaw = [], bothSortCol=-1, bothSortAsc=true;
function initBothSort(){document.querySelectorAll('#bothTbl th.sortable').forEach(function(t){t.onclick=function(){var i=parseInt(this.dataset.idx);if(bothSortCol===i)bothSortAsc=!bothSortAsc;else{bothSortCol=i;bothSortAsc=true;}document.querySelectorAll('#bothTbl th.sortable').forEach(function(x){x.classList.remove('sort-asc','sort-desc')});this.classList.add(bothSortAsc?'sort-asc':'sort-desc');filterBoth()}})}
function filterBoth(){var s=(document.getElementById('bothS').value||'').toUpperCase(),msig=document.getElementById('bothMktSig').value,psig=document.getElementById('bothPapaSig').value;var f=_bothRaw.filter(function(st){if(s&&!st.symbol.toUpperCase().includes(s))return false;if(msig&&st.market_signal!==msig)return false;if(psig&&st.papa_signal!==psig)return false;return true});if(bothSortCol>=0){var ks=['symbol','price','sector','market_signal','market_score','papa_signal','dot_pattern','checks_passed','papa_grade'];f.sort(function(a,b){var k=ks[bothSortCol],av,bv;if(k==='price'||k==='market_score'||k==='checks_passed'){av=parseFloat(a[k])||0;bv=parseFloat(b[k])||0}else if(k==='papa_grade'){av={A:5,B:4,C:3,D:2,E:1}[(a.papa_grade||'E')[0]]||1;bv={A:5,B:4,C:3,D:2,E:1}[(b.papa_grade||'E')[0]]||1}else{av=(a[k]||'').toString().toLowerCase();bv=(b[k]||'').toString().toLowerCase()}return bothSortAsc?av>bv?1:-1:av<bv?1:-1});_bothRaw=f;renderBothResults({stocks:f})}}
</script>
</body>
</html>
'''

PICKS_HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Stock Bot — Daily Picks</title>
<style>BODY_PLACEHOLDER</style>
<style>
.picks-hero { background:linear-gradient(135deg,rgba(59,130,246,0.05),rgba(99,102,241,0.05)); border:1px solid #334155; border-radius:16px; padding:32px; text-align:center; margin-bottom:24px; }
.picks-hero h2 { color:#60a5fa; }
.picks-btn { background:linear-gradient(135deg,#2563eb,#60a5fa); }
.regime-badge { display:inline-block; padding:4px 12px; border-radius:20px; font-size:13px; font-weight:600; }
.regime-risk_on { background:#065f46; color:#6ee7b7; }
.regime-neutral { background:#1e3a5f; color:#93c5fd; }
.regime-cautious { background:#713f12; color:#fcd34d; }
.regime-risk_off { background:#7f1d1d; color:#fca5a5; }
.pick-exp { font-size:12px; font-weight:600; }
.pick-exp.pos { color:#4ade80; }
.pick-exp.neg { color:#f87171; }
.expected-row { display:flex; gap:6px; align-items:center; justify-content:center; }
</style>
</head>
<body>
<div class="container">
    <h1 style="background:linear-gradient(135deg,#3b82f6,#60a5fa);-webkit-background-clip:text;-webkit-text-fill-color:transparent">Stock Bot</h1>
    <div class="subtitle">NSE Market Scanner & Papa Approach</div>
    <div class="tabs">
        <a href="/" class="tab">📊 Market Scanner</a>
        <a href="/papa" class="tab">🎯 Papa Approach</a>
        <a href="/both" class="tab">🤝 Both</a>
        <a href="/picks" class="tab active">📈 Daily Picks</a>
        <a href="/portfolio" class="tab">💼 Portfolio</a>
    </div>
    <div style="display:flex;align-items:flex-start;gap:16px">
        SIDEBAR_PLACEHOLDER
        <div style="flex:1;min-width:0">
            <div class="picks-hero">
                <h2>📈 Daily Top Picks — Best Short-Term Plays</h2>
                <p>Top <strong>3</strong> stocks passing <strong>both</strong> scanners (Market HOLD+ &amp; Papa BUY+), ranked by <strong>blended</strong> score (composite + expected return penalty). Backtest-proven: <strong>+4.1% avg 1d</strong> (81% win), <strong>+5.8% avg 5d</strong> (66% win). In risk_off, only D=green stocks included.</p>
                <button class="scan-btn picks-btn" id="picksBtn" onclick="loadPicks()">📈 Load Daily Picks</button>
            </div>
            <div class="overlay" id="picksOverlay">
                <div class="loader" style="border-top-color:#60a5fa"></div>
                <div class="loader-text" id="picksLoaderText">Running scanners for today...</div>
                <div class="loader-sub" id="picksLoaderSub">Loading data cache (~2,300 stocks)</div>
            </div>
            <div id="picksResults" style="display:none;">
                <div class="summary-cards" id="picksSummary"></div>
                <div class="filter-bar" id="picksFilterBar" style="display:none">
                    <label>🔍 <input type="text" id="picksS" placeholder="Symbol" size="8" oninput="filterPicks()"></label>
                    <div class="col-toggle"><button class="col-toggle-btn" onclick="this.parentNode.classList.toggle('open')">Columns ▾</button><div class="col-toggle-menu" id="picksColM"></div></div>
                </div>
                <table id="picksTbl">
                    <thead><tr>
                        <th class="sortable" data-idx="0">#</th>
                        <th class="sortable" data-idx="1">Symbol</th>
                        <th class="sortable text-right" data-idx="2">Price</th>
                        <th class="sortable text-right" data-idx="3">Mkt</th>
                        <th class="sortable text-right" data-idx="4">Papa</th>
                        <th class="sortable" data-idx="5">D·V·M</th>
                        <th class="sortable text-right" data-idx="6">D</th>
                        <th class="sortable text-right" data-idx="7">D%</th>
                        <th class="sortable text-right" data-idx="8">V</th>
                        <th class="sortable text-right" data-idx="9">M</th>
                        <th class="sortable" data-idx="10">Gear</th>
                        <th class="sortable" data-idx="11">Checks</th>
                        <th class="sortable text-right" data-idx="12">1d</th>
                        <th class="sortable text-right" data-idx="13">5d</th>
                        <th class="text-right" data-idx="14">Fundamentals</th>
                        <th class="text-right" data-idx="15">Allocation</th>
                    </tr></thead></thead>
                    <tbody id="picksBody"></tbody>
                </table>
                <div class="timestamp" id="picksTimestamp"></div>
            </div>
        </div>
    </div>
</div>
<script>
let picksPoll = null;
function loadPicks() {
    document.getElementById("picksOverlay").style.display = "flex";
    document.getElementById("picksResults").style.display = "none";
    document.getElementById("picksBtn").disabled = true;
    document.getElementById("picksBtn").textContent = "Loading...";
    fetch("/api/picks/start", {method:"POST"}).then(r=>r.json()).then(d=>{
        picksPoll = setInterval(()=>pollPicks(d.scan_id), 500);
    });
}
function pollPicks(id) {
    fetch("/api/picks/progress/"+id).then(r=>r.json()).then(d=>{
        if(d.msg) document.getElementById("picksLoaderText").innerHTML = d.msg;
        else document.getElementById("picksLoaderText").innerHTML = "Scanning... "+(d.scanned||0)+"/"+(d.total||2300);
        if(d.status==="done") {
            clearInterval(picksPoll);
            setTimeout(()=>fetchPicksResults(id), 200);
        } else if(d.status==="error") {
            clearInterval(picksPoll);
            document.getElementById("picksOverlay").style.display = "none";
            document.getElementById("picksBtn").disabled = false;
            document.getElementById("picksBtn").textContent = "📈 Load Daily Picks";
            alert("Error: "+d.error);
        }
    });
}
function fetchPicksResults(id) {
    fetch("/api/picks/results/"+id).then(r=>r.json()).then(d=>{
        document.getElementById("picksOverlay").style.display = "none";
        document.getElementById("picksBtn").disabled = false;
        document.getElementById("picksBtn").textContent = "📈 Load Daily Picks";
        if(d.error) { alert(d.error); return; }
        renderPicks(d);
    });
}
function renderPicks(d) {
    const picks = d.picks || [];
    _picksRaw = picks;
    document.getElementById("picksResults").style.display = "block";
    const regime = d.regime || "unknown";
    const regimeLabel = {"risk_on":"Risk On 🟢","neutral":"Neutral 🔵","cautious":"Cautious 🟡","risk_off":"Risk Off 🔴"};
    const regimeCls = "regime-"+regime;
    const avg1d = picks.length ? picks.reduce((s,p)=>s+(p.expected_1d||0),0)/picks.length : 0;
    const avg5d = picks.length ? picks.reduce((s,p)=>s+(p.expected_5d||0),0)/picks.length : 0;
    const avgnet1d = picks.length ? picks.reduce((s,p)=>s+(p.net_expected_1d||0),0)/picks.length : 0;
    const strictCount = d.count_strict || picks.filter(p=>p.strict_qualified).length;
    
    const conf = picks.length && picks[0].confidence ? picks[0].confidence : {"1d":{avg:4.13,win:81},"5d":{avg:5.80,win:66}};
    const sizing = picks.length && picks.some(p=>p.strict_qualified) ? picks.find(p=>p.strict_qualified).sizing : (picks.length ? picks[0].sizing : null);
    const costs = picks.length && picks[0].transaction_costs ? picks[0].transaction_costs : null;
    
    let sizingHtml = '';
    if(sizing) {
        sizingHtml = `
            <div class="summary-card"><div class="label">Per Position</div><div class="value" style="color:#fbbf24;font-size:16px">${(sizing.per_position_pct*100).toFixed(0)}% of ₹${sizing.portfolio.toLocaleString()}</div></div>
            <div class="summary-card"><div class="label">Stop Loss</div><div class="value" style="color:#ef4444;font-size:16px">${sizing.stop_loss_pct}%</div></div>
            <div class="summary-card"><div class="label">Net 1d (after costs)</div><div class="value" style="color:${avgnet1d>=0?'#4ade80':'#ef4444'};font-size:16px">${avgnet1d.toFixed(1)}% avg</div></div>
        `;
    }
    
    document.getElementById("picksSummary").innerHTML = `
        <div class="summary-card"><div class="label">Regime</div><div class="value"><span class="regime-badge ${regimeCls}">${regimeLabel[regime]||regime}</span></div></div>
        <div class="summary-card"><div class="label">Candidates</div><div class="value" style="color:#60a5fa;font-size:28px">${picks.length}</div></div>
        <div class="summary-card"><div class="label">Conviction</div><div class="value" style="color:#fbbf24;font-size:28px">${strictCount}</div></div>
        <div class="summary-card"><div class="label">Backtest 1d</div><div class="value" style="color:#4ade80;font-size:16px">+${conf["1d"].avg.toFixed(1)}% avg / ${conf["1d"].win.toFixed(0)}% win</div></div>
        <div class="summary-card"><div class="label">Backtest 5d</div><div class="value" style="color:#4ade80;font-size:16px">+${conf["5d"].avg.toFixed(1)}% avg / ${conf["5d"].win.toFixed(0)}% win</div></div>
        ${sizingHtml}
    `;
    
    const tbody = document.getElementById("picksBody");
    tbody.innerHTML = picks.map((p,i)=>{
        const gc = {"green":"#22c55e","yellow":"#eab308","red":"#ef4444"};
        const dots = '<span style="color:'+(gc[p.dot_d]||'#666')+'">●</span><span style="color:'+(gc[p.dot_v]||'#666')+'">●</span><span style="color:'+(gc[p.dot_m]||'#666')+'">●</span>';
        const e1 = p.expected_1d;
        const e5 = p.expected_5d;
        const ne1 = p.net_expected_1d;
        const e1s = e1!=null ? '<span class="pick-exp '+(e1>=0?'pos':'neg')+'">'+(e1>=0?'+':'')+e1.toFixed(1)+'%</span>' : '<span style="color:#64748b">—</span>';
        const ne1s = ne1!=null ? '<span class="pick-exp '+(ne1>=0?'pos':'neg')+'" style="font-size:11px">'+(ne1>=0?'+':'')+ne1.toFixed(1)+'%</span>' : '';
        const e5s = e5!=null ? '<span class="pick-exp '+(e5>=0?'pos':'neg')+'">'+(e5>=0?'+':'')+e5.toFixed(1)+'%</span>' : '<span style="color:#64748b">—</span>';
        const alloc = p.sizing ? '₹'+(p.sizing.suggested_allocation||0).toLocaleString()+' ('+(p.sizing.suggested_shares||0)+' sh)' : '';
        const f = p.fundamentals || {};
        const peS = f.pe ? f.pe+'x' : '-';
        const roeS = f.roe ? f.roe+'%' : '-';
        const deS = f.debt_to_equity ? f.debt_to_equity : '-';
        const mcap = f.market_cap ? '₹'+(f.market_cap/1e7).toFixed(0)+'Cr' : '-';
        const star = p.strict_qualified ? '<span style="color:#fbbf24;font-size:14px" title="Conviction pick">★</span>' : '';
        const dIndicator = p.d_green ? '<span style="color:#22c55e">🟢</span>' : '<span style="color:#ef4444">🔴</span>';
        return '<tr class="'+(p.strict_qualified?'conviction-row':'')+'"><td>'+(i+1)+'</td><td><strong>'+p.symbol+'</strong> '+star+'</td><td class="text-right">₹'+(p.price||'').toLocaleString()+'</td><td class="text-right">'+(p.market_score||'-')+'</td><td class="text-right"><strong>'+(p.papa_overall||'-')+'</strong></td><td>'+dots+'</td><td class="text-right">'+dIndicator+'</td><td class="text-right">'+(p.d_score||'-')+'</td><td class="text-right">'+(p.v_score||'-')+'</td><td class="text-right">'+(p.m_score||'-')+'</td><td>Gear '+(p.gear_level||'-')+'</td><td class="text-right">'+(p.checks_passed||'0')+'/11</td><td class="text-right">'+e1s+'<br>'+ne1s+'</td><td class="text-right">'+e5s+'</td><td style="font-size:11px;color:#94a3b8">P/E:'+peS+' ROE:'+roeS+' D/E:'+deS+'</td><td style="font-size:11px;color:#94a3b8">'+alloc+'</td></tr>';
    }).join("");
    const costStr = costs ? 'Costs: STT '+costs.stt_pct+'% | Brok '+costs.brokerage_pct+'% | Slippage '+costs.slippage_pct+'%' : '';
    document.getElementById("picksTimestamp").innerHTML = "Generated: "+(d.timestamp||"")+" | As of: "+(d.as_of_date||"")+" | Regime: "+regime.toUpperCase()+" | "+strictCount+" conviction / "+picks.length+" candidates | ★ = Conviction pick &nbsp;|&nbsp; "+costStr+" &nbsp;|&nbsp; <em style='color:#94a3b8'>Backtest confidence: +"+conf["1d"].avg.toFixed(1)+"% 1d ("+conf["1d"].win.toFixed(0)+"% win)</em>";
    document.getElementById("picksFilterBar").style.display = "flex";
    initPicksSort(); initColToggle("picksTbl","picksColM");
}
function initColToggle(tblId,menuId){var tbl=document.getElementById(tblId);if(!tbl)return;var headers=tbl.querySelectorAll('thead th');var menu=document.getElementById(menuId);menu.innerHTML='';headers.forEach(function(th,i){var txt=th.textContent.trim().replace(/[▲▼]/g,'').trim();if(!txt||txt==='#')return;var label=document.createElement('label');var cb=document.createElement('input');cb.type='checkbox';cb.checked=true;cb.onchange=function(){tbl.querySelectorAll('tr').forEach(function(tr){var td=tr.children[i];if(td)td.style.display=cb.checked?'':'none'})};label.appendChild(cb);label.appendChild(document.createTextNode(' '+txt));menu.appendChild(label)})}
var _picksRaw = [], picksSortCol=-1, picksSortAsc=true;
function initPicksSort(){document.querySelectorAll("#picksTbl th.sortable").forEach(function(t){t.onclick=function(){var i=parseInt(this.dataset.idx);if(picksSortCol===i)picksSortAsc=!picksSortAsc;else{picksSortCol=i;picksSortAsc=true}document.querySelectorAll("#picksTbl th.sortable").forEach(function(x){x.classList.remove("sort-asc","sort-desc")});this.classList.add(picksSortAsc?"sort-asc":"sort-desc");filterPicks()}})}
function filterPicks(){var s=(document.getElementById("picksS").value||"").toUpperCase();var f=_picksRaw.filter(function(st){if(s&&!st.symbol.toUpperCase().includes(s))return false;return true});if(picksSortCol>=0){var ks=["symbol","symbol","price","market_score","papa_overall","dot_pattern","d_score","v_score","m_score","gear_level","checks_passed","expected_1d","expected_5d"];f.sort(function(a,b){var k=ks[picksSortCol],av,bv;if(k==="price"||k==="market_score"||k==="papa_overall"||k==="d_score"||k==="v_score"||k==="m_score"||k==="gear_level"||k==="checks_passed"||k==="expected_1d"||k==="expected_5d"){av=parseFloat(a[k])||0;bv=parseFloat(b[k])||0}else{av=(a[k]||"").toString().toLowerCase();bv=(b[k]||"").toString().toLowerCase();if(typeof av==="string")return picksSortAsc?av.localeCompare(bv):bv.localeCompare(av)}return picksSortAsc?av-bv:bv-av});_picksRaw=f;renderPicks({picks:f,regime:"risk_off",timestamp:"",d_filter:true})}}
</script>
</body>
</html>
'''
 
PORTFOLIO_HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Stock Bot — Portfolio</title>
<style>BODY_PLACEHOLDER</style>
<style>
.pf-hero { background:linear-gradient(135deg,rgba(16,185,129,0.05),rgba(52,211,153,0.05)); border:1px solid #334155; border-radius:16px; padding:32px; text-align:center; margin-bottom:24px; }
.pf-hero h2 { color:#34d399; }
.pf-btn { background:linear-gradient(135deg,#059669,#34d399); }
.pf-table { width:100%; border-collapse:collapse; margin-bottom:16px; background:#1e293b; border-radius:12px; overflow:hidden; font-size:12px; }
.pf-table th { text-align:left; padding:9px 10px; background:#334155; font-weight:600; font-size:10px; text-transform:uppercase; letter-spacing:0.05em; color:#94a3b8; }
.pf-table td { padding:9px 10px; border-top:1px solid #334155; }
.pf-table tr:hover td { background:#1a2332; }
.pf-add-form { display:flex; gap:8px; align-items:center; background:#1e293b; padding:14px; border-radius:12px; margin-bottom:16px; flex-wrap:wrap; }
.pf-add-form input { background:#0f172a; border:1px solid #334155; border-radius:6px; padding:7px 10px; color:#e2e8f0; font-size:13px; outline:none; }
.pf-add-form input:focus { border-color:#3b82f6; }
.pf-add-form button { background:linear-gradient(135deg,#059669,#34d399); border:none; border-radius:6px; padding:7px 18px; color:#0f172a; font-weight:600; font-size:13px; cursor:pointer; }
.pf-add-form button:hover { opacity:0.9; }
.pf-summary { display:grid; grid-template-columns:repeat(auto-fill,minmax(170px,1fr)); gap:10px; margin-bottom:20px; }
.pf-empty { padding:40px; text-align:center; color:#64748b; font-size:14px; }
.empty-state { padding:60px 20px; text-align:center; }
.empty-state .icon { font-size:48px; margin-bottom:12px; }
.empty-state p { color:#64748b; font-size:14px; }
</style>
</head>
<body>
<div class="container">
    <h1 style="background:linear-gradient(135deg,#059669,#34d399);-webkit-background-clip:text;-webkit-text-fill-color:transparent">Stock Bot</h1>
    <div class="subtitle">My Portfolio Tracker</div>
    <div class="tabs">
        <a href="/" class="tab">📊 Market Scanner</a>
        <a href="/papa" class="tab">🎯 Papa Approach</a>
        <a href="/both" class="tab">🤝 Both</a>
        <a href="/picks" class="tab">📈 Daily Picks</a>
        <a href="/portfolio" class="tab active">💼 Portfolio</a>
    </div>
    <div id="pfMain">
        <div class="pf-hero">
            <h2>💼 My Portfolio</h2>
            <p>Track your holdings with live analysis, signals, and advice. Data from cached OHLCV + fundamentals.</p>
        </div>
        <div class="pf-add-form" id="pfAddForm">
            <input type="text" id="pfSym" placeholder="Symbol" style="text-transform:uppercase;width:120px" oninput="this.value=this.value.toUpperCase()">
            <input type="number" id="pfQty" placeholder="Qty" min="1" style="width:80px">
            <input type="number" id="pfBuy" placeholder="Buy ₹" min="0" step="0.01" style="width:120px">
            <input type="text" id="pfNote" placeholder="Note (optional)" style="width:150px">
            <button onclick="pfAddHolding()">+ Add</button>
            <button onclick="pfClearAll()" style="background:#7f1d1d;color:#fca5a5;border:none;border-radius:6px;padding:7px 14px;font-weight:600;font-size:12px;cursor:pointer">Clear All</button>
        </div>
        <div class="pf-summary" id="pfCards"></div>
        <div id="pfTableWrap">
            <table class="pf-table" id="pfTbl">
                <thead><tr>
                    <th>Symbol</th><th>Qty</th><th>Buy ₹</th><th>Current ₹</th><th>P&amp;L</th><th>Mkt</th><th>Papa</th><th>D·V·M</th><th>1d Exp</th><th>Advice</th><th>Note</th><th></th>
                </tr></thead>
                <tbody id="pfBody"></tbody>
            </table>
        </div>
    </div>
    <div class="disclaimer">
        <strong>⚠ Disclaimer:</strong> Educational only. Data from cached sources, not live prices. Not investment advice.
    </div>
</div>
<script>
let _pfData = [];
function pfLoad(){fetch('/api/portfolio/holdings').then(function(r){return r.json()}).then(function(d){_pfData=d;pfRender();if(d.length)pfAnalyze();});}
function pfAddHolding(){
    var s=document.getElementById('pfSym').value.trim().toUpperCase();
    var q=parseInt(document.getElementById('pfQty').value)||0;
    var b=parseFloat(document.getElementById('pfBuy').value)||0;
    var n=document.getElementById('pfNote').value.trim();
    if(!s||q<1){alert('Enter symbol and quantity');return;}
    fetch('/api/portfolio/holdings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({symbol:s,qty:q,buy_price:b,note:n})}).then(function(r){return r.json()}).then(function(d){
        if(d.error) alert(d.error); else {document.getElementById('pfSym').value='';document.getElementById('pfQty').value='';document.getElementById('pfBuy').value='';document.getElementById('pfNote').value='';pfLoad();}
    });
}
function pfDel(sym){fetch('/api/portfolio/holdings/'+sym,{method:'DELETE'}).then(function(){pfLoad();});}
function pfClearAll(){if(!confirm('Remove all holdings?'))return;fetch('/api/portfolio/holdings',{method:'DELETE'}).then(function(){pfLoad();});}
function pfRender(){
    var el=document.getElementById('pfBody');
    var cards=document.getElementById('pfCards');
    if(!_pfData.length){
        el.innerHTML='<tr><td colspan="12" style="text-align:center;padding:40px;color:#64748b">No holdings yet. Add stocks above.</td></tr>';
        cards.innerHTML='<div class="summary-card"><div class="label">Holdings</div><div class="value" style="color:#94a3b8;font-size:28px">0</div></div>';
        return;
    }
    var invested=0,value=0,best={sym:'',pl:-999},worst={sym:'',pl:999},buys=0,holds=0,sells=0;
    el.innerHTML=_pfData.map(function(h,i){
        var p=h.analysis||{};
        var cur=p.price||h._lastPrice||0;
        var pl=h.buy_price>0?(cur-h.buy_price)/h.buy_price*100:0;
        var inv=h.buy_price*h.qty||0;
        var val=cur*h.qty;
        invested+=inv;value+=val;
        if(pl>best.pl)best={sym:h.symbol,pl:pl};
        if(pl<worst.pl)worst={sym:h.symbol,pl:pl};
        var adv=p.advice||'WATCH';
        if(adv==='BUY')buys++;else if(adv==='HOLD')holds++;else if(adv==='SELL')sells++;
        var dvm=p.dot_pattern||'---';
        var e1=p.expected_1d!=null?p.expected_1d+'%':'--';
        var mkt=p.market_signal||'-';
        var papa=p.papa_signal||'-';
        return '<tr><td><strong>'+h.symbol+'</strong></td><td>'+h.qty+'</td><td>₹'+(h.buy_price||0).toLocaleString()+'</td><td>₹'+(cur||0).toLocaleString()+'</td><td style="color:'+(pl>=0?'#4ade80':'#f87171')+';font-weight:600">'+(pl>=0?'+':'')+pl.toFixed(1)+'%</td><td>'+mkt+'</td><td>'+papa+'</td><td>'+dvm+'</td><td style="color:'+(parseFloat(e1)>=0?'#4ade80':'#f87171')+'">'+e1+'</td><td><span class="adv-'+adv+'" style="padding:2px 8px;border-radius:4px;font-size:10px">'+adv+'</span></td><td style="color:#64748b;font-size:11px">'+(h.note||'')+'</td><td><button onclick="pfDel(\''+h.symbol+'\')" style="background:transparent;border:none;color:#64748b;cursor:pointer;font-size:13px">✕</button></td></tr>';
    }).join('');
    var plTot=invested>0?(value-invested)/invested*100:0;
    cards.innerHTML='<div class="summary-card"><div class="label">Holdings</div><div class="value" style="color:#e2e8f0;font-size:28px">'+_pfData.length+'</div></div>'+
        '<div class="summary-card"><div class="label">Invested</div><div class="value" style="color:#94a3b8;font-size:20px">₹'+invested.toLocaleString()+'</div></div>'+
        '<div class="summary-card"><div class="label">Value</div><div class="value" style="color:#4ade80;font-size:20px">₹'+value.toLocaleString()+'</div></div>'+
        '<div class="summary-card"><div class="label">P&amp;L</div><div class="value" style="color:'+(plTot>=0?'#4ade80':'#f87171')+';font-size:20px">'+(value-invested>=0?'+':'')+(value-invested).toLocaleString()+' ('+(plTot>=0?'+':'')+plTot.toFixed(1)+'%)</div></div>'+
        '<div class="summary-card"><div class="label">Best</div><div class="value" style="color:#4ade80;font-size:16px">'+best.sym+' '+(best.pl>-999?'+'+(best.pl).toFixed(1)+'%':'')+'</div></div>'+
        '<div class="summary-card"><div class="label">Worst</div><div class="value" style="color:#f87171;font-size:16px">'+worst.sym+' '+(worst.pl<999?worst.pl.toFixed(1)+'%':'')+'</div></div>'+
        '<div class="summary-card"><div class="label">Advice</div><div class="value" style="font-size:14px"><span class="adv-BUY" style="padding:2px 8px;border-radius:4px">'+buys+' Buy</span> <span class="adv-HOLD" style="padding:2px 8px;border-radius:4px">'+holds+' Hold</span> <span class="adv-SELL" style="padding:2px 8px;border-radius:4px">'+sells+' Sell</span></div></div>';
}
function pfAnalyze(){
    if(!_pfData.length)return;
    fetch('/api/portfolio/analyze',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({symbols:_pfData.map(function(h){return h.symbol})})}).then(function(r){return r.json()}).then(function(d){
        _pfData.forEach(function(h){h.analysis=d[h.symbol]||{};h._lastPrice=(d[h.symbol]||{}).price;});
        pfRender();
    }).catch(function(){});
}
pfLoad();
setInterval(pfAnalyze, 60000);
</script>
</body>
</html>
'''

@app.route("/")
def index():
    html = MARKET_HTML.replace("BODY_PLACEHOLDER", BASE_CSS)
    return render_template_string(html.replace("SIDEBAR_PLACEHOLDER", ""))


@app.route("/papa")
def papa():
    html = PAPA_HTML.replace("PAPA_CSS_PLACEHOLDER", BASE_CSS)
    return render_template_string(html.replace("SIDEBAR_PLACEHOLDER", ""))


@app.route("/both")
def both():
    html = BOTH_HTML.replace("BODY_PLACEHOLDER", BASE_CSS)
    return render_template_string(html.replace("SIDEBAR_PLACEHOLDER", ""))


@app.route("/picks")
def picks():
    html = PICKS_HTML.replace("BODY_PLACEHOLDER", BASE_CSS)
    return render_template_string(html.replace("SIDEBAR_PLACEHOLDER", ""))


@app.route("/portfolio")
def portfolio():
    return render_template_string(PORTFOLIO_HTML.replace("BODY_PLACEHOLDER", BASE_CSS))


def process_both_scan(scan_id):
    def progress_callback(scanned, total, qualified, errors=None):
        elapsed = time.time() - start_time[0]
        rate = scanned / elapsed if elapsed > 0 else 0
        update = {
            "scanned": scanned, "total": total,
            "qualified": qualified, "rate": round(rate, 1),
        }
        if isinstance(errors, str):
            update["msg"] = errors
            update["errors"] = 0
        else:
            update["errors"] = errors if errors is not None else 0
        scans[scan_id].update(update)
    start_time = [time.time()]
    try:
        market_msg = "Running Market Scanner..."
        progress_callback(0, 2400, 0, market_msg)
        market_results = scan_market(progress_callback=progress_callback)
        market_sigs = ("STRONG BUY", "BUY", "HOLD")
        market_buy = {r["symbol"]: r for r in market_results
                      if r.get("signal") in market_sigs}
        if not market_buy:
            progress_callback(0, 2400, 0, "Market Scanner done — 0 candidates found. Stopping.")
            scans[scan_id].update({"status": "done", "results": {"stocks": []}})
            return

        papa_msg = f"Market Scanner done: {len(market_buy)} HOLD+ candidates. Running Papa Approach..."
        progress_callback(0, 2400, 0, papa_msg)
        papa_results = scan_all_papa(progress_callback=progress_callback)
        papa_buy = {r["symbol"]: r for r in papa_results
                    if r.get("signal") in ("STRONG BUY", "BUY")}
        progress_callback(0, 2400, len(papa_buy), "Computing intersection...")

        common_symbols = sorted(market_buy.keys() & papa_buy.keys())
        merged = []
        for sym in common_symbols:
            m = market_buy[sym]
            p = papa_buy[sym]
            merged.append({
                "symbol": sym,
                "price": p.get("price") or m.get("price"),
                "sector": p.get("sector", ""),
                "market_signal": m.get("signal", ""),
                "market_score": m.get("score"),
                "market_grade": m.get("grade", ""),
                "papa_signal": p.get("signal", ""),
                "papa_grade": p.get("grade", ""),
                "papa_overall": p.get("overall_score"),
                "d_score": p.get("d_score"),
                "v_score": p.get("v_score"),
                "m_score": p.get("m_score"),
                "d_color": p.get("d_color", ""),
                "v_color": p.get("v_color", ""),
                "m_color": p.get("m_color", ""),
                "dot_pattern": p.get("dot_pattern", ""),
                "checks_passed": p.get("checks_passed"),
                "checks_total": p.get("checks_total", 11),
                "gear_level": p.get("gear_level"),
                "gear_display": p.get("gear_display", ""),
            })

        elapsed = time.time() - start_time[0]
        grade_counts = {}
        for r in merged:
            g = r["papa_grade"]
            grade_counts[g] = grade_counts.get(g, 0) + 1

        scans[scan_id].update({
            "status": "done",
            "scanned": scans[scan_id].get("total", 2400),
            "results": {
                "stocks": merged,
                "total": scans[scan_id].get("total", 2400),
                "qualified": len(merged),
                "grade_counts": grade_counts,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            },
            "scanned": 2400,
            "qualified": len(merged),
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        scans[scan_id].update({"status": "error", "error": str(e)})


@app.route("/api/market/start", methods=["POST"])
def api_market_start():
    scan_id = str(uuid.uuid4())[:8]
    scans[scan_id] = {
        "status": "running", "scanned": 0, "total": 2400,
        "qualified": 0, "errors": 0, "rate": 0, "results": None,
    }
    thread = threading.Thread(target=process_scan, args=(scan_id, scan_market))
    thread.daemon = True
    thread.start()
    return jsonify({"scan_id": scan_id})


@app.route("/api/papa/start", methods=["POST"])
def api_papa_start():
    scan_id = str(uuid.uuid4())[:8]
    scans[scan_id] = {
        "status": "running", "scanned": 0, "total": 2400,
        "qualified": 0, "errors": 0, "rate": 0, "results": None,
    }
    thread = threading.Thread(target=process_scan, args=(scan_id, scan_all_papa))
    thread.daemon = True
    thread.start()
    return jsonify({"scan_id": scan_id})


@app.route("/api/market/progress/<scan_id>")
@app.route("/api/papa/progress/<scan_id>")
def api_progress(scan_id):
    info = scans.get(scan_id)
    if not info:
        return jsonify({"error": "not found"}), 404
    resp = {
        "status": info["status"], "scanned": info["scanned"],
        "total": info["total"], "qualified": info["qualified"],
        "errors": info.get("errors", 0), "rate": info.get("rate", 0),
    }
    if info.get("error"):
        resp["error"] = info["error"]
    return jsonify(resp)


@app.route("/api/market/results/<scan_id>")
@app.route("/api/papa/results/<scan_id>")
def api_results(scan_id):
    info = scans.get(scan_id)
    if not info or info["status"] != "done":
        return jsonify({"error": "not ready"}), 400
    return jsonify(info["results"])


@app.route("/api/both/start", methods=["POST"])
def api_both_start():
    scan_id = str(uuid.uuid4())[:8]
    scans[scan_id] = {
        "status": "running", "scanned": 0, "total": 2400,
        "qualified": 0, "errors": 0, "rate": 0, "results": None,
    }
    thread = threading.Thread(target=process_both_scan, args=(scan_id,))
    thread.daemon = True
    thread.start()
    return jsonify({"scan_id": scan_id})


@app.route("/api/both/progress/<scan_id>")
def api_both_progress(scan_id):
    info = scans.get(scan_id)
    if not info:
        return jsonify({"error": "not found"}), 404
    resp = {
        "status": info["status"], "scanned": info["scanned"],
        "total": info["total"], "qualified": info["qualified"],
        "errors": info.get("errors", 0), "rate": info.get("rate", 0),
    }
    if info.get("error"):
        resp["error"] = info["error"]
    if info.get("msg"):
        resp["msg"] = info["msg"]
    return jsonify(resp)


@app.route("/api/both/results/<scan_id>")
def api_both_results(scan_id):
    info = scans.get(scan_id)
    if not info or info["status"] != "done":
        return jsonify({"error": "not ready"}), 400
    return jsonify(info["results"])


def process_picks_scan(scan_id):
    def progress_callback(scanned, total, qualified, errors=None):
        update = {"scanned": scanned, "total": total, "qualified": qualified}
        if errors and isinstance(errors, str):
            update["msg"] = errors
        scans[scan_id].update(update)
    try:
        progress_callback(0, 2300, 0, "Loading OHLCV cache and fundamentals...")
        
        # Pre-load data to find last valid forward-return date
        from backtest import load_data
        all_data = load_data()
        ref_sym = list(all_data.keys())[0]
        valid_fwd = all_data[ref_sym]["Fwd_1d"].dropna()
        as_of_date = valid_fwd.index[-1].strftime("%Y-%m-%d")
        
        # Strict picks (both scanners, D=green filter, top 3)
        params_strict = {"risk_off_d_filter": True, "rank_by": "blended", "top_n": 3}
        picks_strict = get_daily_picks(as_of_date, all_data=all_data, params=params_strict)
        
        # Relaxed picks (lower thresholds, no D filter, top 15)
        params_relaxed = {
            "market_threshold": "NEUTRAL",
            "papa_threshold": "HOLD",
            "papa_reg_penalty": 2,
            "min_checks_papa_buy": 4,
            "risk_off_d_filter": False,
            "rank_by": "blended",
            "top_n": 15
        }
        picks_relaxed = get_daily_picks(as_of_date, all_data=all_data, params=params_relaxed)
        
        regime = picks_strict[0].get("regime", "unknown") if picks_strict else "unknown"
        
        # Mark which relaxed picks pass strict filters
        strict_symbols = {p["symbol"] for p in picks_strict}
        for p in picks_relaxed:
            p["strict_qualified"] = p["symbol"] in strict_symbols
            p["d_green"] = p.get("dot_d") == "green"
        
        # Append any strict picks not already in the relaxed list
        shown_symbols = {p["symbol"] for p in picks_relaxed}
        for p in picks_strict:
            if p["symbol"] not in shown_symbols:
                p["strict_qualified"] = True
                p["d_green"] = p.get("dot_d") == "green"
                picks_relaxed.append(p)
        
        # Sort by expected_1d descending so best upside appears first
        picks_relaxed.sort(key=lambda p: p.get("expected_1d") or 0, reverse=True)
        
        progress_callback(len(picks_relaxed), 2300, len(picks_strict), f"Done — {len(picks_strict)} conviction + {len(picks_relaxed)} candidates for {as_of_date}")
        
        scans[scan_id].update({
            "status": "done",
            "results": {
                "picks": picks_relaxed,
                "count": len(picks_relaxed),
                "count_strict": len(picks_strict),
                "regime": regime,
                "d_filter": True,
                "as_of_date": as_of_date,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            },
        })
        progress_callback(2300, 2300, len(picks_strict), "Done")
    except Exception as e:
        import traceback
        traceback.print_exc()
        scans[scan_id].update({"status": "error", "error": str(e)})


@app.route("/api/picks/start", methods=["POST"])
def api_picks_start():
    scan_id = str(uuid.uuid4())[:8]
    scans[scan_id] = {
        "status": "running", "scanned": 0, "total": 2300,
        "qualified": 0, "errors": 0, "rate": 0, "results": None,
    }
    thread = threading.Thread(target=process_picks_scan, args=(scan_id,))
    thread.daemon = True
    thread.start()
    return jsonify({"scan_id": scan_id})


@app.route("/api/picks/progress/<scan_id>")
def api_picks_progress(scan_id):
    info = scans.get(scan_id)
    if not info:
        return jsonify({"error": "not found"}), 404
    resp = {"status": info["status"], "scanned": info.get("scanned", 0), "total": info.get("total", 2300), "qualified": info.get("qualified", 0)}
    if info.get("error"):
        resp["error"] = info["error"]
    if info.get("msg"):
        resp["msg"] = info["msg"]
    return jsonify(resp)


@app.route("/api/picks/results/<scan_id>")
def api_picks_results(scan_id):
    info = scans.get(scan_id)
    if not info or info["status"] != "done":
        return jsonify({"error": "not ready"}), 400
    return jsonify(info["results"])


PORTFOLIO_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "portfolio.json")

def _load_portfolio():
    if os.path.exists(PORTFOLIO_JSON):
        try:
            with open(PORTFOLIO_JSON) as f:
                return json.load(f)
        except Exception:
            return []
    return []

def _save_portfolio(data):
    with open(PORTFOLIO_JSON, "w") as f:
        json.dump(data, f, indent=2)

@app.route("/api/portfolio/holdings", methods=["GET", "POST", "DELETE"])
def api_portfolio_holdings():
    if request.method == "GET":
        return jsonify(_load_portfolio())

    if request.method == "DELETE":
        _save_portfolio([])
        return jsonify({"ok": True})

    body = request.get_json(silent=True) or {}
    symbol = body.get("symbol", "").strip().upper()
    qty = int(body.get("qty", 0))
    buy_price = float(body.get("buy_price", 0))
    note = body.get("note", "").strip()
    if not symbol or qty < 1:
        return jsonify({"error": "symbol and qty required"}), 400

    holdings = _load_portfolio()
    existing = [h for h in holdings if h["symbol"] == symbol]
    if existing:
        return jsonify({"error": symbol + " already in portfolio"}), 400
    holdings.append({"symbol": symbol, "qty": qty, "buy_price": buy_price, "note": note})
    _save_portfolio(holdings)
    return jsonify({"ok": True})

@app.route("/api/portfolio/holdings/<symbol>", methods=["DELETE"])
def api_portfolio_del(symbol):
    symbol = symbol.upper()
    holdings = _load_portfolio()
    holdings = [h for h in holdings if h["symbol"] != symbol]
    _save_portfolio(holdings)
    return jsonify({"ok": True})


@app.route("/api/portfolio/analyze", methods=["POST"])
def api_portfolio_analyze():
    body = request.get_json(silent=True) or {}
    symbols = body.get("symbols", [])
    if not symbols:
        return jsonify({})

    # Load cached data (same pools as daily picks)
    from backtest import load_data
    all_data = load_data()
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "fundamentals_cache.json")) as f:
            funda_cache = json.load(f).get("data", {})
    except Exception:
        funda_cache = {}

    result = {}
    for sym in symbols:
        info = {"price": None, "expected_1d": None, "expected_5d": None,
                "market_signal": "-", "papa_signal": "-",
                "dot_pattern": "---", "d_green": False, "fundamentals": {},
                "rsi": None, "advice": "WATCH"}

        if sym not in all_data:
            result[sym] = info
            continue

        df = all_data[sym]
        if len(df) == 0:
            result[sym] = info
            continue

        last = df.iloc[-1]
        price = float(last.get("Close", last.get("close", 0)))
        info["price"] = round(price, 2) if price else 0

        # Fwd returns: use most recent non-NaN value
        f1_series = df["Fwd_1d"].dropna()
        info["expected_1d"] = round(float(f1_series.iloc[-1]) * 100, 2) if len(f1_series) > 0 else None
        f5_series = df["Fwd_5d"].dropna()
        info["expected_5d"] = round(float(f5_series.iloc[-1]) * 100, 2) if len(f5_series) > 0 else None

        rsi = last.get("RSI")
        info["rsi"] = round(float(rsi), 1) if rsi is not None and not pd.isna(rsi) else None

        # Quick market signal from RSI + MACD + BB
        macd_hist = last.get("MACD_Hist")
        bb_pos = last.get("BB_Position")
        score = 0
        if rsi is not None and not pd.isna(rsi):
            if rsi > 60: score += 3
            elif rsi > 40: score += 1
            else: score -= 1
        if macd_hist is not None and not pd.isna(macd_hist) and macd_hist > 0:
            score += 2
        elif macd_hist is not None and not pd.isna(macd_hist):
            score -= 1
        if bb_pos is not None and not pd.isna(bb_pos) and bb_pos > -0.5:
            score += 1
        if bb_pos is not None and not pd.isna(bb_pos) and bb_pos < -0.8:
            score -= 1
        if score >= 4: info["market_signal"] = "BUY"
        elif score >= 1: info["market_signal"] = "HOLD"
        else: info["market_signal"] = "CAUTION"

        # Papa-style signal from RSI + indicators
        macd_hist_val = float(macd_hist) if macd_hist is not None and not pd.isna(macd_hist) else 0
        rsi_val = float(rsi) if rsi is not None and not pd.isna(rsi) else 50
        bb_pos_val = float(bb_pos) if bb_pos is not None and not pd.isna(bb_pos) else 0

        # D (Durability): RSI trend + MACD health
        d_score = 60 if rsi_val > 50 and macd_hist_val > 0 else (40 if rsi_val > 40 else 30)
        # V (Valuation): BB position as proxy
        v_score = 60 if bb_pos_val > 0 else (45 if bb_pos_val > -0.5 else 30)
        # M (Momentum): RSI momentum + MACD
        m_score = 60 if rsi_val > 55 and macd_hist_val > 0 else (40 if rsi_val > 40 else 25)
        info["d_score"] = d_score
        info["v_score"] = v_score
        info["m_score"] = m_score

        d_green = d_score >= 55; d_yellow = 35 <= d_score < 55
        v_green = v_score >= 50; v_yellow = 30 <= v_score < 50
        m_green = m_score >= 60; m_yellow = 35 <= m_score < 60
        dot_d = "🟢" if d_green else ("🟡" if d_yellow else "🔴")
        dot_v = "🟢" if v_green else ("🟡" if v_yellow else "🔴")
        dot_m = "🟢" if m_green else ("🟡" if m_yellow else "🔴")
        info["dot_pattern"] = dot_d + dot_v + dot_m
        info["d_green"] = d_green

        if d_green and v_green and m_green: info["papa_signal"] = "BUY"
        elif d_green and v_green: info["papa_signal"] = "HOLD"
        elif d_green: info["papa_signal"] = "WATCH"
        else: info["papa_signal"] = "AVOID"

        # Fundamentals
        funda = funda_cache.get(sym, {})
        info["fundamentals"] = {
            "market_cap": funda.get("marketCap"),
            "pe": funda.get("trailingPE"),
            "roe": round(float(funda.get("returnOnEquity", 0)) * 100, 1) if funda.get("returnOnEquity") else None,
            "debt_to_equity": round(float(funda.get("debtToEquity", 0)), 2) if funda.get("debtToEquity") is not None else None,
        }

        # Advice
        e1 = info["expected_1d"]
        msig = info["market_signal"]
        psig = info["papa_signal"]
        if e1 is not None and e1 >= 2 and msig in ("BUY", "STRONG BUY") and d_green:
            info["advice"] = "BUY"
        elif e1 is not None and e1 >= 0 and msig in ("BUY", "HOLD", "STRONG BUY"):
            info["advice"] = "HOLD"
        elif e1 is not None and e1 < 0:
            info["advice"] = "SELL"
        elif msig == "CAUTION" or psig == "AVOID":
            info["advice"] = "SELL"
        else:
            info["advice"] = "WATCH"

        result[sym] = info

    return jsonify(result)


if __name__ == "__main__":
    print("Stock Bot — Market Scanner + Papa Approach")
    print("Open http://127.0.0.1:5000 in your browser")
    app.run(debug=False, port=int(sys.argv[1]) if len(sys.argv) > 1 else 5000)
