'use strict';
/* RSI Overhead – Renderer.
   Baut die Oberflaeche komplett aus config/*.json:
     app.json      Rahmen (Titel, Statusleiste, Kopf-Buttons, Button->Aktion)
     pages.json    Seiten > Spalten > Karten > Elemente
     themes.json   Farbschemata
     keybinds.json Tastenaktionen
   Neues Element-Verhalten: Eintrag in RENDER (Aussehen) bzw. ACTIONS (Klick-Aktionen) ergaenzen. */

const $ = (s, r = document) => r.querySelector(s);
const h = (t, c, x) => { const e = document.createElement(t); if (c) e.className = c; if (x != null) e.innerHTML = x; return e; };
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const slug = s => String(s).toLowerCase().replace(/[^a-z0-9äöü]+/g, '-').replace(/^-|-$/g, '');

const DRAKE_HEX = { '0A0907': 'bg', '141210': 'panel', '1D1A15': 'panel2', '3B352B': 'line', 'F58A1F': 'acc', '9A5410': 'acc2',
  'EFE9DD': 'text', 'A39A88': 'muted', '140A02': 'onacc', 'F2D14B': 'warn', 'F0544A': 'bad' };
const ICONS = {
  gear: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>',
  wifi: '<path d="M3 9a14 14 0 0 1 18 0M6 12.5a9.5 9.5 0 0 1 12 0M9 16a5 5 0 0 1 6 0"/><circle cx="12" cy="19" r="1"/>',
  shield: '<path d="M12 3l8 3v6c0 4.5-3.4 8-8 9-4.6-1-8-4.5-8-9V6z"/>',
  edit: '<path d="M4 20h4L19 9l-4-4L4 16z"/><path d="M13.5 6.5l4 4"/>',
  lock: '<rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
};
const icon = (n, c = 'var(--acc)') => `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="${c}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[n]}</svg>`;

let CFG = {}, S = { ui: {}, stats: {}, info: { paths: {} }, keys: { profiles: {} }, rebinds: {} }, THEME = 'RSI', PAGE = '', DRAFT = {}, LOADED = false;
const ART = {};

/* ---------- Server / Einstellungen ---------- */
async function api(p, b) {
  try {
    const r = await fetch(p, b ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b) } : undefined);
    return await r.json();
  } catch (e) { return { ok: false, error: 'KEINE VERBINDUNG' }; }
}
const get = (id, d) => (id in S.ui ? S.ui[id] : d);
let pend = {}, tm;
function set(id, v) {
  S.ui[id] = v; pend[id] = v; clearTimeout(tm);
  tm = setTimeout(() => { api('/api/set', { ui: pend }); pend = {}; }, 250);
}
async function refresh() {
  const s = await api('/api/state');
  if (!s || s.ok === false) { refresh.fails = (refresh.fails || 0) + 1; return; }
  /* Programm war kurz weg (z. B. Neustart nach einem Update) und ist zurueck -> Seite neu laden, damit der neue Stand erscheint */
  const keepDone = () => { try { if (s.notice) sessionStorage.setItem('rsi_done', s.notice); } catch (e) { /* ohne Speicher geht es auch */ } };
  if (refresh.fails > 0 && LOADED) { keepDone(); location.reload(); return; }
  /* Programm wurde ausgetauscht (auch wenn der Neustart so schnell war, dass keine Abfrage fehlschlug) -> neue Oberflaeche laden */
  const ver = s.info && s.info.app_version;
  if (ver) { if (!refresh.ver) refresh.ver = ver; else if (refresh.ver !== ver) { keepDone(); location.reload(); return; } }
  refresh.fails = 0;
  if (!LOADED) { S.ui = s.ui || {}; LOADED = true; }
  delete s.ui; Object.assign(S, s); updateLive();
  if (s.notice) { PENDING_DONE = s.notice; showUpdateDone(); }
  if (s.info && s.info.update && s.info.update.available && !refresh.told) {
    refresh.told = true;
    toast(s.info.settings && s.info.settings.autoupdate
      ? 'UPDATE ' + s.info.update.latest_name + ' WIRD AUTOMATISCH INSTALLIERT' + (s.info.game_running ? ' (NACH DEM SPIEL)' : '')
      : 'UPDATE ' + s.info.update.latest_name + ' VERFÜGBAR · ZAHNRAD › NACH UPDATE SUCHEN');
  }
}

/* ---------- Theme / Skalierung ---------- */
function applyTheme(n) {
  if (!CFG.themes[n] || typeof CFG.themes[n] !== 'object') n = 'RSI';
  THEME = n;
  const b = document.querySelector('#brand i'); if (b && CFG.app.brandSub === 'auto') b.textContent = n === 'RSI' ? 'STAR CITIZEN' : n;
  for (const [k, v] of Object.entries(CFG.themes[n])) document.documentElement.style.setProperty('--' + k, v);
}
const recolor = str => str.replace(/#([0-9A-Fa-f]{6})([0-9A-Fa-f]{2})?/g, (m, c, a) => {
  const k = DRAKE_HEX[c.toUpperCase()]; return k ? CFG.themes[THEME][k] + (a || '') : m;
});
function fit() {
  const { width: w, height: ht } = CFG.app.design, st = $('#stage');
  /* Fluid: Faktor s so waehlen, dass das Design mindestens passt; die virtuelle Flaeche
     (Fenster / s) wird komplett gefuellt -> beim Aufziehen bekommen Spalten und Karten mehr Platz. */
  const zoom = Math.min(2, Math.max(0.5, (get('uiscale', 100) || 100) / 100));       // einstellbare Oberflaechen-Groesse (50-200 %)
  const s = Math.min(innerWidth / w, innerHeight / ht) * zoom;
  $('#root').classList.toggle('zoomed', zoom > 1);
  /* Bei starker Vergroesserung wird die nutzbare Flaeche schmal -> Spalten umbrechen: wide >= 1100, mid >= 700 (2 Spalten), sonst 1 Spalte */
  const vw = innerWidth / s, mode = vw >= 950 ? 'wide' : vw >= 640 ? 'mid' : 'narrow';
  if ($('#root').dataset.w !== mode) { $('#root').dataset.w = mode; applyCols(); }
  st.style.transform = `scale(${s})`;
  st.style.width = innerWidth / s + 'px';
  st.style.height = innerHeight / s + 'px';
}
function setScale(v, quiet) {
  v = Math.min(200, Math.max(50, Math.round(v / 5) * 5));
  set('uiscale', v); fit(); zoomLabel();
  if (!quiet) toast('GRÖSSE ' + v + ' %');
}
function zoomLabel() {
  const z = document.getElementById('zv'); if (z) z.textContent = (get('uiscale', 100) || 100) + ' %';
}
function toast(msg) {
  const t = $('#toast'); t.textContent = msg; t.classList.add('show');
  clearTimeout(toast.t); toast.t = setTimeout(() => t.classList.remove('show'), 2400);
}

