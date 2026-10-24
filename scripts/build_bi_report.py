"""Write the Power BI report of `bi/FloodPolicyKit.pbip` as PBIR files.

The report is a story in six pages - the headline, where, downstream of
someone else, who, declared vs exposed, and a drillthrough page for one region
- and PBIR is the documented, schema-validated text format Power BI Desktop
reads (one `visual.json` per visual). The layout is generated rather than
typed because sixty-odd files sharing one grid, one palette and one way of
naming a field are only consistent if one function writes them all.

Run it once to (re)build the layout; then `scripts/validate_bi_report.py`
checks every file against Microsoft's schemas. Once the report has been edited
and saved in Power BI Desktop, the saved files are the source: running this
again overwrites `bi/FloodPolicyKit.Report/definition/` and the theme.

Every field is named here as (table, column or measure) and
`tests/test_export_bi.py` checks each one against the TMDL model, so a rename
on either side fails a test instead of opening as a grey box.
"""

from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "bi" / "FloodPolicyKit.Report"
DEFINITION = REPORT / "definition"
THEME_NAME = "FloodPolicyKit.json"
THEME_PATH = REPORT / "StaticResources" / "RegisteredResources" / THEME_NAME

SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition"
#: The newest versions Microsoft publishes at the time of writing. Desktop
#: 2.159 (October 2026) saves visual.json as 2.14.0, which is not published, so
#: visuals are written at 2.13.0: Desktop reads older versions and upgrades them.
VERSIONS = {"report": "3.3.0", "page": "2.1.0", "visualContainer": "2.13.0",
            "pagesMetadata": "1.1.0", "versionMetadata": "1.0.0"}

W, H = 1280, 720          # 16:9 canvas
M, G = 24, 16             # outer margin, gutter
CW = W - 2 * M            # content width

INK, MUTED, LINE = "#1B1F27", "#5D6675", "#E1E4EA"
PAGE_BG, CARD_BG = "#F6F7F9", "#FFFFFF"
#: YlOrBr, the ramp the Streamlit map uses (src/svgmap.py::PALETTE).
RAMP = ("#FFF7BC", "#FEE391", "#FE9929", "#EC7014", "#CC4C02", "#8C2D04")
EXPOSURE = RAMP[4]
ACCENT = "#1F6FEB"        # the one accent: the cross-border argument
NEUTRAL = "#9AA0A6"

CREDIT = "© EuroGeographics for the administrative boundaries"
SOURCE = ("Sources: JRC river-flood hazard maps (undefended), GHSL population, "
          "GISCO NUTS 2024, EEA declared risk areas, WFD river basin districts. "
          "Right-click any region, then Drill through > Region detail.")


# --- field references ---------------------------------------------------------

def col(table: str, name: str) -> dict:
    return {"Column": {"Expression": {"SourceRef": {"Entity": table}}, "Property": name}}


def measure(name: str) -> dict:
    """Every measure lives on the Exposure table."""
    return {"Measure": {"Expression": {"SourceRef": {"Entity": "Exposure"}}, "Property": name}}


def level(name: str) -> dict:
    """A level of the Regions[Geography] hierarchy (Country, Region)."""
    return {"HierarchyLevel": {
        "Expression": {"Hierarchy": {"Expression": {"SourceRef": {"Entity": "Regions"}},
                                     "Hierarchy": "Geography"}},
        "Level": name}}


def ref(field: dict) -> str:
    """The queryRef Power BI itself writes: Table.Field or Table.Hierarchy.Level."""
    if "HierarchyLevel" in field:
        return f"Regions.Geography.{field['HierarchyLevel']['Level']}"
    kind = "Column" if "Column" in field else "Measure"
    return f"{field[kind]['Expression']['SourceRef']['Entity']}.{field[kind]['Property']}"


def proj(field: dict, display: str | None = None, active: bool | None = None) -> dict:
    out = {"field": field, "queryRef": ref(field)}
    if display:
        out["displayName"] = display
    if active is not None:
        out["active"] = active
    return out


# --- formatting values --------------------------------------------------------

