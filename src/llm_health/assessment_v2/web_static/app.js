(() => {
  const DATA = window.HEALTH_ASSESSMENT_V2 || { observations: [], reports: [], profile_context: {} };
  const rawRows = (DATA.observations || []).map(normalizeRow);
  const wearableRows = (DATA.wearable_daily || []).map(normalizeWearableRow).filter(r => r.isNumeric);
  const reports = new Map((DATA.reports || []).map(r => [r.source_id, r]));
  const state = readState();
  const categoryMap = new Map();
  const preferred = ['All categories', 'Liver', 'Lipids', 'CBC / Hematology', 'Heavy Metals', 'Vitals'];
  const linePalette = ['#2f6fb2', '#1f8a5b', '#b7791f', '#7c3aed', '#d94670', '#0891b2', '#b64035', '#6b7280'];
  const scaleOptions = [
    ['auto', 'Auto'],
    ['raw', 'Raw values'],
    ['norm', 'Normalized 0-100'],
    ['center', 'Mean-centered'],
    ['pctmean', '% of mean'],
    ['pctfirst', '% change from first'],
    ['z', 'Z-score'],
    ['log', 'Log10']
  ];
  const smoothOptions = [
    ['none', 'None'],
    ['mean3', '3-point mean'],
    ['mean7', '7-point mean'],
    ['mean30', '30-point mean']
  ];

  init();

  function init() {
    populateCategories();
    bindControls();
    render();
  }

  function readState() {
    const p = new URLSearchParams(location.search);
    return {
      profile: p.get('profile') || 'rod',
      range: p.get('range') || 'all',
      category: p.get('category') || 'All categories',
      mode: p.get('mode') || 'stack',
      scale: p.get('scale') || 'auto',
      agg: p.get('agg') || 'observed',
      smooth: p.get('smooth') || 'none',
      section: p.get('section') || 'review',
      search: p.get('q') || '',
      showWeight: p.get('weight') !== '0',
      showFlags: p.get('flags') !== '0',
      showLabels: p.get('labels') === '1',
      theme: p.get('theme') || localStorage.getItem('health-v2-theme') || 'light'
    };
  }

  function persist() {
    const p = new URLSearchParams();
    ['profile','range','category','mode','section'].forEach(k => p.set(k, state[k]));
    if (state.scale !== 'auto') p.set('scale', state.scale);
    if (state.agg !== 'observed') p.set('agg', state.agg);
    if (state.smooth !== 'none') p.set('smooth', state.smooth);
    if (state.search) p.set('q', state.search);
    if (!state.showWeight) p.set('weight', '0');
    if (!state.showFlags) p.set('flags', '0');
    if (state.showLabels) p.set('labels', '1');
    if (state.theme === 'dark') p.set('theme', 'dark');
    history.replaceState(null, '', `${location.pathname}?${p.toString()}`);
    localStorage.setItem('health-v2-theme', state.theme);
  }

  function bindControls() {
    document.documentElement.dataset.theme = state.theme;
    byId('themeToggle').textContent = state.theme === 'dark' ? 'Light theme' : 'Dark theme';
    byId('themeToggle').onclick = () => { state.theme = state.theme === 'dark' ? 'light' : 'dark'; render(); };
    byId('copyLink').onclick = async () => navigator.clipboard?.writeText(location.href);
    byId('downloadCsv').onclick = downloadCsv;
    byId('scaleSelect').innerHTML = scaleOptions.map(([value, label]) => `<option value="${value}">${escapeHtml(label)}</option>`).join('');
    byId('scaleSelect').value = state.scale;
    byId('scaleSelect').onchange = e => { state.scale = e.target.value; render(); };
    byId('smoothSelect').innerHTML = smoothOptions.map(([value, label]) => `<option value="${value}">${escapeHtml(label)}</option>`).join('');
    byId('smoothSelect').value = state.smooth;
    byId('smoothSelect').onchange = e => { state.smooth = e.target.value; render(); };
    byId('searchBox').value = state.search;
    byId('searchBox').oninput = e => { state.search = e.target.value; render(); };
    byId('showWeight').checked = state.showWeight;
    byId('showWeight').onchange = e => { state.showWeight = e.target.checked; render(); };
    byId('showFlags').checked = state.showFlags;
    byId('showFlags').onchange = e => { state.showFlags = e.target.checked; render(); };
    byId('showLabels').checked = state.showLabels;
    byId('showLabels').onchange = e => { state.showLabels = e.target.checked; render(); };
    for (const btn of document.querySelectorAll('[data-profile]')) {
      btn.onclick = () => { state.profile = btn.dataset.profile; render(); };
    }
    for (const btn of document.querySelectorAll('[data-range]')) {
      btn.onclick = () => { state.range = btn.dataset.range; render(); };
    }
    for (const btn of document.querySelectorAll('[data-mode]')) {
      btn.onclick = () => { state.mode = btn.dataset.mode; render(); };
    }
    for (const btn of document.querySelectorAll('[data-agg]')) {
      btn.onclick = () => { state.agg = btn.dataset.agg; render(); };
    }
    for (const btn of document.querySelectorAll('[data-section]')) {
      btn.onclick = () => { state.section = btn.dataset.section; render(); };
    }
    byId('categorySelect').onchange = e => { state.category = e.target.value; render(); };
  }

  function populateCategories() {
    for (const row of rawRows) {
      if (!row.isNumeric) continue;
      const label = canonicalCategory(row.panel_en || 'Other');
      if (!categoryMap.has(label)) categoryMap.set(label, []);
      categoryMap.get(label).push(row);
    }
    const categories = ['All categories', ...[...categoryMap.keys()].sort((a,b) => rank(a) - rank(b) || a.localeCompare(b))];
    byId('categorySelect').innerHTML = categories.map(c => `<option>${escapeHtml(c)}</option>`).join('');
    if (!categories.includes(state.category)) state.category = 'All categories';
    byId('categorySelect').value = state.category;
  }

  function render() {
    document.documentElement.dataset.theme = state.theme;
    byId('themeToggle').textContent = state.theme === 'dark' ? 'Light theme' : 'Dark theme';
    for (const btn of document.querySelectorAll('[data-profile]')) btn.classList.toggle('active', btn.dataset.profile === state.profile);
    for (const btn of document.querySelectorAll('[data-range]')) btn.classList.toggle('active', btn.dataset.range === state.range);
    for (const btn of document.querySelectorAll('[data-mode]')) btn.classList.toggle('active', btn.dataset.mode === state.mode);
    for (const btn of document.querySelectorAll('[data-agg]')) btn.classList.toggle('active', btn.dataset.agg === state.agg);
    for (const btn of document.querySelectorAll('[data-section]')) btn.classList.toggle('active', btn.dataset.section === state.section);
    byId('categorySelect').value = state.category;
    byId('scaleSelect').value = state.scale;
    byId('smoothSelect').value = state.smooth;
    byId('reviewSection').hidden = state.section !== 'review';
    byId('timelineSection').hidden = state.section !== 'timeline';
    byId('sourcesSection').hidden = state.section !== 'sources';
    const rows = filteredRows();
    renderSummary(rows);
    renderReview(rows);
    renderTimeline(rows);
    renderTable(rows);
    persist();
  }

  function filteredRows() {
    const profileRows = rawRows.filter(r => r.profile_id === state.profile);
    const latest = maxDate(profileRows);
    const min = rangeStart(latest, state.range);
    const q = state.search.trim().toLowerCase();
    return profileRows.filter(r => {
      if (min && r.time < min.getTime()) return false;
      if (state.category !== 'All categories' && canonicalCategory(r.panel_en || 'Other') !== state.category) return false;
      if (q && !`${r.analyte_en} ${r.panel_en} ${r.source_id} ${r.value_raw}`.toLowerCase().includes(q)) return false;
      return true;
    });
  }

  function renderSummary(rows) {
    const numeric = rows.filter(r => r.isNumeric);
    const flagged = rows.filter(r => r.flag_raw || r.isPending).length;
    const context = DATA.profile_context?.[state.profile] || {};
    const dates = rows.map(r => r.date).filter(Boolean).sort();
    byId('summaryGrid').innerHTML = [
      metric('Rows', rows.length.toLocaleString(), `${numeric.length.toLocaleString()} numeric`),
      metric('Flag/pending', flagged.toLocaleString(), 'source attention rows'),
      metric('Span', dates.length ? `${dates[0]} → ${dates.at(-1)}` : '—', state.range),
      metric('Weight', Number.isFinite(context.currentWeightKg) ? `${context.currentWeightKg} kg` : '—', context.currentWeightDate || 'no context')
    ].join('');
  }

  function metric(label, value, sub) {
    return `<div class="metric"><div class="label">${escapeHtml(label)}</div><div class="value">${escapeHtml(String(value))}</div><div class="muted">${escapeHtml(sub || '')}</div></div>`;
  }

  function renderReview(rows) {
    const numeric = rows.filter(r => r.isNumeric);
    const flags = rows.filter(r => r.flag_raw || r.isPending).slice(0, 6);
    const context = DATA.profile_context?.[state.profile] || {};
    const latestLab = maxDate(rows);
    const cards = [];
    cards.push(reviewCard('Current context', [
      ['CONTEXT', context.currentWeightKg ? `Latest weight ${context.currentWeightKg} kg on ${context.currentWeightDate}` : 'No weight context for this profile'],
      ['OBSERVED', `${numeric.length} numeric observations in this view`]
    ]));
    if (flags.length) cards.push(reviewCard('Needs attention', flags.map(r => ['FLAG', `${r.date} · ${r.analyte_en}: ${r.value_raw || r.interpretation_en || 'pending'} ${r.unit_raw || ''}`])));
    const wearableSummary = wearableReviewLines();
    if (wearableSummary.length) cards.push(reviewCard('Wearable context', wearableSummary));
    cards.push(reviewCard('Timeline posture', [
      ['OBSERVED', `Latest visible date ${latestLab ? iso(latestLab) : '—'}`],
      ['DATA_GAP', 'Interpret patterns with clinician context, meds/supplements, symptoms, and source references.']
    ]));
    byId('reviewGrid').innerHTML = cards.join('');
  }

  function reviewCard(title, rows) {
    return `<article class="review-card"><strong>${escapeHtml(title)}</strong>${rows.map(([tag,text]) => `<div><span class="tag ${tagClass(tag)}">${escapeHtml(tag)}</span>${escapeHtml(text)}</div>`).join('')}</article>`;
  }

  function renderTimeline(rows) {
    const numeric = rows.filter(r => r.isNumeric);
    const groups = groupSeries(numeric);
    byId('timelineTitle').textContent = `${state.category} · ${state.mode === 'overlay' ? 'overlay' : 'stacked small multiples'}`;
    byId('timelineMeta').textContent = `${numeric.length} numeric points · ${groups.length} marker/unit series · ${state.range} · ${scaleLabel(effectiveScale(state.mode))} · ${aggLabel()} · ${smoothLabel()}`;
    byId('weightRail').innerHTML = state.showWeight ? weightRail() : '';
    if (!groups.length) {
      byId('charts').innerHTML = '<div class="empty">No numeric observations match this view.</div>';
      return;
    }
    byId('charts').innerHTML = state.mode === 'overlay' ? overlayCards(groups) : stackedCards(groups);
  }

  function groupSeries(rows) {
    const map = new Map();
    for (const r of rows) {
      const category = canonicalCategory(r.panel_en || 'Other');
      const key = `${category}||${r.analyte_en}||${r.unit_raw || ''}`;
      if (!map.has(key)) map.set(key, { category, name: r.analyte_en, unit: r.unit_raw || '', rows: [] });
      map.get(key).rows.push(r);
    }
    return [...map.values()].filter(g => g.rows.length).sort((a,b) => rank(a.category) - rank(b.category) || a.category.localeCompare(b.category) || a.name.localeCompare(b.name));
  }

  function stackedCards(groups) {
    const limit = state.category === 'All categories' ? 160 : 50;
    if (state.category !== 'All categories') return groups.slice(0, limit).map(g => chartCard(g)).join('');
    const sections = groupBy(groups.slice(0, limit), g => g.category);
    return [...sections.entries()].map(([category, categoryGroups]) => categorySection(category, categoryGroups.map(g => chartCard(g)).join(''))).join('');
  }

  function overlayCards(groups) {
    const sections = state.category === 'All categories' ? groupBy(groups, g => g.category) : new Map([[state.category, groups]]);
    return [...sections.entries()].map(([category, categoryGroups]) => overlayCard(category, categoryGroups)).join('');
  }

  function categorySection(category, body) {
    const count = (categoryMap.get(category) || []).filter(r => r.profile_id === state.profile).length;
    return `<section class="category-section"><div class="category-head"><strong>${escapeHtml(category)}</strong><span>${count.toLocaleString()} visible-capable rows</span></div>${body}</section>`;
  }

  function chartCard(group) {
    const rawPoints = group.rows.sort((a,b) => a.time - b.time);
    const prepared = preparePoints(rawPoints, 'stack');
    const points = prepared.points;
    if (!points.length) return '';
    const ref = prepared.scale === 'raw' ? referenceFor(rawPoints) : null;
    const refText = ref?.label ? ` · ref ${ref.label}` : '';
    return `<article class="chart-card"><div class="chart-title"><strong>${escapeHtml(group.name)}${group.unit ? ` (${escapeHtml(group.unit)})` : ''}</strong><span>${points.length} points · ${points[0].date} → ${points.at(-1).date} · ${escapeHtml(prepared.note)}${escapeHtml(refText)}</span></div>${svgFor(points, group, prepared)}</article>`;
  }

  function svgFor(points, group, prepared) {
    const w = 1040, h = 150, left = 58, right = 18, top = 18, bottom = 30;
    const xs = points.map(p => p.time); const ys = points.map(p => p.plotNum);
    const minX = Math.min(...xs), maxX = Math.max(...xs);
    let minY = Math.min(...ys), maxY = Math.max(...ys);
    const ref = prepared.scale === 'raw' ? referenceFor(points) : null;
    if (ref?.low !== null && Number.isFinite(ref?.low)) minY = Math.min(minY, ref.low);
    if (ref?.high !== null && Number.isFinite(ref?.high)) maxY = Math.max(maxY, ref.high);
    if (minY === maxY) { minY -= 1; maxY += 1; }
    const pad = (maxY - minY) * .12; minY -= pad; maxY += pad;
    const x = t => left + ((t - minX) / Math.max(1, maxX - minX)) * (w - left - right);
    const y = v => top + (1 - ((v - minY) / Math.max(1e-9, maxY - minY))) * (h - top - bottom);
    const d = points.map((p,i) => `${i ? 'L' : 'M'}${x(p.time).toFixed(1)},${y(ys[i]).toFixed(1)}`).join(' ');
    const ticks = [minY, (minY + maxY) / 2, maxY];
    const band = refBand(ref, minY, maxY, y, left, w - right);
    const weight = state.showWeight ? weightOverlay(minX, maxX, x, y, minY, maxY) : '';
    return `<svg viewBox="0 0 ${w} ${h}" aria-label="${escapeAttr(points[0].analyte_en)} timeline">
      ${band}
      ${ticks.map(t => `<line class="grid" x1="${left}" x2="${w-right}" y1="${y(t)}" y2="${y(t)}"/><text class="tick-label" x="8" y="${y(t)+4}">${round(t)}</text>`).join('')}
      <line class="axis" x1="${left}" x2="${w-right}" y1="${h-bottom}" y2="${h-bottom}"/>
      <path class="series-line" d="${d}"/>
      ${weight}
      ${points.map((p,i) => `<circle class="point${state.showFlags && p.flag_raw ? ' flagged' : ''}" cx="${x(p.time)}" cy="${y(ys[i])}" r="4.6"><title>${escapeHtml(`${p.date} · ${p.analyte_en}: ${p.value_raw} ${group.unit}\nplotted ${round(p.plotNum)} (${prepared.ylabel})\n${p.reference_range_raw ? 'ref ' + p.reference_range_raw : ''}\n${p.flag_raw || ''}`)}</title></circle>`).join('')}
      ${state.showLabels ? points.map((p,i) => `<text class="point-label" x="${x(p.time)+6}" y="${y(ys[i])-6}">${escapeHtml(p.date.slice(2))}</text>`).join('') : ''}
      <text class="tick-label" x="${left}" y="${h-8}">${escapeHtml(points[0].date)}</text><text class="tick-label" text-anchor="end" x="${w-right}" y="${h-8}">${escapeHtml(points.at(-1).date)}</text>
    </svg>`;
  }

  function overlayCard(category, groups) {
    const useful = groups.filter(g => g.rows.length).slice(0, 18);
    const hidden = Math.max(0, groups.length - useful.length);
    const points = useful.flatMap(g => g.rows);
    const dateSpan = points.length ? `${minIso(points)} → ${maxIso(points)}` : '—';
    const legend = useful.map((g, i) => `<span><i class="swatch" style="background:${lineColor(i)}"></i>${escapeHtml(g.name)}</span>`).join('');
    return `<article class="chart-card overlay-card"><div class="chart-title"><strong>${escapeHtml(category)} overlay</strong><span>${useful.length} series · ${dateSpan} · ${escapeHtml(scaleLabel(effectiveScale('overlay')))}${hidden ? ` · ${hidden} hidden to keep readable` : ''}</span></div><div class="overlay-note">${escapeHtml(overlayNote())}</div><div class="inline-legend">${legend}</div>${overlaySvg(useful)}</article>`;
  }

  function overlaySvg(groups) {
    const w = 1040, h = 260, left = 58, right = 22, top = 22, bottom = 32;
    const preparedGroups = groups.map(g => ({ ...g, prepared: preparePoints(g.rows, 'overlay') })).filter(g => g.prepared.points.length);
    const allPoints = preparedGroups.flatMap(g => g.prepared.points);
    if (!allPoints.length) return '<div class="empty">No overlayable series.</div>';
    const minX = Math.min(...allPoints.map(p => p.time));
    const maxX = Math.max(...allPoints.map(p => p.time));
    let minY = Math.min(...allPoints.map(p => p.plotNum));
    let maxY = Math.max(...allPoints.map(p => p.plotNum));
    if (minY === maxY) { minY -= 1; maxY += 1; }
    const pad = (maxY - minY) * .08; minY -= pad; maxY += pad;
    const x = t => left + ((t - minX) / Math.max(1, maxX - minX)) * (w - left - right);
    const y = v => top + (1 - ((v - minY) / Math.max(1e-9, maxY - minY))) * (h - top - bottom);
    const ticks = [minY, (minY + maxY) / 2, maxY];
    const lines = preparedGroups.map((g, i) => {
      const points = g.prepared.points;
      const ys = points.map(p => p.plotNum);
      const d = points.map((p,j) => `${j ? 'L' : 'M'}${x(p.time).toFixed(1)},${y(ys[j]).toFixed(1)}`).join(' ');
      const circles = points.map((p,j) => `<circle class="point${state.showFlags && p.flag_raw ? ' flagged' : ''}" style="fill:${lineColor(i)}" cx="${x(p.time)}" cy="${y(ys[j])}" r="3.5"><title>${escapeHtml(`${p.date} · ${g.name}: ${p.value_raw} ${g.unit || ''}\nplotted ${round(p.plotNum)} (${g.prepared.ylabel})`)}</title></circle>`).join('');
      return `<path class="series-line overlay-series" style="stroke:${lineColor(i)}" d="${d}"/>${circles}`;
    }).join('');
    const weight = state.showWeight ? normalizedWeightOverlay(minX, maxX, x, y, minY, maxY) : '';
    const labels = state.showLabels ? allPoints.slice(0, 60).map(p => `<text class="point-label" x="${x(p.time)+5}" y="${y(maxY)-5}">${escapeHtml(p.date.slice(2))}</text>`).join('') : '';
    return `<svg viewBox="0 0 ${w} ${h}" aria-label="normalized overlay">
      ${ticks.map(t => `<line class="grid" x1="${left}" x2="${w-right}" y1="${y(t)}" y2="${y(t)}"/><text class="tick-label" x="8" y="${y(t)+4}">${round(t)}</text>`).join('')}
      <line class="axis" x1="${left}" x2="${w-right}" y1="${h-bottom}" y2="${h-bottom}"/>
      ${lines}
      ${weight}
      ${labels}
      <text class="tick-label" x="${left}" y="${h-8}">${escapeHtml(iso(new Date(minX)))}</text><text class="tick-label" text-anchor="end" x="${w-right}" y="${h-8}">${escapeHtml(iso(new Date(maxX)))}</text>
    </svg>`;
  }

  function refBand(ref, minY, maxY, y, x1, x2) {
    if (!ref) return '';
    const low = Number.isFinite(ref.low) ? ref.low : minY;
    const high = Number.isFinite(ref.high) ? ref.high : maxY;
    const y1 = y(Math.min(maxY, Math.max(minY, high)));
    const y2 = y(Math.max(minY, Math.min(maxY, low)));
    return `<rect class="band" x="${x1}" y="${Math.min(y1, y2)}" width="${x2 - x1}" height="${Math.abs(y2 - y1)}"><title>${escapeHtml(`reference ${ref.label}`)}</title></rect>`;
  }

  function weightOverlay(minX, maxX, x, y, minY, maxY) {
    const rows = weightRowsInDomain(minX, maxX);
    if (rows.length < 2) return '';
    const minKg = Math.min(...rows.map(r => r.kg)), maxKg = Math.max(...rows.map(r => r.kg));
    const value = kg => minY + (maxKg === minKg ? .5 : (kg - minKg) / (maxKg - minKg)) * (maxY - minY);
    const d = rows.map((r,i) => `${i ? 'L' : 'M'}${x(r.time).toFixed(1)},${y(value(r.kg)).toFixed(1)}`).join(' ');
    return `<path class="weight-line" d="${d}"><title>normalized weight context; not the same unit as this marker</title></path>`;
  }

  function normalizedWeightOverlay(minX, maxX, x, y, minY, maxY) {
    const rows = weightRowsInDomain(minX, maxX);
    if (rows.length < 2) return '';
    const values = normalize(rows.map(r => r.kg));
    const scaled = values.map(v => minY + (v / 100) * (maxY - minY));
    const d = rows.map((r,i) => `${i ? 'L' : 'M'}${x(r.time).toFixed(1)},${y(scaled[i]).toFixed(1)}`).join(' ');
    return `<path class="weight-line" d="${d}"><title>normalized weight context</title></path>`;
  }

  function weightRowsInDomain(minX, maxX) {
    return rawRows
      .filter(r => r.profile_id === state.profile && r.analyte_en.toLowerCase() === 'weight' && r.isNumeric && r.time >= minX && r.time <= maxX)
      .map(r => ({ ...r, kg: weightKg(r) }))
      .filter(r => Number.isFinite(r.kg))
      .sort((a,b) => a.time - b.time);
  }

  function weightRail() {
    const rows = rawRows.filter(r => r.profile_id === state.profile && r.analyte_en.toLowerCase() === 'weight' && r.isNumeric).map(r => ({ ...r, kg: weightKg(r) })).filter(r => Number.isFinite(r.kg)).sort((a,b) => a.time - b.time);
    if (!rows.length) return '<div class="empty">No weight context for this profile.</div>';
    const w = 1040, h = 86, left = 58, right = 18, top = 14, bottom = 24;
    const minX = rows[0].time, maxX = rows.at(-1).time;
    let minY = Math.min(...rows.map(r => r.kg)), maxY = Math.max(...rows.map(r => r.kg));
    if (minY === maxY) { minY -= 1; maxY += 1; }
    const x = t => left + ((t - minX) / Math.max(1, maxX - minX)) * (w - left - right);
    const y = v => top + (1 - ((v - minY) / (maxY - minY))) * (h - top - bottom);
    const d = rows.map((r,i) => `${i ? 'L' : 'M'}${x(r.time).toFixed(1)},${y(r.kg).toFixed(1)}`).join(' ');
    return `<article class="chart-card"><div class="chart-title"><strong>Weight context</strong><span>${rows.length} points · latest ${round(rows.at(-1).kg)} kg on ${rows.at(-1).date}</span></div><svg viewBox="0 0 ${w} ${h}"><path class="weight-line" d="${d}"/>${rows.map(r => `<circle class="weight-point" cx="${x(r.time)}" cy="${y(r.kg)}" r="4"><title>${r.date}: ${round(r.kg)} kg</title></circle>`).join('')}<text class="tick-label" x="8" y="${y(maxY)+4}">${round(maxY)}kg</text><text class="tick-label" x="8" y="${y(minY)+4}">${round(minY)}kg</text></svg></article>`;
  }

  function renderTable(rows) {
    const visible = rows.slice().sort((a,b) => b.time - a.time).slice(0, 500);
    byId('tableMeta').textContent = `Showing ${visible.length} of ${rows.length} rows`;
    byId('rowsTable').innerHTML = visible.map(r => `<tr><td>${escapeHtml(r.date)}</td><td>${escapeHtml(r.panel_en)}</td><td>${escapeHtml(r.analyte_en)}</td><td class="result">${escapeHtml(r.value_raw)}</td><td>${escapeHtml(r.reference_range_raw)}</td><td>${r.flag_raw ? `<span class="tag flag">${escapeHtml(r.flag_raw)}</span>` : r.isPending ? '<span class="tag gap">PENDING</span>' : ''}</td><td>${sourceLink(r)}</td></tr>`).join('') || '<tr><td colspan="7">No rows.</td></tr>';
  }

  function sourceLink(r) {
    const report = reports.get(r.source_id) || {};
    const text = r.source_id || 'source';
    return report.source_note_path ? `<a href="${escapeAttr(report.source_note_path)}">${escapeHtml(text)}</a>` : escapeHtml(text);
  }

  function downloadCsv() {
    const rows = filteredRows();
    const fields = ['observation_date','profile_id','panel_en','analyte_en','value_raw','numeric_value','unit_raw','reference_range_raw','flag_raw','source_id'];
    const csv = [fields.join(','), ...rows.map(r => fields.map(f => csvCell(r[f])).join(','))].join('\n');
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }));
    a.download = `health-v2-${state.profile}-${state.category.replaceAll(' ', '-')}.csv`;
    a.click(); URL.revokeObjectURL(a.href);
  }

  function preparePoints(points, mode) {
    let rows = points.slice().sort((a,b) => a.time - b.time).filter(p => p.isNumeric);
    if (state.agg === 'mean-date') rows = meanByDate(rows);
    const smoothWindow = smoothingWindow();
    let values = rows.map(r => r.num);
    if (smoothWindow > 1) values = rollingMean(values, smoothWindow);
    rows = rows.map((r, i) => ({ ...r, plotNum: values[i] }));
    const scale = effectiveScale(mode);
    const transformed = transformRows(rows, scale).filter(r => Number.isFinite(r.plotNum));
    return {
      points: transformed,
      scale,
      ylabel: scaleLabel(scale),
      note: `${scaleLabel(scale)} · ${aggLabel()} · ${smoothLabel()}`
    };
  }

  function transformRows(rows, scale) {
    const values = rows.map(r => r.plotNum);
    if (scale === 'raw') return rows;
    if (scale === 'norm') {
      const norm = normalize(values);
      return rows.map((r, i) => ({ ...r, plotNum: norm[i] }));
    }
    if (scale === 'center') {
      const mean = average(values);
      return rows.map(r => ({ ...r, plotNum: r.plotNum - mean }));
    }
    if (scale === 'pctmean') {
      const mean = average(values);
      return rows.map(r => ({ ...r, plotNum: mean ? (r.plotNum / mean) * 100 : Number.NaN }));
    }
    if (scale === 'pctfirst') {
      const first = values.find(Number.isFinite);
      return rows.map(r => ({ ...r, plotNum: first ? ((r.plotNum - first) / Math.abs(first)) * 100 : Number.NaN }));
    }
    if (scale === 'z') {
      const mean = average(values);
      const sd = standardDeviation(values, mean);
      return rows.map(r => ({ ...r, plotNum: sd ? (r.plotNum - mean) / sd : 0 }));
    }
    if (scale === 'log') {
      return rows.map(r => ({ ...r, plotNum: r.plotNum > 0 ? Math.log10(r.plotNum) : Number.NaN }));
    }
    return rows;
  }

  function meanByDate(rows) {
    const map = new Map();
    for (const row of rows) {
      const key = row.date;
      if (!map.has(key)) map.set(key, []);
      map.get(key).push(row);
    }
    return [...map.values()].map(group => {
      const avg = average(group.map(r => r.num));
      return { ...group[0], num: avg, value_raw: `mean ${round(avg)}` };
    }).sort((a,b) => a.time - b.time);
  }

  function rollingMean(values, windowSize) {
    return values.map((_, i) => {
      const start = Math.max(0, i - windowSize + 1);
      return average(values.slice(start, i + 1));
    });
  }

  function smoothingWindow() {
    if (state.smooth === 'mean3') return 3;
    if (state.smooth === 'mean7') return 7;
    if (state.smooth === 'mean30') return 30;
    return 1;
  }

  function effectiveScale(mode) {
    if (state.scale !== 'auto') return state.scale;
    return mode === 'overlay' ? 'norm' : 'raw';
  }

  function scaleLabel(scale) {
    return new Map(scaleOptions).get(scale) || scale;
  }

  function aggLabel() {
    return state.agg === 'mean-date' ? 'mean by date' : 'observed points';
  }

  function smoothLabel() {
    return new Map(smoothOptions).get(state.smooth) || 'None';
  }

  function overlayNote() {
    const scale = effectiveScale('overlay');
    if (scale === 'raw') return 'Raw overlay can mix units and scales; use it only for same-unit series.';
    if (scale === 'norm') return 'Each line is scaled 0-100 inside its own marker. Use this to compare timing/direction, not absolute values.';
    if (scale === 'log') return 'Log10 overlay hides non-positive values and compresses large ranges.';
    return `${scaleLabel(scale)} overlay compares relative shape across visible series.`;
  }

  function normalizeRow(r) {
    const num = Number.parseFloat(r.numeric_value);
    return { ...r, date: r.observation_date || r.collection_date || '', time: Date.parse(r.observation_date || r.collection_date || ''), num, isNumeric: Number.isFinite(num), isPending: /pending/i.test(r.result_type || r.value_raw || '') };
  }
  function normalizeWearableRow(r) {
    const value = wearableValue(r);
    const date = r.date || '';
    return { ...r, date, time: Date.parse(date), value, isNumeric: Number.isFinite(value) && Number.isFinite(Date.parse(date)) };
  }
  function wearableValue(r) {
    const pref = (r.aggregation_preferred || '').toLowerCase();
    const field = pref === 'avg' || pref === 'average' ? 'value_avg' : pref === 'last' ? 'value_last' : 'value_sum';
    const value = Number.parseFloat(r[field] || r.value_sum || r.value_avg || r.value_last);
    return Number.isFinite(value) ? value : Number.NaN;
  }
  function wearableReviewLines() {
    const rows = wearableRows.filter(r => r.profile_id === state.profile);
    if (!rows.length) return [];
    const latest = maxDate(rows);
    const min = rangeStart(latest, state.range) || new Date(latest.getFullYear(), latest.getMonth(), latest.getDate() - 29);
    const visible = rows.filter(r => r.time >= min.getTime());
    const lines = [];
    const steps = avgForWearable(visible, 'Step count');
    const active = avgForWearable(visible, 'Active energy burned');
    const distance = avgForWearable(visible, 'Walking/running distance');
    if (steps) lines.push(['WEARABLE_CONTEXT', `${steps.days}d avg steps ${round(steps.value)} count/day`]);
    if (active) lines.push(['WEARABLE_CONTEXT', `${active.days}d avg active energy ${round(active.value)} ${active.unit || 'Cal'}/day`]);
    if (distance) lines.push(['WEARABLE_CONTEXT', `${distance.days}d avg walk/run distance ${round(distance.value)} ${distance.unit || ''}/day`]);
    return lines.slice(0, 3);
  }
  function avgForWearable(rows, metric) {
    const matches = rows.filter(r => r.metric_en === metric && Number.isFinite(r.value));
    if (!matches.length) return null;
    return { value: matches.reduce((sum, r) => sum + r.value, 0) / matches.length, days: matches.length, unit: matches.at(-1).unit };
  }
  function canonicalCategory(panel) {
    const lower = panel.toLowerCase();
    if (lower.includes('liver') || lower.includes('bilirubin')) return 'Liver';
    if (lower.includes('lipid') || lower.includes('cholesterol')) return 'Lipids';
    if (lower.includes('heavy metal')) return 'Heavy Metals';
    if (lower.includes('cbc') || lower.includes('blood count') || lower.includes('hematology')) return 'CBC / Hematology';
    if (lower.includes('thyroid')) return 'Thyroid';
    if (lower.includes('kidney') || lower.includes('renal')) return 'Kidney';
    if (lower.includes('vital')) return 'Vitals';
    return panel || 'Other';
  }
  function referenceFor(points) {
    const labels = points.map(p => p.reference_range_raw).filter(Boolean);
    for (let i = labels.length - 1; i >= 0; i--) {
      const parsed = parseReference(labels[i]);
      if (parsed) return parsed;
    }
    return null;
  }
  function parseReference(raw) {
    const label = String(raw || '').trim();
    if (!label) return null;
    const text = label.replaceAll(',', '.').replace(/[–—]/g, '-');
    const range = text.match(/(\d+(?:\.\d+)?)\s*(?:-|to)\s*(\d+(?:\.\d+)?)/i);
    if (range) return { low: Number(range[1]), high: Number(range[2]), label };
    const nums = text.match(/\d+(?:\.\d+)?/g)?.map(Number) || [];
    if (!nums.length) return null;
    if (/[≤<]|<=|less than|up to/i.test(text)) return { low: 0, high: nums[0], label };
    if (/[≥>]|>=|greater than|at least/i.test(text)) return { low: nums[0], high: null, label };
    return null;
  }
  function groupBy(items, keyFn) {
    const map = new Map();
    for (const item of items) {
      const key = keyFn(item);
      if (!map.has(key)) map.set(key, []);
      map.get(key).push(item);
    }
    return new Map([...map.entries()].sort(([a], [b]) => rank(a) - rank(b) || String(a).localeCompare(String(b))));
  }
  function minIso(rows) { return iso(new Date(Math.min(...rows.map(r => r.time)))); }
  function maxIso(rows) { return iso(new Date(Math.max(...rows.map(r => r.time)))); }
  function lineColor(index) { return linePalette[index % linePalette.length]; }
  function rank(c) { const i = preferred.indexOf(c); return i === -1 ? 99 : i; }
  function maxDate(rows) { const ts = rows.map(r => r.time).filter(Number.isFinite); return ts.length ? new Date(Math.max(...ts)) : null; }
  function rangeStart(latest, range) { if (!latest || range === 'all') return null; const d = new Date(latest); if (range === '30d') d.setDate(d.getDate() - 29); else if (range === '90d') d.setDate(d.getDate() - 89); else if (range === '18mo') d.setMonth(d.getMonth() - 18); else if (range === 'ytd') return new Date(latest.getFullYear(), 0, 1); return d; }
  function normalize(values) {
    const finite = values.filter(Number.isFinite);
    const min = Math.min(...finite), max = Math.max(...finite);
    return values.map(v => !Number.isFinite(v) ? Number.NaN : max === min ? 50 : ((v - min) / (max - min)) * 100);
  }
  function average(values) {
    const finite = values.filter(Number.isFinite);
    return finite.length ? finite.reduce((sum, value) => sum + value, 0) / finite.length : Number.NaN;
  }
  function standardDeviation(values, mean) {
    const finite = values.filter(Number.isFinite);
    if (finite.length < 2) return 0;
    const variance = finite.reduce((sum, value) => sum + ((value - mean) ** 2), 0) / (finite.length - 1);
    return Math.sqrt(variance);
  }
  function weightKg(r) { const v = r.num; const u = (r.unit_raw || '').toLowerCase(); return ['lb','lbs','pound','pounds'].includes(u) ? v * 0.45359237 : v; }
  function tagClass(tag) { return tag === 'FLAG' ? 'flag' : tag === 'CONTEXT' || tag === 'WEARABLE_CONTEXT' ? 'context' : tag === 'DATA_GAP' ? 'gap' : tag === 'DERIVED' ? 'derived' : 'obs'; }
  function iso(d) { return d.toISOString().slice(0,10); }
  function round(v) { return Number.isFinite(v) ? Number(v.toFixed(Math.abs(v) < 10 ? 2 : 1)).toString() : '—'; }
  function byId(id) { return document.getElementById(id); }
  function escapeHtml(s) { return String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }
  function escapeAttr(s) { return escapeHtml(s).replace(/'/g, '&#39;'); }
  function csvCell(v) { const s = String(v ?? ''); return /[",\n]/.test(s) ? `"${s.replaceAll('"','""')}"` : s; }
})();
