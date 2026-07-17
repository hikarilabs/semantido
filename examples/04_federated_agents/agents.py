"""Agents answering cross-institution requests against a semantic layer.

One agent per institution. A request arrives in the ASKING institution's
vocabulary; the ANSWERING agent must ground each requested term in its
own schema, run the query, and return rows plus provenance. Three
resolution strategies — the experiment's independent variable:

* LexicalResolver     (condition 1): substring match on column names.
                      What "just let the LLMs talk" degrades to.
* SemanticResolver    (condition 2): match on the semantic layer's
                      labels, synonyms, and descriptions. Better — and
                      exactly where the homonym trap snaps shut, because
                      both institutions call legally distinct things
                      "counterparty".
* ConceptResolver     (condition 3): requests carry concept ids; the
                      answering agent resolves them through the
                      alignment table, refuses non-substitutable
                      verdicts, and grounds via realized_by annotations.

The query engine (SQL over the institution's own SQLite database) is
identical across conditions; only grounding differs.
"""

from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy import create_engine, func, select

from alignment import SUBSTITUTABLE, Alignment, Verdict
from semantido.concepts import ConceptRegistry
from semantido.generators.semantic_layer import SemanticLayer


@dataclass
class Request:
    """A cross-institution question, in the asker's vocabulary.

    ``concepts`` maps role -> the asker's concept id (condition 3);
    ``terms`` maps role -> the asker's surface term (conditions 1-2).
    Roles: "group_by" and "measure".
    """

    asking_namespace: str
    intent: str  # human-readable, for the report
    terms: dict[str, str]
    concepts: dict[str, str]


@dataclass
class Response:
    ok: bool
    rows: list[tuple] = field(default_factory=list)
    grounding: dict[str, str] = field(default_factory=dict)
    provenance: list[str] = field(default_factory=list)
    refusal: Optional[str] = None


class Institution:
    """An institution's queryable estate: models, layer, registry, data."""

    def __init__(self, base, registry: ConceptRegistry, seed_rows, model):
        self.base = base
        self.registry = registry
        self.layer: SemanticLayer = base.sync_semantic_layer(concept_registry=registry)
        self.engine = create_engine("sqlite://")
        base.metadata.create_all(self.engine)
        self.model = model
        with self.engine.begin() as conn:
            table = model.__table__
            non_date = [
                c.name for c in table.columns if "DATE" not in str(c.type).upper()
            ]
            conn.execute(
                table.insert(),
                [dict(zip(non_date, row)) for row in seed_rows],
            )

    # ---------------- grounding helpers ---------------- #
    def columns(self):
        for table in self.layer.tables.values():
            for column in table.columns:
                yield table, column

    def column_for_concept(self, concept_id: str):
        for table, column in self.columns():
            if column.concept == concept_id:
                return table, column
        return None, None


# --------------------------------------------------------------------- #
# Resolvers                                                             #
# --------------------------------------------------------------------- #
class LexicalResolver:
    """Condition 1: name matching with a capable agent's priors.

    The equivalence table stands in for what any competent LLM "just
    knows": cpty means counterparty, notional is an amount. That
    competence is exactly what makes the homonym dangerous — the agent
    is right about the words and wrong about the law.
    """

    name = "lexical"

    PRIORS = {
        "counterparty": ("cpty",),
        "party": ("cpty", "counterparty"),
        "amount": ("notional", "amt", "value"),
        "asset class": ("asset_class",),
    }

    def resolve(self, inst: Institution, request: Request, _alignments):
        grounding, provenance = {}, []
        for role, term in request.terms.items():
            needles = (term.lower(),) + self.PRIORS.get(term.lower(), ())
            hit = None
            for _, column in inst.columns():
                name = column.name.lower()
                if any(n in name or name.split("_")[0] in n for n in needles):
                    hit = column.name
                    break
            if hit is None:
                return None, [f"{role}: no column resembling {term!r}"]
            grounding[role] = hit
            provenance.append(f"{role}: {term!r} ~ column {hit!r} (name prior)")
        return grounding, provenance


