#!/usr/bin/env python3
"""Build the deterministic HIPPRA Tableau workbook from the certified base TWB.

The script reads the certified Tableau preparation CSV only to derive stable display
filters (top accounts/review reasons). It never changes the CSV, Parquet, DuckDB, or
prior workbook. The output is a new, versioned TWB.
"""

from __future__ import annotations

import copy
import csv
import hashlib
import json
import os
import uuid
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path


PROJECT_ROOT = Path(os.environ.get("NEXUS_PROJECT_ROOT", Path(__file__).resolve().parents[1])).expanduser().resolve()
HERE = Path(
    os.environ.get(
        "HIPPRA_TABLEAU_OUTPUT_DIR",
        PROJECT_ROOT / "14_tableau_workbook" / "hippra_tableau_workbook_20260810T215829Z",
    )
).expanduser().resolve()
BASE_TWB = HERE / "HIPPRA_Account_Intelligence_v1.twb"
OUTPUT_TWB = HERE / "HIPPRA_Account_Intelligence_v2.twb"
BUILD_MANIFEST = HERE / "HIPPRA_Account_Intelligence_v2_build.json"
SOURCE_CSV = Path(
    os.environ.get(
        "HIPPRA_TABLEAU_SOURCE_CSV",
        PROJECT_ROOT
        / "13_tableau_preparation"
        / "hippra_tableau_prep_20260810T213214Z"
        / "hippra_tableau_account_360.csv",
    )
).expanduser().resolve()

NAVY = "#093b58"
ORANGE = "#da5810"
TEAL = "#1da39d"
GRAY = "#d9d9d9"
PALE = "#f5f8fa"
WHITE = "#ffffff"
INK = "#23313a"

ET.register_namespace("user", "http://www.tableausoftware.com/xml/user")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_display_filters() -> tuple[list[str], list[str], list[str]]:
    account_relationships: Counter[str] = Counter()
    review_reasons: Counter[str] = Counter()
    with SOURCE_CSV.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            name = (row.get("account_name") or "").strip()
            if name:
                try:
                    account_relationships[name] += int(row.get("provider_relationship_count") or 0)
                except ValueError:
                    pass
            reason = (row.get("review_attention_reason") or "").strip()
            if reason:
                review_reasons[reason] += 1
    ranked_accounts = sorted(account_relationships, key=lambda n: (-account_relationships[n], n))
    ranked_reasons = sorted(review_reasons, key=lambda n: (-review_reasons[n], n))
    return ranked_accounts[:15], ranked_accounts[:40], ranked_reasons[:10]


def new_uuid() -> str:
    return "{" + str(uuid.uuid4()).upper() + "}"


def ref(ds_name: str, instance: str) -> str:
    return f"[{ds_name}].[{instance}]"


def field_name(name: str) -> str:
    return f"[{name}]"


def formatted_text(parent: ET.Element, text: str, **attrs: str) -> ET.Element:
    node = ET.SubElement(parent, "formatted-text")
    run = ET.SubElement(node, "run", attrs)
    run.text = text
    return node


def title_block(parent: ET.Element, title: str) -> None:
    options = ET.SubElement(parent, "layout-options")
    title_node = ET.SubElement(options, "title")
    formatted_text(title_node, title, fontname="Tableau Semibold", fontcolor=NAVY, fontsize="13")


def find_source_column(datasource: ET.Element, raw_name: str) -> ET.Element:
    target = field_name(raw_name)
    for column in datasource.findall("column"):
        if column.get("name") == target:
            return column
    raise KeyError(f"Datasource column not found: {raw_name}")