/* ---------- Tasten ---------- */
const profile = () => get('keys.profile', CFG.keys.profiles[0]);
function keyFor(act) {
  const p = profile();
  if (DRAFT[p] && DRAFT[p][act.id] != null) return { t: DRAFT[p][act.id], mod: true };
  const u = S.keys.profiles && S.keys.profiles[p] && S.keys.profiles[p][act.id];
  if (u) return { t: u };
  const rb = S.rebinds && S.rebinds[act.action];
  if (rb && rb.length) return { t: rb[0] };
  if (act.default) return { t: act.default };
  return { t: null };
}
const shortKey = t => t.replace(/Left Mouse Button/g, 'Maus L').replace(/Right Mouse Button/g, 'Maus R').replace(/Middle Mouse Button/g, 'Maus M')
  .replace(/\bLeft /g, 'L').replace(/\bRight /g, 'R').toUpperCase();

/* ---------- Aktionen (Buttons) ---------- */
function confirmClick(btn, fn) {
  if (btn.dataset.arm) { clearTimeout(+btn.dataset.arm); delete btn.dataset.arm; btn.textContent = btn.dataset.txt; fn(); return; }
  btn.dataset.txt = btn.textContent; btn.textContent = 'WIRKLICH?';
  btn.dataset.arm = setTimeout(() => { delete btn.dataset.arm; btn.textContent = btn.dataset.txt; }, 3000);
}
const ACTIONS = {
  'keys.save': async () => {
    const p = profile(), m = Object.assign({}, (S.keys.profiles || {})[p] || {}, DRAFT[p] || {});
    const r = await api('/api/keys/save', { profile: p, map: m });
    if (r.ok) { (S.keys.profiles = S.keys.profiles || {})[p] = m; delete DRAFT[p]; toast('GESPEICHERT · ' + p); renderPage(); } else toast(r.error || 'FEHLER');
  },
  'keys.load': async () => { await refresh(); delete DRAFT[profile()]; renderPage(); toast('GELADEN · ' + profile()); },
  'reset': async () => {
    await api('/api/reset', {}); S.ui = {}; DRAFT = {}; applyTheme('RSI'); build(); toast('STANDARD WIEDERHERGESTELLT');
  },
  'launch': async () => { const r = await api('/api/launch', {}); toast(r.ok ? 'STAR CITIZEN WIRD GESTARTET' : (r.error || 'FEHLER')); },
};
/* Update: erster Klick sucht, ist eins da, wird der Button zu "UPDATE INSTALLIEREN" (zweiter Klick installiert, dann Neustart). */
ACTIONS['update.check'] = async btn => {
  if (btn && btn.dataset.ready) {
    toast('UPDATE WIRD INSTALLIERT …');
    const r = await api('/api/update/apply', {});
    toast(r.ok ? 'UPDATE LÄUFT …' : (r.error || 'FEHLER'));    // Fortschritt zeigt die Update-Animation
    return;
  }
  toast('SUCHE NACH UPDATE …');
  const r = await api('/api/update/check', {});
  if (!r.ok) { toast(r.error || 'FEHLER'); return; }
  if (!r.available) { toast('AKTUELL · VERSION ' + r.name); return; }
  toast('UPDATE ' + r.latest_name + ' VERFÜGBAR' + (r.notes && r.notes.length ? ' · ' + r.notes[r.notes.length - 1].slice(0, 60) : ''));
  if (btn) { btn.dataset.ready = '1'; btn.textContent = 'UPDATE INSTALLIEREN'; }
};
ACTIONS['layout.edit'] = () => { closeSettings(); setEdit(true); };
ACTIONS['layout.add'] = () => { closeSettings(); if (!EDIT) setEdit(true); openPicker(); };
ACTIONS['layout.reset'] = () => resetLayout();
/* Hotkey zum Ein-/Ausblenden: neue Tastenkombination druecken (ohne Fenster-Fokus aufgenommen). Esc = abbrechen. */
ACTIONS['hotkey.change'] = async btn => {
  const old = btn ? btn.textContent : '';
  if (btn) btn.textContent = 'TASTENKOMBINATION DRÜCKEN …';
  const r = await api('/api/hotkey', {});
  if (btn) btn.textContent = old;
  if (r.ok) { await refresh(); renderPage(); toast('HOTKEY: ' + r.hotkey.toUpperCase().replace(/\+/g, ' + ')); } else toast(r.error || 'FEHLER');
};
ACTIONS.quit = async () => { await api('/api/quit', {}); toast('BEENDET'); setTimeout(() => window.close(), 300); };
ACTIONS['paths.change'] = async () => {
  toast('ORDNER WÄHLEN …');
  const r = await api('/api/pickdir', {});
  if (r.ok) { await refresh(); renderPage(); toast('SPIELORDNER GESETZT'); } else toast(r.error || 'FEHLER');
};
ACTIONS.backup = async () => { const r = await api('/api/backup', {}); toast(r.ok ? 'KEYBINDS GESICHERT (Ordner backups)' : (r.error || 'FEHLER')); };
for (const w of ['game', 'logs', 'screens', 'config', 'gamelog', 'cache', 'status'])
  ACTIONS['open.' + w] = async () => { const r = await api('/api/open', { what: w }); if (!r.ok) toast(r.error || 'ORDNER NICHT GEFUNDEN'); };

function runAction(name, label, btn) {
  const a = name || CFG.app.labelActions[(label || '').toUpperCase()];
  if (!a || !ACTIONS[a]) { toast('NOCH NICHT VERBUNDEN'); return; }
  if (a === 'reset') confirmClick(btn, ACTIONS[a]); else ACTIONS[a](btn);
}

