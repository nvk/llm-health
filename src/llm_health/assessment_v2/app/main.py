"""Panel dashboard entry point."""

from __future__ import annotations

import math
from pathlib import Path

import pandas as pd

from llm_health.assessment_v2.app.theme import (
    ThemeMode,
    css_variables,
    palette_for,
    panel_theme_for,
    theme_mode_from_session_args,
)
from llm_health.assessment_v2.config import get_settings
from llm_health.assessment_v2.storage.repository import HealthRepository, make_date_filter

try:
    import hvplot.pandas  # noqa: F401
    import panel as pn
except ImportError:  # pragma: no cover - dependency absent in scaffold-only env
    pn = None

PROFILE_OPTIONS = {"Rod": "rod", "Cara": "cara"}
RANGE_OPTIONS = ["All", "30d", "90d", "YTD", "18mo"]
ROLLUP_OPTIONS = ["daily", "weekly", "monthly"]
COMPARISON_OPTIONS = ["Stacked", "Overlay"]
GRAPH_SCALE_OPTIONS = [
    "Auto",
    "Raw values",
    "Normalized 0-100",
    "Mean-centered",
    "% of mean",
    "% change from first",
    "Z-score",
    "Log10",
]
GRAPH_AGGREGATION_OPTIONS = ["Observed points", "Mean by date"]
GRAPH_SMOOTHING_OPTIONS = ["None", "3-point mean", "7-point mean", "30-point mean"]
ALL_LAB_CATEGORIES = "All categories"
PREFERRED_LAB_CATEGORIES = [
    "Liver",
    "Blood chemistry / Liver profile",
    "Blood chemistry / Liver profile / Bilirubins",
    "Lipids",
]
PREFERRED_LAB_MARKERS = [
    "ALT",
    "AST",
    "Total bilirubin",
    "Total Bilirubin",
    "LDL Cholesterol",
    "ApoB",
]


def _effective_theme_mode(default: str | ThemeMode) -> ThemeMode:
    """Honor Panel FastTemplate's query-string theme toggle for this session."""

    if pn is None:
        return ThemeMode.LIGHT
    try:
        from panel.io.state import state
    except ImportError:  # pragma: no cover - Panel import already guarded above
        return ThemeMode.LIGHT
    return theme_mode_from_session_args(state.session_args, default)


def _preferred_values(options: list[str], preferred: list[str], max_items: int = 3) -> list[str]:
    chosen = [item for item in preferred if item in options]
    if chosen:
        return chosen[:max_items]
    return options[:max_items]


def _category_query_value(category: str) -> str | None:
    return None if category == ALL_LAB_CATEGORIES else category


def _lab_category_options(repo: HealthRepository, profile: str) -> list[str]:
    categories = repo.lab_categories(profile)
    return [ALL_LAB_CATEGORIES, *categories] if categories else [ALL_LAB_CATEGORIES]


def _preferred_lab_category(options: list[str]) -> str:
    for category in PREFERRED_LAB_CATEGORIES:
        if category in options:
            return category
    return next((category for category in options if category != ALL_LAB_CATEGORIES), options[0])


def _status_card(title: str, body: str, tags: list[str] | None = None) -> str:
    tag_html = "".join(f'<span class="ha-tag">{tag}</span>' for tag in tags or [])
    return f"""
<div class="ha-card">
  <h2>{title}</h2>
  <p class="ha-muted">{body}</p>
  <div>{tag_html}</div>
</div>
"""


def _metric_card(label: str, value: object, hint: str = "") -> str:
    return f"""
<div class="ha-card ha-metric-card">
  <div class="ha-metric-label">{label}</div>
  <div class="ha-metric-value">{value}</div>
  <div class="ha-muted">{hint}</div>
</div>
"""


