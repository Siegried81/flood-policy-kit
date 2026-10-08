"""Tests for the future-hazard layer.

The aggregation takes arrays rather than a path, so everything here runs without
a NetCDF. What is pinned is the three properties that make the figure quotable:
the median survives the near-zero-reference tail, a region with a handful of
cells gets no figure at all, and no mean or maximum is ever produced.
"""

from __future__ import annotations

import geopandas as gpd
import numpy as np
import pytest
from shapely.geometry import box

from src import climate

REAL_NAME = (
    "rdisreturnmax50_tmean_rel_E-HYPEgrid-EUR-11_ICHEC-EC-EARTH_rcp85_r12i1p1_"
    "CLMcom-CCLM4-8-17-v1_2041-2070_1971-2000_grid5km_v1.nc"
)


def _grid(values, *, lon0=0.5, lat0=0.5):
    """A small lon/lat grid and its values, as the reader returns them."""
    values = np.asarray(values, dtype="float64")
    rows, cols = values.shape
    lon, lat = np.meshgrid(
        lon0 + np.arange(cols, dtype="float64"),
        lat0 + np.arange(rows, dtype="float64"),
    )
    return lon, lat, values


def _one_region(lon_max=10.0, lat_max=10.0):
    return gpd.GeoDataFrame(
        {"id": ["one"]}, geometry=[box(0, 0, lon_max, lat_max)], crs=climate.POINT_CRS
    )


# --- the filename is the provenance -------------------------------------------

def test_the_filename_yields_the_whole_request():
    """A percentage is meaningless without the two periods it is a change
    between, and unreproducible without the model chain."""
    fields = climate.describe(REAL_NAME)
    assert fields["variable"] == "rdisreturnmax50"
    assert fields["kind"] == "rel"
    assert fields["hydro_model"] == "E-HYPEgrid-EUR-11"
    assert fields["gcm"] == "ICHEC-EC-EARTH"
    assert fields["experiment"] == "rcp85"
    assert fields["member"] == "r12i1p1"
    assert fields["period"] == "2041-2070"
    assert fields["reference"] == "1971-2000"


def test_an_unexpected_filename_is_refused_with_the_shape_it_wanted():
    """Guessing the fields of a file someone renamed is how a brief ends up
    quoting RCP 4.5 as RCP 8.5."""
    with pytest.raises(ValueError, match="does not look like"):
        climate.describe("flood_data_final_v2.nc")


# --- points ---------------------------------------------------------------------

def test_nodata_and_masked_cells_never_reach_a_quantile():
    """The CDS sentinel is 1e20. One of those surviving into a median puts the
    region at the top of the ranking, and it looks like a finding."""
    lon, lat, values = _grid([[10.0, 1e20], [20.0, np.nan]])
    values = np.ma.masked_equal(values, 1e20)
    points = climate.change_points(lon, lat, values)
    assert len(points) == 2
    assert sorted(points["change_pct"]) == [10.0, 20.0]


def test_three_arrays_of_different_shapes_are_refused():
    """They are three readings of one grid; a mismatch means the wrong
    subdataset was read, and zipping them would pair a value with another
    cell's coordinates."""
    lon, lat, values = _grid([[1.0, 2.0]])
    with pytest.raises(ValueError, match="same shape"):
        climate.change_by_region(_one_region(), lon, lat, values[:, :1])


# --- the aggregation ------------------------------------------------------------

def test_the_median_is_the_median_of_the_cells_inside():
    lon, lat, values = _grid([[10.0, 20.0], [30.0, 40.0]])
    out = climate.change_by_region(_one_region(), lon, lat, values, min_points=1)
    assert out["change_pct_median"].iat[0] == pytest.approx(25.0)
    assert out["change_pct_p25"].iat[0] == pytest.approx(17.5)
    assert out["change_pct_p75"].iat[0] == pytest.approx(32.5)
    assert out["change_points"].iat[0] == 4


