# Copyright 2025 Dragos Crintea - HikariLabs LTD
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Concept registry: the concept tier above semantido's physical-object graph.

The ``SemanticLayer`` is a graph whose nodes are physical objects (tables,
columns). The concept registry adds the missing tier: named business
concepts that exist independently of any schema, which physical objects
*realize* and which may map to external reference ontologies or catalog
glossaries.

Three edge families, on two distinct axes:

* concept -> physical (``realized_by``): declared from the physical side,
  via ``@semantic_table(concept=...)`` for tables and
  ``<column>_concept = "<concept_id>"`` class attributes for columns.
* concept <-> concept (``ConceptRelation``): SAME_AS / BROADER / NARROWER /
  RELATED / DISTINCT_FROM edges inside the registry. DISTINCT_FROM is the
  homonym declaration: two concepts sharing a label that must never be
  conflated (e.g. EMIR "counterparty" vs MiFIR "counterparty").
* concept -> external (``ExternalMapping``): a typed, source-pinned pointer
  to an external ontology class or glossary term (FIBO IRI, DataHub glossary
  URN, ...). The relation vocabulary is SKOS-aligned because a bare pointer
  reads as an implicit exactMatch, and almost nothing is an exact match.

Every external mapping must name a registered ``OntologySource`` carrying a
pinned version. Without the pin, a mapping's validity is unfalsifiable: it
cannot be told apart from a stale or wrong one. Validation here is
referential only (IDs resolve, sources are pinned, the broader/narrower
graph is acyclic); no OWL semantics are projected onto the model.

Usage:

    from semantido.generators.concept_registry import (
        Concept, ConceptRegistry, ConceptRelation,
        ExternalMapping, MappingRelation, OntologySource,
    )

    from semantido.concepts import ConceptRegistry, OntologySource, close_match

    registry = ConceptRegistry("hikari.regreport")
    registry.add_source(OntologySource(
        name="fibo",
        namespace="https://spec.edmcouncil.org/fibo/ontology/",
        version="2025Q3",
    ))
    registry.concept(
        "trade",
        definition="A legally binding agreement to exchange instruments.",
        external=close_match(
            "fibo",
            "https://spec.edmcouncil.org/fibo/ontology/FBC/"
            "ProductsAndServices/FinancialProductsAndServices/Trade",
            because="system trade is narrower in operational scope",
        ),
    )
    registry.validate()

