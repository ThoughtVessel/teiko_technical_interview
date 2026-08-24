#!/usr/bin/env python3
"""Interactive dashboard for the Loblaw Bio cell-count analysis.

Start with `make dashboard` (or `python app.py`), then open port 8050.
Each part of the analysis is a tab in the bar along the bottom of the screen.
"""

import os

import dash
import pandas as pd
import plotly.express as px
from dash import Input, Output, dash_table, dcc, html

import analysis

# Override with `PORT=8060 make dashboard` if 8050 is taken.
PORT = int(os.environ.get("PORT", 8050))

# Blue palette, defined once so every view stays consistent.
NAVY = "#0b2545"
NAVY_SOFT = "#16365e"
PRIMARY = "#1d4ed8"
ACCENT = "#3b82f6"
PAGE_BG = "#eef3fa"
CARD_BG = "#ffffff"
BORDER = "#d3e0f0"
TEXT = "#0f172a"
MUTED = "#5b7089"

NAV_HEIGHT = 68
FONT = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"


NON_RESPONDER = "#93c5fd"


def load_all():
    """Read every part straight from the database, so the dashboard and the
    generated CSV files are always the same numbers."""
    try:
        conn = analysis.connect()
    except FileNotFoundError:
        return None
    try:
        comparison, cohort = analysis.compare_responders(conn)
        return {
            "frequencies": pd.DataFrame(
                analysis.cell_frequencies(conn), columns=analysis.FREQUENCY_COLUMNS
            ),
            "comparison": pd.DataFrame(comparison, columns=analysis.COMPARISON_COLUMNS),
            "cohort": cohort,
            "responder_frequencies": pd.DataFrame(analysis.responder_frequencies(conn)),
            "baseline_samples": pd.DataFrame(
                analysis.baseline_samples(conn), columns=analysis.BASELINE_COLUMNS
            ),
            "breakdowns": analysis.baseline_breakdowns(conn),
            "b_cell": analysis.male_melanoma_baseline_b_cell(conn),
        }
    finally:
        conn.close()


DATA = load_all()
DB_READY = DATA is not None
FREQUENCIES = DATA["frequencies"] if DB_READY else pd.DataFrame(
    columns=analysis.FREQUENCY_COLUMNS
)


def stat_card(label, value):
    return html.Div(
        [
            html.Div(value, style={"fontSize": "30px", "fontWeight": "700", "color": PRIMARY}),
            html.Div(label, style={"fontSize": "12px", "color": MUTED,
                                   "textTransform": "uppercase", "letterSpacing": "0.06em",
                                   "marginTop": "4px"}),
        ],
        style={"background": CARD_BG, "border": f"1px solid {BORDER}", "borderRadius": "10px",
               "padding": "18px 24px", "flex": "1", "minWidth": "160px"},
    )


def section_title(title, subtitle):
    return html.Div(
        [
            html.H2(title, style={"margin": "0", "fontSize": "22px", "color": TEXT}),
            html.P(subtitle, style={"margin": "6px 0 0", "color": MUTED, "fontSize": "14px"}),
        ],
        style={"marginBottom": "22px"},
    )


def missing_db():
    return html.Div(
        "Database not found. Run `make pipeline` first.",
        style={"background": "#fdecea", "border": "1px solid #f5b7b1", "color": "#922b21",
               "padding": "18px", "borderRadius": "10px"},
    )


def card(children, **extra):
    style = {"background": CARD_BG, "border": f"1px solid {BORDER}",
             "borderRadius": "10px", "padding": "20px", "marginBottom": "20px"}
    style.update(extra)
    return html.Div(children, style=style)


def callout(title, body, tone=PRIMARY, background="#e8f0fd"):
    return html.Div(
        [
            html.Div(title, style={"fontWeight": "700", "color": tone,
                                   "marginBottom": "6px", "fontSize": "14px"}),
            html.Div(body, style={"color": TEXT, "fontSize": "14px", "lineHeight": "1.6"}),
        ],
        style={"background": background, "borderLeft": f"4px solid {tone}",
               "borderRadius": "8px", "padding": "16px 20px", "marginBottom": "20px"},
    )


def simple_table(frame, columns, formats=None):
    formats = formats or {}
    return dash_table.DataTable(
        columns=[{"name": label, "id": key, **formats.get(key, {})}
                 for key, label in columns],
        data=frame.to_dict("records"),
        page_size=15,
        sort_action="native",
        style_table={"overflowX": "auto"},
        style_cell={"fontFamily": FONT, "fontSize": "13px", "padding": "9px 13px",
                    "textAlign": "left", "border": "none",
                    "borderBottom": f"1px solid {BORDER}"},
        style_header={"background": NAVY, "color": "#ffffff", "fontWeight": "600",
                      "fontSize": "12px", "textTransform": "uppercase",
                      "letterSpacing": "0.04em", "border": "none"},
        style_data_conditional=[{"if": {"row_index": "odd"}, "backgroundColor": "#f6f9fd"}],
    )