def lit(value) -> dict:
    """A literal in Power BI's query syntax: 'text', 12D, 3L, true."""
    if isinstance(value, bool):
        text = "true" if value else "false"
    elif isinstance(value, int):
        text = f"{value}L"
    elif isinstance(value, float):
        text = f"{int(value)}D" if value.is_integer() else f"{value}D"
    else:
        text = "'" + str(value).replace("'", "''") + "'"
    return {"expr": {"Literal": {"Value": text}}}


def color(hex_: str) -> dict:
    return {"solid": {"color": lit(hex_)}}


def obj(**properties) -> list:
    """One formatting object with no selector: [{"properties": {...}}]."""
    return [{"properties": {k: v if isinstance(v, dict) else lit(v) for k, v in properties.items()}}]


def container(title: str | None = None, subtitle: str | None = None, frame: bool = True) -> dict:
    """Title, subtitle and the white card every data visual sits on."""
    out: dict = {}
    if title:
        out["title"] = obj(show=True, text=title, fontColor=color(INK), fontSize=12.0, bold=True)
    else:
        out["title"] = obj(show=False)
    if subtitle:
        out["subTitle"] = obj(show=True, text=subtitle, fontColor=color(MUTED), fontSize=9.0)
    if frame:
        out["background"] = obj(show=True, color=color(CARD_BG), transparency=0.0)
        out["border"] = obj(show=True, color=color(LINE), radius=8.0, width=1.0)
        out["padding"] = obj(top=8.0, bottom=8.0, left=12.0, right=12.0)
    else:
        out["background"] = obj(show=False)
        out["border"] = obj(show=False)
    return out


def gradient(field: dict, low: str = RAMP[1], high: str = RAMP[5]) -> dict:
    """Bar or cell colour on a sequential ramp, driven by `field`."""
    return {"solid": {"color": {"expr": {"FillRule": {
        "Input": field,
        "FillRule": {"linearGradient2": {
            "min": {"color": {"Literal": {"Value": f"'{low}'"}}},
            "max": {"color": {"Literal": {"Value": f"'{high}'"}}},
            "nullColoringStrategy": {"strategy": {"Literal": {"Value": "'asZero'"}}},
        }},
    }}}}}


def sort_desc(field: dict) -> dict:
    return {"sort": [{"field": field, "direction": "Descending"}], "isDefaultSort": False}


# --- visuals ------------------------------------------------------------------

def visual(name: str, box: tuple, kind: str, *, roles: dict | None = None, sort: dict | None = None,
           objects: dict | None = None, frame: dict | None = None, z: int = 0,
           sync: str | None = None, how: str | None = None) -> dict:
    x, y, w, h = box
    body: dict = {"visualType": kind}
    if roles:
        body["query"] = {"queryState": {role: {"projections": p} for role, p in roles.items()}}
        if sort:
            body["query"]["sortDefinition"] = sort
    if objects:
        body["objects"] = objects
    body["visualContainerObjects"] = frame if frame is not None else container()
    if sync:
        body["syncGroup"] = {"groupName": sync, "fieldChanges": True, "filterChanges": True}
    body["drillFilterOtherVisuals"] = True
    out = {"$schema": f"{SCHEMA}/visualContainer/{VERSIONS['visualContainer']}/schema.json",
           "name": name,
           "position": {"x": x, "y": y, "z": z, "width": w, "height": h, "tabOrder": z},
           "visual": body}
    if how:
        out["howCreated"] = how
    return out


def text(name: str, box: tuple, paragraphs: list, frame: dict | None = None, z: int = 0) -> dict:
    """A text box. `paragraphs` is a list of (text, size_pt, colour, bold) runs, one per paragraph."""
    paras = [{"textRuns": [{"value": t, "textStyle": {
        "fontSize": f"{size}pt", "color": colour, "fontWeight": "bold" if bold else "normal",
        "fontFamily": "Segoe UI"}}]} for t, size, colour, bold in paragraphs]
    return visual(name, box, "textbox", objects={"general": [{"properties": {"paragraphs": paras}}]},
                  frame=frame if frame is not None else container(frame=False), z=z)


def header(page: str, title: str, subtitle: str) -> list:
    return [
        text(f"{page}_title", (M, 14, CW, 44), [(title, 20, INK, True)]),
        text(f"{page}_subtitle", (M, 56, CW, 36), [(subtitle, 11, MUTED, False)]),
    ]