def add_calculation(
    datasource: ET.Element,
    name: str,
    caption: str,
    formula: str,
    datatype: str = "string",
    role: str = "dimension",
    type_: str = "nominal",
) -> ET.Element:
    internal = field_name(name)
    for column in datasource.findall("column"):
        if column.get("name") == internal:
            return column
    column = ET.Element(
        "column",
        {
            "caption": caption,
            "datatype": datatype,
            "name": internal,
            "role": role,
            "type": type_,
        },
    )
    ET.SubElement(column, "calculation", {"class": "tableau", "formula": formula})
    # Tableau requires every <column> to precede column instances, groups, folders,
    # extracts, layout, and downstream datasource metadata.
    children = list(datasource)
    insert_at = next(
        (
            i
            for i, child in enumerate(children)
            if child.tag
            in {
                "column-instance",
                "group",
                "mapped-images",
                "drill-paths",
                "folders-common",
                "folders-parameters",
                "actions",
                "calculated-members",
                "extract",
                "layout",
                "style",
                "semantic-values",
                "date-options",
                "default-date-format",
                "default-sorts",
                "field-sort-info",
                "datasource-dependencies",
                "explainability",
                "filter",
                "object-graph",
            }
        ),
        len(children),
    )
    datasource.insert(insert_at, column)
    return column


def add_aliases(datasource: ET.Element, raw_name: str, mappings: dict[str, str]) -> None:
    column = find_source_column(datasource, raw_name)
    aliases = column.find("aliases")
    if aliases is None:
        aliases = ET.SubElement(column, "aliases")
    existing = {alias.get("key") for alias in aliases.findall("alias")}
    for key, value in mappings.items():
        if key not in existing:
            ET.SubElement(aliases, "alias", {"key": f'"{key}"', "value": value})


def source_column_copy(datasource: ET.Element, raw_name: str) -> ET.Element:
    return copy.deepcopy(find_source_column(datasource, raw_name))


def add_instance(
    deps: ET.Element,
    raw_name: str,
    derivation: str,
    instance: str,
    type_: str,
) -> None:
    ET.SubElement(
        deps,
        "column-instance",
        {
            "column": field_name(raw_name),
            "derivation": derivation,
            "name": field_name(instance),
            "pivot": "key",
            "type": type_,
        },
    )


def sheet_shell(
    worksheets: ET.Element,
    datasource: ET.Element,
    ds_name: str,
    ds_caption: str,
    name: str,
    title: str,
    raw_columns: list[str],
    instances: list[tuple[str, str, str, str]],
    include_map: bool = False,
) -> tuple[ET.Element, ET.Element, ET.Element]:
    sheet = ET.SubElement(worksheets, "worksheet", {"name": name})
    title_block(sheet, title)
    table = ET.SubElement(sheet, "table")
    view = ET.SubElement(table, "view")
    sources = ET.SubElement(view, "datasources")
    ET.SubElement(sources, "datasource", {"caption": ds_caption, "name": ds_name})
    if include_map:
        mapsources = ET.SubElement(view, "mapsources")
        ET.SubElement(mapsources, "mapsource", {"name": "Tableau"})
    deps = ET.SubElement(view, "datasource-dependencies", {"datasource": ds_name})
    for raw_name in raw_columns:
        deps.append(source_column_copy(datasource, raw_name))
    for raw_name, derivation, instance, type_ in instances:
        add_instance(deps, raw_name, derivation, instance, type_)
    ET.SubElement(view, "aggregation", {"value": "true"})
    return sheet, table, view


def add_member_filter(view: ET.Element, ds_name: str, instance: str, values: list[str]) -> None:
    filt = ET.Element("filter", {"class": "categorical", "column": ref(ds_name, instance)})
    if len(values) == 1:
        ET.SubElement(
            filt,
            "groupfilter",
            {"function": "member", "level": field_name(instance), "member": json.dumps(values[0])},
        )
        aggregation = view.find("aggregation")
        view.insert(list(view).index(aggregation) if aggregation is not None else len(view), filt)
        return
    union = ET.SubElement(filt, "groupfilter", {"function": "union"})
    for value in values:
        ET.SubElement(
            union,
            "groupfilter",
            {"function": "member", "level": field_name(instance), "member": json.dumps(value)},
        )
    aggregation = view.find("aggregation")
    view.insert(list(view).index(aggregation) if aggregation is not None else len(view), filt)