``registry.concept()`` is the only authoring path for concepts, and the
relation-named helpers are the only path to an external mapping; the
``Concept`` and ``ExternalMapping`` dataclasses remain public as *read*
types for consumers iterating a registry.
"""

import hashlib
import re as _re

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Optional, Union

# Concept identifiers are dotted paths of lowercase snake_case segments
# (e.g. "counterparty.emir"). Dots are a namespacing *convention* only —
# no relation is ever derived from an id prefix; the id is an address,
# a relation is an assertion, and they are free to disagree.
_ID_CHARS = "abcdefghijklmnopqrstuvwxyz0123456789_"


def _valid_id(concept_id: str) -> bool:
    """A valid id is 1+ dot-separated, non-empty snake_case segments."""
    if not concept_id:
        return False
    segments = concept_id.split(".")
    return all(
        segment and all(ch in _ID_CHARS for ch in segment) for segment in segments
    )


class MappingRelation(Enum):
    """SKOS-aligned relation between a concept and an external target.

    The default assumption of a bare identifier is equivalence; forcing an
    explicit relation prevents encoding "narrower, system-scoped surrogate"
    as "exact match".
    """

    EXACT_MATCH = "exact_match"
    CLOSE_MATCH = "close_match"
    BROADER = "broader"
    NARROWER = "narrower"
    RELATED = "related"

    @property
    def skos(self) -> str:
        """The direction-correct SKOS mapping property IRI suffix.

        MappingRelation values are concept-first: ``NARROWER`` states the
        *concept* is narrower than the external target. SKOS hierarchical
        mapping properties read the other way around: per the SKOS
        reference, ``<concept> skos:broadMatch <target>`` asserts the
        *target* (the object of the triple) is the broader one. A concept
        narrower than its target therefore serializes as
        ``skos:broadMatch``, and vice versa. Hierarchy values map to
        their SKOS inverses; symmetric values map name-for-name.
        """
        return {
            MappingRelation.EXACT_MATCH: "skos:exactMatch",
            MappingRelation.CLOSE_MATCH: "skos:closeMatch",
            MappingRelation.BROADER: "skos:narrowMatch",
            MappingRelation.NARROWER: "skos:broadMatch",
            MappingRelation.RELATED: "skos:relatedMatch",
        }[self]


class ConceptRelation(Enum):
    """Typed edge between two concepts inside the registry."""

    SAME_AS = "same_as"
    BROADER = "broader"
    NARROWER = "narrower"
    RELATED = "related"
    DISTINCT_FROM = "distinct_from"


@dataclass
class OntologySource:
    """A pinned external ontology or glossary release.

    Attributes:
        name: Registry-local handle referenced by mappings (e.g. "fibo").
        namespace: Base IRI / URN prefix of the source.
        version: The pinned release (e.g. "2025Q3"). Required: an unpinned
            mapping cannot be validated or detected as stale.
        location: Optional resolvable URL of the release artifact.
        profile: Optional named subset/profile of the source in use.
    """

    name: str
    namespace: str
    version: str
    location: Optional[str] = None
    profile: Optional[str] = None

    def __post_init__(self):
        for attr in ("name", "namespace", "version"):
            value = getattr(self, attr)
            if not value or not str(value).strip():
                raise ValueError(
                    f"OntologySource.{attr} is required and must be non-empty"
                )


@dataclass
class ExternalMapping:
    """A typed, source-pinned pointer from a concept to an external target.

    Attributes:
        target: Full IRI, CURIE, or URN of the external class/term.
        relation: The mapping relation; never defaults to equivalence.
        source: Name of a registered ``OntologySource``.
        justification: Optional human rationale for the mapping choice.
    """

    target: str
    relation: MappingRelation
    source: str
    justification: Optional[str] = None

    def __post_init__(self):
        if not self.target or not str(self.target).strip():
            raise ValueError("ExternalMapping.target must be non-empty")
        if not isinstance(self.relation, MappingRelation):
            raise TypeError(
                "ExternalMapping.relation must be a MappingRelation, "
                f"got {type(self.relation).__name__}"
            )
        if not self.source or not str(self.source).strip():
            raise ValueError("ExternalMapping.source must be non-empty")


@dataclass
class Concept:
    """A business concept independent of any physical schema.

    Attributes:
        id: Stable lowercase snake_case identifier referenced by decorators.
        label: Human-readable name. Labels may collide across concepts —
            that is the homonym case the registry exists to expose.
        definition: The business definition; the thing two schemas disagree
            about when their labels collide.
        synonyms: Alternative labels.
        mappings: Typed pointers to external ontology/glossary targets.
        relations: Typed edges to other concepts, as
            ``(ConceptRelation, other_concept_id)`` pairs.
    """

    id: str  # pylint: disable=C0103
    label: str
    definition: str
    synonyms: Optional[list[str]] = None
    mappings: list[ExternalMapping] = field(default_factory=list)
    relations: list[tuple[ConceptRelation, str]] = field(default_factory=list)

    def __post_init__(self):
        if not _valid_id(self.id):
            raise ValueError(
                f"Concept.id {self.id!r} must be dot-separated lowercase "
                "snake_case segments (e.g. 'counterparty.emir')"
            )
        if not self.label or not self.label.strip():
            raise ValueError(f"Concept {self.id!r}: label must be non-empty")
        if not self.definition or not self.definition.strip():
            raise ValueError(
                f"Concept {self.id!r}: definition must be non-empty — a "
                "concept without a definition is just a label"
            )
        if self.synonyms is not None:
            self.synonyms = list(self.synonyms)

    @property
    def definition_checksum(self) -> str:
        """Checksum of the normalized definition text.

        Computed, never stored, so it cannot drift from the definition it
        describes. Two concepts derived from the same source definition
        agree on this value even when ids, labels, and toolchains differ;
        a paraphrased or truncated derivation disagrees. Normalization is
        deliberately light (case, whitespace, trailing punctuation): the
        checksum should detect *textual* divergence, and semantic
        equivalence under rewording is exactly the judgment left to a
        human review it triggers.
        """
        normalized = _re.sub(r"\s+", " ", self.definition.strip().lower())
        normalized = normalized.rstrip(".")
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12]


@dataclass
class ConceptRegistry:
    """The collection of concepts, their relations, and pinned sources.

    The registry is schema-independent: one registry can serve many
    ``SemanticLayer`` instances, which is what allows two schemas'
    divergent vocabularies to be aligned at the concept tier.

    Attributes:
        namespace: Optional identity of this registry (e.g.
            "hikari.regreport"). A namespaced registry can itself be
            pinned as an ``OntologySource`` by other parties — federation
            reuses the same mechanism as reference-ontology mapping.
        concepts: Registered concepts keyed by id.
        sources: Pinned external sources keyed by name.
    """

    namespace: Optional[str] = None
    concepts: dict[str, Concept] = field(default_factory=dict)
    sources: dict[str, OntologySource] = field(default_factory=dict)

    def add_source(self, source: OntologySource) -> None:
        """Registers a pinned external source.

        Args:
            source: The OntologySource to register.

        Raises:
            ValueError: If a source with the same name is already registered
                with a different pin (silent re-pin is how stale mappings
                are born).
        """
        existing = self.sources.get(source.name)
        if existing is not None and existing != source:
            raise ValueError(
                f"Source {source.name!r} already registered with a different "
                f"pin (existing version {existing.version!r}, "
                f"new {source.version!r}); re-pinning must be explicit — "
                "remove the old source first"
            )
        self.sources[source.name] = source

    def _register_concept(self, concept: Concept) -> None:
        """Internal registration; ``concept()`` is the only public
        authoring path — one way to write, so every concept passes
        through the same construction checks and defaulting.

        Args:
            concept: The Concept to register.

        Raises:
            ValueError: If the concept id is already registered.
        """
        if concept.id in self.concepts:
            raise ValueError(f"Concept id {concept.id!r} already registered")
        self.concepts[concept.id] = concept

    def concept(  # pylint: disable=R0913,R0914
        # The kwargs ARE the API: one keyword-only slot per relation type.
        self,
        concept_id: str,
        definition: str,
        *,
        label: Optional[str] = None,
        synonyms: Optional[list[str]] = None,
        broader: "ConceptRefs" = None,
        narrower: "ConceptRefs" = None,
        same_as: "ConceptRefs" = None,
        related: "ConceptRefs" = None,
        distinct_from: "ConceptRefs" = None,
        external: "MappingArg" = None,
    ) -> Concept:
        """Constructs, registers, and returns a concept in one step.

        This is the authoring API: relation kwargs accept only ``Concept``
        handles returned by earlier ``concept()`` calls (or iterables of
        them), so every failure is at author time — a misspelled handle is
        a ``NameError``, a handle from another registry a ``ValueError``,
        a string a ``TypeError``. Relations are declared from whichever
        concept is registered *later*: hierarchy via ``broader=`` on the
        child or ``narrower=`` on the parent, and symmetric relations
        (``same_as``, ``related``, ``distinct_from``) from either side —
        the mirror edge is recorded automatically. External mappings must
        be built with the relation-named helpers (``exact_match``,
        ``narrow_match``, ...) so a mapping without a stated relation
        stays unrepresentable.

        Args:
            concept_id: Dotted snake_case id (e.g. "counterparty.emir").
                Dots are namespacing convention only; no relation is
                derived from the prefix.
            definition: The business definition. Required.
            label: Human-readable name. Defaults to the last id segment
                with underscores as spaces. Deliberate homonyms share a
                label and are surfaced by ``find_homonyms()``.
            synonyms: Alternative labels.
            broader: Concept(s) this one is narrower than.
            narrower: Concept(s) this one is broader than.
            same_as: Concept(s) asserted identical to this one.
            related: Concept(s) associatively related.
            distinct_from: Concept(s) that share surface forms but must
                never be conflated — the explicit homonym declaration.
                Symmetric: declaring it here also records the mirror
                edge on the target.
            external: One mapping or an iterable of mappings built with
                the relation helpers.

        Returns:
            Concept: The registered concept, usable as a reference in
            later ``concept()`` calls and in ``@semantic_table``.
        """
        relations: list[tuple[ConceptRelation, str]] = []
        for relation, refs in (
            (ConceptRelation.BROADER, broader),
            (ConceptRelation.NARROWER, narrower),
            (ConceptRelation.SAME_AS, same_as),
            (ConceptRelation.RELATED, related),
            (ConceptRelation.DISTINCT_FROM, distinct_from),
        ):
            for target_id in _ref_ids(refs):
                # Author-time membership check: a handle from a different
                # registry is the one remaining way to smuggle in an
                # unregistered target — fail here, not at validate().
                if target_id not in self.concepts:
                    raise ValueError(
                        f"Concept {concept_id!r}: relation target "
                        f"{target_id!r} is not registered in this "
                        "registry — handles do not transfer between "
                        "registries"
                    )
                relations.append((relation, target_id))

        if external is None:
            mappings: list[ExternalMapping] = []
        elif isinstance(external, ExternalMapping):
            mappings = [external]
        else:
            mappings = list(external)
            for mapping in mappings:
                if not isinstance(mapping, ExternalMapping):
                    raise TypeError(
                        f"Concept {concept_id!r}: external entries must be "
                        "ExternalMapping (use exact_match(), narrow_match(), "
                        f"...); got {type(mapping).__name__}"
                    )

        registered = Concept(
            id=concept_id,
            label=(
                label
                if label is not None
                else concept_id.split(".")[-1].replace("_", " ")
            ),
            definition=definition,
            synonyms=synonyms,
            mappings=mappings,
            relations=relations,
        )
        self._register_concept(registered)
        self._reciprocate_symmetric(registered)
        return registered

    # Relations that hold in both directions; declaring either side is
    # declaring both. Hierarchy (BROADER/NARROWER) is deliberately not
    # reciprocated — both spellings already feed one directed graph in
    # cycle detection, and mirroring them would only duplicate edges.
    _SYMMETRIC = frozenset(
        {
            ConceptRelation.SAME_AS,
            ConceptRelation.RELATED,
            ConceptRelation.DISTINCT_FROM,
        }
    )

    def _reciprocate_symmetric(self, concept: Concept) -> None:
        """Materializes the mirror edge for symmetric relations.

        Declaring ``distinct_from=other`` on the later concept also
        records ``(DISTINCT_FROM, later)`` on ``other``, so exports show
        the assertion from both sides and ``subset()`` closure reaches
        either concept from the other. Idempotent: existing mirror edges
        are not duplicated.
        """
        for relation, target_id in concept.relations:
            if relation not in self._SYMMETRIC:
                continue
            target = self.concepts[target_id]
            mirror = (relation, concept.id)
            if mirror not in target.relations:
                target.relations.append(mirror)

    # ------------------------------------------------------------------ #
    # Validation                                                          #
    # ------------------------------------------------------------------ #
    def validate(self) -> None:
        """Referential validation of the registry.

        Checks, in order: relation targets resolve; no self-relations;
        mapping sources are registered (and therefore pinned); the
        broader/narrower graph is acyclic. Collects all violations and
        raises once, so a failing registry reports every problem.

        Raises:
            ValueError: Listing every violation found.
        """
        errors: list[str] = []

        for concept in self.concepts.values():
            for relation, target_id in concept.relations:
                if target_id == concept.id:
                    errors.append(
                        f"{concept.id}: self-relation {relation.value} -> {target_id}"
                    )
                elif target_id not in self.concepts:
                    errors.append(
                        f"{concept.id}: relation {relation.value} -> "
                        f"unknown concept {target_id!r}"
                    )
            for mapping in concept.mappings:
                if mapping.source not in self.sources:
                    errors.append(
                        f"{concept.id}: mapping to {mapping.target!r} names "
                        f"unregistered source {mapping.source!r}"
                    )

        errors.extend(self._find_hierarchy_cycles())

        if errors:
            raise ValueError(
                "Concept registry validation failed:\n  - " + "\n  - ".join(errors)
            )

    def _find_hierarchy_cycles(self) -> list[str]:
        """Detects cycles in the broader/narrower hierarchy via DFS.

        NARROWER edges are inverted to BROADER so both declarations feed
        one directed graph.

        Returns:
            list: One error string per distinct cycle entry point.
        """
        graph: dict[str, set[str]] = {cid: set() for cid in self.concepts}
        for concept in self.concepts.values():
            for relation, target_id in concept.relations:
                if target_id not in self.concepts or target_id == concept.id:
                    continue  # reported by validate() already
                if relation is ConceptRelation.BROADER:
                    graph[concept.id].add(target_id)
                elif relation is ConceptRelation.NARROWER:
                    graph[target_id].add(concept.id)

        errors: list[str] = []
        white, grey, black = set(graph), set(), set()

        def visit(node: str, path: list[str]) -> None:
            white.discard(node)
            grey.add(node)
            path.append(node)
            for nxt in sorted(graph[node]):
                if nxt in grey:
                    cycle = path[path.index(nxt) :] + [nxt]
                    errors.append("broader/narrower cycle: " + " -> ".join(cycle))
                elif nxt in white:
                    visit(nxt, path)
            path.pop()
            grey.discard(node)
            black.add(node)

        while white:
            visit(sorted(white)[0], [])

        return errors

    # ------------------------------------------------------------------ #
    # Introspection                                                       #
    # ------------------------------------------------------------------ #
    def find_homonyms(self) -> dict[str, list[str]]:
        """Finds labels (and synonyms) shared by more than one concept.

        These are the silent homonyms: identical surface forms with
        different registered meanings. Consumers (exporters, audits)
        can turn this into an explicit disambiguation section.

        Returns:
            dict: Lowercased surface form -> sorted list of concept ids,
                only for forms claimed by 2+ concepts.
        """
        claims: dict[str, set[str]] = {}
        for concept in self.concepts.values():
            forms = {concept.label.strip().lower()}
            forms.update(s.strip().lower() for s in (concept.synonyms or []))
            for form in forms:
                claims.setdefault(form, set()).add(concept.id)

        return {
            form: sorted(ids) for form, ids in sorted(claims.items()) if len(ids) > 1
        }

    def subset(self, concept_ids: set[str]) -> "ConceptRegistry":
        """Builds the sub-registry closed over the given concept ids.

        Follows concept relations transitively and keeps only the sources
        actually referenced — this is what exporters embed, so a large
        registry does not bloat every model export.

        Args:
            concept_ids: The seed concept ids (unknown ids are ignored).

        Returns:
            ConceptRegistry: A new registry containing the closure.
        """
        keep: set[str] = set()
        frontier = [cid for cid in concept_ids if cid in self.concepts]
        while frontier:
            cid = frontier.pop()
            if cid in keep:
                continue
            keep.add(cid)
            for _, target_id in self.concepts[cid].relations:
                if target_id in self.concepts and target_id not in keep:
                    frontier.append(target_id)

        result = ConceptRegistry()
        needed_sources: set[str] = set()
        for cid in sorted(keep):
            concept = self.concepts[cid]
            result.concepts[cid] = concept
            needed_sources.update(m.source for m in concept.mappings)
        for name in sorted(needed_sources):
            if name in self.sources:
                result.sources[name] = self.sources[name]
        return result

    # ------------------------------------------------------------------ #
    # Serialization                                                       #
    # ------------------------------------------------------------------ #
    def to_dict(self) -> dict[str, Any]:
        """Serializes the registry to a plain dictionary.

        Returns:
            dict: Deterministically ordered, JSON/YAML-ready structure.
        """
        return {
            **({"namespace": self.namespace} if self.namespace else {}),
            "sources": {
                name: {
                    "namespace": src.namespace,
                    "version": src.version,
                    **({"location": src.location} if src.location else {}),
                    **({"profile": src.profile} if src.profile else {}),
                }
                for name, src in sorted(self.sources.items())
            },
            "concepts": {
                cid: {
                    "label": concept.label,
                    "definition": concept.definition,
                    "definition_checksum": concept.definition_checksum,
                    **({"synonyms": concept.synonyms} if concept.synonyms else {}),
                    **(
                        {
                            "mappings": [
                                {
                                    "target": m.target,
                                    "relation": m.relation.value,
                                    "skos": m.relation.skos,
                                    "source": m.source,
                                    **(
                                        {"justification": m.justification}
                                        if m.justification
                                        else {}
                                    ),
                                }
                                for m in concept.mappings
                            ]
                        }
                        if concept.mappings
                        else {}
                    ),
                    **(
                        {
                            "relations": [
                                {"relation": rel.value, "concept": target}
                                for rel, target in concept.relations
                            ]
                        }
                        if concept.relations
                        else {}
                    ),
                }
                for cid, concept in sorted(self.concepts.items())
            },
        }

    def to_yaml(self, path: Optional[str] = None) -> str:
        """Serializes the registry as a sidecar ``concepts.yaml`` document.

        The sidecar is the interchange shape for registries: it travels
        next to an OSI model file without requiring spec extensions.
        Requires PyYAML (``pip install semantido[osi]``).

        Args:
            path: Optional filesystem path to also write the YAML to.

        Returns:
            str: The registry as YAML text.
        """
        try:
            import yaml  # pylint: disable=C0415
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "PyYAML is required for YAML export. "
                "Install it with: pip install semantido[osi]"
            ) from exc

        doc = {"concept_registry": self.to_dict()}
        text = yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=88)
        if path is not None:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
        return text


# ---------------------------------------------------------------------- #
# Authoring helpers                                                       #
# ---------------------------------------------------------------------- #

#: A relation argument in authoring code: one registered Concept handle,
#: an iterable of them, or None. String ids are deliberately not accepted:
#: object handles fail at author time (NameError / TypeError), and every
#: relation can be declared from the later-registered side, so late-binding
#: forward references are never necessary.
ConceptRefs = Union[Concept, Iterable[Concept], None]

#: One ExternalMapping, an iterable of them, or None.
MappingArg = Union["ExternalMapping", Iterable["ExternalMapping"], None]


def _ref_ids(refs: ConceptRefs) -> list[str]:
    """Normalizes a relation argument to a list of concept ids.

    Raises:
        TypeError: For strings or other non-Concept values, with guidance
            toward the declare-from-the-later-side pattern.
    """
    if refs is None:
        return []
    if isinstance(refs, Concept):
        return [refs.id]
    if isinstance(refs, str):
        raise TypeError(
            f"Relation target {refs!r} is a string; pass the Concept "
            "handle returned by registry.concept(). Relations are "
            "declared from whichever concept is registered later — "
            "symmetric relations (same_as, related, distinct_from) are "
            "reciprocated automatically, so a forward reference is "
            "never needed."
        )
    result: list[str] = []
    for ref in refs:
        if not isinstance(ref, Concept):
            raise TypeError(
                f"Relation targets must be Concept handles, got {type(ref).__name__}"
            )
        result.append(ref.id)
    return result


def _make_mapping_helper(relation: MappingRelation):
    """Builds a relation-named ExternalMapping constructor."""

    def helper(
        source: str, target: str, because: Optional[str] = None
    ) -> ExternalMapping:
        return ExternalMapping(
            target=target,
            relation=relation,
            source=source,
            justification=because,
        )

    helper.__name__ = relation.value
    helper.__doc__ = (
        f"Builds an ExternalMapping with relation "
        f"{relation.value!r} ({relation.skos}).\n\n"
        "Args:\n"
        "    source: Name of a registered OntologySource.\n"
        "    target: IRI, CURIE, or URN of the external term.\n"
        "    because: Optional human justification for the mapping.\n"
    )
    return helper


#: Relation-named mapping constructors. There is deliberately no helper
#: that omits the relation: a bare pointer reading as an implicit
#: exactMatch is the failure mode this vocabulary exists to prevent.
#: Helper names are spelled after the SKOS *mapping* property family
#: (broad_match, not broader) to avoid clashing with the
#: broader=/narrower= concept-relation kwargs — but their semantics are
#: concept-first: ``narrow_match(...)`` declares the concept narrower
#: than the target, which serializes as the SKOS inverse
#: (``skos:broadMatch``); see ``MappingRelation.skos``.
exact_match = _make_mapping_helper(MappingRelation.EXACT_MATCH)
close_match = _make_mapping_helper(MappingRelation.CLOSE_MATCH)
broad_match = _make_mapping_helper(MappingRelation.BROADER)
narrow_match = _make_mapping_helper(MappingRelation.NARROWER)
related_match = _make_mapping_helper(MappingRelation.RELATED)