def footer(page: str, credit: bool = False) -> list:
    out = [text(f"{page}_source", (M, 690, CW, 24), [(SOURCE, 8, MUTED, False)])]
    if credit:
        out.append(text(f"{page}_credit", (M + 616, 660, CW - 616, 26), [(CREDIT, 9, MUTED, False)]))
    return out


def card(name: str, box: tuple, field: dict, label: str, *, units: int = 0, decimals: int | None = None,
         value_size: float = 26.0, value_colour: str = INK) -> dict:
    labels = {"color": color(value_colour), "fontSize": value_size, "labelDisplayUnits": float(units)}
    if decimals is not None:
        labels["labelPrecision"] = decimals
    return visual(name, box, "card", roles={"Values": [proj(field, label)]},
                  objects={"labels": obj(**labels),
                           "categoryLabels": obj(show=True, color=color(MUTED), fontSize=10.0)})


def rp_slicer(name: str, box: tuple) -> dict:
    """Return period as tiles, one at a time, synced on every page that has one."""
    return visual(name, box, "slicer", roles={"Values": [proj(col("Exposure", "return_period"), active=True)]},
                  objects={"data": obj(mode="HorizontalList"),
                           "selection": obj(singleSelect=True, strictSingleSelect=False),
                           "header": obj(show=True, text="Return period - 1 in ... years (none = 100)",
                                         fontColor=color(MUTED), textSize=10.0),
                           "items": obj(fontColor=color(INK), textSize=11.0, background=color(CARD_BG))},
                  frame=container(), sync="ReturnPeriod")


def bars(name: str, box: tuple, kind: str, category: list, value: dict, title: str, subtitle: str,
         *, fill: dict, units: int = 1000000, tooltips: list | None = None, sort: bool = True) -> dict:
    roles = {"Category": category, "Y": [proj(value)]}
    if tooltips:
        roles["Tooltips"] = [proj(t) for t in tooltips]
    return visual(name, box, kind, roles=roles, sort=sort_desc(value) if sort else None,
                  objects={
                      # A rule-driven colour applies per data point, hence the wildcard selector.
                      "dataPoint": [{"properties": {"fill": fill},
                                     "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}]}}]
                      if "FillRule" in fill["solid"]["color"].get("expr", {}) else obj(fill=fill),
                      "labels": obj(show=True, color=color(INK), fontSize=9.0,
                                    labelDisplayUnits=float(units), labelPrecision=1),
                      "categoryAxis": obj(show=True, fontSize=9.0, labelColor=color(INK),
                                          showAxisTitle=False, axisType="Categorical"),
                      "valueAxis": obj(show=False, gridlineShow=False),
                  },
                  frame=container(title, subtitle))


def table(name: str, box: tuple, columns: list, title: str, subtitle: str, sort_by: dict,
          shade: dict | None = None) -> dict:
    objects = {"columnHeaders": obj(fontColor=color(INK), bold=True, fontSize=9.0,
                                    backColor=color(PAGE_BG)),
               "values": obj(fontSize=9.0, fontColorPrimary=color(INK), backColorPrimary=color(CARD_BG),
                             backColorSecondary=color(PAGE_BG)),
               "grid": obj(gridHorizontal=False, gridVertical=False, rowPadding=3.0)}
    if shade:
        objects["values"].append({"properties": {"backColor": gradient(shade, RAMP[0], RAMP[3])},
                                  "selector": {"metadata": ref(shade)}})
    return visual(name, box, "tableEx", roles={"Values": columns}, sort=sort_desc(sort_by),
                  objects=objects, frame=container(title, subtitle))


def matrix(name: str, box: tuple, rows: list, values: list, title: str, subtitle: str,
           sort_by: dict, shade: dict | None = None) -> dict:
    """A matrix whose rows are a hierarchy, with the expand/collapse buttons shown.

    The plainest drill-down Power BI has: a +/- beside every country or basin,
    always visible, where a bar chart's drill arrows only appear on hover and
    were missed. Stepped layout keeps the regions indented under their parent.
    """
    objects = {"rowHeaders": obj(showExpandCollapseButtons=True, fontSize=9.0, fontColor=color(INK),
                                 expandCollapseButtonsColor=color(EXPOSURE), stepped=True),
               "columnHeaders": obj(fontColor=color(INK), bold=True, fontSize=9.0,
                                    backColor=color(PAGE_BG)),
               "values": obj(fontSize=9.0, fontColorPrimary=color(INK), backColorPrimary=color(CARD_BG),
                             backColorSecondary=color(PAGE_BG)),
               "grid": obj(gridHorizontal=False, gridVertical=False, rowPadding=3.0)}
    if shade:
        objects["values"].append({"properties": {"backColor": gradient(shade, RAMP[0], RAMP[3])},
                                  "selector": {"metadata": ref(shade)}})
    return visual(name, box, "pivotTable", roles={"Rows": rows, "Values": values},
                  sort=sort_desc(sort_by), objects=objects, frame=container(title, subtitle))


def scatter(name: str, box: tuple, x: tuple, y: tuple, title: str, subtitle: str, colour: str) -> dict:
    return visual(name, box, "scatterChart",
                  roles={"Category": [proj(col("Regions", "region"))],
                         "X": [proj(measure(x[0]), x[1])],
                         "Y": [proj(measure(y[0]), y[1])],
                         "Size": [proj(measure("Exposed population"), "People exposed")]},
                  objects={"dataPoint": obj(defaultColor=color(colour)),
                           "bubbles": obj(bubbleSize=-10.0),
                           "categoryAxis": obj(show=True, showAxisTitle=True, fontSize=9.0,
                                               gridlineShow=False),
                           "valueAxis": obj(show=True, showAxisTitle=True, fontSize=9.0,
                                            gridlineShow=True, gridlineColor=color(LINE))},
                  frame=container(title, subtitle))


# --- pages --------------------------------------------------------------------

def eu27_filter(page: str) -> dict:
    """The brief quotes the EU-27: a page filter, visible and changeable in the Filters pane."""
    return {"filters": [{
        "name": f"{page}_eu27",
        "field": col("Regions", "is_eu27"),
        "type": "Categorical",
        "filter": {"Version": 2,
                   "From": [{"Name": "r", "Entity": "Regions", "Type": 0}],
                   "Where": [{"Condition": {"In": {
                       "Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "r"}},
                                                   "Property": "is_eu27"}}],
                       "Values": [[{"Literal": {"Value": "true"}}]]}}}]},
        "howCreated": "User",
    }]}