/* ---------- Bindungen von Platzhaltern ---------- */
function bindText(b) {
  const i = S.info || {}, p = (i.paths || {});
  const v = { ping: S.stats.ping != null ? S.stats.ping + ' ms' : '—', version: i.version, build: i.build, channel: i.channel, device: i.device,
    'path.game': p.game, 'path.cache': p.cache, 'path.logs': p.logs, appversion: i.app_version,
    cpu: S.stats.cpu != null ? S.stats.cpu + ' %' : null, ram: S.stats.ram != null ? S.stats.ram + ' %' : null,
    game: i.game_running ? 'LÄUFT' : 'NICHT GESTARTET', hotkey: S.hotkey ? String(S.hotkey).toUpperCase().replace(/\+/g, ' + ') : null }[b];
  return v || '—';
}
/* ---------- Update-Animation: Vollbild beim Laden/Installieren/Neustart, danach "aktualisiert" ---------- */
let UPD_BUILT = false, UPD_DONE = false, PENDING_DONE = null;
const UPD_RINGS = '<svg class="rings" viewBox="0 0 150 150" aria-hidden="true"><circle class="sp2" cx="75" cy="75" r="68" fill="none" stroke="var(--acc2)" stroke-dasharray="3 7"/>'
  + '<circle class="sp" cx="75" cy="75" r="52" fill="none" stroke="var(--acc)" stroke-width="2" stroke-dasharray="46 14"/>';
function updateOverlay() {
  const m = document.getElementById('upd'); if (!m || UPD_DONE) return;
  const u = S.info && S.info.update, ph = u && u.phase;
  if (!ph || ph === 'idle') { if (UPD_BUILT) { m.classList.remove('on'); m.innerHTML = ''; UPD_BUILT = false; } return; }
  if (!UPD_BUILT) {
    UPD_BUILT = true; m.classList.add('on');
    m.innerHTML = `<div class="box"><div class="scan"></div>${UPD_RINGS}<g class="arrow"><path d="M75 102 V52 M54 72 L75 50 L96 72" fill="none" stroke="var(--acc)" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/></g></svg>`
      + '<h2 id="uh">UPDATE WIRD INSTALLIERT</h2><div class="uv" id="uv"></div><div class="bar"><i id="uf"></i></div><div class="pct" id="up">0 %</div>'
      + '<div class="steps" id="us"><span>LADEN</span><span>PRÜFEN</span><span>INSTALLIEREN</span><span>NEUSTART</span></div></div>';
  }
  const p = u.progress || {};
  const idx = ph === 'restart' ? 3 : p.step === 'installieren' ? 2 : ((p.step === 'pruefen' && p.pct >= 60) || p.step === 'entpacken') ? 1 : 0;
  const pct = ph === 'restart' ? 100 : Math.max(5, Math.min(99, p.pct || 5));
  $('#uh').textContent = ph === 'restart' ? 'NEUSTART …' : 'UPDATE WIRD INSTALLIERT';
  $('#uv').textContent = u.latest_name ? 'VERSION ' + u.latest_name : '';
  $('#uf').style.width = pct + '%'; $('#up').textContent = pct + ' %';
  [...$('#us').children].forEach((s, i) => { s.className = i < idx ? 'done' : i === idx ? 'on' : ''; });
}
function showUpdateDone() {
  const m = document.getElementById('upd'); if (!m || !PENDING_DONE) return;
  const name = PENDING_DONE; PENDING_DONE = null; UPD_DONE = true; UPD_BUILT = false;
  m.classList.add('on');
  m.innerHTML = `<div class="box ok"><div class="scan"></div>${UPD_RINGS}<path class="chk" d="M50 78 L68 96 L102 56" fill="none" stroke="var(--acc)" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"/></svg>`
    + `<h2>AKTUALISIERT</h2><div class="uv">VERSION ${esc(name)}</div></div>`;
  setTimeout(() => { m.classList.remove('on'); m.innerHTML = ''; UPD_DONE = false; }, 4200);
}
function updateLive() {
  updateOverlay();
  document.querySelectorAll('[data-bind]').forEach(e => { e.textContent = bindText(e.dataset.bind); e.title = e.textContent; });
  const run = !!(S.info && S.info.game_running);
  document.querySelectorAll('.pill').forEach(p => {
    const st = p.dataset.status;
    p.classList.remove('ok', 'wait', 'off');
    p.classList.add(st === 'ping' ? (S.stats.ping != null ? 'ok' : 'off') : st === 'game' ? (run ? 'ok' : 'wait') : 'ok');
  });
  const s = $('#state'); if (s) s.textContent = run ? CFG.app.statusText.running : CFG.app.statusText.ready;
  /* Version immer sichtbar unter dem Namen, damit man sieht, welcher Stand gerade laeuft */
  const bi = document.querySelector('#brand i');
  if (bi && S.info && S.info.app_version) {
    const base = CFG.app.brandSub === 'auto' ? (THEME === 'RSI' ? 'STAR CITIZEN' : THEME) : CFG.app.brandSub;
    bi.textContent = base + ' · V' + S.info.app_version;
  }
}