def build_app(theme: str | ThemeMode = ThemeMode.LIGHT, duckdb_path: Path | None = None):
    """Build the Panel app.

    The template starts with both light/dark support enabled through Panel's theme toggle.
    """

    if pn is None:
        raise RuntimeError("Panel is not installed. Install project dependencies first.")

    mode = _effective_theme_mode(theme)
    settings = get_settings()
    repo = HealthRepository(duckdb_path or settings.duckdb_path)
    palette = palette_for(mode)
    pn.extension("tabulator", raw_css=[css_variables(palette)], sizing_mode="stretch_width")

    profile = pn.widgets.RadioButtonGroup(
        label="Profile", options=PROFILE_OPTIONS, value="rod", color="primary"
    )
    date_range = pn.widgets.RadioButtonGroup(label="Time", options=RANGE_OPTIONS, value="All")
    lab_category_options = _lab_category_options(repo, "rod")
    default_lab_category = _preferred_lab_category(lab_category_options)
    lab_metric_options = (
        repo.lab_metrics_for_category("rod", _category_query_value(default_lab_category))
        or repo.lab_metrics("rod")
        or ["ALT"]
    )
    wearable_metric_options = repo.wearable_metrics("rod") or ["Step count"]
    lab_category = pn.widgets.Select(
        label="Lab category", options=lab_category_options, value=default_lab_category
    )
    lab_show_all_category = pn.widgets.Checkbox(
        label="Show every marker in selected category", value=True
    )
    lab_metrics = pn.widgets.MultiChoice(
        label="Lab markers (when show-all is off)",
        options=lab_metric_options,
        value=_preferred_values(lab_metric_options, PREFERRED_LAB_MARKERS),
    )
    lab_context_metric_options = repo.lab_context_metrics("rod")
    lab_context_metrics = pn.widgets.MultiChoice(
        label="Context overlays",
        options=lab_context_metric_options,
        value=_preferred_values(lab_context_metric_options, ["Weight (kg)"], max_items=1),
    )
    wearable_metrics = pn.widgets.MultiChoice(
        label="Wearable metrics",
        options=wearable_metric_options,
        value=_preferred_values(
            wearable_metric_options,
            ["Step count", "Walking/running distance", "Active energy burned"],
        ),
    )
    wearable_rollup = pn.widgets.RadioButtonGroup(
        label="Rollup", options=ROLLUP_OPTIONS, value="daily"
    )
    comparison_mode = pn.widgets.RadioButtonGroup(
        label="Timeline comparison", options=COMPARISON_OPTIONS, value="Stacked"
    )
    graph_scale = pn.widgets.Select(
        label="Graph scale / transform", options=GRAPH_SCALE_OPTIONS, value="Auto"
    )
    graph_aggregation = pn.widgets.RadioButtonGroup(
        label="Point aggregation", options=GRAPH_AGGREGATION_OPTIONS, value="Observed points"
    )
    graph_smoothing = pn.widgets.Select(
        label="Trend smoothing", options=GRAPH_SMOOTHING_OPTIONS, value="None"
    )

    def _sync_lab_metrics(profile_id: str, category: str) -> None:
        metrics = (
            repo.lab_metrics_for_category(profile_id, _category_query_value(category))
            or repo.lab_metrics(profile_id)
            or [""]
        )
        lab_metrics.options = metrics
        lab_metrics.value = _preferred_values(metrics, PREFERRED_LAB_MARKERS)

    def _on_profile_change(event) -> None:  # noqa: ANN001 - Panel callback event
        categories = _lab_category_options(repo, event.new)
        lab_category.options = categories
        lab_category.value = _preferred_lab_category(categories)
        _sync_lab_metrics(event.new, lab_category.value)
        context_metrics = repo.lab_context_metrics(event.new)
        lab_context_metrics.options = context_metrics
        lab_context_metrics.value = _preferred_values(context_metrics, ["Weight (kg)"], max_items=1)
        wearables = repo.wearable_metrics(event.new) or [""]
        wearable_metrics.options = wearables
        wearable_metrics.value = _preferred_values(
            wearables, ["Step count", "Walking/running distance", "Active energy burned"]
        )

    def _on_lab_category_change(event) -> None:  # noqa: ANN001 - Panel callback event
        _sync_lab_metrics(profile.value, event.new)

    profile.param.watch(_on_profile_change, "value")
    lab_category.param.watch(_on_lab_category_change, "value")

    template = pn.template.FastListTemplate(
        title="Health Assessment v2",
        site="Local health analytics",
        theme=panel_theme_for(palette.mode),
        theme_toggle=True,
        accent_base_color=palette.accent,
        header_accent_base_color=palette.accent,
        neutral_color=palette.border,
        background_color=palette.background,
        header_background=palette.accent,
        header_color="#151d2b" if palette.mode is ThemeMode.DARK else "#ffffff",
        main_layout="card",
    )

    template.sidebar.append(
        pn.Column(
            "## Review controls",
            pn.pane.Markdown(
                "`OWN-RISK` Private local briefing; not diagnosis, medical advice, "
                "orders, prescriptions, or a clinician relationship."
            ),
            pn.pane.Markdown(
                "**Workflow:** Review queue → domain map → timeline evidence → "
                "source rows/export."
            ),
            profile,
            date_range,
            "### Timelines",
            comparison_mode,
            graph_scale,
            graph_aggregation,
            graph_smoothing,
            pn.pane.Markdown(
                "`Auto` means raw values in stacked mode and normalized 0-100 in overlay mode. "
                "`Mean by date` averages duplicate same-day points per series before plotting. "
                "Smoothing is a rolling mean by observed point order."
            ),
            "### Labs",
            lab_category,
            lab_show_all_category,
            lab_metrics,
            lab_context_metrics,
            pn.pane.Markdown(
                "The category selector filters marker choices. In stacked mode, show-all "
                "plots every marker in that category; turn it off for only the selected chips. "
                "Context overlays are tagged `CONTEXT` and can be stacked or normalized."
            ),
            "### Wearables",
            wearable_metrics,
            wearable_rollup,
            pn.pane.Markdown(
                "Theme: use the header light/dark toggle. The current theme is stored in the "
                "URL, so `?theme=dark` and `?theme=default` are bookmarkable."
            ),
        )
    )

    if not repo.available:
        template.main.append(_missing_data_panel(settings.duckdb_path))
        return template

    overview = pn.Column(
        pn.bind(_hero_panel, repo=repo, profile=profile),
        pn.bind(_review_now_panel, repo=repo, profile=profile),
        pn.bind(_what_changed_panel, repo=repo, profile=profile),
        pn.bind(_domain_cards, repo=repo, profile=profile),
        pn.bind(_activity_cards, repo=repo, profile=profile),
        pn.bind(_latest_flags_table, repo=repo, profile=profile),
        pn.bind(_overview_cards, repo=repo, profile=profile),
        pn.bind(_coverage_table, repo=repo, profile=profile),
    )
    labs = pn.Column(
        pn.bind(
            _lab_plot,
            repo=repo,
            profile=profile,
            metrics=lab_metrics,
            category=lab_category,
            show_all_category=lab_show_all_category,
            context_metrics=lab_context_metrics,
            range_label=date_range,
            mode=comparison_mode,
            graph_scale=graph_scale,
            aggregation=graph_aggregation,
            smoothing=graph_smoothing,
        ),
        pn.bind(_lab_category_table, repo=repo, profile=profile, category=lab_category),
    )
    wearables = pn.Column(
        pn.bind(
            _wearable_plot,
            repo=repo,
            profile=profile,
            metrics=wearable_metrics,
            rollup=wearable_rollup,
            range_label=date_range,
            mode=comparison_mode,
            graph_scale=graph_scale,
            aggregation=graph_aggregation,
            smoothing=graph_smoothing,
        )
    )
    context = pn.Column(pn.bind(_context_table, repo=repo, profile=profile))
    analysis = pn.Column(pn.bind(_analysis_table, repo=repo, profile=profile))
    qa = pn.Column(_qa_table(repo), _table_counts(repo))

    template.main.append(
        pn.Tabs(
            ("Overview", overview),
            ("Labs", labs),
            ("Wearables", wearables),
            ("Context windows", context),
            ("Analysis", analysis),
            ("Sources & QA", qa),
            dynamic=True,
        )
    )
    return template