def page_json(name: str, display: str, **extra) -> dict:
    return {"$schema": f"{SCHEMA}/page/{VERSIONS['page']}/schema.json",
            "name": name, "displayName": display, "displayOption": "FitToPage",
            "height": H, "width": W, **extra}


def headline() -> tuple[dict, list]:
    p = "headline"
    cw = (CW - 3 * G) // 4
    visuals = header(p, "25.7 million people in the EU-27 live where a 1-in-100-year river flood reaches",
                     "What to look at: the four figures, then how the footprint grows from the 1-in-10 to "
                     "the 1-in-500 flood. Pick a return period above; none picked means 1-in-100.")
    visuals += [
        rp_slicer(f"{p}_rp", (M, 100, 824, 64)),
        card(f"{p}_rp_label", (M + 840, 100, CW - 840, 64), measure("Return period label"),
             "Figures shown for", value_size=14.0),
        card(f"{p}_exposed", (M, 180, cw, 112), measure("Exposed population"), "People exposed",
             units=1000000, decimals=1, value_colour=EXPOSURE),
        card(f"{p}_share", (M + (cw + G), 180, cw, 112), measure("Share exposed"),
             "Share of residents exposed"),
        card(f"{p}_shared", (M + 2 * (cw + G), 180, cw, 112), measure("Share in shared basins"),
             "Of them, in a basin shared with another country", value_colour=ACCENT),
        card(f"{p}_eae", (M + 3 * (cw + G), 180, cw, 112), measure("Expected annual exposure"),
             "Expected annual exposure (people a year, lower bound)", units=1000000, decimals=2),
        bars(f"{p}_by_rp", (M, 308, 808, 374), "clusteredColumnChart",
             [proj(col("Exposure", "return_period"), "Return period (1 in ... years)")],
             measure("Exposed population"),
             "People in the flood footprint, by return period",
             "Each footprint contains the smaller ones: read the bars one at a time, never add them up",
             fill=color(EXPOSURE), sort=False),
        text(f"{p}_undefended", (M + 824, 308, CW - 824, 374), [
            ("These are undefended figures", 13, INK, True),
            ("The JRC hazard maps model no dykes, walls or retention: they show where a river "
             "flood would go, not where defences let it go today.", 10, INK, False),
            ("The JRC's own headline, about 160,000 people a year, is defended and weighted by "
             "probability. It answers a different question; it does not contradict this one.",
             10, INK, False),
            ("Expected annual exposure weights the nine return periods by their probability over "
             "the sampled band, 1-in-10 to 1-in-500. A lower bound, never an expected damage.",
             10, INK, False),
            ("EU-27 only: a page filter. Clear it in the Filters pane to see all 37 countries.",
             10, MUTED, False),
        ], frame=container()),
    ]
    visuals += footer(p)
    interactions = [{"source": f"{p}_rp", "target": f"{p}_by_rp", "type": "NoFilter"}]
    return page_json(p, "1. Headline", filterConfig=eu27_filter(p), visualInteractions=interactions), visuals