def part3_view():
    if not DB_READY:
        return missing_db()

    comparison = DATA["comparison"]
    cohort = DATA["cohort"]
    significant = comparison[comparison["significant"] == "yes"]["population"].tolist()

    figure = px.box(
        DATA["responder_frequencies"], x="population", y="percentage", color="response",
        category_orders={"population": analysis.POPULATIONS, "response": ["yes", "no"]},
        color_discrete_map={"yes": PRIMARY, "no": NON_RESPONDER},
        labels={"percentage": "Relative frequency (%)", "population": "",
                "response": "Responder"},
        points=False,
    )
    figure.update_layout(
        plot_bgcolor="#ffffff", paper_bgcolor="#ffffff", font_family=FONT,
        margin={"l": 40, "r": 20, "t": 20, "b": 40}, height=460,
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "x": 0},
    )
    figure.update_yaxes(gridcolor="#e8eef7")

    if significant:
        verdict = callout(
            "Significant difference found",
            f"After Benjamini-Hochberg correction, {', '.join(significant)} "
            f"differ{'s' if len(significant) == 1 else ''} significantly between "
            "responders and non-responders (q < 0.05).",
        )
    else:
        verdict = callout(
            "No population differs significantly",
            "No population reaches significance once p-values are corrected for "
            "testing five populations. cd4_t_cell is the closest (raw p = 0.013, "
            "q = 0.067) and is the only one worth following up. Reporting it as a "
            "finding without correction would be a false positive risk.",
            tone="#92400e", background="#fef3c7",
        )

    return html.Div([
        section_title(
            "Part 3 · Responders vs Non-responders",
            "Melanoma patients treated with miraclib, PBMC samples only.",
        ),
        html.Div([
            stat_card("Samples", f"{cohort['n_samples']:,}"),
            stat_card("Responder subjects", f"{cohort['n_responder_subjects']:,}"),
            stat_card("Non-responder subjects", f"{cohort['n_non_responder_subjects']:,}"),
        ], style={"display": "flex", "gap": "16px", "marginBottom": "24px",
                  "flexWrap": "wrap"}),
        verdict,
        card([
            html.Div("Relative frequency by population", style={
                "fontWeight": "600", "marginBottom": "10px", "fontSize": "14px"}),
            dcc.Graph(figure=figure, config={"displayModeBar": False}),
        ]),
        card([
            html.Div("Mann-Whitney U, two-sided, Benjamini-Hochberg corrected",
                     style={"fontWeight": "600", "marginBottom": "12px", "fontSize": "14px"}),
            simple_table(
                comparison,
                [("population", "Population"), ("median_responder", "Median resp. %"),
                 ("median_non_responder", "Median non-resp. %"),
                 ("median_difference", "Difference"), ("p_value", "p"),
                 ("p_value_adjusted", "q (BH)"), ("rank_biserial", "Effect size"),
                 ("significant", "Significant")],
                {k: {"type": "numeric", "format": {"specifier": ".4f"}}
                 for k in ("median_responder", "median_non_responder",
                           "median_difference", "p_value", "p_value_adjusted",
                           "rank_biserial")},
            ),
        ], padding="20px 20px 8px"),
        callout(
            "Caveat on independence",
            "Each subject contributes three samples (days 0, 7 and 14), so samples "
            "within a subject are correlated and the test's independence assumption "
            "is not strictly met. A baseline-only sensitivity analysis, where every "
            "subject appears once, is written to "
            "outputs/part3_responder_stats_baseline.csv; nothing is significant there "
            "either.",
            tone=MUTED, background="#f1f5fb",
        ),
    ])


