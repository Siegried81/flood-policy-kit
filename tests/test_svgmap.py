"""Tests for the offline choropleth.

Squares small enough to check by hand, like the basin tests. Nothing here
touches the network - which is the whole reason this module exists instead of
folium, whose basemap tiles come from a tile server the venue may block.
"""

from __future__ import annotations

import math

import pytest

from src import svgmap


def _square(code: str, lon: float, lat: float, size: float = 1.0) -> dict:
    return {
        "type": "Feature",
        "properties": {"nuts_id": code},
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [lon, lat], [lon + size, lat], [lon + size, lat + size],
                [lon, lat + size], [lon, lat],
            ]],
        },
    }


# --- the classes ----------------------------------------------------------------

def test_the_breaks_are_quantiles_of_what_is_present():
    """Not a linear ramp. Exposure share is so skewed - a median near 3% against
    a Dutch tail at 70% - that equal-width classes paint almost every region the
    palest colour and the map says nothing."""
    breaks = svgmap.quantile_breaks(list(range(1, 101)), classes=4)
    assert breaks == [25, 50, 75, 100]


def test_duplicate_bounds_collapse_rather_than_repeat():
    """Two classes meaning the same thing is a legend that lies about its own
    precision."""
    breaks = svgmap.quantile_breaks([0, 0, 0, 0, 0, 0, 0, 5], classes=4)
    assert breaks == [0, 5]


def test_no_values_means_no_breaks():
    assert svgmap.quantile_breaks([]) == []
    assert svgmap.quantile_breaks([float("nan")]) == []


def test_a_missing_value_is_grey_and_not_the_colour_of_zero():
    """The one thing a risk map must not do. A region the raster never covered is
    not a region where nobody is exposed, so it cannot share a fill with the
    lowest class."""
    features = [_square("AA", 4, 50), _square("BB", 6, 50), _square("CC", 8, 50)]
    svg = svgmap.choropleth_svg(
        features, {"AA": 0.0, "BB": 0.5, "CC": None}, extent_excludes=()
    )
    assert svg.count(svgmap.NO_DATA) >= 1
    lowest = svgmap.PALETTE[0]
    assert f'fill="{lowest}"' in svg, "a measured zero still gets a palette colour"
    assert svgmap.NO_DATA not in svgmap.PALETTE


def test_a_key_absent_from_the_values_is_also_grey():
    """Absent and None have to behave the same: both mean "no figure", and only
    one of them is a key someone remembered to pass."""
    import re

    features = [_square("AA", 4, 50), _square("ZZ", 6, 50)]
    svg = svgmap.choropleth_svg(features, {"AA": 0.3}, extent_excludes=())
    # Paths only: the legend carries a `NO_DATA` swatch of its own, so counting
    # every occurrence in the document would count the key as a region.
    fills = re.findall(r'<path [^>]*fill="(#[0-9a-f]{6})"', svg)
    assert fills.count(svgmap.NO_DATA) == 1
    assert len(fills) == 2


# --- the projection -------------------------------------------------------------

def test_north_is_up_and_east_is_right():
    """SVG counts y downwards and a projected northing counts up, so the flip is
    easy to get backwards - and a map of Europe upside down still renders."""
    features = [_square("S", 10, 40), _square("N", 10, 60), _square("E", 25, 50)]
    svg = svgmap.choropleth_svg(
        features, {"S": 1.0, "N": 1.0, "E": 1.0}, extent_excludes=()
    )
    import re

    first = {
        m.group(2): tuple(float(v) for v in m.group(1).split(","))
        for m in re.finditer(r'<path d="M([\d.,-]+)[^>]*><title>(\w+):', svg)
    }
    assert first["N"][1] < first["S"][1], "the northern square must be higher up"
    assert first["E"][0] > first["S"][0], "the eastern square must be further right"


def test_the_outermost_regions_do_not_set_the_viewport():
    """French Guiana is in South America. Letting it frame the picture is how a
    map of Europe ends up as a blue dot: measured on the GISCO file, the extent
    goes from 4,680 x 4,029 km to 12,850 x 9,486 km, 6.5 times the area.

    They are still DRAWN - the viewBox clips them - because dropping a region
    from a picture with no note reads as a region with nothing to report.
    """
    europe = [_square("DE111", 10, 50), _square("FR101", 2, 48)]
    guiana = _square("FRY30", -53, 4)
    svg = svgmap.choropleth_svg(
        europe + [guiana], {"DE111": 0.2, "FR101": 0.4, "FRY30": 0.9}
    )
    assert "FRY30" in svg, "still drawn, just outside the frame"
    import re

    xs = [
        float(m.group(1).split(",")[0])
        for m in re.finditer(r'<path d="M([\d.,-]+)', svg)
    ]
    # The two European squares stay inside the 900-wide viewport; Guiana does not.
    inside = [x for x in xs if 0 <= x <= 900]
    assert len(inside) == 2
    assert min(xs) < 0


def test_outermost_names_what_is_off_the_map():
    features = [_square("DE111", 10, 50), _square("FRY40", 55, -21),
                _square("ES703", -16, 28)]
    assert svgmap.outermost(features) == ["ES703", "FRY40"]


def test_ceuta_and_melilla_are_not_called_off_the_map():
    """They are in Africa and 15 km off the Spanish coast; measured on the real
    file they move the extent by nothing. Listing them would be a caption that is
    simply untrue."""
    assert not any(p in ("ES63", "ES64") for p in svgmap.OUTERMOST)
    assert svgmap.outermost([_square("ES630", -5, 35)]) == []


# --- degrading rather than failing ----------------------------------------------

def test_a_frame_of_only_outermost_regions_is_still_drawable():
    """A zoom on Reunion excludes everything from the viewport, which would leave
    no extent at all and divide by zero."""
    svg = svgmap.choropleth_svg([_square("FRY40", 55, -21)], {"FRY40": 0.5})
    assert "<path" in svg


def test_no_geometry_returns_an_empty_svg_rather_than_raising():
    svg = svgmap.choropleth_svg([], {})
    assert svg.startswith("<svg")
    assert "<path" not in svg


def test_a_hole_is_kept_as_a_ring():
    """An enclave dropped from its neighbour's polygon gets filled with that
    neighbour's colour, which states the wrong figure for real ground."""
    donut = {
        "type": "Feature",
        "properties": {"nuts_id": "AA"},
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [[0, 50], [4, 50], [4, 54], [0, 54], [0, 50]],
                [[1, 51], [2, 51], [2, 52], [1, 52], [1, 51]],
            ],
        },
    }
    svg = svgmap.choropleth_svg([donut], {"AA": 0.5}, extent_excludes=())
    assert svg.count(" Z") == 2, "both the outer ring and the hole"
    assert 'fill-rule="evenodd"' in svg


def test_a_percentage_is_labelled_as_one():
    features = [_square("AA", 4, 50), _square("BB", 6, 50)]
    svg = svgmap.choropleth_svg(
        features, {"AA": 0.1, "BB": 0.5}, percent=True, extent_excludes=()
    )
    assert "%" in svg
    assert "10.0%" in svg or "50.0%" in svg