def _missing_data_panel(duckdb_path: Path):
    return pn.Column(
        pn.pane.HTML(
            _status_card(
                "Local data lake not built yet",
                f"Expected DuckDB database at `{duckdb_path}`. Run `health-v2 build --from-wiki` "
                "after setting HEALTH_WIKI_ROOT to the de-identified health-assessments wiki.",
                ["local-first", "no raw data bundled"],
            )
        )
    )


def _hero_panel(repo: HealthRepository, profile: str):
    summary = repo.profile_summary(profile)
    if not summary.get("available"):
        return pn.pane.HTML(_status_card("No local database", "Run the build step first."))
    profile_label = profile.title()
    if summary["wearable_rows"]:
        wearable_line = (
            f"Apple Health context: {summary['wearable_rows']:,} optimized daily rows "
            f"from {summary['wearable_start']} to {summary['wearable_end']}."
        )
        tags = ["OWN-RISK", "LABS", "WEARABLE_CONTEXT", "QA REVIEW"]
    else:
        wearable_line = "No Apple Health wearable dataset is assigned to this profile yet."
        tags = ["OWN-RISK", "LABS", "DATA_GAP", "PROFILE EXCLUSIVE"]
    return pn.pane.HTML(
        f"""
<div class="ha-hero">
  <h1>{profile_label} review board</h1>
  <p class="ha-muted">
    Review queue → domain map → timeline evidence → source rows.
    {summary["lab_rows"]:,} lab/vital rows from {summary["lab_start"]} to {summary["lab_end"]}.
    {wearable_line}
  </p>
  <div>{"".join(f'<span class="ha-tag">{tag}</span>' for tag in tags)}</div>
</div>
"""
    )