def add_common_style(table: ET.Element, hide_rows: bool = False, hide_cols: bool = False) -> ET.Element:
    style = ET.SubElement(table, "style")
    worksheet_rule = ET.SubElement(style, "style-rule", {"element": "worksheet"})
    if hide_rows:
        ET.SubElement(worksheet_rule, "format", {"attr": "display-field-labels", "scope": "rows", "value": "false"})
    if hide_cols:
        ET.SubElement(worksheet_rule, "format", {"attr": "display-field-labels", "scope": "cols", "value": "false"})
    grid = ET.SubElement(style, "style-rule", {"element": "gridline"})
    ET.SubElement(grid, "format", {"attr": "line-visibility", "scope": "rows", "value": "off"})
    ET.SubElement(grid, "format", {"attr": "line-visibility", "scope": "cols", "value": "off"})
    divider = ET.SubElement(style, "style-rule", {"element": "table-div"})
    ET.SubElement(divider, "format", {"attr": "line-visibility", "scope": "rows", "value": "off"})
    ET.SubElement(divider, "format", {"attr": "line-visibility", "scope": "cols", "value": "off"})
    return style


def add_palette(style: ET.Element, ds_name: str, instance: str, colors: list[str], palette_type: str = "regular") -> None:
    rule = ET.SubElement(style, "style-rule", {"element": "mark"})
    encoding = ET.SubElement(
        rule,
        "encoding",
        {"attr": "color", "field": ref(ds_name, instance), "type": "palette"},
    )
    palette = ET.SubElement(
        encoding,
        "color-palette",
        {"custom": "true", "name": "HIPPRA", "type": palette_type},
    )
    for color in colors:
        node = ET.SubElement(palette, "color")
        node.text = color


def add_label_style(pane: ET.Element, font_size: str = "10", color: str = INK) -> None:
    style = ET.SubElement(pane, "style")
    rule = ET.SubElement(style, "style-rule", {"element": "mark"})
    ET.SubElement(rule, "format", {"attr": "mark-labels-show", "value": "true"})
    ET.SubElement(rule, "format", {"attr": "mark-labels-cull", "value": "false"})
    ET.SubElement(rule, "format", {"attr": "font-size", "value": font_size})


def add_tooltip(pane: ET.Element, runs: list[tuple[str, dict[str, str]]]) -> None:
    tooltip = ET.SubElement(pane, "customized-tooltip")
    text = ET.SubElement(tooltip, "formatted-text")
    for value, attrs in runs:
        run = ET.SubElement(text, "run", attrs)
        run.text = value


def build_kpi(
    worksheets: ET.Element,
    datasource: ET.Element,
    ds_name: str,
    ds_caption: str,
    name: str,
    title: str,
    filter_field: str | None = None,
    filter_value: str | None = None,
    measure_field: str = "commercial_account_id",
    measure_derivation: str = "CountD",
) -> None:
    instance = ("ctd" if measure_derivation == "CountD" else measure_derivation.lower()) + f":{measure_field}:qk"
    raw = [measure_field] + ([filter_field] if filter_field else [])
    instances = [(measure_field, measure_derivation, instance, "quantitative")]
    if filter_field:
        instances.append((filter_field, "None", f"none:{filter_field}:nk", "nominal"))
    sheet, table, view = sheet_shell(
        worksheets, datasource, ds_name, ds_caption, name, title, raw, instances
    )
    if filter_field and filter_value is not None:
        add_member_filter(view, ds_name, f"none:{filter_field}:nk", [filter_value])
    style = add_common_style(table, hide_rows=True, hide_cols=True)
    cell = ET.SubElement(style, "style-rule", {"element": "cell"})
    ET.SubElement(cell, "format", {"attr": "text-align", "value": "center"})
    ET.SubElement(cell, "format", {"attr": "font-family", "value": "Tableau Semibold"})
    ET.SubElement(cell, "format", {"attr": "font-size", "value": "28"})
    panes = ET.SubElement(table, "panes")
    pane = ET.SubElement(panes, "pane", {"selection-relaxation-option": "selection-relaxation-disallow"})
    pv = ET.SubElement(pane, "view")
    ET.SubElement(pv, "breakdown", {"value": "auto"})
    ET.SubElement(pane, "mark", {"class": "Text"})
    encodings = ET.SubElement(pane, "encodings")
    ET.SubElement(encodings, "text", {"column": ref(ds_name, instance)})
    add_tooltip(
        pane,
        [
            (title + "\n", {"fontname": "Tableau Semibold", "fontcolor": NAVY, "fontsize": "13"}),
            (f"<{ref(ds_name, instance)}>", {"fontname": "Tableau Bold", "fontcolor": ORANGE, "fontsize": "16"}),
        ],
    )
    add_label_style(pane, "28", NAVY)
    ET.SubElement(table, "rows")
    ET.SubElement(table, "cols")
    ET.SubElement(sheet, "simple-id", {"uuid": new_uuid()})