/* ---------- Elemente ---------- */
const RENDER = {
  seg(c, id) {
    /* apply: 'theme' = Farbschema; sonst echte Host-Einstellung (z. B. winsize) mit Index als Wert */
    const real = c.apply && c.apply !== 'theme' && S.info && S.info.settings ? S.info.settings[c.apply] : undefined;
    const cur = c.apply === 'theme' ? c.options.indexOf(THEME) : real !== undefined ? real : get(id, c.value);
    const w = h('div', 'row');
    c.options.forEach((o, i) => {
      const l = h('label', 'seg', `<input type="radio" name="${esc(id)}" ${i === cur ? 'checked' : ''}><span>${esc(o)}</span>`);
      $('input', l).onchange = async () => {
        if (c.apply === 'theme') { set('theme', o); applyTheme(o); renderPage(); }
        else if (c.apply) {
          const r = await api('/api/setting', { key: c.apply, value: i });
          if (r.ok) { await refresh(); toast(o); } else toast(r.error || 'FEHLER');
        } else set(id, i);
      };
      w.append(l);
    });
    return w;
  },
  chips(c, id) {
    const cur = c.apply === 'profile' ? Math.max(0, CFG.keys.profiles.indexOf(profile()))
      : c.apply === 'theme' ? c.options.indexOf(THEME) : get(id, c.value);
    const w = h('div', 'chips');
    c.options.forEach((o, i) => {
      const l = h('label', 'chip', `<input type="radio" name="${esc(id)}" ${i === cur ? 'checked' : ''}><span>${esc(o)}</span>`);
      $('input', l).onchange = () => {
        if (c.apply === 'profile') { set('keys.profile', o); renderPage(); }
        else if (c.apply === 'theme') { set('theme', o); applyTheme(o); renderPage(); }
        else set(id, i);
      };
      w.append(l);
    });
    return w;
  },
  toggles(c, id) {
    const w = h('div', 'tgs' + (c.grid ? ' grid' : ''));
    c.items.forEach(it => {
      const sid = id + '/' + slug(it.label);
      /* it.apply: echte Einstellung (Host) statt nur gespeicherter Schalter, z. B. Autostart, Overlay */
      const real = it.apply && S.info && S.info.settings ? S.info.settings[it.apply] : undefined;
      const on = real !== undefined ? real : get(sid, it.on);
      const l = h('label', 'tg', `<span class="lb">${esc(it.label)}</span><input type="checkbox" ${on ? 'checked' : ''}><span class="trk"><span class="knob"></span></span>`);
      $('input', l).onchange = async e => {
        if (!it.apply) { set(sid, e.target.checked); return; }
        const r = await api('/api/setting', { key: it.apply, value: e.target.checked });
        if (!r.ok) { e.target.checked = !e.target.checked; toast(r.error || 'FEHLER'); return; }
        await refresh(); renderPage(); toast(it.label.toUpperCase() + (e.target.checked ? ' · AN' : ' · AUS'));
      };
      w.append(l);
    });
    return w;
  },
  range(c, id) {
    if (c.apply === 'uiscale') {                      // Oberflaechen-Groesse (Zoom) - wirkt sofort
      const v = get('uiscale', 100);
      const w = h('div', 'field', `<span class="lbl">${esc(c.label)} <b class="v">${v} %</b></span><input class="rng" type="range" min="${c.min}" max="${c.max}" step="5" value="${v}" aria-label="${esc(c.label)}">`);
      $('input', w).oninput = e => { setScale(+e.target.value, true); $('.v', w).textContent = e.target.value + ' %'; };
      return w;
    }
    const sid = id + '/' + slug(c.label);
    const w = h('div', 'field', `<span class="lbl">${esc(c.label)}</span><input class="rng" type="range" min="${c.min}" max="${c.max}" value="${get(sid, c.value)}" aria-label="${esc(c.label)}">`);
    $('input', w).oninput = e => set(sid, +e.target.value);
    return w;
  },
  kv(c) {
    if (c.edit) return editableKv(c);
    const w = h('div', 'kv', `<span class="lbl">${esc(c.label)}</span><b ${c.bind ? `data-bind="${esc(c.bind)}"` : ''}>${esc(c.bind ? bindText(c.bind) : (c.value.startsWith('[') ? '—' : c.value))}</b>`);
    return w;
  },
  key(c) {
    const act = CFG.keys.actions.find(a => a.label.toUpperCase() === c.label.toUpperCase());
    const w = h('div', 'keyrow', `<span>${esc(c.label)}</span>`), b = h('button', 'key');
    const paint = () => {
      const k = act ? keyFor(act) : { t: null };
      b.className = 'key' + (k.mod ? ' mod' : '') + (k.t ? '' : ' none');
      b.textContent = k.t ? shortKey(k.t) : 'NICHT BELEGT';
    };
    paint();
    b.onclick = async () => {
      if (!act) { toast('KEINE AKTION IN keybinds.json'); return; }
      b.className = 'key cap'; b.textContent = 'TASTE DRÜCKEN …';
      const r = await api('/api/capture', {});
      if (r.key) { (DRAFT[profile()] = DRAFT[profile()] || {})[act.id] = r.key; toast('NICHT VERGESSEN: KEYBINDS SPEICHERN'); } else toast('ABGEBROCHEN');
      paint();
    };
    w.append(b);
    return w;
  },
  btn(c) {
    const b = h('button', 'btn'); b.textContent = c.label; b.onclick = () => runAction(c.action, c.label, b); return b;
  },
  danger(c) {
    const b = h('button', 'bad'); b.textContent = c.label; b.onclick = () => runAction(c.action, c.label, b); return b;
  },
  btnrow(c) {
    const w = h('div', 'row');
    c.items.forEach(l => { const b = h('button', 'sq'); b.textContent = l; b.dataset.label = l; b.onclick = () => runAction(null, l, b); w.append(b); });
    return w;
  },
  start() {
    const w = h('div'); w.style.position = 'relative';
    w.innerHTML = '<div class="startlbl">ZUM STARTEN SCHIEBEN</div><input class="slide" type="range" min="0" max="100" value="0" aria-label="Zum Starten schieben">';
    const i = $('input', w), l = $('.startlbl', w);
    i.oninput = () => { l.style.opacity = Math.max(0, 1 - i.value / 50); };
    i.onchange = () => { if (+i.value >= 95) ACTIONS.launch(); i.value = 0; l.style.opacity = 1; };
    return w;
  },
  art(c) { const w = h('div', 'art'); loadArt(c.src, w); return w; },
  hero(c) {
    const w = h('div', 'hero'); const a = h('div', 'art'); loadArt(c.art, a); w.append(a);
    w.append(h('div', 'ttl', esc(c.title)), h('div', 'sub', esc(c.sub.startsWith('[') ? '—' : c.sub)), h('div', 'dsc', esc(c.desc)));
    return w;
  },
  power(c, id) {
    const w = h('div', 'pw');
    c.groups.forEach(g => {
      const sid = id + '/' + g.id, grp = h('div', 'pwg'), col = h('div', 'pwr');
      const paint = () => col.querySelectorAll('.pc').forEach(x => x.classList.toggle('on', +x.dataset.l === get(sid, g.value)));
      for (let l = g.levels; l >= 1; l--) {
        const x = h('div', 'pc'); x.dataset.l = l; x.title = g.label + ' ' + l;
        x.onclick = () => { set(sid, l); paint(); };
        col.append(x);
      }
      paint(); grp.append(col, h('span', '', esc(g.label))); w.append(grp);
    });
    return w;
  },
  palette() {
    const w = h('div', 'pal'), t = CFG.themes[THEME];
    for (const k of ['bg', 'panel', 'panel2', 'line', 'acc', 'acc2', 'text', 'muted', 'onacc', 'warn', 'bad'])
      w.append(h('div', '', `<i style="background:${t[k]}"></i><b>${k.toUpperCase()}</b><em>${esc(t[k])}</em>`));
    return w;
  },
};

/* Wert zum Selbsteintragen (Klick). Der aUEC-Stand liegt nur auf den CIG-Servern, nicht lokal im Spiel. */
function editableKv(c) {
  const id = 'acct.' + c.edit, num = c.edit === 'auec';
  const w = h('div', 'kv'), v = h('b', 'editable');
  w.append(h('span', 'lbl', esc(c.label)), v);
  v.title = num ? 'Klicken zum Eintragen (der aUEC-Stand ist lokal nicht auslesbar)' : 'Klicken zum Eintragen';
  const show = () => {
    const x = get(id, '');
    v.textContent = x === '' ? '—' : (num ? Number(x).toLocaleString('de-DE') : x);
  };
  v.onclick = () => {
    const i = h('input', 'edit'); i.value = get(id, ''); if (num) i.inputMode = 'numeric';
    v.replaceWith(i); i.focus(); i.select();
    const done = ok => {
      if (ok) { let x = i.value.trim(); if (num) x = x.replace(/[^0-9]/g, ''); set(id, x); }
      i.replaceWith(v); show();
    };
    i.onblur = () => done(true);
    i.onkeydown = e => { if (e.key === 'Enter') i.blur(); else if (e.key === 'Escape') { i.onblur = null; done(false); } };
  };
  show();
  return w;
}