def part4_view():
    if not DB_READY:
        return missing_db()

    breakdowns = DATA["breakdowns"]
    samples = DATA["baseline_samples"]
    b_cell = DATA["b_cell"]

    def breakdown_card(title, entries):
        return html.Div([
            html.Div(title, style={"fontSize": "12px", "color": MUTED, "fontWeight": "600",
                                   "textTransform": "uppercase", "letterSpacing": "0.06em",
                                   "marginBottom": "12px"}),
            html.Div([
                html.Div([
                    html.Span(str(entry["category"]), style={"color": TEXT, "fontSize": "14px"}),
                    html.Span(f"{entry['count']:,}", style={
                        "float": "right", "fontWeight": "700", "color": PRIMARY}),
                ], style={"padding": "7px 0", "borderBottom": f"1px solid {BORDER}"})
                for entry in entries
            ]),
        ], style={"background": CARD_BG, "border": f"1px solid {BORDER}",
                  "borderRadius": "10px", "padding": "20px", "flex": "1",
                  "minWidth": "220px"})

    return html.Div([
        section_title(
            "Part 4 · Baseline Subset",
            "Melanoma PBMC samples at day 0 from miraclib-treated patients.",
        ),
        html.Div([
            stat_card("Baseline samples", f"{len(samples):,}"),
            stat_card("Subjects", f"{samples['subject'].nunique():,}"),
            stat_card("Projects", f"{samples['project'].nunique():,}"),
        ], style={"display": "flex", "gap": "16px", "marginBottom": "24px",
                  "flexWrap": "wrap"}),
        html.Div([
            breakdown_card("Samples per project", breakdowns["samples_per_project"]),
            breakdown_card("Subjects by response", breakdowns["subjects_by_response"]),
            breakdown_card("Subjects by sex", breakdowns["subjects_by_sex"]),
        ], style={"display": "flex", "gap": "16px", "marginBottom": "24px",
                  "flexWrap": "wrap"}),
        callout(
            "Average B cell count — male melanoma responders at day 0",
            html.Div([
                html.Span(f"{b_cell['average_b_cell']:,.2f}", style={
                    "fontSize": "30px", "fontWeight": "700", "color": PRIMARY,
                    "display": "block", "marginBottom": "6px"}),
                html.Span(
                    f"Across {b_cell['n_samples']:,} samples from "
                    f"{b_cell['n_subjects']:,} subjects. This question spans all "
                    "sample types and all treatments, so it is a wider cohort than "
                    "the baseline subset above.",
                    style={"color": MUTED, "fontSize": "13px"}),
            ]),
        ),
        card([
            html.Div(f"Baseline samples ({len(samples):,})", style={
                "fontWeight": "600", "marginBottom": "12px", "fontSize": "14px"}),
            simple_table(
                samples,
                [("sample", "Sample"), ("project", "Project"), ("subject", "Subject"),
                 ("age", "Age"), ("sex", "Sex"), ("response", "Response"),
                 ("b_cell", "B cell"), ("cd8_t_cell", "CD8 T"), ("cd4_t_cell", "CD4 T"),
                 ("nk_cell", "NK"), ("monocyte", "Monocyte")],
                {k: {"type": "numeric", "format": {"specifier": ","}}
                 for k in ("b_cell", "cd8_t_cell", "cd4_t_cell", "nk_cell", "monocyte")},
            ),
        ], padding="20px 20px 8px"),
    ])


def part2_view():
    if not DB_READY:
        return html.Div(
            "Database not found. Run `make pipeline` first.",
            style={"background": "#fdecea", "border": "1px solid #f5b7b1", "color": "#922b21",
                   "padding": "18px", "borderRadius": "10px"},
        )

    return html.Div(
        [
            section_title(
                "Part 2 · Cell Population Frequencies",
                "Relative frequency of each immune cell population within each sample. "
                "One row per sample and population.",
            ),
            html.Div(
                [
                    stat_card("Samples", f"{FREQUENCIES['sample'].nunique():,}"),
                    stat_card("Populations", f"{FREQUENCIES['population'].nunique():,}"),
                    stat_card("Total rows", f"{len(FREQUENCIES):,}"),
                ],
                style={"display": "flex", "gap": "16px", "marginBottom": "24px",
                       "flexWrap": "wrap"},
            ),
            html.Div(
                [
                    html.Label("Search by sample ID", style={
                        "display": "block", "fontSize": "12px", "fontWeight": "600",
                        "color": MUTED, "textTransform": "uppercase",
                        "letterSpacing": "0.06em", "marginBottom": "8px"}),
                    dcc.Input(
                        id="sample-search", type="text", debounce=False,
                        placeholder="e.g. sample00042 — leave blank to show all",
                        style={"width": "100%", "maxWidth": "420px", "padding": "10px 14px",
                               "fontSize": "14px", "borderRadius": "8px",
                               "border": f"1px solid {BORDER}", "fontFamily": FONT,
                               "boxSizing": "border-box"},
                    ),
                    html.Span(id="search-result-count", style={
                        "marginLeft": "14px", "fontSize": "13px", "color": MUTED}),
                ],
                style={"background": CARD_BG, "border": f"1px solid {BORDER}",
                       "borderRadius": "10px", "padding": "20px", "marginBottom": "20px"},
            ),
            html.Div(
                dash_table.DataTable(
                    id="frequency-table",
                    columns=[
                        {"name": "Sample", "id": "sample"},
                        {"name": "Total count", "id": "total_count",
                         "type": "numeric", "format": {"specifier": ","}},
                        {"name": "Population", "id": "population"},
                        {"name": "Count", "id": "count",
                         "type": "numeric", "format": {"specifier": ","}},
                        {"name": "Percentage", "id": "percentage",
                         "type": "numeric", "format": {"specifier": ".2f"}},
                    ],
                    data=FREQUENCIES.to_dict("records"),
                    page_size=25,
                    sort_action="native",
                    style_table={"overflowX": "auto"},
                    style_cell={"fontFamily": FONT, "fontSize": "14px", "padding": "10px 14px",
                                "textAlign": "left", "border": "none",
                                "borderBottom": f"1px solid {BORDER}"},
                    style_header={"background": NAVY, "color": "#ffffff", "fontWeight": "600",
                                  "fontSize": "13px", "textTransform": "uppercase",
                                  "letterSpacing": "0.04em", "border": "none"},
                    style_data_conditional=[
                        {"if": {"row_index": "odd"}, "backgroundColor": "#f6f9fd"},
                        {"if": {"column_id": "percentage"},
                         "fontWeight": "600", "color": PRIMARY},
                    ],
                ),
                style={"background": CARD_BG, "border": f"1px solid {BORDER}",
                       "borderRadius": "10px", "padding": "8px", "overflow": "hidden"},
            ),
        ]
    )


