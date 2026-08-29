"""Groundings and lint, end to end.

Four scenes:

  1. Export the groundings document and show what it contains.
  2. Break it two ways — a renamed column and a rewritten definition — and
     watch SL007 catch both.
  3. Declare the naive join and watch SL009 reject it.
  4. Arm the contradictory external mapping and watch SL010 reject that.

Nothing here connects to a database. Every finding below is produced by
parsing, not by executing.

Run:  python run_example.py
"""

from __future__ import annotations

import copy
from pathlib import Path

import yaml

from semantido.exporters import to_groundings_dict, to_groundings_file
from semantido.generators.semantic_layer import Relationship
from semantido.lint import lint_layer

import models

OUT = Path(__file__).parent / "exports"
OUT.mkdir(exist_ok=True)

RULE = "-" * 74


def show(findings, *, only=None) -> None:
    rows = [f for f in findings if only is None or f.code in only]
    if not rows:
        print("  (clean)")
        return
    for f in rows:
        print(f"  {f.code} {f.severity.value:<7} {f.location}")
        for line in _wrap(f.message, 68):
            print(f"          {line}")


def _wrap(text: str, width: int) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return lines


def scene_1_groundings(layer) -> dict:
    print("\n1. THE GROUNDINGS DOCUMENT")
    print(RULE)
    to_groundings_file(layer, str(OUT / "groundings.yaml"))
    doc = to_groundings_dict(layer)
    print(yaml.safe_dump(doc, sort_keys=False).rstrip())
    print(
        "\n  This is a DERIVED artifact. It was authored implicitly, every "
        "time\n  a `_concept` attribute appeared on a column. Regenerating it "
        "is the\n  workflow; hand-editing it is a smell."
    )
    return doc


def scene_2_staleness(layer, doc: dict) -> None:
    print("\n2. SL007 — THE TWO WAYS A GROUNDING GOES STALE")
    print(RULE)

    # (a) migration that never updated the binding
    stale = copy.deepcopy(doc)
    cols = stale["groundings"]["counterparty.mifir"]["columns"]
    stale["groundings"]["counterparty.mifir"]["columns"] = [
        c.replace("market_cpty_lei", "mkt_cpty_lei_v2") for c in cols
    ]
    print("\n  (a) a column was renamed upstream, the binding was not:")
    show(lint_layer(layer, groundings=stale), only={"SL007"})

    # (b) meaning moved, binding did not follow
    drifted = copy.deepcopy(doc)
    drifted["groundings"]["counterparty.emir"]["definition_checksum"] = "deadbeefcafe"
    print("\n  (b) the definition was rewritten, the binding was not re-reviewed:")
    show(lint_layer(layer, groundings=drifted), only={"SL007"})

    print(
        "\n  Neither failure is visible anywhere else in the pipeline. The "
        "first\n  is a migration that outran its documentation; the second is "
        "meaning\n  drift, which no schema tool can see because the schema "
        "did not move."
    )


def scene_3_denotation(layer) -> None:
    print("\n3. SL009 — THE JOIN THAT RUNS AND ANSWERS THE WRONG QUESTION")
    print(RULE)
    layer.add_relationship(
        Relationship(
            from_table="emir_trade_report",
            to_table="mifir_transaction_report",
            join_condition=(
                "emir_trade_report.other_cpty_lei = "
                "mifir_transaction_report.market_cpty_lei"
            ),
            relationship_type="many_to_many",
            description="Naive counterparty join across the two regimes.",
        )
    )
    print(
        "\n  Both sides are LEIs. Both columns are VARCHAR(20). Both are "
        "called\n  'counterparty'. Both concepts share grain 'legal_entity', "
        "so SL008\n  has nothing to compare and stays silent:\n"
    )
    show(lint_layer(layer), only={"SL008", "SL009"})


def scene_4_contradiction() -> None:
    print("\n4. SL010 — A CONTRADICTION IN THE EXTERNAL MAPPINGS")
    print(RULE)
    layer = models.build_layer(contradictory=True)
    print(
        "\n  counterparty.mifir now claims exactMatch to the same FIBO node "
        "as\n  counterparty.emir. exactMatch is transitive, so this entails "
        "they\n  are interchangeable — which the DISTINCT_FROM edge denies:\n"
    )
    show(lint_layer(layer), only={"SL010"})


def main() -> None:
    layer = models.build_layer()
    print("=" * 74)
    print("GROUNDINGS AND LINT — semantido 0.5.3")
    print("=" * 74)

    doc = scene_1_groundings(layer)
    scene_2_staleness(layer, doc)
    scene_3_denotation(layer)
    scene_4_contradiction()

    print("\n" + RULE)
    print("Everything above ran with no database and no query execution.")
    print(RULE)


if __name__ == "__main__":
    main()