def where() -> tuple[dict, list]:
    p = "where"
    visuals = header(p, "Four countries hold three in five of the EU's exposed - the highest shares are elsewhere",
                     "What to look at: bars rank countries by people exposed and are coloured by the share "
                     "exposed. Drill down (arrow icons on the chart) to open a country into its regions; "
                     "the table sorts on any column.")
    visuals += [
        rp_slicer(f"{p}_rp", (M, 100, 600, 64)),
        bars(f"{p}_by_country", (M, 176, 600, 506), "clusteredBarChart",
             [proj(level("Country"), active=True), proj(level("Region"), active=False)],
             measure("Exposed population"),
             "People exposed, by country - drill down to regions",
             "Bar length: people. Colour: share of residents, light to dark.",
             fill=gradient(measure("Share exposed")),
             tooltips=[measure("Share exposed"), measure("Population"), measure("Regions measured")]),
        matrix(f"{p}_regions", (M + 616, 100, CW - 616, 380),
               [proj(level("Country"), "Country"), proj(level("Region"), "Region")],
               [proj(measure("Exposed population"), "People exposed"),
                proj(measure("Share exposed"), "Share exposed"),
                proj(measure("Population"), "Residents")],
               "Countries - click + to open a country into its regions",
               "Click a column header to sort; right-click a region > Drill through for its detail page",
               sort_by=measure("Exposed population"), shade=measure("Share exposed")),
        text(f"{p}_map_note", (M + 616, 492, CW - 616, 160), [
            ("Map to add by hand: Shape map", 11, INK, True),
            ("Insert a Shape map here. Location: Regions > nuts_id. Colour saturation: Share exposed. "
             "Format > Map settings > Custom map > bi/data/regions.topojson. Then delete this note. "
             "Not generated because the Shape map stores the TopoJSON inside the report, and the "
             "boundaries are not committed (GISCO terms). See docs/power_bi.md.", 9, MUTED, False),
        ], frame=container()),
    ]
    visuals += footer(p, credit=True)
    return page_json(p, "2. Where", filterConfig=eu27_filter(p)), visuals


def downstream() -> tuple[dict, list]:
    p = "downstream"
    cw = (CW - 416 - 2 * G) // 3
    visuals = header(p, "Nearly two in three of the EU's exposed live in a river basin shared with another country",
                     "What to look at: which basins carry them. Drill a basin into its regions; the table "
                     "names the partner countries. A floor: Switzerland, Serbia, Ukraine and Belarus do not "
                     "report basins under EU law.")
    x0 = M + 416
    visuals += [
        rp_slicer(f"{p}_rp", (M, 100, 400, 88)),
        card(f"{p}_exposed", (x0, 100, cw, 88), measure("Exposed in shared basins"),
             "People exposed in a shared basin", units=1000000, decimals=1, value_colour=ACCENT),
        card(f"{p}_share", (x0 + cw + G, 100, cw, 88), measure("Share in shared basins"),
             "Share of all the exposed", value_colour=ACCENT),
        card(f"{p}_regions", (x0 + 2 * (cw + G), 100, cw, 88), measure("Regions in shared basins"),
             "Regions with area in a shared basin"),
        bars(f"{p}_by_basin", (M, 204, 600, 478), "clusteredBarChart",
             [proj(col("Regions", "main_shared_basin"), "Basin", active=True),
              proj(col("Regions", "region"), "Region", active=False)],
             measure("Exposed in shared basins"),
             "People exposed in a cross-border basin - drill down to regions",
             "By the shared basin that covers most of each region",
             fill=color(ACCENT), tooltips=[measure("Share exposed")]),
        matrix(f"{p}_partners", (M + 616, 204, CW - 616, 478),
               [proj(col("Regions", "main_shared_basin"), "Basin"), proj(col("Regions", "region"), "Region")],
               [proj(measure("Exposed in shared basins"), "People exposed"),
                proj(measure("Partner countries"), "Shares its rivers with")],
               "Basins - click + to open a basin into its regions",
               "Partner countries are ISO codes, shown once a region is open",
               sort_by=measure("Exposed in shared basins")),
    ]
    visuals += footer(p)
    return page_json(p, "3. Downstream of someone else", filterConfig=eu27_filter(p)), visuals