def nav_tab(label, value):
    base = {"padding": "0 28px", "border": "none", "display": "flex",
            "flexDirection": "column", "justifyContent": "center", "alignItems": "center",
            "fontFamily": FONT, "cursor": "pointer", "background": NAVY, "color": "#8fb0d9",
            "borderTop": "3px solid transparent"}
    selected = {**base, "background": NAVY_SOFT, "color": "#ffffff",
                "borderTop": f"3px solid {ACCENT}"}
    return dcc.Tab(
        label=label, value=value, style=base, selected_style=selected,
        children=[],
    )


app = dash.Dash(__name__, suppress_callback_exceptions=True,
                title="Loblaw Bio · Immune Cell Analysis")

app.layout = html.Div(
    [
        html.Header(
            [
                html.H1("Loblaw Bio — Immune Cell Population Analysis",
                        style={"margin": "0", "fontSize": "20px", "fontWeight": "700"}),
                html.P("Clinical trial cell-count explorer",
                       style={"margin": "4px 0 0", "fontSize": "13px", "color": "#9dbbe0"}),
            ],
            style={"background": NAVY, "color": "#ffffff", "padding": "22px 40px"},
        ),
        html.Main(
            html.Div(id="tab-content", style={"maxWidth": "1200px", "margin": "0 auto"}),
            style={"padding": "32px 40px", "paddingBottom": f"{NAV_HEIGHT + 40}px"},
        ),
        html.Nav(
            dcc.Tabs(
                id="part-tabs", value="part2",
                children=[
                    nav_tab("Part 2 · Frequencies", "part2"),
                    nav_tab("Part 3 · Statistics", "part3"),
                    nav_tab("Part 4 · Subsets", "part4"),
                ],
                style={"height": f"{NAV_HEIGHT}px"},
            ),
            style={"position": "fixed", "bottom": "0", "left": "0", "right": "0",
                   "height": f"{NAV_HEIGHT}px", "background": NAVY,
                   "boxShadow": "0 -2px 12px rgba(11, 37, 69, 0.25)", "zIndex": "100"},
        ),
    ],
    style={"fontFamily": FONT, "background": PAGE_BG, "minHeight": "100vh",
           "margin": "0", "color": TEXT},
)


@app.callback(Output("tab-content", "children"), Input("part-tabs", "value"))
def render_tab(tab):
    if tab == "part2":
        return part2_view()
    if tab == "part3":
        return part3_view()
    return part4_view()


@app.callback(
    Output("frequency-table", "data"),
    Output("search-result-count", "children"),
    Input("sample-search", "value"),
)
def filter_samples(query):
    if not query or not query.strip():
        return FREQUENCIES.to_dict("records"), f"Showing all {len(FREQUENCIES):,} rows"
    matches = FREQUENCIES[
        FREQUENCIES["sample"].str.contains(query.strip(), case=False, regex=False)
    ]
    if matches.empty:
        return [], f"No samples matching “{query.strip()}”"
    n_samples = matches["sample"].nunique()
    return (matches.to_dict("records"),
            f"{len(matches):,} rows across {n_samples:,} "
            f"sample{'' if n_samples == 1 else 's'}")


if __name__ == "__main__":
    print(f"Dashboard running at http://localhost:{PORT}")
    app.run(host="0.0.0.0", port=PORT, debug=False)
