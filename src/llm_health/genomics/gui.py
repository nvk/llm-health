# ruff: noqa: E501

from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from llm_health import __version__
from llm_health.core.privacy import PrivacyError, validate_profile_alias
from llm_health.stores import LocalHealthStore

from .qc import build_qc
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
      --danger: #b64035;
      --good: #1f8a5b;
      --shadow: 0 12px 28px rgba(30, 42, 62, .07);
      --mono: "SF Mono", ui-monospace, Menlo, Consolas, monospace;
      --sans: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    * { box-sizing: border-box; }
    body { margin: 0; background: var(--bg); color: var(--ink); font-family: var(--sans); }
    main { max-width: 1180px; margin: 0 auto; padding: 1.5rem; }
    header, section { background: var(--paper); border: 1px solid var(--line); border-radius: 18px; box-shadow: var(--shadow); padding: 1rem; margin-bottom: 1rem; }
    header { display: flex; justify-content: space-between; gap: 1rem; align-items: start; }
    h1, h2, h3 { margin: 0; letter-spacing: -.02em; }
    p { color: var(--muted); line-height: 1.45; }
    label { display: block; color: var(--muted); font-weight: 780; margin: .7rem 0 .35rem; }
    select, input[type="file"] { width: 100%; min-height: 2.55rem; border: 1px solid var(--line); border-radius: 12px; padding: .45rem .6rem; background: var(--paper); color: var(--ink); }
    input[type="checkbox"] { transform: scale(1.1); margin-right: .4rem; }
    button { border: 0; border-radius: 12px; background: var(--accent); color: #fff; padding: .7rem .95rem; font-weight: 850; cursor: pointer; }
    button.secondary { background: var(--paper-2); color: var(--ink); border: 1px solid var(--line); }
    button:disabled { opacity: .55; cursor: not-allowed; }
    .grid { display: grid; grid-template-columns: minmax(300px, .8fr) minmax(340px, 1.2fr); gap: 1rem; }
    .actions { display: flex; gap: .6rem; flex-wrap: wrap; align-items: center; margin-top: .9rem; }
    .notice { border-left: 4px solid var(--warn); background: color-mix(in srgb, var(--warn), transparent 91%); }
    .status { min-height: 2rem; font-family: var(--mono); color: var(--muted); white-space: pre-wrap; }
    .cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: .75rem; }
    .card { border: 1px solid var(--line); border-radius: 14px; background: var(--paper-2); padding: .8rem; }
    .tag { display: inline-block; border: 1px solid var(--line); border-radius: 999px; padding: .12rem .45rem; margin: .1rem .2rem .2rem 0; font-size: .7rem; font-weight: 850; letter-spacing: .05em; }
    .tag.inference { color: var(--accent); }
    .tag.gap, .tag.warn { color: var(--danger); }
    .tag.context { color: var(--warn); }
    .metric { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: .7rem; }
    .metric div { border: 1px solid var(--line); border-radius: 14px; padding: .75rem; background: var(--paper-2); }
    .metric strong { display: block; font-family: var(--mono); font-size: 1.25rem; margin-top: .25rem; }
    code { font-family: var(--mono); }
    @media (max-width: 800px) { .grid, .metric { grid-template-columns: 1fr; } header { display: block; } }
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

    <section class="notice">
      <h2>Genetic data warning</h2>
      <p>This is experimental local software. Genomic cards are context only: not diagnosis, not prescribing, not test ordering, and not a clinician relationship. High-impact findings need clinical-grade confirmation. The browser does not send the selected file name/path; the local server stores a source fingerprint and matched SNP findings only by default, not dense genome-wide calls.</p>
    </section>

    <div class="grid">
      <section>
        <h2>Upload local genotype text</h2>
        <label for="profile">Profile alias</label>
        <select id="profile"></select>

        <label for="sourceKind">Source kind</label>
        <select id="sourceKind">
          <option value="auto">Auto-detect</option>
          <option value="23andme">23andMe</option>
          <option value="ancestrydna">AncestryDNA</option>
          <option value="raw_genotype">Raw genotype</option>
          <option value="clinical_lab">Clinical lab</option>
        </select>

        <label><input type="checkbox" id="clinicalGrade"> Mark as clinical-grade source</label>
        <label><input type="checkbox" id="acceptRisk"> I accept the genetic privacy/family-risk implications for this local import</label>

        <label for="file">Raw genotype .txt file</label>
        <input id="file" type="file" accept=".txt,.tsv,text/plain">
        <p>The page reads text locally and posts it to this localhost process. It intentionally does not send the browser filename.</p>

        <div class="actions">
          <button type="button" id="importBtn">Import and cross-reference</button>
          <button type="button" class="secondary" id="crossrefBtn">Run cross-reference only</button>
        </div>
        <pre class="status" id="status">Loading profiles…</pre>
      </section>

      <section>
        <h2>Source / QC summary</h2>
        <div class="metric" id="metrics"></div>
        <div id="warnings"></div>
      </section>
    </div>

    <section>
      <h2>Cross-reference cards</h2>
      <p>Cards are discussion prompts only. They are tagged as <code>INFERENCE</code> / <code>DATA_GAP</code> and require confirmation before action.</p>
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
        const [sources, qc, crossrefs] = await Promise.all([
          getJson(`/genomics/sources?profile_id=${encodeURIComponent(state.profile)}`),
          getJson(`/genomics/qc?profile_id=${encodeURIComponent(state.profile)}`),
          getJson(`/genomics/crossrefs?profile_id=${encodeURIComponent(state.profile)}`),
        ]);
        renderMetrics(sources, qc);
        renderCards(crossrefs.cards || []);
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
        renderMetrics({ count: 1, variant_count: payload.stored_variant_count, sources: [payload.source] }, { qc: [payload.qc] });
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
        renderCards(payload.cards || []);
      } catch (err) {
        setStatus(`Cross-reference failed: ${err.message}`);
      } finally {
        setBusy(false);
      }
    }

    function renderMetrics(sources, qcPayload) {
      const rows = qcPayload.qc || [];
      const first = rows[0] || {};
      $('metrics').innerHTML = [
        metric('Sources', sources.count || 0),
        metric('Stored SNPs', sources.variant_count ?? first.stored_variant_count ?? 0),
        metric('Call rate', Number.isFinite(first.call_rate) ? first.call_rate.toFixed(3) : '—'),
      ].join('');
      $('warnings').innerHTML = rows.length ? rows.map(row => `<div class="card"><strong>${esc(row.source_id)}</strong><p>${(row.warnings || []).map(w => `<span class="tag warn">${esc(w)}</span>`).join('') || '<span class="tag">none</span>'}</p></div>`).join('') : '<p>No genomic sources yet.</p>';
    }

    function renderCards(cards) {
      $('cards').innerHTML = cards.length ? cards.map(card => `<article class="card">
        <h3>${esc(card.title)}</h3>
        <p>${(card.tags || []).map(tag => `<span class="tag ${tag === 'INFERENCE' ? 'inference' : tag === 'DATA_GAP' ? 'gap' : ''}">${esc(tag)}</span>`).join('')}</p>
        <p><strong>${esc(card.finding_type)}</strong> · ${esc(card.confidence)} · confirmation required</p>
        <p>${esc(card.summary)}</p>
        <ul>${(card.evidence || []).map(item => `<li>${esc(item)}</li>`).join('')}</ul>
      </article>`).join('') : '<p>No genomic cross-reference cards found yet.</p>';
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


def genomics_sources_payload(store: LocalHealthStore, profile_id: str | None = None) -> dict[str, Any]:
    profile = validate_profile_alias(profile_id) if profile_id else None
    store.init()
    if profile and not store.profile_exists(profile):
        raise PrivacyError(f"profile alias {profile!r} is not enrolled")
    genomics_store = GenomicsStore(store.root)
    sources = genomics_store.sources(profile)
    variant_count = len(genomics_store.variants(profile))
    return {
        "count": len(sources),
        "variant_count": variant_count,
        "sources": [_source_payload(source) for source in sources],
        "privacy": (
            "source summaries and matched SNP findings only; raw genetic file paths "
            "and dense genome-wide calls are not stored by default"
        ),
    }


def genomics_qc_payload(store: LocalHealthStore, profile_id: str) -> dict[str, Any]:
    profile = validate_profile_alias(profile_id)
    store.init()
    if not store.profile_exists(profile):
        raise PrivacyError(f"profile alias {profile!r} is not enrolled")
    genomics_store = GenomicsStore(store.root)
    rows = [
        build_qc(source, genomics_store.variants(profile, source.source_id)).to_dict()
        for source in genomics_store.sources(profile)
    ]
    return {"profile_id": profile, "count": len(rows), "qc": rows}


def _source_payload(source) -> dict[str, Any]:
    payload = source.to_dict()
    payload["call_rate"] = source.call_rate
    return payload


def genomics_crossrefs_payload(
    store: LocalHealthStore,
    profile_id: str,
    *,
    limit: int = 50,
) -> dict[str, Any]:
    profile = validate_profile_alias(profile_id)
    store.init()
    if not store.profile_exists(profile):
        raise PrivacyError(f"profile alias {profile!r} is not enrolled")
    genomics_store = GenomicsStore(store.root)
    cards = genomics_store.inferences(profile)
    cards.sort(key=lambda item: item.created_at, reverse=True)
    cards = cards[:limit]
    return {
        "profile_id": profile,
        "count": len(cards),
        "cards": [card.to_dict() for card in cards],
        "notice": "genomic cards are review artifacts, not diagnosis or prescribing",
    }


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