def build_bar_sheet(
    worksheets: ET.Element,
    datasource: ET.Element,
    ds_name: str,
    ds_caption: str,
    name: str,
    title: str,
    dimension: str,
    measure: str,
    measure_derivation: str,
    filter_values: list[str] | None = None,
    color_dimension: str | None = None,
) -> None:
    dim_instance = f"none:{dimension}:nk"
    prefix = "ctd" if measure_derivation == "CountD" else measure_derivation.lower()
    measure_instance = f"{prefix}:{measure}:qk"
    columns = [dimension, measure]
    instances = [
        (dimension, "None", dim_instance, "nominal"),
        (measure, measure_derivation, measure_instance, "quantitative"),
    ]
    if color_dimension and color_dimension not in columns:
        columns.append(color_dimension)
        instances.append((color_dimension, "None", f"none:{color_dimension}:nk", "nominal"))
    sheet, table, view = sheet_shell(
        worksheets, datasource, ds_name, ds_caption, name, title, columns, instances
    )
    if filter_values:
        add_member_filter(view, ds_name, dim_instance, filter_values)
    style = add_common_style(table, hide_rows=True, hide_cols=True)
    add_palette(
        style,
        ds_name,
        f"none:{color_dimension or dimension}:nk",
        [NAVY, TEAL, ORANGE, "#6d7f8b", "#9bb8c8", "#f2a36f"],
    )
    panes = ET.SubElement(table, "panes")
    pane = ET.SubElement(panes, "pane", {"selection-relaxation-option": "selection-relaxation-allow"})
    pv = ET.SubElement(pane, "view")
    ET.SubElement(pv, "breakdown", {"value": "auto"})
    ET.SubElement(pane, "mark", {"class": "Bar"})
    encodings = ET.SubElement(pane, "encodings")
    ET.SubElement(encodings, "color", {"column": ref(ds_name, f"none:{color_dimension or dimension}:nk")})
    ET.SubElement(encodings, "text", {"column": ref(ds_name, measure_instance)})
    if color_dimension:
        ET.SubElement(encodings, "lod", {"column": ref(ds_name, f"none:{color_dimension}:nk")})
    add_tooltip(
        pane,
        [
            (f"<{ref(ds_name, dim_instance)}>\n", {"fontname": "Tableau Semibold", "fontcolor": NAVY, "fontsize": "12"}),
            (f"<{ref(ds_name, measure_instance)}>", {"fontname": "Tableau Bold", "fontcolor": ORANGE}),
        ],
    )
    add_label_style(pane, "10", INK)
    rows = ET.SubElement(table, "rows")
    rows.text = ref(ds_name, dim_instance)
    cols = ET.SubElement(table, "cols")
    cols.text = ref(ds_name, measure_instance)
    ET.SubElement(sheet, "simple-id", {"uuid": new_uuid()})


