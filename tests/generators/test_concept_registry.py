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

"""Unit tests for the concept registry (v0.4.0 draft)."""

import pytest


from semantido.generators.concept_registry import (
    Concept,
    ConceptRegistry,
    ConceptRelation,
    ExternalMapping,
    OntologySource,
    close_match,
    exact_match,
)
FIBO = OntologySource(
    name="fibo",
    namespace="https://spec.edmcouncil.org/fibo/ontology/",
    version="2025Q3",
    profile="fnd-fbc-core",
)


def _author(registry, cid, label=None, **kwargs):
    """Authors a concept through the single public path."""
    return registry.concept(
        cid,
        definition=f"Definition of {cid}",
        label=label or cid.replace("_", " ").title(),
        **kwargs,
    )


# --------------------------------------------------------------------- #
# Construction invariants                                               #
# --------------------------------------------------------------------- #
class TestConstruction:
    def test_concept_requires_snake_case_id(self):
        with pytest.raises(ValueError, match="snake_case"):
            _author(ConceptRegistry(), "Trade-Report")

    def test_concept_requires_definition(self):
        with pytest.raises(ValueError, match="definition"):
            Concept(id="trade", label="Trade", definition="  ")

    def test_source_requires_version_pin(self):
        with pytest.raises(ValueError, match="version"):
            OntologySource(name="fibo", namespace="https://x/", version="")

    def test_mapping_relation_must_be_enum(self):
        with pytest.raises(TypeError, match="MappingRelation"):
            ExternalMapping(
                target="https://x/Trade", relation="exact_match", source="fibo"
            )

    def test_duplicate_concept_id_rejected(self):
        registry = ConceptRegistry()
        _author(registry, "trade")
        with pytest.raises(ValueError, match="already registered"):
            _author(registry, "trade")

    def test_silent_source_repin_rejected(self):
        registry = ConceptRegistry()
        registry.add_source(FIBO)
        registry.add_source(FIBO)  # identical re-add is idempotent
        with pytest.raises(ValueError, match="different\\s+pin"):
            registry.add_source(
                OntologySource(
                    name="fibo",
                    namespace="https://spec.edmcouncil.org/fibo/ontology/",
                    version="2026Q1",
                )
            )


# --------------------------------------------------------------------- #
# Validation                                                            #
# --------------------------------------------------------------------- #
class TestValidation:
    def test_valid_registry_passes(self):
        registry = ConceptRegistry()
        registry.add_source(FIBO)
        _author(
            registry,
            "trade",
            external=close_match(
                "fibo",
                "fibo-fbc-fi/Trade",
                because="System trade is narrower in scope",
            ),
        )
        _author(registry, "block_trade", broader=registry.concepts["trade"])
        registry.validate()  # must not raise

    def test_unknown_relation_target_reported(self):
        registry = ConceptRegistry()
        ghost = Concept(id="deal", label="Deal", definition="x")
        registry._register_concept(ghost)  # pylint: disable=W0212
        _author(registry, "trade", same_as=ghost)
        del registry.concepts["deal"]  # simulate deserialized dangling ref
        with pytest.raises(ValueError, match="unknown concept 'deal'"):
            registry.validate()

    def test_self_relation_reported(self):
        registry = ConceptRegistry()
        trade = Concept(
            id="trade",
            label="Trade",
            definition="x",
            relations=[(ConceptRelation.RELATED, "trade")],
        )
        registry._register_concept(trade)  # pylint: disable=W0212
        with pytest.raises(ValueError, match="self-relation"):
            registry.validate()

    def test_unregistered_mapping_source_reported(self):
        registry = ConceptRegistry()
        _author(registry, "trade", external=exact_match("fibo", "https://x/Trade"))
        with pytest.raises(ValueError, match="unregistered source 'fibo'"):
            registry.validate()

    def test_broader_narrower_cycle_detected(self):
        registry = ConceptRegistry()
        # a broader b, b broader c, and c declares a NARROWER c edge on a,
        # i.e. c broader a  =>  a -> b -> c -> a cycle
        a_term = _author(registry, "a_term")
        b_term = _author(registry, "b_term", narrower=a_term)
        _author(registry, "c_term", narrower=b_term, broader=a_term)
        with pytest.raises(ValueError, match="cycle"):
            registry.validate()

    def test_narrower_edges_feed_same_hierarchy(self):
        registry = ConceptRegistry()
        # a NARROWER b means b is narrower than a => b broader-points to a
        # combined with b BROADER a this is consistent, not a cycle
        a_term = _author(registry, "a_term")
        _author(registry, "b_term", broader=a_term)
        a_term.relations.append((ConceptRelation.NARROWER, "b_term"))
        registry.validate()  # must not raise

    def test_all_errors_collected_in_one_raise(self):
        registry = ConceptRegistry()
        trade = Concept(
            id="trade",
            label="Trade",
            definition="x",
            relations=[(ConceptRelation.SAME_AS, "ghost")],
            mappings=[exact_match("nowhere", "https://x/Trade")],
        )
        registry._register_concept(trade)  # pylint: disable=W0212
        with pytest.raises(ValueError) as exc:
            registry.validate()
        message = str(exc.value)
        assert "ghost" in message and "nowhere" in message