def who() -> tuple[dict, list]:
    p = "who"
    half = (CW - G) // 2
    visuals = header(p, "Older and poorer regions are not more exposed - the link is weak, and if anything the other way",
                     "What to look at: the cloud has no upward slope. Each dot is a region, sized by the "
                     "people exposed; hover for its name, right-click to drill through to it.")
    visuals += [
        scatter(f"{p}_age", (M, 100, half, 512), ("Share over 65", "Residents aged 65+"),
                ("Share exposed", "Share of residents exposed"),
                "Share exposed against the share of residents aged 65 or over",
                "One dot per region, EU-27", EXPOSURE),
        scatter(f"{p}_poverty", (M + half + G, 100, half, 512), ("Poverty rate", "At-risk-of-poverty rate"),
                ("Share exposed", "Share of residents exposed"),
                "Share exposed against the at-risk-of-poverty rate",
                "One dot per region, EU-27; regions without a poverty figure are left out", EXPOSURE),
        text(f"{p}_caption", (M, 624, CW, 60), [
            ("How to read it: these are regional averages. A region's over-65 share or poverty rate says "
             "nothing about who, inside the region, lives in the footprint - that would need the "
             "population grid by age and income, which the kit does not have. So this page can rule out "
             "a strong regional pattern; it cannot say the exposed are younger or richer.", 9, MUTED, False),
        ]),
    ]
    visuals += footer(p)
    return page_json(p, "4. Who is exposed", filterConfig=eu27_filter(p)), visuals


def declared() -> tuple[dict, list]:
    p = "declared"
    visuals = header(p, "Declared risk areas do not follow exposure: Belgium declares almost all its land, Germany and Spain almost none",
                     "What to look at: the median region's declared share of area, by country, against the "
                     "share of residents exposed. Declarations follow national mapping conventions and are "
                     "not comparable across countries.")
    visuals += [
        bars(f"{p}_by_country", (M, 100, 600, 512), "clusteredBarChart",
             [proj(level("Country"), active=True), proj(level("Region"), active=False)],
             measure("Median declared share"),
             "Declared share of area, median region - drill down to regions",
             "Blank is 'not reported' (Ireland, Lithuania), not zero",
             fill=color(NEUTRAL), units=1, tooltips=[measure("Share exposed"),
                                                     measure("Regions with a declared risk area")]),
        scatter(f"{p}_scatter", (M + 616, 100, CW - 616, 512),
                ("Declared share of area", "Declared share of the region's area"),
                ("Share exposed", "Share of residents exposed"),
                "Each region: declared share against share exposed",
                "No slope: what is declared does not track who is exposed", NEUTRAL),
        text(f"{p}_caption", (M, 624, CW, 60), [
            ("Read with care: Germany reports river reaches as thin ribbons, Belgium whole zones, so a low "
             "share is a reporting style, not a safe region. No Member State is accused of under-declaring: "
             "the Directive lets a State assess an area and find the risk not significant. "
             "(EEA layer, 2018 cycle.)", 9, MUTED, False),
        ]),
    ]
    visuals += footer(p)
    return page_json(p, "5. Declared vs exposed", filterConfig=eu27_filter(p)), visuals


