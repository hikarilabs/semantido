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

"""Tests for the concept authoring API: factory, relation kwargs, helpers."""

import pytest

from semantido.concepts import (
    Concept,
    ConceptRegistry,
    ConceptRelation,
    ExternalMapping,
    MappingRelation,
    OntologySource,
    exact_match,
    narrow_match,
)


def _regreport_registry() -> ConceptRegistry:
    """The counterparty homonym case, authored with the fluent API."""
    registry = ConceptRegistry("hikari.regreport")
    registry.add_source(
        OntologySource(
            name="emir_rts",
            namespace="urn:eu:emir:rts:2024refit",
            version="2024",
        )
    )
    registry.add_source(
        OntologySource(
            name="datahub",
            namespace="urn:li:glossaryTerm:",
            version="prod-2026-07",
        )
    )

    counterparty = registry.concept(
        "counterparty",
        definition="A legal entity that is party to a financial transaction.",
        synonyms=("legal entity", "trading party"),
    )
    emir = registry.concept(
        "counterparty.emir",
        label="counterparty",  # same label — deliberate homonym
        definition="Counterparty within the meaning of EMIR Art. 2(8)-(9).",
        broader=counterparty,
        external=[
            exact_match(
                "emir_rts",
                "field:1.9",
                because="definition is the regulation's own",
            ),
            narrow_match("datahub", "emir.counterparty"),
        ],
    )
    registry.concept(
        "counterparty.mifir",
        label="counterparty",
        definition=(
            "Entity identified in MiFIR transaction reports (RTS 22); "
            "legally distinct from the EMIR notion despite the shared label."
        ),
        broader=counterparty,
        distinct_from=emir,  # declared once; mirror edge is automatic
        external=exact_match("emir_rts", "rts22:art26"),
    )
    return registry


class TestFactory:
    def test_sketch_registry_validates(self):
        registry = _regreport_registry()
        registry.validate()  # must not raise
        assert registry.namespace == "hikari.regreport"

    def test_returns_registered_handle(self):
        registry = ConceptRegistry()
        handle = registry.concept("trade", definition="A trade.")
        assert isinstance(handle, Concept)
        assert registry.concepts["trade"] is handle
        assert not hasattr(registry, "add_concept")  # single authoring path

    def test_label_defaults_to_last_segment(self):
        registry = ConceptRegistry()
        concept = registry.concept("risk.block_trade", definition="A block trade.")
        assert concept.label == "block trade"

    def test_dotted_id_grammar(self):
        registry = ConceptRegistry()
        registry.concept("a.b_c.d", definition="x")
        for bad in ("", ".", "a.", ".a", "a..b", "A.b", "a b"):
            with pytest.raises(ValueError, match="dot-separated"):
                registry.concept(bad, definition="x")

    def test_no_relation_derived_from_id_prefix(self):
        registry = ConceptRegistry()
        registry.concept("counterparty", definition="x")
        child = registry.concept("counterparty.emir", definition="y")
        assert child.relations == []  # address is not assertion

    def test_object_refs_and_iterables(self):
        registry = ConceptRegistry()
        parent = registry.concept("party", definition="x")
        seller = registry.concept("party.seller", definition="z")
        child = registry.concept(
            "party.buyer",
            definition="y",
            broader=parent,
            related=[seller, parent],
        )
        assert (ConceptRelation.BROADER, "party") in child.relations
        assert (ConceptRelation.RELATED, "party.seller") in child.relations
        registry.validate()

    def test_string_ref_rejected_with_guidance(self):
        registry = ConceptRegistry()
        registry.concept("party", definition="x")
        with pytest.raises(TypeError, match="registered later"):
            registry.concept("a", definition="y", broader="party")

    def test_bad_ref_type_raises(self):
        registry = ConceptRegistry()
        with pytest.raises(TypeError, match="Concept handles"):
            registry.concept("a", definition="x", broader=[42])

    def test_foreign_handle_rejected_at_author_time(self):
        other = ConceptRegistry()
        foreign = other.concept("party", definition="x")
        registry = ConceptRegistry()
        with pytest.raises(ValueError, match="do not transfer"):
            registry.concept("a", definition="y", broader=foreign)

    def test_untyped_external_rejected(self):
        registry = ConceptRegistry()
        with pytest.raises(TypeError, match="exact_match"):
            registry.concept(
                "a",
                definition="x",
                external=[{"regulation": "EMIR Art. 2(8)"}],
            )

    def test_single_mapping_without_list(self):
        registry = ConceptRegistry()
        registry.add_source(OntologySource(name="s", namespace="urn:x:", version="1"))
        concept = registry.concept("a", definition="x", external=exact_match("s", "t"))
        assert len(concept.mappings) == 1


class TestHelpers:
    def test_helpers_carry_relation_and_justification(self):
        mapping = narrow_match("fibo", "x/Trade", because="scoped")
        assert isinstance(mapping, ExternalMapping)
        assert mapping.relation is MappingRelation.NARROWER
        assert mapping.justification == "scoped"
        assert mapping.relation.skos == "skos:narrowMatch"

    def test_symmetric_relation_reciprocated(self):
        registry = ConceptRegistry()
        first = registry.concept("a", definition="x")
        second = registry.concept("b", definition="y", distinct_from=first)
        mirror = (ConceptRelation.DISTINCT_FROM, "b")
        assert mirror in first.relations
        assert (ConceptRelation.DISTINCT_FROM, "a") in second.relations
        registry.validate()

    def test_reciprocation_idempotent_and_in_subset(self):
        registry = ConceptRegistry()
        first = registry.concept("a", definition="x")
        registry.concept("b", definition="y", related=[first, first])
        assert first.relations.count((ConceptRelation.RELATED, "b")) == 1
        # closure reaches b starting from a via the mirror edge
        assert set(registry.subset({"a"}).concepts) == {"a", "b"}


class TestNamespace:
    def test_namespace_serialized(self):
        registry = _regreport_registry()
        doc = registry.to_dict()
        assert doc["namespace"] == "hikari.regreport"

    def test_anonymous_registry_omits_namespace(self):
        assert "namespace" not in ConceptRegistry().to_dict()

    def test_homonyms_still_surface(self):
        registry = _regreport_registry()
        # Three claimants, not two: the generic parent's default label is
        # also "counterparty". A bare mention of the term is ambiguous
        # between the generic notion and both regulatory senses — the
        # registry correctly reports all three.
        assert registry.find_homonyms() == {
            "counterparty": [
                "counterparty",
                "counterparty.emir",
                "counterparty.mifir",
            ]
        }

    def test_synonyms_tuple_normalized_to_list(self):
        registry = _regreport_registry()
        assert registry.concepts["counterparty"].synonyms == [
            "legal entity",
            "trading party",
        ]