def test_one_absurd_cell_does_not_move_the_figure():
    """The reason this module reports a median at all.

    A relative change has no upper bound where the 1971-2000 reference discharge
    is near zero: measured on the real file, the maximum is +16,452,833% against
    a median of +16.9%. A mean over these five cells would be +3,290,578%; the
    median is +30%, which is what the region is actually doing.
    """
    lon, lat, values = _grid([[10.0, 20.0, 30.0], [40.0, 16_452_833.0, 50.0]])
    out = climate.change_by_region(_one_region(), lon, lat, values, min_points=1)
    assert out["change_pct_median"].iat[0] == pytest.approx(35.0)
    assert out["change_pct_median"].iat[0] < 100.0


def test_no_mean_and_no_maximum_are_offered():
    """Not an omission. Either one is a number a reader would quote, and both
    belong entirely to the near-zero-reference tail."""
    lon, lat, values = _grid([[10.0, 20.0], [30.0, 40.0]])
    out = climate.change_by_region(_one_region(), lon, lat, values, min_points=1)
    assert not [c for c in out.columns if "mean" in c or "max" in c]


def test_a_region_with_too_few_cells_gets_no_figure():
    """A quantile over three cells is the three cells. Reporting it beside a
    region summarising four hundred invites a comparison that is not there."""
    lon, lat, values = _grid([[10.0, 20.0], [30.0, 40.0]])
    out = climate.change_by_region(_one_region(), lon, lat, values, min_points=10)
    assert out["change_points"].iat[0] == 4
    assert np.isnan(out["change_pct_median"].iat[0])


def test_a_region_the_grid_misses_entirely_is_counted_as_zero_cells():
    """Distinguishable from a region with cells but no spread: 0 points says the
    projection does not cover it, which is a different sentence in a brief."""
    lon, lat, values = _grid([[10.0, 20.0], [30.0, 40.0]])
    far = gpd.GeoDataFrame(
        {"id": ["elsewhere"]}, geometry=[box(100, 100, 110, 110)], crs=climate.POINT_CRS
    )
    out = climate.change_by_region(far, lon, lat, values, min_points=1)
    assert out["change_points"].iat[0] == 0
    assert np.isnan(out["change_pct_median"].iat[0])


def test_every_region_comes_back_once_and_in_order():
    """The frame is joined onto the exposure table by position elsewhere, so a
    dropped or reordered row would silently attach one region's future to
    another's present."""
    lon, lat, values = _grid([[10.0, 20.0], [30.0, 40.0]])
    admin = gpd.GeoDataFrame(
        {"id": ["covered", "empty"]},
        geometry=[box(0, 0, 10, 10), box(100, 100, 110, 110)],
        crs=climate.POINT_CRS,
    )
    out = climate.change_by_region(admin, lon, lat, values, min_points=1)
    assert list(out.index) == list(admin.index)
    assert out["change_points"].tolist() == [4, 0]


# --- the ensemble ---------------------------------------------------------------

def _member_name(variable="rdisreturnmax50", model="E-HYPEgrid-EUR-11",
                 gcm="ICHEC-EC-EARTH", member="r12i1p1", period="2041-2070"):
    return (f"{variable}_tmean_rel_{model}_{gcm}_rcp85_{member}_"
            f"CLMcom-CCLM4-8-17-v1_{period}_1971-2000_grid5km_v1.nc")


def test_an_ensemble_of_nothing_is_refused():
    with pytest.raises(ValueError, match="no median"):
        climate.ensemble_change_by_region(_one_region(), [])


def test_members_must_answer_the_same_question():
    """Two periods are two questions. A median over them is a number about
    neither, and it would read exactly like a figure about one."""
    with pytest.raises(ValueError, match="disagree on `period`"):
        climate.ensemble_change_by_region(
            _one_region(),
            [_member_name(period="2041-2070"), _member_name(period="2071-2100")],
        )