class SemanticResolver:
    """Condition 2: match on layer labels, synonyms, descriptions."""

    name = "semantic layer"

    def resolve(self, inst: Institution, request: Request, _alignments):
        grounding, provenance = {}, []
        for role, term in request.terms.items():
            needle = term.lower()
            hit = None
            for table, column in inst.columns():
                haystack = " ".join(
                    filter(
                        None,
                        [
                            column.name,
                            column.description or "",
                            " ".join(column.synonyms or []),
                        ],
                    )
                ).lower()
                if needle in haystack:
                    hit = column.name
                    break
            if hit is None:
                return None, [f"{role}: no semantic match for {term!r}"]
            grounding[role] = hit
            provenance.append(
                f"{role}: {term!r} matched description/synonyms of {hit!r}"
            )
        return grounding, provenance


class ConceptResolver:
    """Condition 3: alignment-table resolution with refusal semantics."""

    name = "concept protocol"

    def resolve(
        self,
        inst: Institution,
        request: Request,
        alignments: dict[tuple[str, str], Alignment],
    ):
        grounding, provenance = {}, []
        for role, foreign_id in request.concepts.items():
            # find local concepts aligned with the asker's concept
            candidates = [
                a for (local, foreign), a in alignments.items() if foreign == foreign_id
            ]
            if not candidates:
                return None, [
                    f"{role}: no bridge for foreign concept "
                    f"{request.asking_namespace}:{foreign_id} — "
                    "NO_BRIDGE, asking for clarification instead of guessing"
                ]
            best = max(candidates, key=lambda a: a.verdict)
            if best.verdict not in SUBSTITUTABLE:
                return None, [
                    f"{role}: {best.verdict.name} for "
                    f"{foreign_id} vs local {best.concept_a}: "
                    + "; ".join(best.reasons)
                ]
            table, column = inst.column_for_concept(best.concept_a)
            caveat = ""
            if column is None:
                # Descend: a realized local concept that is NARROWER than
                # the aligned one is a defensible proxy, disclosed as such.
                from semantido.concepts import ConceptRelation

                for local_id, local in inst.registry.concepts.items():
                    if (
                        ConceptRelation.BROADER,
                        best.concept_a,
                    ) in local.relations:
                        table, column = inst.column_for_concept(local_id)
                        if column is not None:
                            caveat = (
                                f" (narrower proxy {local_id}: covers only "
                                f"that subset of {best.concept_a})"
                            )
                            break
            if column is None:
                return None, [
                    f"{role}: concept {best.concept_a} has no realized_by "
                    "column in this schema and no realized narrower proxy"
                ]
            grounding[role] = column.name
            provenance.append(
                f"{role}: {request.asking_namespace}:{foreign_id} "
                f"={best.verdict.name}= {inst.registry.namespace}:"
                f"{best.concept_a} -> column {column.name!r}{caveat} "
                f"[{'; '.join(best.reasons)}]"
            )
        return grounding, provenance


# --------------------------------------------------------------------- #
# Agent                                                                 #
# --------------------------------------------------------------------- #
class Agent:
    def __init__(self, inst: Institution, resolver, alignments=None):
        self.inst = inst
        self.resolver = resolver
        self.alignments = alignments or {}

    def answer(self, request: Request) -> Response:
        grounding, provenance = self.resolver.resolve(
            self.inst, request, self.alignments
        )
        if grounding is None:
            return Response(ok=False, refusal=provenance[0], provenance=provenance)

        table = self.inst.model.__table__
        group_col = table.c[grounding["group_by"]]
        measure_col = table.c[grounding["measure"]]
        query = (
            select(group_col, func.sum(measure_col))
            .group_by(group_col)
            .order_by(group_col)
        )
        with self.inst.engine.connect() as conn:
            rows = [tuple(r) for r in conn.execute(query)]
        return Response(ok=True, rows=rows, grounding=grounding, provenance=provenance)