def _review_now_panel(repo: HealthRepository, profile: str):
    queue = repo.review_queue(profile)
    if queue.empty:
        return pn.pane.HTML(
            _status_card(
                "Review queue",
                "No prioritized review items are available for this profile yet.",
                ["DATA_GAP"],
            )
        )
    items = []
    for row in queue.head(6).itertuples(index=False):
        items.append(
            f"<li><strong>{row.priority.upper()}</strong> · {row.domain}: {row.review_item} "
            f"<span class='ha-muted'>[{row.tag}; {row.status}]</span></li>"
        )
    return pn.pane.HTML(
        f"""
<div class="ha-card">
  <h2>Review queue</h2>
  <ul class="ha-review-list">{"".join(items)}</ul>
</div>
"""
    )


def _activity_cards(repo: HealthRepository, profile: str):
    df = repo.activity_snapshot(profile)
    if df.empty or df["days_with_data"].fillna(0).sum() == 0:
        return pn.pane.HTML(
            _status_card(
                "Recent activity context",
                "No wearable activity rows for this profile. "
                "Cara currently has no Apple Health dataset.",
                ["DATA_GAP"],
            )
        )
    cards = []
    preferred = {
        ("Steps/day", 90): "steps/day",
        ("Distance/day", 90): "km/day",
        ("Active kcal/day", 90): "kcal/day",
        ("Steps/day", 30): "30d steps",
    }
    for (label, window), display_unit in preferred.items():
        rows = df[(df["label"] == label) & (df["window_days"] == window)]
        if rows.empty:
            continue
        row = rows.iloc[0]
        value = row["avg_per_day"]
        if pd.isna(value):
            rendered = "—"
        elif "steps" in display_unit:
            rendered = f"{value:,.0f}"
        elif "km" in display_unit:
            rendered = f"{value:,.2f}"
        else:
            rendered = f"{value:,.0f}"
        cards.append(
            pn.pane.HTML(
                _metric_card(
                    f"{window}d {label}",
                    rendered,
                    f"{int(row['days_with_data'])} days · {display_unit}",
                )
            )
        )
    return pn.Column("### Recent activity context", pn.GridBox(*cards, ncols=4))


def _domain_cards(repo: HealthRepository, profile: str):
    df = repo.domain_status(profile)
    if df.empty:
        return pn.pane.HTML(_status_card("Domain review", "No domain summaries are available."))
    cards = []
    for row in df.itertuples(index=False):
        cards.append(
            pn.pane.HTML(
                f"""
<div class="ha-card">
  <h3>{row.domain}</h3>
  <div>
    <span class="ha-tag">{row.status}</span>
    <span class="ha-tag">{row.priority}</span>
    <span class="ha-tag">{row.primary_tag}</span>
  </div>
  <p>{row.summary}</p>
  <p class="ha-muted"><strong>Evidence:</strong> {row.evidence}</p>
  <p class="ha-muted"><strong>Needs:</strong> {row.data_needed}</p>
</div>
"""
            )
        )
    return pn.Column("### Domain map / review cards", pn.GridBox(*cards, ncols=2))