def build_map(
    worksheets: ET.Element,
    datasource: ET.Element,
    ds_name: str,
    ds_caption: str,
) -> None:
    sheet, table, _ = sheet_shell(
        worksheets,
        datasource,
        ds_name,
        ds_caption,
        "Geographic Coverage",
        "Account Coverage by State",
        ["geocode_state", "geocode_country", "commercial_account_id"],
        [
            ("geocode_state", "None", "none:geocode_state:nk", "nominal"),
            ("geocode_country", "None", "none:geocode_country:nk", "nominal"),
            ("commercial_account_id", "CountD", "ctd:commercial_account_id:qk", "quantitative"),
        ],
        include_map=True,
    )
    style = add_common_style(table, hide_rows=True, hide_cols=True)
    map_rule = ET.SubElement(style, "style-rule", {"element": "map"})
    ET.SubElement(map_rule, "format", {"attr": "map-style", "value": "light"})
    ET.SubElement(map_rule, "format", {"attr": "washout", "value": "0.15"})
    mark_rule = ET.SubElement(style, "style-rule", {"element": "mark"})
    ET.SubElement(
        mark_rule,
        "encoding",
        {
            "attr": "color",
            "field": ref(ds_name, "ctd:commercial_account_id:qk"),
            "palette": "tableau-blue",
            "type": "interpolated",
        },
    )
    panes = ET.SubElement(table, "panes")
    pane = ET.SubElement(panes, "pane", {"selection-relaxation-option": "selection-relaxation-allow"})
    pv = ET.SubElement(pane, "view")
    ET.SubElement(pv, "breakdown", {"value": "auto"})
    ET.SubElement(pane, "mark", {"class": "Automatic"})
    encodings = ET.SubElement(pane, "encodings")
    ET.SubElement(encodings, "color", {"column": ref(ds_name, "ctd:commercial_account_id:qk")})
    ET.SubElement(encodings, "lod", {"column": ref(ds_name, "none:geocode_state:nk")})
    ET.SubElement(encodings, "lod", {"column": ref(ds_name, "none:geocode_country:nk")})
    add_tooltip(
        pane,
        [
            (f"<{ref(ds_name, 'none:geocode_state:nk')}>\n", {"fontname": "Tableau Semibold", "fontcolor": NAVY, "fontsize": "12"}),
            (f"<{ref(ds_name, 'ctd:commercial_account_id:qk')}> accounts", {"fontname": "Tableau Bold", "fontcolor": ORANGE}),
        ],
    )
    rows = ET.SubElement(table, "rows")
    rows.text = ref(ds_name, "Latitude (generated)")
    cols = ET.SubElement(table, "cols")
    cols.text = ref(ds_name, "Longitude (generated)")
    ET.SubElement(sheet, "simple-id", {"uuid": new_uuid()})


def dashboard_zone_style(zone: ET.Element, background: str = WHITE, margin: str = "6") -> None:
    style = ET.SubElement(zone, "zone-style")
    ET.SubElement(style, "format", {"attr": "border-color", "value": GRAY})
    ET.SubElement(style, "format", {"attr": "border-style", "value": "solid"})
    ET.SubElement(style, "format", {"attr": "border-width", "value": "1"})
    ET.SubElement(style, "format", {"attr": "margin", "value": margin})
    ET.SubElement(style, "format", {"attr": "padding", "value": "6"})
    ET.SubElement(style, "format", {"attr": "background-color", "value": background})


def add_sheet_zone(parent: ET.Element, id_: int, name: str, x: int, y: int, w: int, h: int) -> None:
    zone = ET.SubElement(
        parent,
        "zone",
        {"id": str(id_), "name": name, "x": str(x), "y": str(y), "w": str(w), "h": str(h)},
    )
    ET.SubElement(zone, "layout-cache", {"type-h": "scalable", "type-w": "scalable"})
    dashboard_zone_style(zone)


def add_text_zone(
    parent: ET.Element,
    id_: int,
    text: str,
    x: int,
    y: int,
    w: int,
    h: int,
    background: str = PALE,
    color: str = INK,
    size: str = "10",
) -> None:
    zone = ET.SubElement(
        parent,
        "zone",
        {"id": str(id_), "type-v2": "text", "x": str(x), "y": str(y), "w": str(w), "h": str(h)},
    )
    formatted_text(zone, text, fontname="Tableau Regular", fontcolor=color, fontsize=size)
    dashboard_zone_style(zone, background=background)


