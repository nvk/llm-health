"""Command line interface for Health Assessment v2."""

from __future__ import annotations

import importlib.util
import platform
from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from llm_health.assessment_v2.app.main import build_app
from llm_health.assessment_v2.app.theme import ThemeMode
from llm_health.assessment_v2.config import get_settings
from llm_health.assessment_v2.export.old_web import export_old_web_data_js
from llm_health.assessment_v2.export.v2_web import export_v2_web
from llm_health.assessment_v2.storage.build import build_from_wiki
from llm_health.assessment_v2.storage.user_facts import upsert_user_weight

app = typer.Typer(help="Health Assessment v2 local analytics CLI")
console = Console()


@app.command()
def doctor() -> None:
    """Print local configuration and readiness checks."""

    settings = get_settings()
    console.print("[bold]Health Assessment v2[/bold]")
    console.print(f"Python: {platform.python_version()}")
    console.print(f"Wiki root: {settings.wiki_root or '[not set]'}")
    console.print(f"Data dir: {settings.data_dir}")
    console.print(f"DuckDB: {settings.duckdb_path}")
    modules = [
        "duckdb",
        "polars",
        "panel",
        "hvplot",
        "holoviews",
        "datashader",
        "pydantic",
        "pandera",
    ]
    for module in modules:
        status = "ok" if importlib.util.find_spec(module) else "missing"
        console.print(f"{module}: {status}")


@app.command("build")
def build(
    from_wiki: Annotated[
        bool, typer.Option(help="Build from existing de-identified wiki CSV outputs.")
    ] = False,
    include_record_level: Annotated[
        bool, typer.Option(help="Also convert the large record-level Apple Health CSV.")
    ] = False,
) -> None:
    """Build local canonical Parquet tables and DuckDB views."""

    settings = get_settings()
    if not from_wiki:
        console.print(
            "Nothing to build yet. Use --from-wiki for existing de-identified wiki outputs."
        )
        return
    if settings.wiki_root is None:
        raise typer.BadParameter("Set HEALTH_WIKI_ROOT before using --from-wiki")

    built = build_from_wiki(
        settings.wiki_root,
        settings.data_dir,
        settings.duckdb_path,
        include_record_level=include_record_level,
    )
    for table in built:
        if table.skipped:
            console.print(f"[yellow]skipped[/yellow] {table.table}: {table.reason}")
        else:
            console.print(f"[green]built[/green] {table.table}: {table.row_count:,} rows")


@app.command("add-weight")
def add_weight(
    profile: Annotated[str, typer.Argument(help="De-identified profile alias: rod or cara.")],
    kg: Annotated[float, typer.Option(help="Weight in kilograms.")],
    measurement_date: Annotated[
        str | None, typer.Option("--date", help="Measurement date in YYYY-MM-DD.")
    ] = None,
) -> None:
    """Add or update a de-identified user-provided weight observation."""

    settings = get_settings()
    if settings.wiki_root is None:
        raise typer.BadParameter("Set HEALTH_WIKI_ROOT before adding canonical facts")

    date_value = (
        datetime.strptime(measurement_date, "%Y-%m-%d").date()
        if measurement_date
        else datetime.now().date()
    )
    added = upsert_user_weight(settings.wiki_root, profile, date_value, kg)
    console.print(
        f"[green]upserted[/green] {added.profile_id} weight {kg:g} kg on "
        f"{added.measurement_date.isoformat()}"
    )
    console.print(f"observation: {added.observation_id}")
    console.print(f"source: {added.source_id}")