def detail() -> tuple[dict, list]:
    p = "region_detail"
    filter_name = "region_detail_drillthrough"
    cw = (CW - 3 * G) // 4
    visuals = [
        visual(f"{p}_back", (M, 18, 40, 40), "actionButton",
               objects={"icon": [{"properties": {"shapeType": lit("back"), "lineColor": color(INK)},
                                  "selector": {"id": "default"}}]},
               frame={**container(frame=False), "visualLink": obj(show=True, type="Back",
                                                                  tooltip="Back to the page you came from")},
               how="InsertVisualButton"),
        text(f"{p}_title", (M + 52, 14, CW - 52, 44), [("Region detail", 20, INK, True)]),
        card(f"{p}_name", (M + 52, 54, CW - 52, 44), measure("Region shown"), "Region", value_size=14.0),
        text(f"{p}_subtitle", (M, 100, CW, 30), [(
            "What to look at: how fast the footprint grows as floods get rarer, and the profile beside it. "
            "The four figures are at 1-in-100.", 11, MUTED, False)]),
        card(f"{p}_exposed", (M, 136, cw, 96), measure("Exposed population"), "People exposed (1-in-100)",
             value_colour=EXPOSURE),
        card(f"{p}_share", (M + cw + G, 136, cw, 96), measure("Share exposed"), "Share of residents exposed"),
        card(f"{p}_pop", (M + 2 * (cw + G), 136, cw, 96), measure("Population"), "Residents"),
        card(f"{p}_eae", (M + 3 * (cw + G), 136, cw, 96), measure("Expected annual exposure"),
             "Expected annual exposure (lower bound)"),
        bars(f"{p}_by_rp", (M, 248, 608, 434), "clusteredColumnChart",
             [proj(col("Exposure", "return_period"), "Return period (1 in ... years)")],
             measure("Exposed population"), "People in the footprint, by return period",
             "Nested footprints: never add the bars", fill=color(EXPOSURE), units=0, sort=False),
        visual(f"{p}_profile", (M + 624, 248, CW - 624, 206), "multiRowCard",
               roles={"Values": [proj(col("Regions", "nuts_id"), "NUTS3 code"),
                                 proj(col("Regions", "country_name"), "Country"),
                                 proj(measure("Share over 65"), "Residents aged 65+"),
                                 proj(measure("Poverty rate"), "At-risk-of-poverty rate"),
                                 proj(measure("Declared share of area"), "Declared risk area, share of area"),
                                 proj(col("Regions", "main_shared_basin"), "Main shared basin"),
                                 proj(col("Regions", "shared_with"), "Shares a basin with")]},
               frame=container("Profile", "Regional figures, not figures for the exposed")),
        visual(f"{p}_climate", (M + 624, 470, CW - 624, 212), "multiRowCard",
               roles={"Values": [
                   proj(measure("Median change in discharge 2041-2070"), "Median change, %"),
                   proj(measure("Lower quartile change in discharge 2041-2070"), "Lower quartile, %"),
                   proj(measure("Upper quartile change in discharge 2041-2070"), "Upper quartile, %"),
                   proj(measure("Simulations agree on direction 2041-2070"), "All simulations agree on direction")]},
               frame=container("Climate: change in reference discharge, 2041-2070",
                               "Ensemble of eight bias-adjusted simulations: median and quartiles, never a mean")),
    ]
    visuals += footer(p)
    region = col("Regions", "region")
    page = page_json(
        p, "Region detail", type="Drillthrough", visibility="HiddenInViewMode",
        filterConfig={"filters": [{"name": filter_name, "field": region, "type": "Categorical",
                                   "howCreated": "Drillthrough"}]},
        pageBinding={"name": str(uuid.uuid5(uuid.NAMESPACE_URL, "flood-policy-kit/region_detail")),
                     "type": "Drillthrough", "referenceScope": "Default",
                     "acceptsFilterContext": "None",
                     "parameters": [{"name": str(uuid.uuid5(uuid.NAMESPACE_URL,
                                                            "flood-policy-kit/region_detail/region")),
                                     "boundFilter": filter_name, "fieldExpr": region}]},
    )
    return page, visuals


PAGES = (headline, where, downstream, who, declared, detail)


# --- theme and report ---------------------------------------------------------

