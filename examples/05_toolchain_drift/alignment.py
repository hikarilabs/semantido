"""Cross-registry concept alignment via shared external anchors.

Two registries never talk to each other; a consumer holding both computes
candidate alignments from their outward mappings. The rules, in order of
application per shared anchor (same source namespace AND same target):

1. Pin gate — if the two registries pin different versions of the anchor
   source, the anchor itself may have shifted: verdict is capped at
   CANDIDATE_REVERIFY regardless of relation types.
2. Sibling rule — if BOTH mappings are NARROWER than the anchor, the two
   concepts are siblings under a broader notion and may be disjoint
   (the EMIR/MiFIR counterparty case): RELATED_NOT_SUBSTITUTABLE.
3. Weakest-link composition — otherwise the verdict strength is the
   weaker of the two relations: exact∘exact = ALIGNED_EXACT,
   anything involving close = ALIGNED_CLOSE, anything involving a
   hierarchy relation = RELATED_NOT_SUBSTITUTABLE.

No shared anchor at all: NO_BRIDGE. The strongest verdict across all
shared anchors wins, but reasons for every considered anchor are kept —
an alignment claim you cannot inspect is a similarity score with extra
steps.
"""

from dataclasses import dataclass, field
from enum import IntEnum

from semantido.concepts import ConceptRegistry, MappingRelation


class Verdict(IntEnum):
    """Alignment strength, ordered so max() picks the strongest."""

    NO_BRIDGE = 0
    RELATED_NOT_SUBSTITUTABLE = 1
    CANDIDATE_REVERIFY = 2
    ALIGNED_CLOSE = 3
    ALIGNED_EXACT = 4


#: Verdicts an agent may treat as substitutable without a human in the loop.
SUBSTITUTABLE = {Verdict.ALIGNED_EXACT, Verdict.ALIGNED_CLOSE}


@dataclass
class Alignment:
    """One concept-pair alignment with full provenance."""

    concept_a: str
    concept_b: str
    verdict: Verdict
    reasons: list[str] = field(default_factory=list)


def _compose(rel_a: MappingRelation, rel_b: MappingRelation) -> Verdict:
    exactish = {MappingRelation.EXACT_MATCH, MappingRelation.CLOSE_MATCH}
    if rel_a not in exactish or rel_b not in exactish:
        return Verdict.RELATED_NOT_SUBSTITUTABLE
    if rel_a is rel_b is MappingRelation.EXACT_MATCH:
        return Verdict.ALIGNED_EXACT
    return Verdict.ALIGNED_CLOSE


def align(
    registry_a: ConceptRegistry, registry_b: ConceptRegistry
) -> dict[tuple[str, str], Alignment]:
    """Computes all concept-pair alignments between two registries.

    Returns:
        dict: (concept_id_a, concept_id_b) -> Alignment, for every pair
        that shares at least one anchor, plus NO_BRIDGE entries omitted.
    """
    results: dict[tuple[str, str], Alignment] = {}

    for id_a, concept_a in registry_a.concepts.items():
        for id_b, concept_b in registry_b.concepts.items():
            best = Verdict.NO_BRIDGE
            reasons: list[str] = []

            for map_a in concept_a.mappings:
                src_a = registry_a.sources[map_a.source]
                for map_b in concept_b.mappings:
                    src_b = registry_b.sources[map_b.source]
                    if (
                        src_a.namespace != src_b.namespace
                        or map_a.target != map_b.target
                    ):
                        continue

                    anchor = f"{src_a.namespace}#{map_a.target}"

                    # Base verdict from relation semantics first: the
                    # sibling objection is *semantic* and survives any
                    # re-pinning, so it must not be shadowed by the
                    # (weaker, operational) pin objection.
                    if (
                        map_a.relation
                        is map_b.relation
                        is MappingRelation.NARROWER
                    ):
                        verdict = Verdict.RELATED_NOT_SUBSTITUTABLE
                        reasons.append(
                            f"{anchor}: both narrower than the anchor — "
                            "siblings under a broader notion, possibly "
                            "disjoint"
                        )
                    else:
                        verdict = _compose(map_a.relation, map_b.relation)
                        reasons.append(
                            f"{anchor}: {map_a.relation.value} ∘ "
                            f"{map_b.relation.value} -> {verdict.name}"
                        )

                    # Pin mismatch caps the verdict: it can weaken an
                    # exact bridge to a candidate, never strengthen a
                    # semantic objection.
                    if src_a.version != src_b.version:
                        verdict = min(verdict, Verdict.CANDIDATE_REVERIFY)
                        reasons.append(
                            f"{anchor}: pin mismatch "
                            f"({src_a.version} vs {src_b.version}) — "
                            "capped at CANDIDATE_REVERIFY"
                        )

                    best = max(best, verdict)

            if best is not Verdict.NO_BRIDGE:
                results[(id_a, id_b)] = Alignment(
                    concept_a=id_a,
                    concept_b=id_b,
                    verdict=best,
                    reasons=reasons,
                )

    return results