/* Jedes Theme zeigt das Schiff "seines" Herstellers (config/ships.json); Szenen enthalten nur Platzhalter. */
const SHIPS = {};
async function shipFor(theme) {
  const m = CFG.ships || { default: 'cutlass', themes: {}, names: {} };
  const id = m.themes[theme] || m.default;
  /* Eigenes Bild statt Zeichnung: in config/ships.json unter "images" einen Pfad eintragen (PNG/SVG, Nase oben, transparenter Grund) */
  const img = m.images && m.images[id];
  if (img) return { svg: `<image href="${esc(img)}" x="70" y="2" width="160" height="146" preserveAspectRatio="xMidYMid meet"/>`, name: (m.names && m.names[id]) || '' };
  if (!SHIPS[id]) SHIPS[id] = fetch('art/ships/' + id + '.svg').then(r => (r.ok ? r.text() : '')).catch(() => '');
  return { svg: await SHIPS[id], name: (m.names && m.names[id]) || '' };
}
async function loadArt(src, host) {
  if (!ART[src]) ART[src] = fetch('art/' + src + '.svg').then(r => r.text()).catch(() => '');
  let svg = await ART[src];
  if (svg.includes('<!--SHIP')) {
    const sh = await shipFor(THEME);
    svg = svg.replace('<!--SHIP-->', () => sh.svg).replace('<!--SHIPNAME-->', () => esc(sh.name));
  }
  host.innerHTML = recolor(svg);
}

/* ---------- Seiten ---------- */
function renderCard(card, pid, idx, key) {
  const title = card.title.startsWith('THEME') ? 'THEME · ' + THEME
    : card.title.startsWith('TASTENBELEGUNG') ? 'TASTENBELEGUNG · ' + profile() : card.title;
  const c = h('section', 'card' + (card.flex ? ' flex' : ''),
    '<i class="d a"></i><i class="d b"></i><i class="d c"></i><i class="d e"></i><span class="t"></span>');
  $('.t', c).textContent = title;
  c.style.animationDelay = (idx * 0.035) + 's';
  const base = pid + '/' + slug(card.title), n = {};
  cardControls(card, key).forEach(ct => {
    n[ct.type] = (n[ct.type] || 0) + 1;
    const f = RENDER[ct.type];
    if (f) c.append(f(ct, ct.id || `${base}/${ct.type}${n[ct.type]}`));
  });
  return c;
}

/* ---------- Layout (Module) ----------
   Jede Karte ist ein Modul mit dem Schluessel "seite/titel". Die Anordnung kommt aus pages.json;
   im Bearbeiten-Modus kann sie pro Seite veraendert werden (verschieben, entfernen, Module aus
   anderen Seiten hinzufuegen) und wird in den Einstellungen gespeichert. */
const REG = {};
const cardKey = (pid, card) => pid + '/' + slug(card.title);
function buildRegistry() {
  CFG.pages.pages.forEach(p => p.columns.forEach(col => col.forEach(card => { REG[cardKey(p.id, card)] = { card, pid: p.id }; })));
}
function layoutFor(page) {
  const saved = (get('layout', {}) || {})[page.id];
  if (saved) return saved.map(col => col.filter(k => REG[k]));
  return page.columns.map(col => col.map(c => cardKey(page.id, c)));
}
function saveLayout(pid, L) { set('layout', Object.assign({}, get('layout', {}), { [pid]: L })); renderPage(); }
function moveCard(page, key, dx, dy) {
  const L = layoutFor(page).map(c => c.slice());
  let ci = L.findIndex(c => c.includes(key)); if (ci < 0) return;
  let ri = L[ci].indexOf(key);
  if (dy) { const j = ri + dy; if (j < 0 || j >= L[ci].length) return; [L[ci][ri], L[ci][j]] = [L[ci][j], L[ci][ri]]; }
  if (dx) {
    const nc = ci + dx; if (nc < 0 || nc >= L.length) return;
    L[ci].splice(ri, 1); L[nc].splice(Math.min(ri, L[nc].length), 0, key);
  }
  saveLayout(page.id, L);
}
/* Ziehen & Ablegen: am Griff ⠿ ziehen, in beliebige Spalte/Position fallen lassen. */
let DRAG = null;
function clearDrop() {
  document.querySelectorAll('.dropline').forEach(x => x.remove());
  document.querySelectorAll('.col.over').forEach(x => x.classList.remove('over'));
}
function dropIndex(col, e) {
  let i = 0;
  for (const c of col.querySelectorAll(':scope > .card')) { const r = c.getBoundingClientRect(); if (e.clientY > r.top + r.height / 2) i++; else break; }
  return i;
}
function enableDnD(page, grid) {
  grid.querySelectorAll('.col').forEach((col, ci) => {
    col.ondragover = e => {
      if (!DRAG) return;
      e.preventDefault(); e.dataTransfer.dropEffect = 'move';
      clearDrop(); col.classList.add('over');
      const cards = col.querySelectorAll(':scope > .card'), i = dropIndex(col, e), line = h('div', 'dropline');
      if (i < cards.length) col.insertBefore(line, cards[i]); else col.append(line);
    };
    col.ondrop = e => {
      if (!DRAG) return;
      e.preventDefault();
      const i = dropIndex(col, e), key = DRAG; DRAG = null; clearDrop();
      const L = layoutFor(page).map(c => c.slice());
      const sc = L.findIndex(c => c.includes(key)); let idx = i;
      if (sc >= 0) { const si = L[sc].indexOf(key); L[sc].splice(si, 1); if (sc === ci && si < idx) idx--; }
      L[ci].splice(Math.min(idx, L[ci].length), 0, key);
      saveLayout(page.id, L);
    };
  });
}
function toolbar(page, key, card) {
  const t = h('div', 'etools');
  const g = h('button', 'grab', '⠿'); g.title = 'Zum Verschieben ziehen'; g.draggable = true;
  g.ondragstart = e => {
    DRAG = key; e.dataTransfer.effectAllowed = 'move'; e.dataTransfer.setData('text/plain', key);
    try { e.dataTransfer.setDragImage(card, 24, 14); } catch (x) { /* ignore */ }
    requestAnimationFrame(() => card.classList.add('dragging'));
  };
  g.ondragend = () => { DRAG = null; card.classList.remove('dragging'); clearDrop(); };
  t.append(g);
  [['◀', -1, 0, 'Spalte links'], ['▲', 0, -1, 'nach oben'], ['▼', 0, 1, 'nach unten'], ['▶', 1, 0, 'Spalte rechts']].forEach(([s, dx, dy, tip]) => {
    const b = h('button', '', s); b.title = tip; b.onclick = () => moveCard(page, key, dx, dy); t.append(b);
  });
  const x = h('button', 'rm', '✕'); x.title = 'Modul entfernen';
  x.onclick = () => saveLayout(page.id, layoutFor(page).map(c => c.filter(k => k !== key)));
  t.append(x);
  return t;
}
function renderLib(page) {
  const lib = $('#lib'); if (!lib) return;
  lib.style.display = EDIT ? 'flex' : 'none';
  if (!EDIT) return;
  lib.innerHTML = '<span class="lbl">LAYOUT-MODUS · Module am ⠿ ziehen, ✕ entfernt sie</span>';
  const add = h('button', 'mod', '+ MODUL HINZUFÜGEN'); add.onclick = () => openPicker();
  const r = h('button', 'mod reset', 'LAYOUT ZURÜCKSETZEN'); r.onclick = () => resetLayout();
  const ok = h('button', 'mod done', 'FERTIG'); ok.onclick = () => setEdit(false);
  lib.append(add, r, ok);
}
const curPage = () => CFG.pages.pages.find(p => p.id === PAGE) || CFG.pages.pages[0];
function resetLayout() {
  /* Layout, Spaltenbreiten, Modulhoehen und eigene Tasten/Buttons dieser Seite zuruecksetzen */
  const page = curPage(), pid = page.id, keys = new Set([...layoutFor(page).flat(), ...page.columns.flat().map(c => cardKey(pid, c))]);
  const drop = (name, test) => { const o = Object.assign({}, get(name, {})); Object.keys(o).forEach(k => { if (test(k)) delete o[k]; }); set(name, o); };
  drop('layout', k => k === pid); drop('colw', k => k === pid); drop('sizes', k => keys.has(k)); drop('items', k => keys.has(k));
  renderPage(); toast('LAYOUT ZURÜCKGESETZT');
}

