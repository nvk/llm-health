# ruff: noqa: E501

from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from llm_health import __version__
from llm_health.core.privacy import PrivacyError
from llm_health.stores import LocalHealthStore

from .pipeline import (
    genomics_crossrefs_payload,
    genomics_qc_payload,
    genomics_review_payload,
    genomics_sources_payload,
)
from .store import GenomicsStore
from .workflow import import_raw_genotype_text_into_store, run_crossrefs_into_store

MAX_GENOTYPE_UPLOAD_BYTES = 80 * 1024 * 1024


def render_genomics_import_ui() -> str:
    """Return a local-only genotype import page.

    The browser reads the chosen file as text and posts only the file content to the localhost
    server. Browser-provided file names and filesystem paths are never sent by the page.
    """

    return r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>llm-health · Genomics import</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f5f7fa;
      --paper: #fff;
      --paper-2: #eef3f7;
      --ink: #162033;
      --muted: #66748a;
      --line: #d8e0ea;
      --accent: #2f6fb2;
      --warn: #b7791f;
      --danger: #9b6a5e;
      --good: #1f8a5b;
      --shadow: 0 12px 28px rgba(30, 42, 62, .07);
      --focus: color-mix(in srgb, var(--accent), transparent 68%);
      --space-1: .25rem;
      --space-2: .5rem;
      --space-3: .75rem;
      --space-4: 1rem;
      --space-5: 1.25rem;
      --space-6: 1.5rem;
      --space-7: 2rem;
      --mono: "SF Mono", ui-monospace, Menlo, Consolas, monospace;
      --sans: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    * { box-sizing: border-box; }
    body { margin: 0; background: var(--bg); color: var(--ink); font-family: var(--sans); line-height: 1.45; }
    main { max-width: 1280px; margin: 0 auto; padding: clamp(var(--space-4), 2.4vw, var(--space-7)); }
    header, section { background: var(--paper); border: 1px solid var(--line); border-radius: 22px; box-shadow: var(--shadow); padding: clamp(var(--space-5), 2vw, var(--space-7)); margin-bottom: var(--space-5); }
    header { display: flex; justify-content: space-between; gap: var(--space-6); align-items: flex-start; }
    h1, h2, h3 { margin: 0; letter-spacing: -.02em; line-height: 1.08; }
    h1 { font-size: clamp(1.75rem, 2.6vw, 2.45rem); }
    h2 { font-size: clamp(1.35rem, 2.1vw, 1.85rem); margin-bottom: var(--space-4); }
    h3 { margin-bottom: var(--space-2); }
    p { color: var(--muted); line-height: 1.55; margin: var(--space-3) 0 0; }
    header p:first-child { margin: 0 0 var(--space-2); }
    header p:last-child, .privacy-note { max-width: 76ch; }
    label { display: block; color: var(--muted); font-weight: 780; margin: 0 0 var(--space-2); }
    select, input[type="file"] { width: 100%; min-height: 2.85rem; border: 1px solid var(--line); border-radius: 14px; padding: .55rem .75rem; background: var(--paper); color: var(--ink); font: inherit; }
    input[type="checkbox"] { width: 1.1rem; height: 1.1rem; margin: .12rem 0 0; accent-color: var(--accent); flex: 0 0 auto; }
    select:focus-visible, input[type="file"]:focus-visible, input[type="checkbox"]:focus-visible, button:focus-visible, summary:focus-visible { outline: 3px solid var(--focus); outline-offset: 3px; }
    button { min-height: 2.75rem; border: 0; border-radius: 14px; background: var(--accent); color: #fff; padding: .75rem 1.05rem; font-weight: 850; cursor: pointer; font: inherit; transition: transform .12s ease, box-shadow .12s ease, background .12s ease; }
    button:hover:not(:disabled) { transform: translateY(-1px); box-shadow: 0 8px 18px rgba(47, 111, 178, .18); }
    button.secondary { background: var(--paper-2); color: var(--ink); border: 1px solid var(--line); }
    button:disabled { opacity: .55; cursor: not-allowed; }
    .grid { display: grid; grid-template-columns: minmax(340px, .9fr) minmax(460px, 1.35fr); gap: var(--space-5); align-items: start; }
    .form-stack { display: grid; gap: var(--space-4); }
    .field { min-width: 0; }
    .checkbox-group { display: grid; gap: var(--space-3); padding: var(--space-4); border: 1px solid var(--line); border-radius: 16px; background: color-mix(in srgb, var(--paper-2), transparent 35%); }
    .checkbox-row { display: flex; align-items: flex-start; gap: var(--space-3); color: var(--ink); line-height: 1.35; margin: 0; }
    .privacy-note { margin: calc(var(--space-1) * -1) 0 0; }
    .actions { display: flex; gap: var(--space-3); flex-wrap: wrap; align-items: center; padding-top: var(--space-1); }
    .status { min-height: 3rem; margin: 0; padding: var(--space-3); border: 1px solid var(--line); border-radius: 14px; background: var(--paper-2); font-family: var(--mono); color: var(--muted); white-space: pre-wrap; }
    .cards { overflow-x: auto; margin-top: var(--space-4); }
    .card { border: 1px solid var(--line); border-radius: 16px; background: var(--paper-2); padding: var(--space-4); }
    .table-wrap { border: 1px solid var(--line); border-radius: 16px; overflow: hidden; background: var(--paper); }
    table.review-table { width: 100%; border-collapse: collapse; table-layout: fixed; font-size: .9rem; }
    .review-table th { text-align: left; color: var(--muted); font-size: .72rem; letter-spacing: .08em; text-transform: uppercase; background: var(--paper-2); padding: .8rem .9rem; border-bottom: 1px solid var(--line); }
    .review-table td { vertical-align: top; padding: .95rem .9rem; border-bottom: 1px solid var(--line); line-height: 1.4; }
    .review-table tr:last-child td { border-bottom: 0; }
    .review-table th:nth-child(1), .review-table td:nth-child(1) { width: 23%; }
    .review-table th:nth-child(2), .review-table td:nth-child(2) { width: 18%; }
    .review-table th:nth-child(3), .review-table td:nth-child(3) { width: 16%; }
    .review-table th:nth-child(4), .review-table td:nth-child(4) { width: 27%; }
    .review-table th:nth-child(5), .review-table td:nth-child(5) { width: 16%; }
    .marker-title { display: block; font-weight: 900; color: var(--ink); margin-bottom: .35rem; }
    .plain-summary { color: var(--ink); font-weight: 850; line-height: 1.35; margin-bottom: .55rem; }
    .technical-summary { color: var(--muted); line-height: 1.45; }
    .muted { color: var(--muted); }
    .compact-tags .tag { font-size: .62rem; margin-bottom: .15rem; }
    details.evidence summary { color: var(--accent); cursor: pointer; font-weight: 850; }
    details.evidence ul { margin: .4rem 0 0; padding-left: 1rem; }
    details.evidence li { margin-bottom: .35rem; }
    .tag { display: inline-block; border: 1px solid var(--line); border-radius: 999px; padding: .12rem .45rem; margin: .1rem .2rem .2rem 0; font-size: .7rem; font-weight: 850; letter-spacing: .05em; }
    .tag.inference { color: var(--accent); }
    .tag.gap, .tag.warn { color: var(--warn); }
    .tag.context { color: var(--warn); }
    .metric { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--space-4); }
    .metric div { min-height: 5.4rem; border: 1px solid var(--line); border-radius: 16px; padding: var(--space-4); background: var(--paper-2); display: flex; flex-direction: column; justify-content: center; }
    .metric span { color: var(--ink); }
    .metric strong { display: block; font-family: var(--mono); font-size: 1.35rem; margin-top: .25rem; letter-spacing: -.02em; }
    #warnings { display: grid; gap: var(--space-3); margin-top: var(--space-4); }
    #warnings .card p { margin-top: var(--space-3); }
    .patient-summary { margin-top: var(--space-4); border: 1px solid var(--line); border-radius: 18px; padding: var(--space-5); background: linear-gradient(135deg, color-mix(in srgb, var(--accent), transparent 92%), var(--paper-2)); }
    .patient-summary h3 { font-size: 1.08rem; margin: var(--space-2) 0 0; }
    .patient-summary .summary-lead { color: var(--ink); font-size: 1.02rem; font-weight: 850; line-height: 1.45; margin-top: var(--space-3); }
    .patient-summary ul { display: grid; gap: var(--space-2); margin: var(--space-3) 0 0; padding-left: 1.1rem; color: var(--muted); }
    .patient-summary li { padding-left: var(--space-1); }
    code { font-family: var(--mono); }
    @media (max-width: 900px) {
      main { padding: var(--space-4); }
      header, section { border-radius: 18px; padding: var(--space-5); }
      .grid, .metric { grid-template-columns: 1fr; }
      header { display: block; }
      header button { margin-top: var(--space-4); }
      .actions { display: grid; }
      .actions button { width: 100%; }
      .review-table { min-width: 860px; }
    }
  </style>
