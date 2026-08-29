"""One instrument, three grains, twelve rows.

Reproduces the Vodafone fan-out from the v0.5 release article as a computation
rather than a claim: the matrix is derived from the fixture below, not typed
out. Then points the linter at two joins and shows which one it catches.

The uncomfortable result is scene 3. The join that destroys the reconciliation
is the one the linter is silent on.

Run:  python run_example.py
"""

from __future__ import annotations

from decimal import Decimal
from itertools import product
from pathlib import Path

from semantido.exporters import to_groundings_file, to_markdown_file
from semantido.generators.semantic_layer import Relationship
from semantido.lint import lint_layer

import models

OUT = Path(__file__).parent / "exports"
OUT.mkdir(exist_ok=True)

RULE = "-" * 78
VOD = "GB00BH4HKS39"

# Vodafone Group plc ordinary shares as each source counts it.
# Prices are the venue's own quote convention: XLON in pence, XETR/XMIL in EUR.
BLOOMBERG = [
    ("BBG00B2VFT35", "XLON", Decimal("74.82")),
    ("BBG00KDBWTF1", "XETR", Decimal("0.87")),
    ("BBG00LMR8QT4", "XMIL", Decimal("0.87")),
]
REFINITIV = [
    ("VOD.L", "XLON", Decimal("74.82")),
    ("VOD.MI", "XMIL", Decimal("0.87")),
    ("VODl.CHI", "CHIX", Decimal("74.80")),
    ("VODl.DE", "XETR", Decimal("0.87")),
]


def classify(b_venue, b_px, r_venue, r_px) -> str:
    if b_venue == r_venue:
        return "MEANINGFUL"
    return "FALSE PASS" if b_px == r_px else "FALSE BREAK"


def scene_1_counting() -> None:
    print("\n1. ONE INSTRUMENT, COUNTED AT EACH GRAIN")
    print(RULE)
    print(f"\n  ISIN {VOD} — Vodafone Group plc ordinary shares\n")
    print("    issue grain   (ANNA register rows) : 1")
    print(f"    listing grain (Bloomberg FIGIs)    : {len(BLOOMBERG)}")
    print(f"    listing grain (Refinitiv RICs)     : {len(REFINITIV)}")
    print(
        "\n  These are not synonyms. They are three different questions with "
        "three\n  different answers, and the schema records all three in "
        "VARCHAR columns."
    )


def scene_2_fanout() -> None:
    print("\n2. THE JOIN A COMPETENT ENGINEER WRITES")
    print(RULE)
    print("\n  SELECT ... FROM bloomberg_feed b")
    print("  JOIN refinitiv_feed r ON b.isin = r.isin\n")

    rows = []
    for (bf, bv, bp), (rc, rv, rp) in product(BLOOMBERG, REFINITIV):
        rows.append((bf, bv, bp, rc, rv, rp, classify(bv, bp, rv, rp)))

    print(
        f"  {'FIGI':<14}{'venue':<7}{'px':>7}   "
        f"{'RIC':<10}{'venue':<7}{'px':>7}  {'classification'}"
    )
    print("  " + "-" * 74)
    for bf, bv, bp, rc, rv, rp, kind in rows:
        print(f"  {bf:<14}{bv:<7}{bp:>7}   {rc:<10}{rv:<7}{rp:>7}  {kind}")

    tally = {}
    for r in rows:
        tally[r[6]] = tally.get(r[6], 0) + 1
    print()
    for kind in ("FALSE BREAK", "FALSE PASS", "MEANINGFUL"):
        print(f"    {tally.get(kind, 0):>3}  {kind}")
    signal = tally.get("MEANINGFUL", 0) / len(rows)
    print(
        f"\n  {len(rows)} rows for 1 instrument. signal: "
        f"{tally.get('MEANINGFUL', 0)}/{len(rows)} = {signal:.0%}"
    )
    print(
        "\n  ISIN is not a key on either side. It is an issue-grain value "
        "repeated\n  once per listing, so the equi-join emits every matching "
        "pair. The\n  reconciliation wanted the diagonal; it computed the "
        "whole matrix."
    )