def test_a_lone_member_never_claims_agreement(tmp_path, monkeypatch):
    """One member trivially agrees with itself, and saying True there would
    licence the one sentence this column exists to stop."""
    lon, lat, values = _grid([[10.0, 20.0], [30.0, 40.0]])
    monkeypatch.setattr(climate, "read_change", lambda p, variable=None: (lon, lat, values))
    out = climate.ensemble_change_by_region(
        _one_region(), [_member_name()], min_points=1
    )
    assert out["ensemble_members"].iat[0] == 1
    assert bool(out["ensemble_agrees_on_sign"].iat[0]) is False
    assert out["change_pct_ensemble_median"].iat[0] == pytest.approx(25.0)


def test_members_that_disagree_on_sign_are_flagged(monkeypatch):
    """The column that licenses a sentence. "Flood discharge increases here" is
    defensible where every member says so and is not where they split, whatever
    the median reads."""
    grids = {
        "a": _grid([[10.0, 20.0], [30.0, 40.0]]),      # all up
        "b": _grid([[-10.0, -20.0], [-30.0, -40.0]]),  # all down
    }
    order = iter(("a", "b"))
    monkeypatch.setattr(
        climate, "read_change", lambda p, variable=None: grids[next(order)]
    )
    out = climate.ensemble_change_by_region(
        _one_region(),
        [_member_name(model="E-HYPEgrid-EUR-11"), _member_name(model="VIC-WUR-EUR-11")],
        min_points=1,
    )
    assert out["ensemble_members"].iat[0] == 2
    assert bool(out["ensemble_agrees_on_sign"].iat[0]) is False
    assert out["change_pct_ensemble_min"].iat[0] == pytest.approx(-25.0)
    assert out["change_pct_ensemble_max"].iat[0] == pytest.approx(25.0)


def test_members_that_agree_are_flagged_as_agreeing(monkeypatch):
    grids = {
        "a": _grid([[10.0, 20.0], [30.0, 40.0]]),
        "b": _grid([[12.0, 22.0], [32.0, 42.0]]),
    }
    order = iter(("a", "b"))
    monkeypatch.setattr(
        climate, "read_change", lambda p, variable=None: grids[next(order)]
    )
    out = climate.ensemble_change_by_region(
        _one_region(),
        [_member_name(model="E-HYPEgrid-EUR-11"), _member_name(model="VIC-WUR-EUR-11")],
        min_points=1,
    )
    assert bool(out["ensemble_agrees_on_sign"].iat[0]) is True
    assert out["change_pct_ensemble_median"].iat[0] == pytest.approx(26.0)


def test_a_region_no_member_covers_gets_no_agreement(monkeypatch):
    """Zero members is not agreement either."""
    lon, lat, values = _grid([[10.0, 20.0], [30.0, 40.0]])
    monkeypatch.setattr(climate, "read_change", lambda p, variable=None: (lon, lat, values))
    far = gpd.GeoDataFrame(
        {"id": ["elsewhere"]}, geometry=[box(100, 100, 110, 110)], crs=climate.POINT_CRS
    )
    out = climate.ensemble_change_by_region(far, [_member_name()], min_points=1)
    assert out["ensemble_members"].iat[0] == 0
    assert bool(out["ensemble_agrees_on_sign"].iat[0]) is False
    assert np.isnan(out["change_pct_ensemble_median"].iat[0])


# --- the reader picks the indicator by name -------------------------------------

class _Fake:
    """Enough of a rasterio dataset to exercise the subdataset selection."""

    def __init__(self, subdatasets=(), array=None):
        self.subdatasets = list(subdatasets)
        self._array = array

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, _band, masked=False):
        return self._array


def _patched_open(subdatasets, array):
    def opener(target, *a, **k):
        target = str(target)
        if target.startswith("NETCDF:"):
            return _Fake(array=array)
        return _Fake(subdatasets=subdatasets)
    return opener


