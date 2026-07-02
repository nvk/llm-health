from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from llm_health import __version__
from llm_health.core.privacy import PrivacyError, validate_profile_alias
from llm_health.genomics import GenomicsStore
from llm_health.genomics.gui import (
    health_ui_target,
    render_genomics_import_ui,
    render_health_ui_missing,
)
from llm_health.genomics.pipeline import (
    genomics_crossrefs_payload,
    genomics_qc_payload,
    genomics_review_payload,
    genomics_sources_payload,
)
from llm_health.genomics.workflow import (
    import_raw_genotype_text_into_store,
    run_crossrefs_into_store,
)
from llm_health.stores import LocalHealthStore

LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


@dataclass(frozen=True)
class ServiceRoute:
    method: str
    path: str
    summary: str

    def to_dict(self) -> dict[str, str]:
        return {"method": self.method, "path": self.path, "summary": self.summary}


SERVICE_ROUTES: tuple[ServiceRoute, ...] = (
    ServiceRoute("GET", "/health", "Local service status and package version."),
    ServiceRoute("GET", "/health/ui/", "Served local Assessment board export when present."),
    ServiceRoute("GET", "/profiles", "Alias-only enrolled profile list."),
    ServiceRoute("GET", "/observations/query", "Alias-scoped observations by marker/category."),
    ServiceRoute("GET", "/reviews/latest", "Alias-scoped latest quick-review cards."),
    ServiceRoute("GET", "/sources/audit", "Source-id counts without source paths or filenames."),
    ServiceRoute("GET", "/charts/payload", "Small chart payload scaffold for UI clients."),
    ServiceRoute("GET", "/operator/drafts", "Visible draft artifacts for agent workflows."),
    ServiceRoute("GET", "/family/tree", "Alias-only family relationships around a profile."),
    ServiceRoute("GET", "/family/risks", "Generated hereditary/household context notes."),
    ServiceRoute("GET", "/genomics/crossrefs", "Alias-scoped genomic review cards."),
    ServiceRoute("GET", "/genomics/qc", "Alias-scoped genotype QC summaries."),
    ServiceRoute("GET", "/genomics/review", "Combined genomics UI/review pipeline payload."),
    ServiceRoute("GET", "/genomics/sources", "Alias-scoped genomic source summaries."),
    ServiceRoute("GET", "/genomics/ui", "Local genotype SNP matching GUI."),
    ServiceRoute(
        "POST",
        "/genomics/import-text",
        "Run local SNP matching on pasted/uploaded genotype text.",
    ),
    ServiceRoute("POST", "/genomics/crossrefs/run", "Create genomic cross-reference cards."),
)


def route_manifest() -> list[dict[str, str]]:
    return [route.to_dict() for route in SERVICE_ROUTES]


def render_service_routes() -> str:
    lines = ["# llm-health local service", "local_only: true", "", "method | path | summary"]
    lines.append("--- | --- | ---")
    for route in SERVICE_ROUTES:
        lines.append(f"{route.method} | {route.path} | {route.summary}")
    return "\n".join(lines)


def _observation_to_payload(observation: Any) -> dict[str, object]:
    return observation.to_dict()


