#!/usr/bin/env python3
"""Interactive dashboard for the Loblaw Bio cell-count analysis.

Start with `make dashboard` (or `python app.py`), then open port 8050.
Each part of the analysis is a tab in the bar along the bottom of the screen.
"""

import os

import dash
import pandas as pd
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


def load_frequencies():
    """Read Part 2 straight from the database, so the dashboard and the
    generated CSV are always the same numbers."""
    try:
        conn = analysis.connect()
    except FileNotFoundError:
        return pd.DataFrame(columns=analysis.FREQUENCY_COLUMNS), False
    try:
        frame = pd.DataFrame(
            analysis.cell_frequencies(conn), columns=analysis.FREQUENCY_COLUMNS
        )
    finally:
        conn.close()
    return frame, True


FREQUENCIES, DB_READY = load_frequencies()


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


def placeholder(title, subtitle, items):
    return html.Div(
        [
            section_title(title, subtitle),
            html.Div(
                [
                    html.Div("Not yet implemented", style={
                        "display": "inline-block", "background": "#e3ecfa", "color": PRIMARY,
                        "padding": "4px 12px", "borderRadius": "999px", "fontSize": "12px",
                        "fontWeight": "600", "marginBottom": "16px"}),
                    html.Ul(
                        [html.Li(item, style={"marginBottom": "8px"}) for item in items],
                        style={"color": MUTED, "fontSize": "14px", "lineHeight": "1.5",
                               "paddingLeft": "20px", "margin": "0"},
                    ),
                ],
                style={"background": CARD_BG, "border": f"1px solid {BORDER}",
                       "borderRadius": "10px", "padding": "28px"},
            ),
        ]
    )


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
        return placeholder(
            "Part 3 · Statistical Analysis",
            "Responders vs non-responders among melanoma patients on miraclib (PBMC only).",
            ["Boxplot of relative frequency per population, split by response",
             "Significance testing across the five populations",
             "Summary of which populations differ significantly"],
        )
    return placeholder(
        "Part 4 · Data Subset Analysis",
        "Melanoma PBMC samples at baseline from miraclib-treated patients.",
        ["Sample counts per project",
         "Responder / non-responder subject counts",
         "Male / female subject counts",
         "Average baseline B cell count for male melanoma responders"],
    )


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
