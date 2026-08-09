"""Unit + regression tests for legged_robot_pivot_drift.py (issue #54).

Pure text/data parsing, no Blender/bpy/Webots dependency. Mirrors
test_linkage_kinematics.py's/test_lqr_tuner.py's existing
`sys.path.insert(0, str(Path(__file__).resolve().parents[1]))` + direct-
import pattern in this same orchestration subproject.

Three groups, per the issue #54 architect's plan:
  1. Parser unit tests (parse_wbt_pivots) against a minimal embedded
     VRML97-shaped fixture, plus malformed-input tests exercising the
     loud-fail count guards.
  2. compare_pivots unit tests against synthetic in-memory dicts
     (identical data / a perturbed manifest value / a deliberately
     mismatched wbt anchor-vs-translation / an exact-tolerance-boundary
     value).
  3. An end-to-end regression test against the REAL committed
     legged_robot_world.wbt + legged_robot_pivots.json (the actual drift
     gate the issue wants wired into CI) -- deliberately not skip-marked;
     a missing file should FileNotFoundError loudly, matching this repo's
     convention elsewhere (see test_lqr_tuner.py's own separation of
     "needs the real webots binary" into out-of-scope rather than a silent
     skip).
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from legged_robot_pivot_drift import (  # noqa: E402
    PIVOT_TOLERANCE_M,
    PivotDiff,
    check_drift,
    compare_pivots,
    load_manifest,
    parse_wbt_pivots,
)

# ---------------------------------------------------------------------------
# Group 1: parser unit tests
# ---------------------------------------------------------------------------

# Minimal VRML97-shaped fixture: one hip HingeJoint + nested knee Solid +
# nested wheel HingeJoint, for BOTH sides (6 named translation/rotation/name
# triples, 4 anchors total) -- enough to exercise the 3-line pattern and the
# anchor extraction/pairing without depending on the real file's current
# numbers. Deliberately does not include boundingObject/physics/device
# blocks -- parse_wbt_pivots() doesn't look at those.
VALID_WBT_FIXTURE = """
HingeJoint {
  jointParameters HingeJointParameters {
    axis 1 0 0
    anchor 0.05 -0.038 0.02
  }
  endPoint Solid {
    translation 0.05 -0.038 0.02
    rotation 0 0 1 0
    name "upper_link_R"
    children [
      Solid {
        translation 0.0 0.0035 -0.04
        rotation 0 0 1 0
        name "lower_link_R"
        children [
          HingeJoint {
            jointParameters HingeJointParameters {
              axis 1 0 0
              anchor 0.022 0.0 -0.04
            }
            endPoint Solid {
              translation 0.022 0.0 -0.04
              rotation 0 0 1 0
              name "wheel_R"
            }
          }
        ]
      }
    ]
  }
}
HingeJoint {
  jointParameters HingeJointParameters {
    axis 1 0 0
    anchor -0.05 -0.038 0.02
  }
  endPoint Solid {
    translation -0.05 -0.038 0.02
    rotation 0 0 1 0
    name "upper_link_L"
    children [
      Solid {
        translation 0.0 0.0035 -0.04
        rotation 0 0 1 0
        name "lower_link_L"
        children [
          HingeJoint {
            jointParameters HingeJointParameters {
              axis 1 0 0
              anchor -0.022 0.0 -0.04
            }
            endPoint Solid {
              translation -0.022 0.0 -0.04
              rotation 0 0 1 0
              name "wheel_L"
            }
          }
        ]
      }
    ]
  }
}
"""

# Everything up to (not including) the "L" HingeJoint block -- only 3 named
# triples / 2 anchors, exercising the "6 named triples" loud-fail guard.
INCOMPLETE_WBT_FIXTURE = VALID_WBT_FIXTURE.split('HingeJoint {\n  jointParameters HingeJointParameters {\n    axis 1 0 0\n    anchor -0.05')[0]


def test_parse_wbt_pivots_extracts_all_six_joints_both_sides():
    pivots = parse_wbt_pivots(VALID_WBT_FIXTURE)

    assert set(pivots.keys()) == {"R", "L"}
    assert set(pivots["R"].keys()) == {"hip", "knee", "wheel"}
    assert set(pivots["L"].keys()) == {"hip", "knee", "wheel"}


def test_parse_wbt_pivots_hip_and_wheel_have_anchor_and_translation():
    pivots = parse_wbt_pivots(VALID_WBT_FIXTURE)

    assert pivots["R"]["hip"]["translation"] == pytest.approx((0.05, -0.038, 0.02))
    assert pivots["R"]["hip"]["anchor"] == pytest.approx((0.05, -0.038, 0.02))
    assert pivots["R"]["wheel"]["translation"] == pytest.approx((0.022, 0.0, -0.04))
    assert pivots["R"]["wheel"]["anchor"] == pytest.approx((0.022, 0.0, -0.04))

    assert pivots["L"]["hip"]["translation"] == pytest.approx((-0.05, -0.038, 0.02))
    assert pivots["L"]["hip"]["anchor"] == pytest.approx((-0.05, -0.038, 0.02))
    assert pivots["L"]["wheel"]["translation"] == pytest.approx((-0.022, 0.0, -0.04))
    assert pivots["L"]["wheel"]["anchor"] == pytest.approx((-0.022, 0.0, -0.04))


def test_parse_wbt_pivots_knee_has_translation_only_no_anchor():
    pivots = parse_wbt_pivots(VALID_WBT_FIXTURE)

    assert pivots["R"]["knee"]["translation"] == pytest.approx((0.0, 0.0035, -0.04))
    assert "anchor" not in pivots["R"]["knee"]
    assert pivots["L"]["knee"]["translation"] == pytest.approx((0.0, 0.0035, -0.04))
    assert "anchor" not in pivots["L"]["knee"]


def test_parse_wbt_pivots_raises_on_wrong_named_triple_count():
    """Only the R side is present (3 named triples, not 6) -- must fail
    loudly (ValueError), not silently return a partial/mispaired result."""
    with pytest.raises(ValueError, match="6 translation/rotation/name"):
        parse_wbt_pivots(INCOMPLETE_WBT_FIXTURE)


def test_parse_wbt_pivots_raises_on_wrong_anchor_count():
    """All 6 named triples present, but one anchor line removed -- must
    fail loudly (ValueError), not silently mispair the remaining anchors."""
    mutated = VALID_WBT_FIXTURE.replace("anchor -0.022 0.0 -0.04\n", "", 1)
    with pytest.raises(ValueError, match="4 HingeJointParameters anchor"):
        parse_wbt_pivots(mutated)


# ---------------------------------------------------------------------------
# Group 2: compare_pivots unit tests (synthetic in-memory dicts)
# ---------------------------------------------------------------------------

def _synthetic_wbt_pivots():
    return {
        "R": {
            "hip": {"anchor": (0.05, -0.038, 0.02), "translation": (0.05, -0.038, 0.02)},
            "knee": {"translation": (0.0, 0.0035, -0.04)},
            "wheel": {"anchor": (0.022, 0.0, -0.04), "translation": (0.022, 0.0, -0.04)},
        },
        "L": {
            "hip": {"anchor": (-0.05, -0.038, 0.02), "translation": (-0.05, -0.038, 0.02)},
            "knee": {"translation": (0.0, 0.0035, -0.04)},
            "wheel": {"anchor": (-0.022, 0.0, -0.04), "translation": (-0.022, 0.0, -0.04)},
        },
    }


def _synthetic_manifest_pivots():
    return {
        "R": {"hip": (0.05, -0.038, 0.02), "knee": (0.0, 0.0035, -0.04), "wheel": (0.022, 0.0, -0.04)},
        "L": {"hip": (-0.05, -0.038, 0.02), "knee": (0.0, 0.0035, -0.04), "wheel": (-0.022, 0.0, -0.04)},
    }


def test_compare_pivots_identical_data_yields_no_diffs():
    diffs = compare_pivots(_synthetic_wbt_pivots(), _synthetic_manifest_pivots())
    assert diffs == []


def test_compare_pivots_manifest_perturbation_on_knee_yields_exactly_one_diff():
    """Knee only has a 'translation' field (no anchor -- rigid Solid, not a
    HingeJoint), so perturbing its manifest value is the clean single-field
    case: exactly one PivotDiff, right side/joint/field/axis, abs_diff
    matching the perturbation exactly."""
    manifest = _synthetic_manifest_pivots()
    x, y, z = manifest["R"]["knee"]
    manifest["R"]["knee"] = (x + 0.01, y, z)

    diffs = compare_pivots(_synthetic_wbt_pivots(), manifest)

    assert len(diffs) == 1
    d = diffs[0]
    assert (d.side, d.joint, d.field, d.axis) == ("R", "knee", "translation", "x")
    assert d.abs_diff == pytest.approx(0.01)


def test_compare_pivots_manifest_perturbation_on_hip_yields_two_diffs():
    """Deviation from the architect's plan (documented, not silent -- see
    PR description): the plan's own compare_pivots spec (section 3) says
    hip/wheel joints compare BOTH 'anchor' and 'translation' independently
    against the single manifest value. Since this synthetic fixture's wbt
    anchor and translation start identical, perturbing the manifest at
    R/hip/x necessarily drifts BOTH fields away from the manifest, so two
    PivotDiffs are produced (one per field), not the one the plan's
    illustrative example describes -- that example undercounts given the
    dual-field-check design the same plan specifies."""
    manifest = _synthetic_manifest_pivots()
    x, y, z = manifest["R"]["hip"]
    manifest["R"]["hip"] = (x + 0.01, y, z)

    diffs = compare_pivots(_synthetic_wbt_pivots(), manifest)

    assert len(diffs) == 2
    fields = {d.field for d in diffs}
    assert fields == {"translation", "anchor"}
    for d in diffs:
        assert (d.side, d.joint, d.axis) == ("R", "hip", "x")
        assert d.abs_diff == pytest.approx(0.01)


def test_compare_pivots_anchor_vs_translation_mismatch_fires():
    """wbt's own anchor and translation deliberately disagree with each
    other (independent of the manifest, which matches translation) --
    the anchor_vs_translation self-consistency diff must fire."""
    wbt = _synthetic_wbt_pivots()
    ax, ay, az = wbt["R"]["hip"]["anchor"]
    wbt["R"]["hip"]["anchor"] = (ax + 0.02, ay, az)  # drift anchor away from translation

    diffs = compare_pivots(wbt, _synthetic_manifest_pivots())

    consistency_diffs = [d for d in diffs if d.field == "anchor_vs_translation"]
    assert len(consistency_diffs) == 1
    d = consistency_diffs[0]
    assert (d.side, d.joint, d.axis) == ("R", "hip", "x")
    assert d.abs_diff == pytest.approx(0.02)


def test_compare_pivots_within_tolerance_boundary_yields_no_diff():
    """A value perturbed by exactly PIVOT_TOLERANCE_M / 2 (i.e. comfortably
    inside the tolerance) must NOT be flagged -- proves the comparison
    isn't off-by-one/inverted (e.g. >= instead of >)."""
    manifest = _synthetic_manifest_pivots()
    x, y, z = manifest["R"]["knee"]
    manifest["R"]["knee"] = (x + PIVOT_TOLERANCE_M / 2.0, y, z)

    diffs = compare_pivots(_synthetic_wbt_pivots(), manifest)

    assert diffs == []