/* Modul-Auswahl: alle Module (nach Seite gruppiert), die auf dieser Seite gerade nicht sichtbar sind. */
let PICK = false;
function renderPicker() {
  const m = $('#picker'); if (!m) return;
  m.style.display = PICK ? 'flex' : 'none';
  if (!PICK) { m.innerHTML = ''; return; }
  if (PICK === 'item') return renderItemPicker(m);
  const page = curPage(), used = new Set(layoutFor(page).flat());
  m.innerHTML = '<div class="sheet"><div class="sh-head"><span class="sh-title">MODUL HINZUFÜGEN</span><button class="ib sh-close" aria-label="Schließen" title="Schließen (Esc)">✕</button></div><div class="pk"></div></div>';
  $('.sh-close', m).onclick = closePicker;
  m.onclick = e => { if (e.target === m) closePicker(); };
  const pk = $('.pk', m); let n = 0;
  CFG.pages.pages.forEach(p => {
    const free = Object.keys(REG).filter(k => REG[k].pid === p.id && !used.has(k));
    if (!free.length) return;
    pk.append(h('div', 'pk-h', esc(p.title)));
    const row = h('div', 'chips');
    free.forEach(k => {
      const b = h('button', 'mod'); b.textContent = '+ ' + REG[k].card.title; n++;
      b.onclick = () => {
        const L = layoutFor(page).map(c => c.slice());
        L.reduce((a, c) => (c.length < a.length ? c : a), L[0]).push(k);
        saveLayout(page.id, L); toast('HINZUGEFÜGT: ' + REG[k].card.title);
      };
      row.append(b);
    });
    pk.append(row);
  });
  if (!n) pk.append(h('div', 'lbl', 'Alle Module sind schon auf dieser Seite.'));
}
function openPicker() { PICK = true; renderPicker(); }
function closePicker() { PICK = false; renderPicker(); }
let EDIT = false;

/* ---------- Pro Modul: Tasten/Buttons hinzufuegen oder entfernen (nur Karten mit ausschliesslich Tasten ODER Buttons) ---------- */
function itemKind(card) {
  const t = card.controls.map(c => c.type);
  if (t.length && t.every(x => x === 'key')) return 'keys';
  if (t.length && t.every(x => x === 'btn' || x === 'btnrow')) return 'buttons';
  return null;
}
const defaultItems = card => itemKind(card) === 'keys' ? card.controls.map(c => c.label)
  : card.controls.flatMap(c => c.type === 'btnrow' ? c.items : [c.label]);
const itemsFor = (key, card) => ((get('items', {}) || {})[key]) || defaultItems(card);
function setItems(key, list) { set('items', Object.assign({}, get('items', {}), { [key]: list })); renderPage(); }
function cardControls(card, key) {
  const kind = itemKind(card), ov = key && kind ? (get('items', {}) || {})[key] : null;
  if (!ov) return card.controls;
  if (kind === 'keys') return ov.map(l => ({ type: 'key', label: l, placeholder: '[TASTE]' }));
  const rows = [];
  for (let i = 0; i < ov.length; i += 2) rows.push({ type: 'btnrow', items: ov.slice(i, i + 2) });
  return rows;
}
function decorateItems(c, key, card) {
  const kind = itemKind(card); if (!kind) return;
  const rm = label => setItems(key, itemsFor(key, card).filter(l => l !== label));
  if (kind === 'keys') c.querySelectorAll('.keyrow').forEach(r => {
    const label = $('span', r).textContent, x = h('button', 'ix', '✕'); x.title = 'Taste entfernen';
    x.onclick = e => { e.stopPropagation(); rm(label); }; r.append(x);
  });
  else c.querySelectorAll('.sq').forEach(b => {
    const x = h('i', 'ix', '✕'); x.title = 'Button entfernen';
    x.onclick = e => { e.stopPropagation(); e.preventDefault(); rm(b.dataset.label); }; b.append(x);
  });
  const add = h('button', 'addi', kind === 'keys' ? '+ TASTE HINZUFÜGEN' : '+ BUTTON HINZUFÜGEN');
  add.onclick = () => openItemPicker(key, card, kind); c.append(add);
}
let PICKCTX = null;
function openItemPicker(key, card, kind) { PICK = 'item'; PICKCTX = { key, card, kind }; renderPicker(); }
function renderItemPicker(m) {
  const { key, card, kind } = PICKCTX, have = new Set(itemsFor(key, card));
  const pool = kind === 'keys' ? CFG.keys.actions.map(a => a.label)
    : Object.keys(CFG.app.labelActions).filter(l => !['STANDARD ZURÜCKSETZEN', 'LAUNCHER BEENDEN'].includes(l));
  const free = [...new Set(pool)].filter(l => !have.has(l));
  m.innerHTML = `<div class="sheet"><div class="sh-head"><span class="sh-title">${kind === 'keys' ? 'TASTE' : 'BUTTON'} HINZUFÜGEN</span><button class="ib sh-close" aria-label="Schließen" title="Schließen (Esc)">✕</button></div><div class="pk"></div></div>`;
  $('.sh-close', m).onclick = closePicker;
  m.onclick = e => { if (e.target === m) closePicker(); };
  const pk = $('.pk', m), row = h('div', 'chips');
  free.forEach(l => {
    const b = h('button', 'mod'); b.textContent = '+ ' + l;
    b.onclick = () => { setItems(key, itemsFor(key, card).concat(l)); toast('HINZUGEFÜGT: ' + l); };
    row.append(b);
  });
  pk.append(free.length ? row : h('div', 'lbl', 'Es gibt nichts mehr zum Hinzufügen.'));
}