def test_a_bounds_array_is_not_mistaken_for_the_indicator(monkeypatch, tmp_path):
    """The CDS does not ship a uniform layout.

    Measured 2026-10-06: the E-HYPE files carry `lon`, `lat` and the indicator,
    while the VIC-WUR files carry `time_bnds` as well - so "the subdataset that is
    not lon or lat" was two candidates and the read failed on a perfectly good
    file, in the middle of a continental build. The filename already states the
    variable.
    """
    import rasterio
    path = tmp_path / REAL_NAME
    path.write_bytes(b"")
    subdatasets = [
        f'NETCDF:"{path}":lon',
        f'NETCDF:"{path}":lat',
        f'NETCDF:"{path}":rdisreturnmax50_tmean',
        f'NETCDF:"{path}":time_bnds',
    ]
    values = np.ma.masked_array([[1.0, 2.0], [3.0, 4.0]])
    monkeypatch.setattr(rasterio, "open", _patched_open(subdatasets, values))
    lon, lat, out = climate.read_change(path)
    assert out.shape == (2, 2)


def test_a_file_whose_name_does_not_parse_still_reads_if_it_is_unambiguous(
    monkeypatch, tmp_path
):
    """The fallback. `describe` refuses a renamed file, but a renamed file with
    one indicator beside lon and lat is still readable - and refusing it would
    make the provenance check a reason not to read good data."""
    import rasterio
    path = tmp_path / "renamed_by_hand.nc"
    path.write_bytes(b"")
    subdatasets = [
        f'NETCDF:"{path}":lon',
        f'NETCDF:"{path}":lat',
        f'NETCDF:"{path}":whatever_tmean',
        f'NETCDF:"{path}":lat_bnds',
    ]
    values = np.ma.masked_array([[5.0]])
    monkeypatch.setattr(rasterio, "open", _patched_open(subdatasets, values))
    lon, lat, out = climate.read_change(path)
    assert out.shape == (1, 1)


# --- the ensemble member fetcher ------------------------------------------------

def test_a_wrong_member_is_refused_before_it_reaches_the_ensemble(tmp_path):
    """The failure that matters is not an empty download, it is the WRONG member
    landing in the directory the ensemble is globbed from.

    `ensemble_change_by_region` takes the median across whatever files it finds
    and only checks that they agree on variable, kind, period and reference - a
    file from another model chain, or another period, would pass that check for
    the period it claims and quietly become a second opinion. So the fetcher
    verifies the filename against what it asked for, using this module's own
    grammar, and moves nothing until every file matches.
    """
    from scripts.fetch_cds_member import check

    wrong_period = (
        "rdisreturnmax5_tmean_rel_VIC-WUR-EUR-11_ICHEC-EC-EARTH_rcp85_r12i1p1_"
        "CLMcom-CCLM4-8-17-v1_2041-2070_1971-2000_grid5km_v1.nc"
    )
    with pytest.raises(SystemExit, match="period is '2041-2070'"):
        check(tmp_path / wrong_period, "vic_wur", "2071_2100")

    wrong_model = (
        "rdisreturnmax5_tmean_rel_E-HYPEgrid-EUR-11_ICHEC-EC-EARTH_rcp85_r12i1p1_"
        "CLMcom-CCLM4-8-17-v1_2071-2100_1971-2000_grid5km_v1.nc"
    )
    with pytest.raises(SystemExit, match="hydro_model"):
        check(tmp_path / wrong_model, "vic_wur", "2071_2100")


def test_the_requested_member_is_accepted(tmp_path):
    from scripts.fetch_cds_member import check

    right = (
        "rdisreturnmax50_tmean_rel_VIC-WUR-EUR-11_ICHEC-EC-EARTH_rcp85_r12i1p1_"
        "CLMcom-CCLM4-8-17-v1_2071-2100_1971-2000_grid5km_v1.nc"
    )
    fields = check(tmp_path / right, "vic_wur", "2071_2100")
    assert fields["period"] == "2071-2100"
    assert fields["hydro_model"] == "VIC-WUR-EUR-11"


def test_the_request_asks_for_one_period_and_one_model():
    """The form's cost cap is the PRODUCT of the selections, not the sum, and a
    multi-period request is also one whose result cannot be checked file by
    file."""
    from scripts.fetch_cds_member import request

    body = request("vic_wur", "2071_2100")
    assert body["period"] == ["2071_2100"]
    assert body["hydrological_model"] == ["vic_wur"]
    assert body["variable_type"] == "relative_change_from_reference_period"