def _what_changed_panel(repo: HealthRepository, profile: str):
    df = repo.what_changed(profile)
    if df.empty:
        return pn.pane.HTML(
            _status_card("What changed", "No comparable prior values for tracked markers yet.")
        )
    groups = []
    for change_type, group in df.groupby("change_type", sort=False):
        items = "".join(
            f"<li>{row.statement} <span class='ha-muted'>({row.latest_date})</span></li>"
            for row in group.head(6).itertuples(index=False)
        )
        groups.append(f"<h3>{change_type.replace('_', ' ').title()}</h3><ul>{items}</ul>")
    return pn.pane.HTML(
        f"""
<div class="ha-card">
  <h2>What changed since prior comparable rows</h2>
  {"".join(groups)}
</div>
"""
    )


def _latest_flags_table(repo: HealthRepository, profile: str):
    df = repo.latest_lab_flags(profile)
    if df.empty:
        return pn.pane.HTML(
            _status_card("Latest source flags", "No source-flagged lab rows for this profile.")
        )
    return pn.Column(
        "### Latest source-flagged labs",
        pn.widgets.Tabulator(df, page_size=8, pagination="local", sizing_mode="stretch_width"),
    )


def _overview_cards(repo: HealthRepository, profile: str):
    summary = repo.profile_summary(profile)
    if not summary.get("available"):
        return pn.pane.HTML(_status_card("No local database", "Run the build step first."))
    cards = pn.GridBox(
        pn.pane.HTML(
            _metric_card(
                "Lab rows",
                f"{summary['lab_rows']:,}",
                f"{summary['lab_start']} → {summary['lab_end']}",
            )
        ),
        pn.pane.HTML(
            _metric_card(
                "Wearable daily rows",
                f"{summary['wearable_rows']:,}",
                f"{summary['wearable_start']} → {summary['wearable_end']}",
            )
        ),
        pn.pane.HTML(
            _metric_card(
                "Latest lab event",
                summary["latest_lab_date"] or "—",
                f"{summary['latest_lab_observations']} observations",
            )
        ),
        pn.pane.HTML(_metric_card("QA issues", summary["qa_issues"], "review before inference")),
        ncols=4,
    )
    caveat = pn.pane.HTML(
        _status_card(
            "Inference contract",
            "Experimental own-risk review layer. This app separates lab observations, wearable "
            "context, derived rollups, QA issues, and inference cards. Apple Health record-level "
            "rows are not loaded by default.",
            ["OWN-RISK", "OBSERVED", "DERIVED", "WEARABLE_CONTEXT", "QA_ISSUE"],
        )
    )
    return pn.Column(cards, caveat)


def _coverage_table(repo: HealthRepository, profile: str):
    df = repo.coverage(profile)
    if df.empty:
        return pn.pane.HTML(
            _status_card(
                "No wearable coverage",
                "This profile has no Apple Health data in the local build.",
                ["DATA_GAP"],
            )
        )
    return pn.Column(
        "### Wearable coverage",
        pn.widgets.Tabulator(df, page_size=12, pagination="local", sizing_mode="stretch_width"),
    )


def _effective_graph_scale(mode: str, graph_scale: str) -> str:
    if graph_scale == "Auto":
        return "Normalized 0-100" if mode == "Overlay" else "Raw values"
    return graph_scale