def test_compare_pivots_diff_is_a_pivotdiff_dataclass_instance():
    manifest = _synthetic_manifest_pivots()
    x, y, z = manifest["R"]["knee"]
    manifest["R"]["knee"] = (x + 0.01, y, z)

    diffs = compare_pivots(_synthetic_wbt_pivots(), manifest)

    assert len(diffs) == 1
    assert isinstance(diffs[0], PivotDiff)


# ---------------------------------------------------------------------------
# Group 3: end-to-end regression test against the real committed files
# ---------------------------------------------------------------------------

def test_real_legged_robot_world_has_no_pivot_drift():
    """Regression guard: the committed legged_robot_world.wbt's
    anchor/translation fields must match the committed
    legged_robot_pivots.json manifest exactly (within tolerance) today. If
    this ever fails, either the .wbt was hand-edited without re-running the
    exporter, or the exporter's geometry changed and the .wbt wasn't
    regenerated/re-synced -- see WEBOTS.md."""
    diffs = check_drift()
    assert diffs == []


def test_load_manifest_returns_expected_shape_for_real_manifest():
    """Sanity check the real manifest parses to the documented shape (not a
    strict value pin -- test_real_legged_robot_world_has_no_pivot_drift()
    above is the actual regression gate on values)."""
    pivots = load_manifest()

    assert set(pivots.keys()) == {"R", "L"}
    for side in ("R", "L"):
        assert set(pivots[side].keys()) == {"hip", "knee", "wheel"}
        for joint in ("hip", "knee", "wheel"):
            assert len(pivots[side][joint]) == 3
