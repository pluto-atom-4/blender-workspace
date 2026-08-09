"""Pivot manifest + drift checker for legged_robot_world.wbt (issue #54).

export_legged_robot_to_webots.py (issue #25 Phase 2) computes real
hip/knee/wheel pivot coordinates (`pivots_m`) and now writes them to a
machine-readable manifest, meshes/legged_robot_pivots.json (see that
script's own manifest-writing block), IN ADDITION to the pre-existing
stdout printout that a human hand-copies into
blender-project/physics/worlds/legged_robot_world.wbt's HingeJoint
`anchor`/endPoint Solid `translation` fields.

Nothing forces those hand-transcribed .wbt numbers to stay in sync with a
re-export if a leg-geometry constant in
model_dual_wheel_legged_robot_precise.py ever changes -- this module closes
that gap: it parses the relevant anchor/translation fields back out of
legged_robot_world.wbt and asserts they match the manifest within a tight
tolerance, failing loudly (nonzero exit + a printed diff of exactly which
field/side/joint drifted) if not.

Pure Python, no bpy dependency -- same posture as linkage_kinematics.py
(this subproject's numpy/scipy/pandas deps are available but unused here;
only stdlib re/json/dataclasses/pathlib/sys are needed).

Parsing strategy -- regex/field-position, not a real VRML97 grammar parser.
This is a deliberate choice (no VRML-parsing package is a dependency
anywhere in this repo, and legged_robot_world.wbt is one hand-authored,
tightly-controlled file, not arbitrary external VRML), not a fallback out
of laziness. Two independent regex passes over the raw text:

  1. Every `translation X Y Z` / `rotation ...` / `name "..."` triple (the
     6 mesh-bearing endPoint Solids: upper_link_{R,L}, lower_link_{R,L},
     wheel_{R,L}) -- one regex, one pass, captures all 6 in document order.
     Joint is derived from the name prefix (upper_link -> hip, lower_link
     -> knee, wheel -> wheel), side from the _R/_L suffix.
  2. Every `anchor X Y Z` line inside a HingeJointParameters block -- the
     word `anchor` is unambiguous in this file's vocabulary
     (boundingObject Transform blocks use `translation`, never `anchor`).
     There are exactly 4 (hip R/L, wheel R/L -- the knee is a rigid Solid,
     no HingeJoint, no anchor).

Because both regexes scan top-to-bottom and the file's nesting order is
hip -> (knee -> wheel) per side, R-block-then-L-block, the 4 anchors zip
POSITIONALLY onto the 4 hip-or-wheel entries filtered out of the 6 named
triples (same document order) -- not matched by line-number proximity, by
the stable sequence of which named triples belong to which joint.

Loud-fail guard against silent mis-mapping: parse_wbt_pivots() asserts
`len(named_triples) == 6` and `len(anchor_triples) == 4` before doing any
pairing, and raises ValueError (not a silent partial result) if either
count is off -- e.g. if a future hand-edit reorders
translation/rotation/name within a block, or adds/removes a joint, parsing
fails hard immediately instead of quietly mispairing values to the wrong
side/joint.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

# Absolute per-axis tolerance (values are O(0.01-0.05) m, so absolute, not
# relative -- same posture as this repo's other pytest.approx(..., abs=...)
# tolerances). Issue's own suggested figure.
PIVOT_TOLERANCE_M = 1e-6

DEFAULT_WBT_PATH = (
    Path(__file__).resolve().parents[1] / "physics" / "worlds" / "legged_robot_world.wbt"
)
DEFAULT_MANIFEST_PATH = (
    Path(__file__).resolve().parents[1]
    / "physics"
    / "worlds"
    / "meshes"
    / "legged_robot_pivots.json"
)

# name prefix -> joint key in the manifest/pivots dict
_JOINT_BY_NAME_PREFIX = {
    "upper_link": "hip",
    "lower_link": "knee",
    "wheel": "wheel",
}

# Joints that have BOTH a HingeJoint anchor and an endPoint Solid
# translation (hip, wheel). The knee is a plain rigid Solid (no HingeJoint),
# so it only ever has a translation to check.
_JOINTS_WITH_ANCHOR = {"hip", "wheel"}

_AXES = ("x", "y", "z")

_FLOAT = r"(-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)"

_NAMED_TRIPLE_RE = re.compile(
    r"translation\s+" + _FLOAT + r"\s+" + _FLOAT + r"\s+" + _FLOAT + r"\s*\n"
    r"\s*rotation\s+[^\n]+\n"
    r'\s*name\s+"([^"]+)"'
)

_ANCHOR_RE = re.compile(r"anchor\s+" + _FLOAT + r"\s+" + _FLOAT + r"\s+" + _FLOAT)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PivotDiff:
    side: str    # "R" | "L"
    joint: str   # "hip" | "knee" | "wheel"
    field: str   # "anchor" | "translation" | "anchor_vs_translation"
    axis: str    # "x" | "y" | "z"
    wbt_value: float
    manifest_value: float
    abs_diff: float


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def _side_and_joint_from_name(name: str) -> tuple[str, str]:
    for prefix, joint in _JOINT_BY_NAME_PREFIX.items():
        if name == f"{prefix}_R":
            return "R", joint
        if name == f"{prefix}_L":
            return "L", joint
    raise ValueError(
        f"Unrecognized endPoint Solid name {name!r} -- expected one of "
        f"{{upper_link,lower_link,wheel}}_{{R,L}}"
    )


def parse_wbt_pivots(wbt_text: str) -> dict:
    """Parse legged_robot_world.wbt's raw text into:

        {side: {'hip':   {'anchor': (x,y,z), 'translation': (x,y,z)},
                'knee':  {'translation': (x,y,z)},
                'wheel': {'anchor': (x,y,z), 'translation': (x,y,z)}}}

    Raises ValueError (loudly, not silently) if the expected exact counts
    of named triples (6) or anchors (4) aren't found -- see module
    docstring's "Loud-fail guard" section for why this matters.
    """
    named_matches = list(_NAMED_TRIPLE_RE.finditer(wbt_text))
    if len(named_matches) != 6:
        raise ValueError(
            f"Expected exactly 6 translation/rotation/name triples "
            f"(upper_link/lower_link/wheel x R/L), found {len(named_matches)}. "
            f"legged_robot_world.wbt's structure may have changed -- refusing "
            f"to guess a partial/mispaired mapping."
        )

    anchor_matches = list(_ANCHOR_RE.finditer(wbt_text))
    if len(anchor_matches) != 4:
        raise ValueError(
            f"Expected exactly 4 HingeJointParameters anchor fields "
            f"(hip/wheel x R/L), found {len(anchor_matches)}. "
            f"legged_robot_world.wbt's structure may have changed -- refusing "
            f"to guess a partial/mispaired mapping."
        )

    result: dict = {}
    named_triples = []  # [(side, joint, (x,y,z)), ...] in document order
    for m in named_matches:
        x, y, z, name = m.groups()
        side, joint = _side_and_joint_from_name(name)
        named_triples.append((side, joint, (float(x), float(y), float(z))))
        result.setdefault(side, {})[joint] = {"translation": (float(x), float(y), float(z))}

    # Anchors only belong to hip/wheel joints -- filter the same 6 named
    # triples down to the 4 that should have a matching anchor, in document
    # order, and zip them positionally onto the 4 parsed anchors.
    anchor_bearing = [t for t in named_triples if t[1] in _JOINTS_WITH_ANCHOR]
    if len(anchor_bearing) != len(anchor_matches):
        raise ValueError(
            f"Found {len(anchor_bearing)} hip/wheel named triples but "
            f"{len(anchor_matches)} anchors -- counts must match 1:1 for "
            f"positional pairing to be safe."
        )
    for (side, joint, _translation), anchor_m in zip(anchor_bearing, anchor_matches):
        ax, ay, az = anchor_m.groups()
        result[side][joint]["anchor"] = (float(ax), float(ay), float(az))

    return result


def load_manifest(manifest_path: str | Path = DEFAULT_MANIFEST_PATH) -> dict:
    """Read + validate the pivot manifest JSON, returning just the
    {side: {joint: (x, y, z)}} payload (the manifest's 'pivots' key)."""
    manifest_path = Path(manifest_path)
    with open(manifest_path) as f:
        data = json.load(f)

    if data.get("schema_version") != 1:
        raise ValueError(
            f"{manifest_path}: unknown schema_version {data.get('schema_version')!r} "
            f"(expected 1)"
        )
    if "pivots" not in data:
        raise ValueError(f"{manifest_path}: missing 'pivots' key")

    pivots = {}
    for side, joints in data["pivots"].items():
        pivots[side] = {joint: tuple(coords) for joint, coords in joints.items()}
    return pivots


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------

def compare_pivots(
    wbt_pivots: dict,
    manifest_pivots: dict,
    tol: float = PIVOT_TOLERANCE_M,
) -> list[PivotDiff]:
    """Pure data in/out (no file I/O) -- easy to unit-test with synthetic
    corruption.

    For hip/wheel joints: compares BOTH the wbt's 'anchor' and
    'translation' fields against the single manifest value, per axis; also
    emits an 'anchor_vs_translation' diff if the wbt's own anchor and
    translation disagree with each other beyond tol (an internal-
    consistency check, independent of the manifest, catching a different
    bug class than drift-from-manifest). For the knee: compares
    'translation' only (no anchor exists for a rigid, non-HingeJoint
    Solid).
    """
    diffs: list[PivotDiff] = []

    for side, joints in manifest_pivots.items():
        if side not in wbt_pivots:
            raise ValueError(f"Manifest has side {side!r} but .wbt has no such side")
        for joint, manifest_xyz in joints.items():
            if joint not in wbt_pivots[side]:
                raise ValueError(
                    f"Manifest has {side}/{joint} but .wbt has no such joint"
                )
            wbt_fields = wbt_pivots[side][joint]

            fields_to_check = ["translation"]
            if joint in _JOINTS_WITH_ANCHOR:
                fields_to_check.append("anchor")

            for field in fields_to_check:
                wbt_xyz = wbt_fields[field]
                for axis, wbt_v, manifest_v in zip(_AXES, wbt_xyz, manifest_xyz):
                    diff = abs(wbt_v - manifest_v)
                    if diff > tol:
                        diffs.append(
                            PivotDiff(
                                side=side,
                                joint=joint,
                                field=field,
                                axis=axis,
                                wbt_value=wbt_v,
                                manifest_value=manifest_v,
                                abs_diff=diff,
                            )
                        )

            if joint in _JOINTS_WITH_ANCHOR:
                anchor_xyz = wbt_fields["anchor"]
                translation_xyz = wbt_fields["translation"]
                for axis, a_v, t_v in zip(_AXES, anchor_xyz, translation_xyz):
                    diff = abs(a_v - t_v)
                    if diff > tol:
                        diffs.append(
                            PivotDiff(
                                side=side,
                                joint=joint,
                                field="anchor_vs_translation",
                                axis=axis,
                                wbt_value=a_v,
                                manifest_value=t_v,
                                abs_diff=diff,
                            )
                        )

    return diffs


# ---------------------------------------------------------------------------
# File-reading wrapper
# ---------------------------------------------------------------------------

def check_drift(
    wbt_path: str | Path = DEFAULT_WBT_PATH,
    manifest_path: str | Path = DEFAULT_MANIFEST_PATH,
    tol: float = PIVOT_TOLERANCE_M,
) -> list[PivotDiff]:
    """Parse both files and return the list of PivotDiffs (empty == no
    drift)."""
    wbt_text = Path(wbt_path).read_text()
    wbt_pivots = parse_wbt_pivots(wbt_text)
    manifest_pivots = load_manifest(manifest_path)
    return compare_pivots(wbt_pivots, manifest_pivots, tol=tol)


if __name__ == "__main__":
    diffs = check_drift()
    if diffs:
        print(f"PIVOT DRIFT DETECTED ({len(diffs)} field(s)):")
        for d in diffs:
            print(
                f"  {d.side}/{d.joint}/{d.field}.{d.axis}: "
                f"wbt={d.wbt_value} manifest={d.manifest_value} "
                f"diff={d.abs_diff:.9f} (tol={PIVOT_TOLERANCE_M})"
            )
        sys.exit(1)
    print(
        f"OK -- legged_robot_world.wbt pivots match "
        f"legged_robot_pivots.json within {PIVOT_TOLERANCE_M} m."
    )
    sys.exit(0)