def _prepare_graph_dataframe(
    df: pd.DataFrame,
    *,
    mode: str,
    graph_scale: str,
    aggregation: str,
    smoothing: str,
) -> tuple[pd.DataFrame, str, str]:
    """Return plot-ready values plus a ylabel and note for the selected transform."""

    prepared = df.copy()
    prepared["value"] = pd.to_numeric(prepared["value"], errors="coerce")
    prepared = prepared.dropna(subset=["date", "series", "value"]).sort_values(["series", "date"])
    if prepared.empty:
        return prepared, "value", "No numeric points."

    if aggregation == "Mean by date":
        first_cols = [
            column
            for column in [
                "metric",
                "unit",
                "source_id",
                "flag_raw",
                "reference_range_raw",
                "category",
                "record_count",
                "aggregation_preferred",
            ]
            if column in prepared.columns
        ]
        agg_spec = {"value": "mean", **{column: "first" for column in first_cols}}
        prepared = (
            prepared.groupby(["series", "date"], as_index=False)
            .agg(agg_spec)
            .sort_values(["series", "date"])
        )

    window = _smoothing_window(smoothing)
    if window > 1:
        prepared["value"] = prepared.groupby("series", group_keys=False)["value"].transform(
            lambda values: values.rolling(window=window, min_periods=1).mean()
        )

    scale = _effective_graph_scale(mode, graph_scale)
    prepared["plot_value"] = prepared["value"]
    ylabel = "value"
    note_parts = []
    if aggregation == "Mean by date":
        note_parts.append("duplicate same-day points averaged per series")
    if window > 1:
        note_parts.append(f"{window}-point rolling mean")

    if scale == "Raw values":
        ylabel = "value"
    elif scale == "Normalized 0-100":
        mins = prepared.groupby("series")["value"].transform("min")
        maxs = prepared.groupby("series")["value"].transform("max")
        span = maxs - mins
        prepared["plot_value"] = ((prepared["value"] - mins) / span * 100).where(span != 0, 50)
        ylabel = "Normalized index (0-100 per series)"
        note_parts.append("each series scaled to its visible min/max")
    elif scale == "Mean-centered":
        means = prepared.groupby("series")["value"].transform("mean")
        prepared["plot_value"] = prepared["value"] - means
        ylabel = "Value minus visible mean"
        note_parts.append("zero line is each series mean")
    elif scale == "% of mean":
        means = prepared.groupby("series")["value"].transform("mean")
        prepared["plot_value"] = (prepared["value"] / means * 100).where(means != 0)
        ylabel = "% of visible mean"
        note_parts.append("100 means equal to that series visible mean")
    elif scale == "% change from first":
        first = prepared.groupby("series")["value"].transform("first")
        prepared["plot_value"] = ((prepared["value"] - first) / first.abs() * 100).where(first != 0)
        ylabel = "% change from first visible point"
        note_parts.append("baseline is first visible point per series")
    elif scale == "Z-score":
        means = prepared.groupby("series")["value"].transform("mean")
        stds = prepared.groupby("series")["value"].transform("std").fillna(0)
        prepared["plot_value"] = ((prepared["value"] - means) / stds).where(stds != 0, 0)
        ylabel = "Z-score within visible window"
        note_parts.append("standard deviations from each series visible mean")
    elif scale == "Log10":
        prepared["plot_value"] = prepared["value"].where(prepared["value"] > 0).map(math.log10)
        prepared = prepared.dropna(subset=["plot_value"])
        ylabel = "log10(value)"
        note_parts.append("non-positive values hidden for log scale")

    return prepared, ylabel, "; ".join(note_parts) or "observed values"


def _smoothing_window(smoothing: str) -> int:
    if smoothing.startswith("3-"):
        return 3
    if smoothing.startswith("7-"):
        return 7
    if smoothing.startswith("30-"):
        return 30
    return 1