def add_dashboard(
    dashboards: ET.Element,
    ds_name: str,
    name: str,
    title: str,
    sheet_zones: list[tuple[str, int, int, int, int]],
    note: str,
) -> None:
    dashboard = ET.SubElement(dashboards, "dashboard", {"name": name})
    options = ET.SubElement(dashboard, "layout-options")
    title_node = ET.SubElement(options, "title")
    formatted_text(title_node, title, fontname="Tableau Semibold", fontcolor=WHITE, fontsize="18")
    style = ET.SubElement(dashboard, "style")
    rule = ET.SubElement(style, "style-rule", {"element": "dashboard"})
    ET.SubElement(rule, "format", {"attr": "background-color", "value": PALE})
    ET.SubElement(dashboard, "size", {"minheight": "900", "minwidth": "1440", "sizing-mode": "range"})
    sources = ET.SubElement(dashboard, "datasources")
    ET.SubElement(sources, "datasource", {"name": ds_name})
    zones = ET.SubElement(dashboard, "zones")
    canvas = ET.SubElement(
        zones,
        "zone",
        {"id": "1", "type-v2": "layout-basic", "x": "0", "y": "0", "w": "100000", "h": "100000"},
    )
    header = ET.SubElement(
        canvas,
        "zone",
        {"id": "2", "type-v2": "text", "x": "0", "y": "0", "w": "100000", "h": "7500"},
    )
    formatted_text(header, title, fontname="Tableau Semibold", fontcolor=WHITE, fontsize="22")
    dashboard_zone_style(header, background=NAVY, margin="0")
    zone_id = 10
    for sheet_name, x, y, w, h in sheet_zones:
        add_sheet_zone(canvas, zone_id, sheet_name, x, y, w, h)
        zone_id += 1
    add_text_zone(canvas, 90, note, 1500, 89500, 97000, 9000, background="#edf3f6", color=INK, size="10")
    ET.SubElement(dashboard, "simple-id", {"uuid": new_uuid()})


def worksheet_window(parent: ET.Element, name: str, hidden: bool = True) -> None:
    attrs = {"class": "worksheet", "name": name}
    if hidden:
        attrs["hidden"] = "true"
    window = ET.SubElement(parent, "window", attrs)
    cards = ET.SubElement(window, "cards")
    left = ET.SubElement(cards, "edge", {"name": "left"})
    strip = ET.SubElement(left, "strip", {"size": "180"})
    ET.SubElement(strip, "card", {"type": "pages"})
    ET.SubElement(strip, "card", {"type": "filters"})
    ET.SubElement(strip, "card", {"type": "marks"})
    top = ET.SubElement(cards, "edge", {"name": "top"})
    for card_type in ("columns", "rows", "title"):
        strip = ET.SubElement(top, "strip", {"size": "2147483647"})
        ET.SubElement(strip, "card", {"type": card_type})
    viewpoint = ET.SubElement(window, "viewpoint")
    ET.SubElement(viewpoint, "zoom", {"type": "entire-view"})
    ET.SubElement(window, "simple-id", {"uuid": new_uuid()})


def dashboard_window(parent: ET.Element, name: str, sheets: list[str], maximized: bool = False) -> None:
    attrs = {"class": "dashboard", "name": name}
    if maximized:
        attrs["maximized"] = "true"
    window = ET.SubElement(parent, "window", attrs)
    viewpoints = ET.SubElement(window, "viewpoints")
    for sheet in sheets:
        viewpoint = ET.SubElement(viewpoints, "viewpoint", {"name": sheet})
        ET.SubElement(viewpoint, "zoom", {"type": "entire-view"})
    ET.SubElement(window, "active", {"id": "-1"})
    ET.SubElement(window, "simple-id", {"uuid": new_uuid()})