def theme() -> dict:
    """The custom theme: page and card colours, the YlOrBr ramp, Segoe UI throughout."""
    return {
        "name": "FloodPolicyKit",
        "dataColors": [EXPOSURE, ACCENT, RAMP[5], RAMP[2], MUTED, NEUTRAL, RAMP[3], "#2166AC"],
        "foreground": INK, "foregroundNeutralSecondary": MUTED, "foregroundNeutralTertiary": NEUTRAL,
        "background": CARD_BG, "backgroundLight": PAGE_BG, "backgroundNeutral": LINE,
        "tableAccent": EXPOSURE,
        "minimum": RAMP[1], "center": RAMP[3], "maximum": RAMP[5], "null": "#D9D9D9",
        "good": "#1A7F4B", "neutral": "#B26A00", "bad": "#C62828",
        "textClasses": {
            "callout": {"fontSize": 26, "fontFace": "Segoe UI Semibold", "color": INK},
            "title": {"fontSize": 12, "fontFace": "Segoe UI Semibold", "color": INK},
            "header": {"fontSize": 11, "fontFace": "Segoe UI Semibold", "color": INK},
            "label": {"fontSize": 10, "fontFace": "Segoe UI", "color": INK},
        },
        "visualStyles": {
            "page": {"*": {"background": [{"color": {"solid": {"color": PAGE_BG}}, "transparency": 0}]}},
            "*": {"*": {
                "background": [{"show": True, "color": {"solid": {"color": CARD_BG}}, "transparency": 0}],
                "border": [{"show": True, "color": {"solid": {"color": LINE}}, "radius": 8}],
                "title": [{"fontColor": {"solid": {"color": INK}}, "fontSize": 12, "bold": True}],
                "subTitle": [{"fontColor": {"solid": {"color": MUTED}}, "fontSize": 9}],
            }},
            "textbox": {"*": {"background": [{"show": False}], "border": [{"show": False}]}},
        },
    }


def report_json() -> dict:
    stamp = {"visual": VERSIONS["visualContainer"], "report": VERSIONS["report"], "page": VERSIONS["page"]}
    return {
        "$schema": f"{SCHEMA}/report/{VERSIONS['report']}/schema.json",
        "themeCollection": {"customTheme": {"name": THEME_NAME, "reportVersionAtImport": stamp,
                                            "type": "RegisteredResources"}},
        "resourcePackages": [{"name": "RegisteredResources", "type": "RegisteredResources",
                              "items": [{"name": THEME_NAME, "path": THEME_NAME, "type": "CustomTheme"}]}],
        "settings": {"useStylableVisualContainerHeader": True, "defaultDrillFilterOtherVisuals": True,
                     "useEnhancedTooltips": True, "exportDataMode": "AllowSummarized"},
        "annotations": [{"name": "generatedBy", "value": "scripts/build_bi_report.py"}],
    }


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def build(report: Path = REPORT) -> list[Path]:
    """Write the report definition, the theme and definition.pbir; return the files written."""
    definition = report / "definition"
    if definition.exists():
        shutil.rmtree(definition)
    legacy = report / "report.json"
    if legacy.exists():
        legacy.unlink()
    written = []

    def put(path: Path, data: dict) -> None:
        _write(path, data)
        written.append(path)

    put(report / "definition.pbir", {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json",
        "version": "4.0",
        "datasetReference": {"byPath": {"path": "../FloodPolicyKit.SemanticModel"}}})
    put(definition / "version.json", {
        "$schema": f"{SCHEMA}/versionMetadata/{VERSIONS['versionMetadata']}/schema.json", "version": "2.0.0"})
    put(definition / "report.json", report_json())
    put(report / "StaticResources" / "RegisteredResources" / THEME_NAME, theme())
    names = []
    for make in PAGES:
        page, visuals = make()
        names.append(page["name"])
        folder = definition / "pages" / page["name"]
        put(folder / "page.json", page)
        for z, v in enumerate(visuals):
            v["position"]["z"] = v["position"]["tabOrder"] = z * 1000
            put(folder / "visuals" / v["name"] / "visual.json", v)
    put(definition / "pages" / "pages.json", {
        "$schema": f"{SCHEMA}/pagesMetadata/{VERSIONS['pagesMetadata']}/schema.json",
        "pageOrder": names, "activePageName": names[0]})
    return written


def main() -> int:
    written = build()
    print(f"{len(written)} files written under {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