def _stacked_series_plots(
    df: pd.DataFrame,
    title: str,
    *,
    graph_scale: str = "Auto",
    aggregation: str = "Observed points",
    smoothing: str = "None",
    mode: str = "Stacked",
    max_series: int | None = 8,
    height: int = 190,
    group_by_category: bool = False,
):
    df, global_ylabel, transform_note = _prepare_graph_dataframe(
        df,
        mode=mode,
        graph_scale=graph_scale,
        aggregation=aggregation,
        smoothing=smoothing,
    )
    if df.empty:
        return pn.pane.HTML(
            _status_card("No plottable points", "Selected series have no numeric values.")
        )
    scale = _effective_graph_scale(mode, graph_scale)

    total_series = df["series"].dropna().nunique()
    chart_height = 150 if total_series > 20 else height
    plots: list[object] = []
    groups: list[tuple[str | None, pd.DataFrame]]
    if group_by_category and "category" in df.columns:
        groups = [
            (str(category), group.sort_values(["series", "date"]))
            for category, group in df.groupby("category", sort=True)
        ]
    else:
        groups = [(None, df)]

    shown_series = 0
    for category, category_df in groups:
        if category is not None:
            plots.append(pn.pane.Markdown(f"#### {category}"))
        series_names = list(category_df["series"].dropna().unique())
        if max_series is not None:
            remaining = max(max_series - shown_series, 0)
            series_names = series_names[:remaining]
        for series in series_names:
            group = category_df[category_df["series"] == series]
            unit = ", ".join(sorted(str(u) for u in group["unit"].dropna().unique() if str(u)))
            ylabel = (unit or "value") if scale == "Raw values" else global_ylabel
            plots.append(
                group.hvplot.line(
                    x="date",
                    y="plot_value",
                    height=chart_height,
                    responsive=True,
                    title=str(series),
                    ylabel=ylabel,
                    xlabel="Date",
                    grid=True,
                ).opts(shared_axes=False)
            )
        shown_series += len(series_names)
        if max_series is not None and shown_series >= max_series:
            break

    note = ""
    if max_series is not None and total_series > max_series:
        note = f" Showing first {max_series} series; reduce selection for the rest."
    elif max_series is None:
        note = f" Showing all {total_series} series."
    return pn.Column(
        pn.pane.Markdown(f"### {title}\nStacked timelines · {transform_note}.{note}"),
        *plots,
    )


def _overlay_series_plot(
    df: pd.DataFrame,
    title: str,
    *,
    graph_scale: str = "Auto",
    aggregation: str = "Observed points",
    smoothing: str = "None",
):
    plotted, ylabel, transform_note = _prepare_graph_dataframe(
        df,
        mode="Overlay",
        graph_scale=graph_scale,
        aggregation=aggregation,
        smoothing=smoothing,
    )
    if plotted.empty:
        return pn.pane.HTML(
            _status_card("No plottable points", "Selected series have no numeric values.")
        )
    plot = plotted.hvplot.line(
        x="date",
        y="plot_value",
        by="series",
        height=430,
        responsive=True,
        title=title,
        ylabel=ylabel,
        xlabel="Date",
        grid=True,
    )
    note = pn.pane.Markdown(
        f"Overlay mode · {transform_note}. If multiple units are overlaid, prefer "
        "`Auto`, `Normalized 0-100`, `% change from first`, `% of mean`, or `Z-score`."
    )
    return pn.Column(note, plot)


def _lab_plot(
    repo: HealthRepository,
    profile: str,
    metrics: list[str],
    category: str,
    show_all_category: bool,
    context_metrics: list[str],
    range_label: str,
    mode: str,
    graph_scale: str,
    aggregation: str,
    smoothing: str,
):
    window = make_date_filter(range_label, repo.latest_window(profile).end)
    category_value = _category_query_value(category)
    use_category_markers = show_all_category and (
        mode == "Stacked" or category != ALL_LAB_CATEGORIES
    )
    if use_category_markers:
        df = repo.lab_series_for_category(profile, category_value, window)
        selected = f"all markers in {category}" if category_value else "all lab markers"
    else:
        metrics = [metric for metric in metrics if metric]
        df = repo.lab_series_multi(profile, metrics, window)
        selected = ", ".join(metrics) if metrics else "selected markers"

    context_metrics = [metric for metric in context_metrics if metric]
    context_df = repo.lab_context_series(profile, context_metrics, window)
    if not context_df.empty:
        df = pd.concat([df, context_df], ignore_index=True)
        selected = f"{selected} + {', '.join(context_metrics)}"

    if df.empty:
        return pn.pane.HTML(_status_card("No lab points", f"No numeric data for {selected}."))
    title = f"Lab comparison · {category} · {range_label}"
    if mode == "Overlay":
        return _overlay_series_plot(
            df,
            title,
            graph_scale=graph_scale,
            aggregation=aggregation,
            smoothing=smoothing,
        )
    return _stacked_series_plots(
        df,
        title,
        graph_scale=graph_scale,
        aggregation=aggregation,
        smoothing=smoothing,
        mode=mode,
        max_series=None if use_category_markers else 8,
        group_by_category=use_category_markers and category == ALL_LAB_CATEGORIES,
    )