# --------------------------------------------------------------------- #
# Homonyms and subsetting                                               #
# --------------------------------------------------------------------- #
class TestIntrospection:
    def test_find_homonyms_across_labels_and_synonyms(self):
        registry = ConceptRegistry()
        _author(registry, "counterparty_emir", label="Counterparty")
        _author(
            registry,
            "counterparty_mifir",
            label="Transaction Counterparty",
            synonyms=["counterparty"],
        )
        homonyms = registry.find_homonyms()
        assert homonyms == {"counterparty": ["counterparty_emir", "counterparty_mifir"]}

    def test_subset_closes_over_relations_and_prunes_sources(self):
        registry = ConceptRegistry()
        registry.add_source(FIBO)
        registry.add_source(
            OntologySource(name="unused", namespace="urn:x:", version="1")
        )
        block = _author(registry, "block_trade")
        _author(
            registry,
            "trade",
            narrower=block,
            external=close_match("fibo", "fibo-fbc-fi/Trade"),
        )
        _author(registry, "unrelated")

        sub = registry.subset({"trade"})
        assert set(sub.concepts) == {"trade", "block_trade"}
        assert set(sub.sources) == {"fibo"}

    def test_subset_ignores_unknown_seeds(self):
        registry = ConceptRegistry()
        _author(registry, "trade")
        assert set(registry.subset({"ghost"}).concepts) == set()


# --------------------------------------------------------------------- #
# Serialization                                                         #
# --------------------------------------------------------------------- #
class TestSerialization:
    def test_to_dict_shape_and_skos(self):
        registry = ConceptRegistry()
        registry.add_source(FIBO)
        _author(registry, "trade", external=close_match("fibo", "fibo-fbc-fi/Trade"))
        doc = registry.to_dict()
        assert doc["sources"]["fibo"]["version"] == "2025Q3"
        assert doc["sources"]["fibo"]["profile"] == "fnd-fbc-core"
        mapping = doc["concepts"]["trade"]["mappings"][0]
        assert mapping["relation"] == "close_match"
        assert mapping["skos"] == "skos:closeMatch"

    def test_to_yaml_sidecar_roundtrip(self, tmp_path):
        yaml = pytest.importorskip("yaml")
        registry = ConceptRegistry()
        registry.add_source(FIBO)
        _author(registry, "trade")

        path = tmp_path / "concepts.yaml"
        text = registry.to_yaml(str(path))
        assert path.read_text(encoding="utf-8") == text

        loaded = yaml.safe_load(text)
        assert loaded["concept_registry"]["concepts"]["trade"]["label"] == "Trade"


class TestDefinitionChecksum:
    def test_stable_under_formatting_noise(self):
        a = Concept(id="a", label="A", definition="A legal entity.  ")
        b = Concept(id="b", label="B", definition="a legal\nentity")
        assert a.definition_checksum == b.definition_checksum

    def test_differs_under_paraphrase(self):
        a = Concept(id="a", label="A", definition="A legal entity.")
        b = Concept(id="b", label="B", definition="An entity with legal personality.")
        assert a.definition_checksum != b.definition_checksum

    def test_serialized(self):
        registry = ConceptRegistry()
        concept = _author(registry, "trade")
        doc = registry.to_dict()
        assert (
            doc["concepts"]["trade"]["definition_checksum"]
            == concept.definition_checksum
        )