def main() -> None:
    if OUTPUT_TWB.exists() or BUILD_MANIFEST.exists():
        raise SystemExit("Refusing to overwrite an existing v2 workbook or build manifest")

    protected_before = {str(p): sha256(p) for p in (BASE_TWB, SOURCE_CSV)}
    top15, top40, review10 = stable_display_filters()

    tree = ET.parse(BASE_TWB)
    root = tree.getroot()
    datasource = root.find("./datasources/datasource")
    if datasource is None:
        raise RuntimeError("Base workbook datasource not found")
    ds_name = datasource.get("name") or ""
    ds_caption = datasource.get("caption") or "HIPPRA Account 360"

    add_aliases(
        datasource,
        "account_type",
        {"PHYSICIAN_GROUP": "Physician Groups", "HOSPITAL": "Hospitals", "HEALTH_SYSTEM": "Health Systems"},
    )
    add_calculation(
        datasource,
        "Calculation_EnrichmentStatus",
        "Enrichment Coverage",
        'IF [has_targeted_enrichment] THEN "Enriched" ELSE "Not Enriched" END',
    )
    add_calculation(
        datasource,
        "Calculation_ReviewStatus",
        "Evidence Review Status",
        'IF [review_attention_required] THEN "Review Required" ELSE "No Review Flag" END',
    )

    worksheets = root.find("worksheets")
    if worksheets is None:
        raise RuntimeError("Base workbook worksheets container not found")
    for child in list(worksheets):
        worksheets.remove(child)

    build_kpi(worksheets, datasource, ds_name, ds_caption, "KPI Accounts", "Portfolio Accounts")
    build_kpi(
        worksheets,
        datasource,
        ds_name,
        ds_caption,
        "KPI Physician Groups",
        "Physician Groups",
        "account_type",
        "PHYSICIAN_GROUP",
    )
    build_kpi(
        worksheets, datasource, ds_name, ds_caption, "KPI Hospitals", "Hospitals", "account_type", "HOSPITAL"
    )
    build_kpi(
        worksheets,
        datasource,
        ds_name,
        ds_caption,
        "KPI Health Systems",
        "Health Systems",
        "account_type",
        "HEALTH_SYSTEM",
    )
    build_kpi(
        worksheets,
        datasource,
        ds_name,
        ds_caption,
        "KPI Provider Relationships",
        "Provider Relationships",
        measure_field="provider_relationship_count",
        measure_derivation="Sum",
    )
    build_kpi(
        worksheets,
        datasource,
        ds_name,
        ds_caption,
        "KPI Enriched",
        "Enriched Accounts",
        "Calculation_EnrichmentStatus",
        "Enriched",
    )
    build_kpi(
        worksheets,
        datasource,
        ds_name,
        ds_caption,
        "KPI Review",
        "Review-Attention Accounts",
        "Calculation_ReviewStatus",
        "Review Required",
    )

    build_bar_sheet(
        worksheets,
        datasource,
        ds_name,
        ds_caption,
        "Account Mix",
        "Account Portfolio Mix",
        "account_type",
        "commercial_account_id",
        "CountD",
    )
    build_bar_sheet(
        worksheets,
        datasource,
        ds_name,
        ds_caption,
        "Top Accounts",
        "Top Accounts by Provider Relationships",
        "account_name",
        "provider_relationship_count",
        "Sum",
        filter_values=top15,
        color_dimension="account_type",
    )
    build_bar_sheet(
        worksheets,
        datasource,
        ds_name,
        ds_caption,
        "Enrichment Coverage",
        "Targeted Enrichment Coverage",
        "Calculation_EnrichmentStatus",
        "commercial_account_id",
        "CountD",
    )
    build_map(worksheets, datasource, ds_name, ds_caption)
    build_bar_sheet(
        worksheets,
        datasource,
        ds_name,
        ds_caption,
        "Network Structure",
        "Provider Relationships by Account Type",
        "account_type",
        "provider_relationship_count",
        "Sum",
    )
    build_bar_sheet(
        worksheets,
        datasource,
        ds_name,
        ds_caption,
        "Review Queue",
        "Evidence Review Queue",
        "review_attention_reason",
        "commercial_account_id",
        "CountD",
        filter_values=review10,
    )
    build_bar_sheet(
        worksheets,
        datasource,
        ds_name,
        ds_caption,
        "Account Explorer",
        "Account Explorer — Top 40 by Provider Relationships",
        "account_name",
        "provider_relationship_count",
        "Sum",
        filter_values=top40,
        color_dimension="account_type",
    )

    dashboards = root.find("dashboards")
    if dashboards is None:
        dashboards = ET.Element("dashboards")
        root.insert(list(root).index(worksheets) + 1, dashboards)
    else:
        for child in list(dashboards):
            dashboards.remove(child)

    executive_sheets = [
        ("KPI Accounts", 1500, 8500, 18800, 13500),
        ("KPI Physician Groups", 20800, 8500, 18800, 13500),
        ("KPI Hospitals", 40100, 8500, 18800, 13500),
        ("KPI Health Systems", 59400, 8500, 18800, 13500),
        ("KPI Provider Relationships", 78700, 8500, 19800, 13500),
        ("Account Mix", 1500, 23000, 30000, 64000),
        ("Top Accounts", 32500, 23000, 43500, 64000),
        ("Enrichment Coverage", 77000, 23000, 21500, 64000),
    ]
    add_dashboard(
        dashboards,
        ds_name,
        "Executive Account Landscape",
        "HIPPRA Account Intelligence | Executive Landscape",
        executive_sheets,
        "Descriptive account coverage only. This dashboard does not represent TAM, SAM, SOM, revenue, pricing, customer status, contract value, or sales priority. Review flags identify evidence gaps—not commercial rank.",
    )

    network_sheets = [
        ("Geographic Coverage", 1500, 8500, 51500, 79000),
        ("Network Structure", 54000, 8500, 44500, 34500),
        ("Top Accounts", 54000, 44000, 44500, 43500),
    ]
    add_dashboard(
        dashboards,
        ds_name,
        "Network and Geography",
        "HIPPRA Account Intelligence | Network & Geography",
        network_sheets,
        "Geographic marks use only approved state-level geocodes. Foreign, military, nonstandard, missing, or unresolved postal identifiers are not coerced into domestic ZIP codes. Provider relationships are descriptive links at the certified account grain.",
    )

    quality_sheets = [
        ("KPI Enriched", 1500, 8500, 23000, 14000),
        ("KPI Review", 25500, 8500, 23000, 14000),
        ("Enrichment Coverage", 49500, 8500, 23500, 14000),
        ("KPI Accounts", 74000, 8500, 24500, 14000),
        ("Review Queue", 1500, 23500, 41000, 64000),
        ("Account Explorer", 43500, 23500, 55000, 64000),
    ]
    add_dashboard(
        dashboards,
        ds_name,
        "Data Quality and Account Explorer",
        "HIPPRA Account Intelligence | Evidence Quality & Explorer",
        quality_sheets,
        "Known limitations remain explicit: targeted clinic enrichment is partial; MCO-to-clinic/network relationships are not documented; AHRQ linkage reflects CY2023; unresolved candidates remain in the review queue. Missing values remain null and are never interpreted as zero.",
    )

    windows = root.find("windows")
    if windows is None:
        windows = ET.SubElement(root, "windows", {"source-height": "30"})
    else:
        for child in list(windows):
            windows.remove(child)
        windows.set("source-height", "30")

    dashboard_window(windows, "Executive Account Landscape", [s[0] for s in executive_sheets], maximized=True)
    dashboard_window(windows, "Network and Geography", [s[0] for s in network_sheets])
    dashboard_window(windows, "Data Quality and Account Explorer", [s[0] for s in quality_sheets])
    for sheet in worksheets.findall("worksheet"):
        worksheet_window(windows, sheet.get("name") or "", hidden=True)

    ET.indent(tree, space="  ")
    tree.write(OUTPUT_TWB, encoding="utf-8", xml_declaration=True)

    protected_after = {str(p): sha256(p) for p in (BASE_TWB, SOURCE_CSV)}
    if protected_before != protected_after:
        OUTPUT_TWB.unlink(missing_ok=True)
        raise RuntimeError("Protected input checksum changed during workbook build")

    manifest = {
        "status": "BUILT_PENDING_TABLEAU_RENDER_QA",
        "base_workbook": str(BASE_TWB),
        "output_workbook": str(OUTPUT_TWB),
        "source_csv": str(SOURCE_CSV),
        "protected_inputs_unchanged": True,
        "protected_sha256": protected_after,
        "top_account_filter_count": len(top15),
        "explorer_filter_count": len(top40),
        "review_reason_filter_count": len(review10),
        "worksheet_count": len(worksheets.findall("worksheet")),
        "dashboard_count": len(dashboards.findall("dashboard")),
        "dashboard_names": [d.get("name") for d in dashboards.findall("dashboard")],
        "commercial_scope_guardrails": [
            "NO_TAM_SAM_SOM",
            "NO_REVENUE_OR_PRICING",
            "NO_CUSTOMER_OR_CONTRACT_CLAIMS",
            "NO_SALES_PRIORITY_INFERENCE",
            "MISSING_IS_NOT_ZERO",
        ],
    }
    BUILD_MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
