"""Tests for the Power BI export, the semantic model that reads it, and the report.

The Power BI project is a third front end, so the failure to pin is a figure
that differs from the one the app and the brief quote. The export is checked
against the frozen tables, and the TMDL model against the export: a column
renamed on one side and not the other would load as an error in Power BI, far
from the change that caused it. The report is checked against the model and
against Microsoft's published PBIR schemas, because nobody opens Power BI
Desktop at every change and Desktop refuses a file that breaks its schema.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import pandas as pd
import pytest

from scripts import build_bi_report, export_bi, validate_bi_report

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
TABLES = ROOT / "bi" / "FloodPolicyKit.SemanticModel" / "definition" / "tables"
REPORT = ROOT / "bi" / "FloodPolicyKit.Report"

# The frozen tables are committed, so this skips only on a checkout that moved
# them aside - which is how the UI tests are checked for leaks - not in CI. The
# report tests read only the project files and never need it.
needs_frozen = pytest.mark.skipif(
    not (PROCESSED / "exposure.parquet").exists(),
    reason="the export is checked against the frozen exposure table",
)


def _frozen_exposure() -> pd.DataFrame:
    return pd.read_parquet(PROCESSED / "exposure.parquet")


@needs_frozen
def test_the_eu27_headline_matches_the_frozen_table() -> None:
    """The number the brief opens with must come out of Power BI unchanged."""
    regions, exposure = export_bi.tables(PROCESSED)
    rp100 = exposure[exposure["return_period"] == 100].merge(
        regions[["nuts_id", "is_eu27"]], on="nuts_id"
    )
    frozen = _frozen_exposure()
    frozen_rp100 = frozen[(frozen["return_period"] == 100)
                          & frozen["country"].isin(export_bi.EU27)]
    assert len(export_bi.EU27) == 27
    assert rp100.loc[rp100["is_eu27"], "exposed_pop"].sum() == frozen_rp100["exposed_pop"].sum()


@needs_frozen
def test_one_region_row_per_region_and_every_scenario_row_kept() -> None:
    """A region duplicated in the dimension would double every figure joined to
    it; a scenario row dropped would silently lower one return period."""
    regions, exposure = export_bi.tables(PROCESSED)
    frozen = _frozen_exposure()
    assert regions["nuts_id"].is_unique
    assert set(regions["nuts_id"]) == set(frozen["nuts_id"])
    assert len(exposure) == len(frozen)


@needs_frozen
def test_list_cells_become_text_power_query_can_read() -> None:
    """Power Query reads a list cell as an error. The separator is "; " because
    a basin name can carry a comma ("Teno, Naatamo and Paatsjoki" split in two
    with ", "). The largest basin also gets a column of its own, so a slicer
    can filter on it."""
    regions, _ = export_bi.tables(PROCESSED)
    for column in ("shared_with", "shared_basins", "main_shared_basin"):
        assert regions[column].map(lambda v: isinstance(v, str)).all(), column
    named = regions[regions["shared_basins"] != ""]
    assert (named["shared_basins"].str.split("; ").str[0] == named["main_shared_basin"]).all()


def _tmdl_columns(name: str) -> list[str]:
    text = (TABLES / f"{name}.tmdl").read_text(encoding="utf-8")
    return re.findall(r"^\tcolumn (\S+)$", text, flags=re.M)


def _tmdl_typed_columns(name: str) -> list[str]:
    text = (TABLES / f"{name}.tmdl").read_text(encoding="utf-8")
    return re.findall(r'\{"([^"]+)", (?:type \w+|Int64\.Type)\}', text)


@needs_frozen
def test_the_model_declares_exactly_the_exported_columns() -> None:
    """Every TMDL column must exist in the CSV it reads, and every CSV column
    must be typed in the Power Query step - in the same order."""
    regions, exposure = export_bi.tables(PROCESSED)
    for name, frame in (("Regions", regions), ("Exposure", exposure)):
        assert _tmdl_columns(name) == list(frame.columns), name
        assert _tmdl_typed_columns(name) == list(frame.columns), name


def test_the_exposed_population_measure_refuses_a_sum_across_return_periods() -> None:
    """The extents are nested: the RP100 footprint contains the RP10 one, so a
    sum over return periods counts the same people several times. The measure
    must be blank unless one return period is selected."""
    text = (TABLES / "Exposure.tmdl").read_text(encoding="utf-8")
    measure = re.search(r"measure 'Exposed population' = (.+)", text).group(1)
    assert "HASONEVALUE(Exposure[return_period])" in measure
    summarize = re.search(r"column exposed_pop\n(?:\t\t.*\n)*?\t\tsummarizeBy: (\w+)", text)
    assert summarize.group(1) == "none", "a default sum would bypass the measure"


def test_topojson_keeps_every_region_and_its_join_key() -> None:
    """The Shape map joins on `nuts_id`; a dropped region is a grey hole."""
    geojson = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"nuts_id": "XX001", "name": "A"},
         "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]}},
        {"type": "Feature", "properties": {"nuts_id": "XX002", "name": "B"},
         "geometry": {"type": "MultiPolygon", "coordinates": [
             [[[2, 2], [3, 2], [3, 3], [2, 2]]], [[[4, 4], [5, 4], [5, 5], [4, 4]]]]}},
    ]}
    topology = export_bi.topojson(geojson)
    geometries = topology["objects"]["regions"]["geometries"]
    assert [g["properties"]["nuts_id"] for g in geometries] == ["XX001", "XX002"]
    assert geometries[1]["arcs"] == [[1], [2]]
    assert topology["arcs"][2] == [[4, 4], [5, 4], [5, 5], [4, 4]]


@needs_frozen
def test_main_writes_the_two_tables_and_skips_absent_geometry(tmp_path, monkeypatch, capsys) -> None:
    """A fresh clone has no regions.geojson: the tables are still written and the
    run says how to get the map."""
    processed = tmp_path / "processed"
    processed.mkdir()
    for name in ("exposure.parquet", "context.parquet"):
        shutil.copy(PROCESSED / name, processed / name)
    out = tmp_path / "bi"
    monkeypatch.setattr("sys.argv", ["export_bi.py", "--processed", str(processed), "--out", str(out)])
    assert export_bi.main() == 0
    assert (out / "regions.csv").exists() and (out / "exposure.csv").exists()
    assert not (out / "regions.topojson").exists()
    assert "build_geometry.py" in capsys.readouterr().out
    back = pd.read_csv(out / "exposure.csv")
    assert back["exposed_pop"].sum() == _frozen_exposure()["exposed_pop"].sum()


# --- the report (PBIR) -----------------------------------------------------------

def _report_files() -> list[Path]:
    return sorted((REPORT / "definition").rglob("*.json"))


def _visual(page: str, name: str) -> dict:
    path = REPORT / "definition" / "pages" / page / "visuals" / name / "visual.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _declared_fields() -> tuple[set, set]:
    """("Table.Field" for every column and measure, "Table.Hierarchy.Level" for every level)."""
    fields, levels = set(), set()
    for name in ("Regions", "Exposure"):
        text = (TABLES / f"{name}.tmdl").read_text(encoding="utf-8")
        fields |= {f"{name}.{c}" for c in re.findall(r"^\tcolumn (\S+)$", text, flags=re.M)}
        fields |= {f"{name}.{m}" for m in re.findall(r"^\tmeasure '([^']+)'", text, flags=re.M)}
        for hierarchy, body in re.findall(r"^\thierarchy (\S+)\n((?:\t\t.*\n|\n)*)", text, flags=re.M):
            levels |= {f"{name}.{hierarchy}.{lv}" for lv in re.findall(r"^\t\tlevel (\S+)$", body, flags=re.M)}
    return fields, levels


def _used_fields(node, aliases: dict | None = None):
    """Every field a PBIR file names: columns and measures as "Table.Field",
    hierarchy levels as "Table.Hierarchy.Level". A filter names its table
    through an alias declared in its `From`, so aliases are carried down."""
    aliases = dict(aliases or {})
    if isinstance(node, dict):
        for source in node.get("From", []):
            aliases[source["Name"]] = source["Entity"]
        for kind in ("Column", "Measure"):
            if isinstance(node.get(kind), dict) and "Property" in node[kind]:
                ref = node[kind]["Expression"]["SourceRef"]
                yield f"{ref.get('Entity') or aliases[ref['Source']]}.{node[kind]['Property']}"
        if "HierarchyLevel" in node:
            hierarchy = node["HierarchyLevel"]["Expression"]["Hierarchy"]
            ref = hierarchy["Expression"]["SourceRef"]
            yield (f"{ref.get('Entity') or aliases[ref['Source']]}."
                   f"{hierarchy['Hierarchy']}.{node['HierarchyLevel']['Level']}")
            return
        for value in node.values():
            yield from _used_fields(value, aliases)
    elif isinstance(node, list):
        for value in node:
            yield from _used_fields(value, aliases)


def test_every_field_the_report_shows_exists_in_the_model() -> None:
    """A visual bound to a renamed column or measure opens as a grey error box
    in Power BI, with nothing pointing back at the rename. Every field reference
    in every PBIR file counts - projections, sorts, filters, drillthrough
    bindings, colour rules - not only the visible ones."""
    fields, levels = _declared_fields()
    used = set()
    for path in _report_files():
        used |= set(_used_fields(json.loads(path.read_text(encoding="utf-8"))))
    assert "Exposure.Exposed population" in used, "the report has no data-bound visual"
    assert used <= fields | levels, sorted(used - fields - levels)


def test_the_legacy_layout_is_gone_and_the_project_opens_as_pbir() -> None:
    """definition.pbir version 1.0 allows only the legacy report.json layout;
    4.0 is the one that reads the definition folder."""
    assert not (REPORT / "report.json").exists()
    pbir = json.loads((REPORT / "definition.pbir").read_text(encoding="utf-8"))
    assert pbir["version"] == "4.0"
    assert pbir["datasetReference"] == {"byPath": {"path": "../FloodPolicyKit.SemanticModel"}}


@pytest.mark.skipif(not validate_bi_report.THEME_SCHEMA.exists(), reason="schemas not vendored")
def test_every_project_json_file_validates_against_its_microsoft_schema() -> None:
    """Desktop blocks on a PBIR file that breaks its schema. The schemas are
    vendored in bi/schemas - microsoft/json-schemas and
    microsoft/powerbi-desktop-samples, both under the MIT licence, which
    permits copying them; the licence texts are kept beside them - so this
    runs offline. Each visual's formatting is also checked against the theme
    schema, because the visual schema accepts any formatting name."""
    files = validate_bi_report.project_files()
    assert sum(p.name == "visual.json" for p in files) > 40
    failures = {}
    for path in files:
        errors = validate_bi_report.validate_file(path)
        if path.name == "visual.json":
            errors += validate_bi_report.formatting_errors(path)
        if errors:
            failures[path.relative_to(ROOT).as_posix()] = errors
    assert not failures, failures


@pytest.mark.skipif(not validate_bi_report.THEME_SCHEMA.exists(), reason="schemas not vendored")
def test_the_validator_rejects_what_desktop_would_reject(tmp_path) -> None:
    """A validator that passes everything proves nothing: an unknown key, a
    misspelt formatting property, a bad enum value and a malformed colour rule
    must each be caught."""
    visual = _visual("where", "where_by_country")
    path = tmp_path / "visual.json"

    def errors(mutate) -> list:
        data = json.loads(json.dumps(visual))
        mutate(data)
        path.write_text(json.dumps(data), encoding="utf-8")
        return validate_bi_report.validate_file(path) + validate_bi_report.formatting_errors(path)

    objects = lambda d: d["visual"]["objects"]  # noqa: E731
    assert errors(lambda d: None) == []
    assert errors(lambda d: d.update(bogus=1))
    assert errors(lambda d: objects(d)["labels"][0]["properties"].update(
        colour={"expr": {"Literal": {"Value": "'#000000'"}}}))
    assert errors(lambda d: objects(d)["categoryAxis"][0]["properties"].update(
        axisType={"expr": {"Literal": {"Value": "'Diagonal'"}}}))
    assert errors(lambda d: objects(d)["dataPoint"][0]["properties"]["fill"]["solid"]["color"]["expr"]
                  ["FillRule"].update(bogus=1))
    assert errors(lambda d: d["visual"]["query"]["sortDefinition"]["sort"][0].update(direction="Down"))


def test_regions_drill_down_from_country_to_region() -> None:
    """Drill-down needs a hierarchy on the category axis: the model declares
    Geography (Country, Region), and the Where page puts both levels on it."""
    _, levels = _declared_fields()
    assert {"Regions.Geography.Country", "Regions.Geography.Region"} <= levels
    category = _visual("where", "where_by_country")["visual"]["query"]["queryState"]["Category"]["projections"]
    assert [p["queryRef"] for p in category] == ["Regions.Geography.Country", "Regions.Geography.Region"]
    assert [p["active"] for p in category] == [True, False], "opens on countries, drills to regions"


def test_the_region_detail_page_is_a_drillthrough_bound_to_a_regions_column() -> None:
    """Right-click a region anywhere, then Drill through: the menu exists only if
    a page is bound as a drillthrough to a field the source visual carries, and
    the binding must point at that page's own drillthrough filter."""
    pages = [json.loads(p.read_text(encoding="utf-8"))
             for p in sorted((REPORT / "definition" / "pages").glob("*/page.json"))]
    drillthroughs = [p for p in pages if p.get("pageBinding", {}).get("type") == "Drillthrough"]
    assert len(drillthroughs) == 1
    page = drillthroughs[0]
    parameter, = page["pageBinding"]["parameters"]
    bound = {f["name"]: f for f in page["filterConfig"]["filters"]}[parameter["boundFilter"]]
    assert bound["howCreated"] == "Drillthrough"
    assert bound["field"] == parameter["fieldExpr"]
    column = parameter["fieldExpr"]["Column"]
    assert column["Expression"]["SourceRef"]["Entity"] == "Regions"
    assert f"Regions.{column['Property']}" in _declared_fields()[0]
    back = _visual(page["name"], f"{page['name']}_back")["visual"]["visualContainerObjects"]["visualLink"]
    assert back[0]["properties"]["type"]["expr"]["Literal"]["Value"] == "'Back'"