/* ---------- Groesse: Hoehe pro Modul (unten ziehen), Breite pro Spalte (Trennlinie ziehen) ---------- */
function resizer(key, c) {
  const z = h('div', 'rz'); z.title = 'Höhe ziehen · Doppelklick = automatisch';
  z.onpointerdown = e => {
    e.preventDefault(); try { z.setPointerCapture(e.pointerId); } catch (x) { /* ohne Capture geht es auch */ }
    const s = c.getBoundingClientRect().height / c.offsetHeight || 1, y0 = e.clientY, h0 = c.offsetHeight;
    c.style.flex = 'none'; c.dataset.fixed = '1';
    z.onpointermove = ev => { c.style.height = Math.max(70, Math.round(h0 + (ev.clientY - y0) / s)) + 'px'; };
    z.onpointerup = () => { z.onpointermove = z.onpointerup = null; set('sizes', Object.assign({}, get('sizes', {}), { [key]: c.offsetHeight })); };
  };
  z.ondblclick = () => { const s = Object.assign({}, get('sizes', {})); delete s[key]; set('sizes', s); renderPage(); };
  return z;
}
/* Spaltenbreiten (nur bei breiter Flaeche); bei mid/narrow bestimmt das CSS die Spaltenzahl */
function applyCols(page) {
  const grid = $('#grid'); if (!grid || !CFG.pages) return;
  page = page || curPage();
  const cw = (get('colw', {}) || {})[page.id], n = layoutFor(page).length, wide = ($('#root').dataset.w || 'wide') === 'wide';
  grid.style.gridTemplateColumns = wide && cw && cw.length === n ? cw.map(x => x + 'fr').join(' ') : '';
}
function colHandles(page, grid) {
  if (($('#root').dataset.w || 'wide') !== 'wide') return;
  const cols = [...grid.children].filter(x => x.classList.contains('col'));
  for (let i = 0; i < cols.length - 1; i++) {
    const d = h('div', 'cdiv'); d.title = 'Spaltenbreite ziehen · Doppelklick = Standard';
    d.style.left = ((cols[i].offsetLeft + cols[i].offsetWidth + cols[i + 1].offsetLeft) / 2) + 'px';
    d.onpointerdown = e => {
      e.preventDefault(); try { d.setPointerCapture(e.pointerId); } catch (x) { /* ohne Capture geht es auch */ }
      const s = grid.getBoundingClientRect().width / grid.offsetWidth || 1, x0 = e.clientX, w0 = cols.map(c => c.offsetWidth), x00 = parseFloat(d.style.left);
      let w = w0.slice();
      d.onpointermove = ev => {
        const dx = (ev.clientX - x0) / s, pair = w0[i] + w0[i + 1], a = Math.min(pair - 160, Math.max(160, w0[i] + dx));
        w = w0.slice(); w[i] = a; w[i + 1] = pair - a;
        grid.style.gridTemplateColumns = w.map(v => v + 'fr').join(' ');
        d.style.left = (x00 + (a - w0[i])) + 'px';
      };
      d.onpointerup = () => {
        d.onpointermove = d.onpointerup = null;
        const tot = w.reduce((p, v) => p + v, 0);
        set('colw', Object.assign({}, get('colw', {}), { [page.id]: w.map(v => Math.round(v / tot * w.length * 100) / 100) }));
        renderPage();
      };
    };
    d.ondblclick = () => { const o = Object.assign({}, get('colw', {})); delete o[page.id]; set('colw', o); renderPage(); };
    grid.append(d);
  }
}

function renderPage() {
  const page = CFG.pages.pages.find(p => p.id === PAGE) || CFG.pages.pages[0], grid = $('#grid');
  grid.innerHTML = '';
  grid.classList.toggle('edit', EDIT);
  const L = layoutFor(page), cw = (get('colw', {}) || {})[page.id], sizes = get('sizes', {}) || {};
  applyCols(page);
  let i = 0;
  L.forEach(col => {
    const cd = h('div', 'col');
    col.forEach(key => {
      const m = REG[key]; if (!m) return;
      const c = renderCard(m.card, m.pid, i++, key);
      if (sizes[key]) { c.style.flex = 'none'; c.style.height = sizes[key] + 'px'; c.dataset.fixed = '1'; }
      if (EDIT) { c.append(toolbar(page, key, c)); decorateItems(c, key, m.card); c.append(resizer(key, c)); }
      cd.append(c);
    });
    const last = cd.lastElementChild;
    if (last && !cd.querySelector('.flex') && !last.dataset.fixed) last.classList.add('flex');   // Resthoehe auffuellen
    grid.append(cd);
  });
  if (EDIT) { enableDnD(page, grid); colHandles(page, grid); }
  if (PICK) renderPicker();
  document.querySelectorAll('.tab').forEach(t => t.classList.toggle('on', t.dataset.p === page.id));
  renderLib(page);
  if (MODAL) renderModal();
  updateLive();
}
function setPage(id) { PAGE = id; set('page', id); renderPage(); }
function setEdit(on) {
  EDIT = on; if (!on) { PICK = false; renderPicker(); }
  const x = document.querySelector('#hb .ib[data-act="edit"]'); if (x) x.classList.toggle('on', EDIT);
  renderPage();
  toast(EDIT ? 'LAYOUT-MODUS: MODULE VERSCHIEBEN, ENTFERNEN, HINZUFÜGEN' : 'LAYOUT GESPEICHERT');
}