def _lab_category_table(repo: HealthRepository, profile: str, category: str):
    df = repo.lab_category_recent(profile, _category_query_value(category))
    if df.empty:
        return pn.pane.HTML(_status_card("No category rows", f"No numeric data for {category}."))
    return pn.Column(
        f"### Recent rows · {category}",
        pn.widgets.Tabulator(df, page_size=15, pagination="local", sizing_mode="stretch_width"),
    )


def _wearable_plot(
    repo: HealthRepository,
    profile: str,
    metrics: list[str],
    rollup: str,
    range_label: str,
    mode: str,
    graph_scale: str,
    aggregation: str,
    smoothing: str,
):
    window = make_date_filter(range_label, repo.latest_window(profile).end)
    metrics = [metric for metric in metrics if metric]
    df = repo.wearable_series_multi(profile, metrics, rollup, window)  # type: ignore[arg-type]
    if df.empty:
        selected = ", ".join(metrics) if metrics else "selected metrics"
        return pn.pane.HTML(
            _status_card(
                "No wearable points",
                f"No {rollup} Apple Health data for {selected} on this profile/window.",
                ["DATA_GAP"],
            )
        )
    title = f"Wearable comparison · {rollup} · {range_label}"
    meta = pn.pane.Markdown(
        f"**{len(df):,} optimized {rollup} points** across "
        f"{df['series'].nunique()} selected series. Raw Apple record rows are not loaded."
    )
    if mode == "Overlay":
        return pn.Column(
            "### Wearable timelines",
            meta,
            _overlay_series_plot(
                df,
                title,
                graph_scale=graph_scale,
                aggregation=aggregation,
                smoothing=smoothing,
            ),
        )
    return pn.Column(
        "### Wearable timelines",
        meta,
        _stacked_series_plots(
            df,
            title,
            graph_scale=graph_scale,
            aggregation=aggregation,
            smoothing=smoothing,
            mode=mode,
        ),
    )


def _context_table(repo: HealthRepository, profile: str):
    df = repo.context_windows(profile)
    if df.empty:
        return pn.pane.HTML(
            _status_card(
                "No context windows",
                "No wearable/lab-date context windows are available for this profile.",
                ["DATA_GAP"],
            )
        )
    return pn.Column(
        "### Lab-window wearable context",
        pn.pane.Markdown(
            "Trailing 7/30/90-day wearable summaries before lab events. Tagged "
            "`DERIVED|WEARABLE_CONTEXT`."
        ),
        pn.widgets.Tabulator(df, page_size=20, pagination="local", sizing_mode="stretch_width"),
    )


def _analysis_table(repo: HealthRepository, profile: str):
    df = repo.inference_events(profile)
    if df.empty:
        return pn.pane.HTML(
            _status_card(
                "No inference events yet",
                "No reviewable inference/context/data-gap events are available for this profile.",
                ["DATA_GAP"],
            )
        )
    return pn.Column(
        "### Reviewable analysis events",
        pn.pane.Markdown(
            "Deterministic events only. Statements preserve tags, inputs, confidence, and caveats. "
            "They are not diagnoses."
        ),
        pn.widgets.Tabulator(df, page_size=12, pagination="local", sizing_mode="stretch_width"),
    )


def _qa_table(repo: HealthRepository):
    df = repo.qa_issues()
    if df.empty:
        return pn.pane.HTML(_status_card("No QA issues", "No current QA issues found."))
    return pn.Column(
        "### QA issues",
        pn.widgets.Tabulator(df, page_size=12, pagination="local", sizing_mode="stretch_width"),
    )


def _table_counts(repo: HealthRepository):
    df = repo.table_counts()
    if df.empty:
        return pn.pane.Markdown("No local table counts available.")
    df = df.assign(rows=df["rows"].map(lambda value: f"{value:,}"))
    return pn.Column(
        "### Local tables",
        pn.widgets.Tabulator(df, page_size=20, pagination="local", sizing_mode="stretch_width"),
    )


# Ensure pandas import remains used when documentation tooling inspects module globals.
assert pd is not None