def test_the_committed_report_is_what_the_generator_writes(tmp_path) -> None:
    """The PBIR files come from scripts/build_bi_report.py: a hand edit to the
    files and not to the script would be lost on the next build."""
    build_bi_report.build(tmp_path / "Report")
    committed = _report_files() + [REPORT / "definition.pbir", build_bi_report.THEME_PATH]
    rebuilt = sorted((tmp_path / "Report" / "definition").rglob("*.json"))
    assert [p.relative_to(tmp_path / "Report") for p in rebuilt] == \
        [p.relative_to(REPORT) for p in _report_files()]
    for path in committed:
        again = tmp_path / "Report" / path.relative_to(REPORT)
        assert again.read_text(encoding="utf-8") == path.read_text(encoding="utf-8"), path.name


def test_every_page_laid_out_for_boundaries_credits_eurogeographics() -> None:
    """GISCO terms: a page that shows the region boundaries, or holds the place
    of the Shape map that will, carries the credit."""
    checked = 0
    for page in sorted((REPORT / "definition" / "pages").glob("*/")):
        texts = " ".join(p.read_text(encoding="utf-8") for p in page.rglob("visual.json"))
        if "regions.topojson" in texts or '"shapeMap"' in texts:
            checked += 1
            assert "EuroGeographics for the administrative boundaries" in texts, page.name
    assert checked, "no page is laid out for the map"


def test_the_drill_down_is_visible_without_hovering() -> None:
    """The bar charts' drill arrows only appear on hover and were missed: the
    Where and Downstream pages carry a matrix whose rows are a hierarchy, with
    the +/- buttons switched on."""
    import json

    pages = ROOT / "bi" / "FloodPolicyKit.Report" / "definition" / "pages"
    for page, visual in (("where", "where_regions"), ("downstream", "downstream_partners")):
        spec = json.loads((pages / page / "visuals" / visual / "visual.json").read_text(encoding="utf-8"))
        assert spec["visual"]["visualType"] == "pivotTable"
        assert len(spec["visual"]["query"]["queryState"]["Rows"]["projections"]) == 2
        row_headers = json.dumps(spec["visual"]["objects"]["rowHeaders"])
        assert "showExpandCollapseButtons" in row_headers