</head>
<body>
  <main>
    <header>
      <div>
        <p><span class="tag context">LOCALHOST</span><span class="tag warn">OWN-RISK</span></p>
        <h1>Genomics SNP matching</h1>
        <p>Run local matching against a 23andMe/Ancestry-style raw genotype text file and save only the matched review artifacts by default.</p>
      </div>
      <div>
        <button type="button" class="secondary" id="refresh">Refresh status</button>
      </div>
    </header>

    <div class="grid">
      <section>
        <h2>Upload local genotype text</h2>
        <div class="form-stack">
          <div class="field">
            <label for="profile">Profile alias</label>
            <select id="profile"></select>
          </div>

          <div class="field">
            <label for="sourceKind">Source kind</label>
            <select id="sourceKind">
              <option value="auto">Auto-detect</option>
              <option value="23andme">23andMe</option>
              <option value="ancestrydna">AncestryDNA</option>
              <option value="raw_genotype">Raw genotype</option>
              <option value="clinical_lab">Clinical lab</option>
            </select>
          </div>

          <div class="checkbox-group">
            <label class="checkbox-row"><input type="checkbox" id="clinicalGrade"><span>Mark as clinical-grade source</span></label>
            <label class="checkbox-row"><input type="checkbox" id="acceptRisk"><span>I accept the genetic privacy/family-risk implications for this local import</span></label>
          </div>

          <div class="field">
            <label for="file">Raw genotype .txt file</label>
            <input id="file" type="file" accept=".txt,.tsv,text/plain">
          </div>
          <p class="privacy-note">The page reads text locally and posts it to this localhost process. It intentionally does not send the browser filename.</p>

          <div class="actions">
            <button type="button" id="importBtn">Import and cross-reference</button>
            <button type="button" class="secondary" id="crossrefBtn">Run cross-reference only</button>
          </div>
          <pre class="status" id="status">Loading profiles…</pre>
        </div>
      </section>

      <section>
        <h2>Source / QC summary</h2>
        <div class="metric" id="metrics"></div>
        <div id="warnings"></div>
        <div class="patient-summary" id="patientSummary" aria-live="polite"></div>
      </section>
    </div>

    <section>
      <h2>Cross-reference cards</h2>
      <p>Cards are review notes. Tags such as <code>INFERENCE</code> / <code>DATA_GAP</code> show context and follow-up items; confirm anything that would change decisions.</p>
      <div class="cards" id="cards"></div>
    </section>
  </main>

  <script>
    const $ = id => document.getElementById(id);
    const state = { profile: new URLSearchParams(location.search).get('profile') || '' };
    $('refresh').onclick = refresh;
    $('profile').onchange = () => { state.profile = $('profile').value; refresh(); };
    $('importBtn').onclick = importFile;
    $('crossrefBtn').onclick = runCrossref;

    init();

    async function init() {
      try {
        const payload = await getJson('/profiles');
        const profiles = payload.profiles || [];
        $('profile').innerHTML = profiles.map(p => `<option value="${escAttr(p.profile_id)}">${esc(p.profile_id)}${p.role ? ' · ' + esc(p.role) : ''}</option>`).join('');
        if (state.profile && profiles.some(p => p.profile_id === state.profile)) $('profile').value = state.profile;
        state.profile = $('profile').value || profiles[0]?.profile_id || '';
        await refresh();
      } catch (err) {
        setStatus(`Profile load failed: ${err.message}`);
      }
    }

    async function refresh() {
      if (!state.profile) return;
      try {
        setStatus(`Profile: ${state.profile}`);
        const review = await getJson(`/genomics/review?profile_id=${encodeURIComponent(state.profile)}`);
        renderReview(review);
      } catch (err) {
        setStatus(`Refresh failed: ${err.message}`);
      }
    }

    async function importFile() {
      const file = $('file').files[0];
      if (!file) { setStatus('Choose a raw genotype text file first.'); return; }
      if (!$('acceptRisk').checked) { setStatus('Check the genetic-risk acknowledgement first.'); return; }
      setBusy(true);
      try {
        setStatus('Reading file locally…');
        const content = await file.text();
        setStatus('Running local SNP matching…');
        const payload = await postJson('/genomics/import-text', {
          profile_id: $('profile').value,
          source_kind: $('sourceKind').value,
          clinical_grade: $('clinicalGrade').checked,
          accept_genetic_risk: $('acceptRisk').checked,
          content
        });
        setStatus(`Matched source ${payload.source.source_id}\nmarkers_scanned: ${payload.source.marker_count}\nstored_variants: ${payload.stored_variant_count}\nstorage_scope: ${payload.stored_variant_scope}\ncall_rate: ${payload.source.call_rate.toFixed(3)}\nstored_cards: ${payload.stored_inferences}\nprivacy: ${payload.privacy}`);
        renderMetrics({ count: 1, variant_count: payload.stored_variant_count, sources: [payload.source] }, { qc: [payload.qc] }, payload.patient_summary);
        renderCards(payload.inferences || []);
      } catch (err) {
        setStatus(`Import failed: ${err.message}`);
      } finally {
        setBusy(false);
      }
    }

    async function runCrossref() {
      setBusy(true);
      try {
        const payload = await postJson('/genomics/crossrefs/run', {
          profile_id: $('profile').value,
          include: ['labs', 'meds', 'family']
        });
        setStatus(`Cross-reference complete.\ncards: ${payload.count}\nstored_new_or_changed: ${payload.stored_inferences}`);
        $('patientSummary').innerHTML = renderPatientSummary(payload.patient_summary);
        renderCards(payload.cards || []);
      } catch (err) {
        setStatus(`Cross-reference failed: ${err.message}`);
      } finally {
        setBusy(false);
      }
    }

    function renderMetrics(sources, qcPayload, summary) {
      const rows = qcPayload.qc || [];
      const first = rows[0] || {};
      $('metrics').innerHTML = [
        metric('Sources', sources.count || 0),
        metric('Stored SNPs', sources.variant_count ?? first.stored_variant_count ?? 0),
        metric('Call rate', Number.isFinite(first.call_rate) ? first.call_rate.toFixed(3) : '—'),
      ].join('');
      $('warnings').innerHTML = rows.length ? rows.map(row => `<div class="card"><strong>${esc(row.source_id)}</strong><p>${warningTags(row)}</p></div>`).join('') : '<p>No genomic sources yet.</p>';
      $('patientSummary').innerHTML = renderPatientSummary(summary);
    }

    function renderReview(review) {
      renderMetrics(review.sources || {}, review.qc || {}, review.patient_summary);
      renderCards((review.crossrefs || {}).cards || []);
    }

    function warningTags(row) {
      const details = row.warning_details || [];
      if (details.length) return details.map(item => `<span class="tag warn" title="${escAttr(item.code || '')}">${esc(item.label || item.code)}</span>`).join('');
      return (row.warnings || []).map(w => `<span class="tag warn">${esc(w)}</span>`).join('') || '<span class="tag">none</span>';
    }

    function renderPatientSummary(summary) {
      if (!summary) return '<p class="summary-lead">Summary will appear after the local review pipeline runs.</p>';
      const tags = (summary.tags || []).map(tag => `<span class="tag ${tag === 'DATA_GAP' ? 'gap' : tag === 'CONTEXT' ? 'context' : ''}">${esc(tag)}</span>`).join('');
      const bullets = (summary.bullets || []).map(item => `<li>${esc(item)}</li>`).join('');
      return `${tags}<p class="summary-lead">${esc(summary.lead || '')}</p>${bullets ? `<ul>${bullets}</ul>` : ''}`;
    }

    function renderCards(cards) {
      if (!cards.length) {
        $('cards').innerHTML = '<p>No genomic cross-reference cards found yet.</p>';
        return;
      }
      $('cards').innerHTML = `<div class="table-wrap"><table class="review-table">
        <thead><tr>
          <th>Marker</th>
          <th>Tags</th>
          <th>Type / confidence</th>
          <th>Summary</th>
          <th>Evidence</th>
        </tr></thead>
        <tbody>${cards.map(card => `<tr>
          <td><span class="marker-title">${esc(card.title)}</span><span class="muted">confirmation required</span></td>
          <td class="compact-tags">${(card.tags || []).map(tag => `<span class="tag ${tag === 'INFERENCE' ? 'inference' : tag === 'DATA_GAP' ? 'gap' : ''}">${esc(tag)}</span>`).join('')}</td>
          <td><strong>${esc(card.finding_type)}</strong><br><span class="muted">${esc(card.confidence)}</span></td>
          <td><div class="plain-summary">${esc(cardPatientSummary(card))}</div><div class="technical-summary">${esc(card.summary)}</div></td>
          <td><details class="evidence"><summary>${(card.evidence || []).length} item(s)</summary><ul>${(card.evidence || []).map(item => `<li>${esc(item)}</li>`).join('')}</ul></details></td>
        </tr>`).join('')}</tbody>
      </table></div>`;
    }


    function cardPatientSummary(card) {
      return card.patient_summary || card.summary || 'Review card generated by the local pipeline.';
    }

    function metric(label, value) { return `<div><span>${esc(label)}</span><strong>${esc(String(value))}</strong></div>`; }
    async function getJson(url) { const res = await fetch(url); return parseResponse(res); }
    async function postJson(url, body) {
      const res = await fetch(url, { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(body) });
      return parseResponse(res);
    }
    async function parseResponse(res) {
      const payload = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(payload.detail || payload.error || res.statusText);
      return payload;
    }
    function setBusy(busy) { $('importBtn').disabled = busy; $('crossrefBtn').disabled = busy; }
    function setStatus(text) { $('status').textContent = text; }
    function esc(value) { return String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
    function escAttr(value) { return esc(value).replace(/`/g, '&#96;'); }
  </script>
</body>
</html>
"""



class GenomicsGuiServer(ThreadingHTTPServer):
    def __init__(self, server_address, health_store: LocalHealthStore):
        super().__init__(server_address, GenomicsGuiHandler)
        self.health_store = health_store


class GenomicsGuiHandler(BaseHTTPRequestHandler):
    server: GenomicsGuiServer

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        try:
            if parsed.path in {"/", "/genomics", "/genomics/ui"}:
                self._send_html(render_genomics_import_ui())
                return
            if parsed.path == "/health":
                self._send_json(
                    {"status": "ok", "version": __version__, "local_only": True}
                )
                return
            if parsed.path == "/profiles":
                self.server.health_store.init()
                self._send_json(
                    {
                        "profiles": [
                            profile.to_dict()
                            for profile in self.server.health_store.enrolled_profiles()
                        ]
                    }
                )
                return
            query = parse_qs(parsed.query)
            profile = _first(query.get("profile_id"))
            if parsed.path == "/genomics/sources":
                self._send_json(genomics_sources_payload(self.server.health_store, profile))
                return
            if parsed.path == "/genomics/qc":
                self._send_json(genomics_qc_payload(self.server.health_store, profile or ""))
                return
            if parsed.path == "/genomics/review":
                limit = int(_first(query.get("limit")) or "50")
                self._send_json(
                    genomics_review_payload(
                        self.server.health_store,
                        profile or "",
                        limit=max(1, min(500, limit)),
                    )
                )
                return
            if parsed.path == "/genomics/crossrefs":
                limit = int(_first(query.get("limit")) or "50")
                self._send_json(
                    genomics_crossrefs_payload(
                        self.server.health_store,
                        profile or "",
                        limit=max(1, min(500, limit)),
                    )
                )
                return
            self._send_json({"error": "not found"}, status=HTTPStatus.NOT_FOUND)
        except (PrivacyError, ValueError) as exc:
            self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
        except Exception as exc:  # pragma: no cover - defensive server boundary
            self._send_json({"error": str(exc)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        try:
            payload = self._read_json()
            if parsed.path == "/genomics/import-text":
                content = payload.get("content")
                if not isinstance(content, str):
                    raise ValueError("content is required")
                result = import_raw_genotype_text_into_store(
                    self.server.health_store,
                    GenomicsStore(self.server.health_store.root),
                    profile_id=str(payload.get("profile_id", "")),
                    content=content,
                    source_kind=str(payload.get("source_kind") or "auto"),
                    clinical_grade=bool(payload.get("clinical_grade")),
                    accept_genetic_risk=bool(payload.get("accept_genetic_risk")),
                    run_crossref=True,
                )
                self._send_json(result.to_dict())
                return
            if parsed.path == "/genomics/crossrefs/run":
                include_raw = payload.get("include") or ["labs", "meds", "family"]
                include = {str(item) for item in include_raw} if isinstance(include_raw, list) else None
                self._send_json(
                    run_crossrefs_into_store(
                        self.server.health_store,
                        GenomicsStore(self.server.health_store.root),
                        profile_id=str(payload.get("profile_id", "")),
                        include=include,
                    )
                )
                return
            self._send_json({"error": "not found"}, status=HTTPStatus.NOT_FOUND)
        except (PrivacyError, ValueError, json.JSONDecodeError) as exc:
            self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
        except Exception as exc:  # pragma: no cover - defensive server boundary
            self._send_json({"error": str(exc)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)

    def log_message(self, fmt: str, *args) -> None:  # noqa: A003
        return

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or "0")
        if length > MAX_GENOTYPE_UPLOAD_BYTES:
            raise ValueError("genotype upload is too large for this local GUI")
        raw = self.rfile.read(length)
        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("JSON object body is required")
        return payload

    def _send_html(self, html: str) -> None:
        data = html.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_json(self, payload: dict[str, Any], *, status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def _first(values: list[str] | None) -> str | None:
    if not values:
        return None
    return values[0]