/* ---------- Einstellungen (Zahnrad oben rechts): Karten kommen aus config/settings.json ---------- */
let MODAL = false;
function renderModal() {
  const m = $('#modal'); if (!m) return;
  m.style.display = MODAL ? 'flex' : 'none';
  if (!MODAL) { m.innerHTML = ''; return; }
  const keep = m.querySelector('.sheet') ? m.querySelector('.sheet').scrollTop : 0, cfg = CFG.settings;
  m.innerHTML = '<div class="sheet"><div class="sh-head"><span class="sh-title"></span><button class="ib sh-close" aria-label="Schließen" title="Schließen (Esc)">✕</button></div><div class="sh-grid"></div></div>';
  $('.sh-title', m).textContent = cfg.title || 'EINSTELLUNGEN';
  $('.sh-close', m).onclick = closeSettings;
  m.onclick = e => { if (e.target === m) closeSettings(); };
  const g = $('.sh-grid', m); let i = 0;
  cfg.columns.forEach(col => { const cd = h('div', 'col'); col.forEach(card => cd.append(renderCard(card, 'settings', i++))); g.append(cd); });
  $('.sheet', m).scrollTop = keep;
  updateLive();
}
function openSettings() { MODAL = true; renderModal(); }
function closeSettings() { MODAL = false; renderModal(); }

function build() {
  const A = CFG.app;
  document.title = A.title;
  $('#root').innerHTML = `<div id="frame"><div id="scan" aria-hidden="true"></div>
    <div id="top"><span id="hl" style="display:flex;gap:10px;margin-right:6px"></span><div id="brand"><b></b><i></i></div><nav></nav><span class="grow"></span><span id="hb" style="display:flex;gap:14px"></span></div>
    <div id="pills"></div><div id="grid"></div><div id="lib"></div>
    <div id="foot"><div style="display:flex;align-items:center;gap:10px"><span class="lockic">${icon('lock', 'var(--bad)')}</span><button class="bad" id="fr"></button></div>
      <div id="hz"></div><div style="width:220px"><button class="btn" id="fc"></button></div></div>
    <div id="modal"></div><div id="picker"></div><div id="upd"></div><div id="toast"></div></div>`;
  $('#brand b').textContent = A.brand; $('#brand i').textContent = A.brandSub === 'auto' ? (THEME === 'RSI' ? 'STAR CITIZEN' : THEME) : A.brandSub;
  CFG.pages.pages.forEach(p => { const t = h('button', 'tab'); t.textContent = p.title; t.dataset.p = p.id; t.onclick = () => setPage(p.id); $('nav').append(t); });
  /* leftButtons = oben links (Zahnrad), headerButtons = oben rechts; beide aus config/app.json */
  const headerBtn = (b, host) => {
    const x = h('button', 'ib' + (b.big ? ' big' : '') + (b.label ? ' wide' : ''),
      icon(b.icon) + (b.label ? `<span class="bl">${esc(b.label)}</span>` : '')); x.title = b.title; x.setAttribute('aria-label', b.title);
    if (b.action) x.dataset.act = b.action;
    x.onclick = () => {
      if (b.action === 'edit') setEdit(!EDIT);
      else if (b.action === 'settings') openSettings();
      else if (b.goto) setPage(b.goto); else toast(b.toast || '');
    };
    host.append(x);
  };
  (A.leftButtons || []).forEach(b => headerBtn(b, $('#hl')));
  /* Sichtbare Groessen-Knoepfe: - 100 % + (Klick auf die Zahl = zurueck auf 100 %) */
  const zc = h('span', 'zoomctl', '<button class="ib" id="zm" title="Oberfläche kleiner (Strg −)" aria-label="Kleiner">−</button><b id="zv" title="Zurück auf 100 %"></b><button class="ib" id="zp" title="Oberfläche größer (Strg +)" aria-label="Größer">+</button>');
  $('#hb').append(zc);
  $('#zm', zc).onclick = () => setScale(get('uiscale', 100) - 10);
  $('#zp', zc).onclick = () => setScale(get('uiscale', 100) + 10);
  $('#zv', zc).onclick = () => setScale(100);
  zoomLabel();
  A.headerButtons.forEach(b => headerBtn(b, $('#hb')));
  const pl = $('#pills');
  A.pills.forEach(p => pl.append(h('span', 'pill ok', `<i></i>${esc(p.label)}`)));
  pl.querySelectorAll('.pill').forEach((e, i) => e.dataset.status = A.pills[i].status);
  pl.append(h('span', '', '')); pl.lastChild.id = 'state';
  $('#fr').textContent = A.footer.reset; $('#fr').onclick = e => runAction('reset', '', e.target);
  $('#fc').textContent = A.footer.clear; $('#fc').onclick = () => toast('NOCH NICHT VERBUNDEN');
  renderPage();
  try { const n = sessionStorage.getItem('rsi_done'); if (n) { PENDING_DONE = n; sessionStorage.removeItem('rsi_done'); } } catch (e) { /* ok */ }
  showUpdateDone();                                    // nach einem Update: "aktualisiert"-Animation
}

async function boot() {
  const j = u => fetch(u).then(r => r.json());
  [CFG.app, CFG.pages, CFG.themes, CFG.keys, CFG.settings, CFG.ships] = await Promise.all([j('config/app.json'), j('config/pages.json'), j('config/themes.json'), j('config/keybinds.json'), j('config/settings.json'),
    j('config/ships.json').catch(() => ({ default: 'cutlass', themes: {}, names: {} }))]);
  buildRegistry();
  await refresh();
  applyTheme(get('theme', 'RSI'));
  PAGE = get('page', CFG.pages.pages[0].id);
  build(); fit();
  addEventListener('resize', fit);
  /* Groesse der Oberflaeche: Strg + Mausrad oder Strg + / Strg - / Strg 0 (Standard) */
  addEventListener('wheel', e => { if (e.ctrlKey) { e.preventDefault(); setScale(get('uiscale', 100) + (e.deltaY < 0 ? 5 : -5)); } }, { passive: false });
  addEventListener('keydown', e => {
    if ((e.ctrlKey || e.metaKey) && ['+', '=', '-', '0'].includes(e.key)) { e.preventDefault(); setScale(e.key === '0' ? 100 : get('uiscale', 100) + (e.key === '-' ? -5 : 5)); }
  });
  addEventListener('keydown', e => { if (e.key === 'Escape') { if (PICK) closePicker(); else if (MODAL) closeSettings(); } });
  addEventListener('pagehide', () => navigator.sendBeacon('/api/bye', '{}'));
  setInterval(refresh, 1000);
}
boot();