def scene_3_decay() -> None:
    print("\n3. IT GETS WORSE WITH COVERAGE")
    print(RULE)
    print(f"\n  {'BBG':>5}{'RTR':>6}{'rows':>8}{'useful':>8}{'noise':>8}{'signal':>9}")
    for b, r in ((3, 4), (5, 6), (8, 11), (12, 15)):
        rows = b * r
        useful = min(b, r)
        print(
            f"  {b:>5}{r:>6}{rows:>8}{useful:>8}{rows - useful:>8}{useful / rows:>8.0%}"
        )
    print(
        "\n  Every venue either vendor adds makes the reconciliation worse. "
        "Nobody\n  notices, because the breaks look like data quality issues "
        "and get\n  worked by hand."
    )


def scene_4_lint(layer) -> None:
    print("\n4. WHAT THE LINTER CATCHES — AND WHAT IT DOES NOT")
    print(RULE)

    layer.add_relationship(
        Relationship(
            from_table="bloomberg_feed",
            to_table="refinitiv_feed",
            join_condition="bloomberg_feed.figi = refinitiv_feed.ric",
            relationship_type="many_to_many",
            description="Cross-vendor listing identifier join.",
        )
    )
    layer.add_relationship(
        Relationship(
            from_table="bloomberg_feed",
            to_table="refinitiv_feed",
            join_condition="bloomberg_feed.isin = refinitiv_feed.ric",
            relationship_type="many_to_many",
            description="Issue identifier joined to a listing identifier.",
        )
    )
    layer.add_relationship(
        Relationship(
            from_table="bloomberg_feed",
            to_table="refinitiv_feed",
            join_condition="bloomberg_feed.isin = refinitiv_feed.isin",
            relationship_type="many_to_many",
            description="The reconciliation join from scene 2.",
        )
    )

    findings = lint_layer(layer)
    grain = [f for f in findings if f.code in {"SL008", "SL009"}]
    print()
    if grain:
        for f in grain:
            print(f"  {f.code} {f.severity.value:<7} {f.location}")
    else:
        print("  (no join findings)")

    print(f"\n  {'join':<34}{'grains':<24}{'lint':<9}{'rows'}")
    print("  " + "-" * 74)
    print(
        f"  {'figi = ric':<34}{'listing vs listing':<24}{'silent':<9}{'0 (no overlap)'}"
    )
    print(f"  {'isin = ric':<34}{'issue vs listing':<24}{'fires':<9}{'0 (empty set)'}")
    print(f"  {'isin = isin':<34}{'issue vs issue':<24}{'silent':<9}{'12 (fan-out)'}")
    print(
        "\n  The check fires on the join that returns nothing and stays "
        "silent on\n  the join that returns twelve wrong rows. A grain "
        "MISMATCH implies\n  different value spaces, so it is loud and cheap "
        "to fix. The fan-out\n  needs the same concept on both sides, which "
        "is exactly the case the\n  grain check cannot see.\n\n  Cardinality "
        "is the missing axis. Grain as a single string cannot\n  express it; "
        "it needs the tuple that makes a row unique."
    )


def main() -> None:
    layer = models.build_layer()
    print("=" * 78)
    print("SECURITY MASTER — GRAIN, FAN-OUT, AND THE LIMITS OF STATIC CHECKS")
    print("semantido 0.5.3")
    print("=" * 78)

    scene_1_counting()
    scene_2_fanout()
    scene_3_decay()
    scene_4_lint(layer)

    to_markdown_file(layer, str(OUT / "secmaster.semantic.md"))
    to_groundings_file(layer, str(OUT / "groundings.yaml"))
    print("\n" + RULE)
    print(f"exports written to {OUT.name}/")
    print(RULE)


if __name__ == "__main__":
    main()
