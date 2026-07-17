"""Toolchain-drift experiment: one glossary, two derivation stacks.

Conditions reconcile the authored and generated registries:

  C1  name-normalized matching (strip dim_/m_ prefixes, underscores) —
      how tool integrations reconcile catalogs today
  C2  anchor alignment: experiment 04's align(), reused verbatim
  C3  C2 + three corroborations:
        checksum   definition_checksum disagreement -> NEEDS_REVIEW
        asymmetry  relation differs across sides for same anchor ->
                   INFLATION_SUSPECTED (the generated exact vs authored
                   narrower case)
        collision  one generated concept aligned to two authored
                   concepts that are DISTINCT_FROM each other -> CONFLICT

Ground truth is free: both stacks derive from one glossary, so every
authored concept has exactly one correct generated twin (or a known
merge under granularity_merge). Scored per mutation per condition:
DETECTED (flagged the injected fault) / BLIND / plus identity recall.

Run:  python run_experiment.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "04_federated_agents"))


class _Tee:
    """Duplicates stdout to a report file next to the script."""

    def __init__(self, *streams):
        self.streams = streams

    def write(self, text):
        for stream in self.streams:
            stream.write(text)

    def flush(self):
        for stream in self.streams:
            stream.flush()


_REPORT = open(
    Path(__file__).parent / "results" / "experiment_output.txt", "w", encoding="utf-8"
)
sys.stdout = _Tee(sys.__stdout__, _REPORT)


from alignment import SUBSTITUTABLE, Verdict, align  # reused from ex. 04
from authored_stack import GLOSSARY, build_authored_registry
from sml_bridge import Mutations, build_generated_registry
from semantido.concepts import ConceptRelation

AUTHORED = build_authored_registry()


def _norm(concept_id: str) -> str:
    for prefix in ("dim_", "m_"):
        if concept_id.startswith(prefix):
            concept_id = concept_id[len(prefix) :]
    return concept_id.replace("_", " ")


# ------------------------------------------------------------------ #
# Conditions: each returns (matches: dict authored->generated,
#                           flags: list[str])
# ------------------------------------------------------------------ #
def condition_c1(generated):
    matches, flags = {}, []
    for a_id in AUTHORED.concepts:
        for g_id in generated.concepts:
            if _norm(a_id) == _norm(g_id) or _norm(a_id) in _norm(g_id):
                matches[a_id] = g_id
                break
    return matches, flags


def condition_c2(generated):
    matches, flags = {}, []
    table = align(AUTHORED, generated)
    for (a_id, g_id), item in table.items():
        if item.verdict in SUBSTITUTABLE:
            matches[a_id] = g_id
        elif item.verdict is Verdict.CANDIDATE_REVERIFY:
            flags.append(f"REVERIFY {a_id}<->{g_id}: {item.reasons[-1]}")
        elif item.verdict is Verdict.RELATED_NOT_SUBSTITUTABLE:
            flags.append(f"NOT_SUBSTITUTABLE {a_id}<->{g_id}")
    return matches, flags


def condition_c3(generated):
    matches, flags = condition_c2(generated)
    table = align(AUTHORED, generated)

    for (a_id, g_id), item in table.items():
        concept_a = AUTHORED.concepts[a_id]
        concept_g = generated.concepts[g_id]

        # Identity-by-checksum rescue: anchors alone cannot distinguish
        # "same narrow concept twice" from "two narrow siblings" under a
        # shared broader anchor. Same anchor + SAME relation on both
        # sides + same definition checksum corroborates identity where
        # the sibling rule correctly refused to.
        if (
            item.verdict is Verdict.RELATED_NOT_SUBSTITUTABLE
            and a_id not in matches
            and concept_a.definition_checksum == concept_g.definition_checksum
            and any(
                ma.target == mg.target and ma.relation is mg.relation
                for ma in concept_a.mappings
                for mg in concept_g.mappings
            )
        ):
            matches[a_id] = g_id
            flags.append(
                f"IDENTITY_BY_CHECKSUM {a_id}<->{g_id}: sibling verdict "
                "overridden — same anchor, same relation, same definition"
            )

        # checksum corroboration on anything bridged at all
        if concept_a.definition_checksum != concept_g.definition_checksum:
            flags.append(
                f"NEEDS_REVIEW {a_id}<->{g_id}: definition checksum "
                f"mismatch ({concept_a.definition_checksum} vs "
                f"{concept_g.definition_checksum}) — text diverged from "
                "the shared source"
            )

        # relation asymmetry per shared anchor
        for map_a in concept_a.mappings:
            for map_g in concept_g.mappings:
                if (
                    map_a.target == map_g.target
                    and map_a.relation is not map_g.relation
                ):
                    flags.append(
                        f"INFLATION_SUSPECTED {a_id}<->{g_id}: authored "
                        f"says {map_a.relation.value}, generated says "
                        f"{map_g.relation.value} for {map_a.target} — "
                        "generated side likely defaulted to equivalence"
                    )

    # distinct_from collision: one generated id bridging two authored
    # concepts that must never be conflated
    bridged_by_gen: dict[str, list[str]] = {}
    for a_id, g_id in table:
        bridged_by_gen.setdefault(g_id, []).append(a_id)
    for g_id, a_ids in bridged_by_gen.items():
        for i, first in enumerate(a_ids):
            for second in a_ids[i + 1 :]:
                if (
                    ConceptRelation.DISTINCT_FROM,
                    second,
                ) in AUTHORED.concepts[first].relations:
                    flags.append(
                        f"CONFLICT {g_id}: bridges both {first} and "
                        f"{second}, which are DISTINCT_FROM — the "
                        "generator merged legally distinct senses"
                    )
    return matches, flags


CONDITIONS = [
    ("C1 name-normalized", condition_c1),
    ("C2 anchor alignment", condition_c2),
    ("C3 anchors+corroboration", condition_c3),
]

RUNS = [
    Mutations(),
    Mutations(id_rename=True),
    Mutations(definition_paraphrase=True),
    Mutations(stale_pin=True),
    Mutations(equivalence_inflation=True),
    Mutations(granularity_merge=True),
]

#: What counts as detecting each mutation: a flag containing the marker.
DETECTION_MARKER = {
    "definition_paraphrase": "checksum",
    "stale_pin": "pin mismatch",
    "equivalence_inflation": "INFLATION_SUSPECTED",
    "granularity_merge": "CONFLICT",
}


def main():
    anchored_terms = [t for t, spec in GLOSSARY["terms"].items() if spec.get("anchors")]

    print("=" * 74)
    print("EXPERIMENT 05: one glossary, two toolchains (authored vs generated)")
    print("=" * 74)

    matrix: dict[str, dict[str, str]] = {}
    recall: dict[str, dict[str, str]] = {}

    for mutations in RUNS:
        run = mutations.label()
        generated = build_generated_registry(mutations)
        print(f"\nRUN: {run}")
        for cond_name, cond in CONDITIONS:
            matches, flags = cond(generated)
            found = sum(1 for t in anchored_terms if t in matches)
            recall.setdefault(cond_name, {})[run] = f"{found}/{len(anchored_terms)}"
            marker = DETECTION_MARKER.get(run)
            if marker is not None:
                detected = any(marker in f for f in flags)
                matrix.setdefault(cond_name, {})[run] = (
                    "DETECTED" if detected else "BLIND"
                )
            print(
                f"  [{cond_name}] identity {found}/{len(anchored_terms)}"
                f"  flags: {len(flags)}"
            )
            for flag in flags[:3]:
                print(f"      - {flag}")

    print("\n" + "=" * 74)
    print("DRIFT DETECTION MATRIX (per injected fault)")
    print("=" * 74)
    faults = list(DETECTION_MARKER)
    print(f"{'condition':28s}" + "".join(f"{f[:18]:>20s}" for f in faults))
    for cond_name, _ in CONDITIONS:
        row = matrix.get(cond_name, {})
        print(f"{cond_name:28s}" + "".join(f"{row.get(f, '—'):>20s}" for f in faults))

    print("\nIDENTITY RECALL (anchored terms recovered as same)")
    print(f"{'condition':28s}" + "".join(f"{m.label()[:18]:>20s}" for m in RUNS[:3]))
    for cond_name, _ in CONDITIONS:
        row = recall[cond_name]
        print(f"{cond_name:28s}" + "".join(f"{row[m.label()]:>20s}" for m in RUNS[:3]))

    print(
        "\nReading: C1 survives renames it can guess and nothing it can't;\n"
        "C2 recovers identity through anchors regardless of naming but is\n"
        "structurally blind to definition drift and relation inflation;\n"
        "C3 buys detection of every injected fault at the price of review\n"
        "queues. The anchorless term (trade_report) is invisible to C2/C3\n"
        "by construction — anchor alignment cannot see what was never\n"
        "mapped, which is the honest limit of the rendezvous mechanism."
    )


if __name__ == "__main__":
    main()