@app.command()
def sync(
    old_web: Annotated[
        bool, typer.Option(help="Also regenerate the legacy static web-view data.js.")
    ] = False,
    old_web_path: Annotated[
        Path | None, typer.Option(help="Override legacy web-view directory.")
    ] = None,
    v2_web: Annotated[
        bool, typer.Option(help="Also export the v2 polished static dashboard.")
    ] = False,
    v2_web_path: Annotated[
        Path | None, typer.Option(help="Override v2 static dashboard output directory.")
    ] = None,
    include_record_level: Annotated[
        bool, typer.Option(help="Also convert the large record-level Apple Health CSV.")
    ] = False,
) -> None:
    """Rebuild v2 data artifacts and optional legacy static payload from canonical CSVs."""

    settings = get_settings()
    if settings.wiki_root is None:
        raise typer.BadParameter("Set HEALTH_WIKI_ROOT before sync")

    built = build_from_wiki(
        settings.wiki_root,
        settings.data_dir,
        settings.duckdb_path,
        include_record_level=include_record_level,
    )
    for table in built:
        if table.skipped:
            console.print(f"[yellow]skipped[/yellow] {table.table}: {table.reason}")
        else:
            console.print(f"[green]built[/green] {table.table}: {table.row_count:,} rows")

    if old_web:
        export = export_old_web_data_js(settings.wiki_root, old_web_path)
        weights = ", ".join(
            f"{profile}: {value:g} kg" for profile, value in sorted(export.latest_weights.items())
        )
        console.print(
            f"[green]exported[/green] old web data.js: {export.observation_count:,} "
            f"observations, {export.report_count:,} reports"
        )
        if weights:
            console.print(f"latest weights: {weights}")

    if v2_web:
        output_dir = v2_web_path or settings.data_dir / "v2-web"
        export = export_v2_web(settings.wiki_root, output_dir)
        weights = ", ".join(
            f"{profile}: {value:g} kg" for profile, value in sorted(export.latest_weights.items())
        )
        console.print(
            f"[green]exported[/green] v2 static dashboard: {export.observation_count:,} "
            f"observations, {export.report_count:,} reports, "
            f"{export.wearable_daily_count:,} wearable daily rows"
        )
        console.print(f"open: {export.output_dir / 'index.html'}")
        if weights:
            console.print(f"latest weights: {weights}")


@app.command("export-web")
def export_web(
    output_dir: Annotated[
        Path, typer.Option("--output", help="Static dashboard output directory.")
    ] = Path("data/v2-web"),
) -> None:
    """Export the polished v2 static dashboard without rebuilding DuckDB."""

    settings = get_settings()
    if settings.wiki_root is None:
        raise typer.BadParameter("Set HEALTH_WIKI_ROOT before exporting the dashboard")

    export = export_v2_web(settings.wiki_root, output_dir)
    weights = ", ".join(
        f"{profile}: {value:g} kg" for profile, value in sorted(export.latest_weights.items())
    )
    console.print(
        f"[green]exported[/green] v2 static dashboard: {export.observation_count:,} "
        f"observations, {export.report_count:,} reports, "
        f"{export.wearable_daily_count:,} wearable daily rows"
    )
    console.print(f"open: {export.output_dir / 'index.html'}")
    if weights:
        console.print(f"latest weights: {weights}")


@app.command()
def serve(
    port: Annotated[int, typer.Option(help="Local Panel server port.")] = 8866,
    theme: Annotated[
        ThemeMode,
        typer.Option(help="Initial dashboard color theme; header toggle remains enabled."),
    ] = ThemeMode.LIGHT,
    show: Annotated[bool, typer.Option(help="Open the browser when the server starts.")] = True,
) -> None:
    """Serve the local dashboard."""

    try:
        import panel as pn
    except ImportError as exc:  # pragma: no cover - depends on installed extras
        raise typer.BadParameter(
            "Panel is not installed. Install project dependencies first."
        ) from exc

    console.print(f"Serving Health Assessment v2 on http://localhost:{port} ({theme} mode)")

    def app_factory():
        # Build per browser session so Panel's built-in ?theme=dark/default toggle
        # can update both the template theme and our custom dashboard CSS tokens.
        return build_app(theme)

    pn.serve(app_factory, port=port, show=show)


@app.command()
def validate(
    path: Annotated[
        Path | None, typer.Option(help="Optional table or export path to validate.")
    ] = None,
) -> None:
    """Run validation checks. Placeholder for phase 1."""

    console.print(f"Validation scaffold is ready for: {path or 'configured local data'}")


if __name__ == "__main__":
    app()