def build_app(store: LocalHealthStore):  # pragma: no cover - exercised when optional deps present
    try:
        from fastapi import FastAPI, HTTPException, Query, Request
        from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Install optional extra with `pip install llm-health[service]`") from exc

    app = FastAPI(title="llm-health local service", version=__version__)

    @app.get("/health")
    def health() -> dict[str, object]:
        return {
            "status": "ok",
            "version": __version__,
            "local_only": True,
            "routes": route_manifest(),
        }

    @app.get("/profiles")
    def profiles() -> dict[str, object]:
        store.init()
        return {"profiles": [profile.to_dict() for profile in store.enrolled_profiles()]}

    @app.get("/health/ui")
    def health_ui_redirect(request: Request) -> RedirectResponse:
        suffix = f"?{request.url.query}" if request.url.query else ""
        return RedirectResponse(url=f"/health/ui/{suffix}")

    @app.get("/health/ui/", response_class=HTMLResponse)
    @app.get("/health/ui/{asset_path:path}")
    def health_ui(asset_path: str = ""):
        ui_root = (store.root / "v2-web").resolve()
        if not ui_root.exists():
            return HTMLResponse(render_health_ui_missing())
        target = health_ui_target(store.root, f"/health/ui/{asset_path}")
        if target is None or not target.is_file():
            raise HTTPException(status_code=404, detail="health UI asset not found")
        return FileResponse(target)

    @app.get("/observations/query")
    def observations_query(
        profile_id: str | None = None,
        marker: str | None = None,
        category: str | None = None,
        limit: int = Query(250, ge=1, le=5000),
    ) -> dict[str, object]:
        store.init()
        profile = validate_profile_alias(profile_id) if profile_id else None
        if profile and not store.profile_exists(profile):
            raise HTTPException(status_code=404, detail="profile alias is not enrolled")
        marker_needle = (marker or "").strip().lower()
        category_needle = (category or "").strip().lower()
        rows = store.observations(profile) if profile else store.observations()
        if marker_needle:
            rows = [
                row
                for row in rows
                if marker_needle in row.marker.lower() or marker_needle in row.category.lower()
            ]
        if category_needle:
            rows = [row for row in rows if category_needle in row.category.lower()]
        rows.sort(key=lambda item: (item.observed_on, item.marker), reverse=True)
        payload_rows = [_observation_to_payload(row) for row in rows[:limit]]
        return {"count": len(payload_rows), "observations": payload_rows}

    @app.get("/reviews/latest")
    def reviews_latest(profile_id: str, limit: int = Query(20, ge=1, le=250)) -> dict[str, object]:
        store.init()
        profile = validate_profile_alias(profile_id)
        if not store.profile_exists(profile):
            raise HTTPException(status_code=404, detail="profile alias is not enrolled")
        cards = store.quick_review_cards(profile)
        cards.sort(key=lambda item: item.created_at, reverse=True)
        return {"count": len(cards[:limit]), "cards": [card.to_dict() for card in cards[:limit]]}

    @app.get("/sources/audit")
    def sources_audit() -> dict[str, object]:
        store.init()
        counts: dict[str, int] = {}
        for observation in store.observations():
            counts[observation.source_id] = counts.get(observation.source_id, 0) + 1
        return {
            "source_ids": [
                {"source_id": source_id, "observation_count": count}
                for source_id, count in sorted(counts.items())
            ],
            "privacy": "source ids only; no source paths or raw filenames",
        }

    @app.get("/charts/payload")
    def charts_payload(
        profile_id: str,
        marker: str | None = None,
        category: str | None = None,
        limit: int = Query(500, ge=1, le=5000),
    ) -> dict[str, object]:
        profile = validate_profile_alias(profile_id)
        if not store.profile_exists(profile):
            raise HTTPException(status_code=404, detail="profile alias is not enrolled")
        marker_needle = (marker or "").strip().lower()
        category_needle = (category or "").strip().lower()
        rows = store.observations(profile)
        if marker_needle:
            rows = [row for row in rows if marker_needle in row.marker.lower()]
        if category_needle:
            rows = [row for row in rows if category_needle in row.category.lower()]
        rows.sort(key=lambda item: (item.observed_on, item.marker))
        return {
            "schema": "llm-health-chart-payload-v0",
            "profile_id": profile,
            "count": len(rows[:limit]),
            "points": [_observation_to_payload(row) for row in rows[:limit]],
        }

    @app.get("/operator/drafts")
    def operator_drafts(
        profile_id: str | None = None,
        status: str | None = None,
        limit: int = Query(50, ge=1, le=500),
    ) -> dict[str, object]:
        profile = validate_profile_alias(profile_id) if profile_id else None
        drafts = store.operator_drafts(profile, status=status)
        drafts.sort(key=lambda item: item.created_at, reverse=True)
        return {
            "count": len(drafts[:limit]),
            "drafts": [draft.to_dict() for draft in drafts[:limit]],
        }

    @app.get("/family/tree")
    def family_tree(profile_id: str) -> dict[str, object]:
        profile = validate_profile_alias(profile_id)
        if not store.profile_exists(profile):
            raise HTTPException(status_code=404, detail="profile alias is not enrolled")
        relationships = store.family_relationships(profile)
        return {
            "profile_id": profile,
            "count": len(relationships),
            "relationships": [relationship.to_dict() for relationship in relationships],
        }

    @app.get("/family/risks")
    def family_risks(profile_id: str, limit: int = Query(50, ge=1, le=500)) -> dict[str, object]:
        profile = validate_profile_alias(profile_id)
        if not store.profile_exists(profile):
            raise HTTPException(status_code=404, detail="profile alias is not enrolled")
        notes = store.hereditary_risk_notes(profile)
        notes.sort(key=lambda item: (item.priority, item.created_at), reverse=True)
        return {
            "profile_id": profile,
            "count": len(notes[:limit]),
            "notes": [note.to_dict() for note in notes[:limit]],
        }


    @app.get("/genomics/sources")
    def genomics_sources(profile_id: str | None = None) -> dict[str, object]:
        try:
            return genomics_sources_payload(store, profile_id)
        except PrivacyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/genomics/qc")
    def genomics_qc(profile_id: str) -> dict[str, object]:
        try:
            return genomics_qc_payload(store, profile_id)
        except PrivacyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/genomics/crossrefs")
    def genomics_crossrefs(
        profile_id: str,
        limit: int = Query(50, ge=1, le=500),
    ) -> dict[str, object]:
        try:
            return genomics_crossrefs_payload(store, profile_id, limit=limit)
        except PrivacyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/genomics/review")
    def genomics_review(
        profile_id: str,
        limit: int = Query(50, ge=1, le=500),
    ) -> dict[str, object]:
        try:
            return genomics_review_payload(store, profile_id, limit=limit)
        except PrivacyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/genomics/ui", response_class=HTMLResponse)
    def genomics_ui() -> str:
        return render_genomics_import_ui()

    @app.post("/genomics/import-text")
    def genomics_import_text(payload: dict[str, object]) -> dict[str, object]:
        content = payload.get("content")
        if not isinstance(content, str):
            raise HTTPException(status_code=400, detail="content is required")
        try:
            result = import_raw_genotype_text_into_store(
                store,
                GenomicsStore(store.root),
                profile_id=str(payload.get("profile_id", "")),
                content=content,
                source_kind=str(payload.get("source_kind") or "auto"),
                clinical_grade=bool(payload.get("clinical_grade")),
                accept_genetic_risk=bool(payload.get("accept_genetic_risk")),
                include_research_markers=bool(payload.get("include_research_markers")),
                run_crossref=True,
            )
        except (PrivacyError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return result.to_dict()

    @app.post("/genomics/crossrefs/run")
    def genomics_crossrefs_run(payload: dict[str, object]) -> dict[str, object]:
        include_raw = payload.get("include") or ["labs", "meds", "family"]
        include = {str(item) for item in include_raw} if isinstance(include_raw, list) else None
        try:
            return run_crossrefs_into_store(
                store,
                GenomicsStore(store.root),
                profile_id=str(payload.get("profile_id", "")),
                include=include,
            )
        except (PrivacyError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return app


def run_service(store: LocalHealthStore, *, host: str = "127.0.0.1", port: int = 8765) -> None:
    try:
        import uvicorn
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Install optional extra with `pip install llm-health[service]`") from exc
    uvicorn.run(build_app(store), host=host, port=port)
