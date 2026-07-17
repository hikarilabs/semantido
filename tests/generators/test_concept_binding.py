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

"""End-to-end tests for concept binding: decorator -> bridge -> layer -> OSI.

The fixture models the registry's motivating case: an EMIR-style and a
MiFIR-style table whose "counterparty" columns are homonyms — same surface
form, legally distinct definitions — bound to two distinct concepts that
declare DISTINCT_FROM.
"""

import json

import pytest
from sqlalchemy import Column as SAColumn
from sqlalchemy import Date, Integer, String
from sqlalchemy.orm import DeclarativeBase

from semantido import (
    ConceptRegistry,
    OntologySource,
    SemanticBase,
    semantic_table,
)
from semantido.concepts import narrow_match
from semantido.exporters import to_osi_dict


def _registry() -> ConceptRegistry:
    registry = ConceptRegistry()
    registry.add_source(
        OntologySource(
            name="fibo",
            namespace="https://spec.edmcouncil.org/fibo/ontology/",
            version="2025Q3",
        )
    )
    registry.concept(
        "trade_report",
        label="Trade Report",
        definition="A regulatory submission describing a trade lifecycle event.",
    )
    emir = registry.concept(
        "counterparty_emir",
        label="Counterparty",
        definition="EMIR Art. 2: an entity party to a derivative contract.",
        external=narrow_match(
            "fibo",
            "https://spec.edmcouncil.org/fibo/ontology/"
            "FND/Parties/Parties/Counterparty",
            because="EMIR counterparty is jurisdiction-scoped",
        ),
    )
    registry.concept(
        "counterparty_mifir",
        label="Counterparty",
        definition="MiFIR RTS 22: buyer/seller identification in a transaction report.",
        distinct_from=emir,  # mirror edge recorded automatically
    )
    return registry


def _build_models():
    class Base(SemanticBase, DeclarativeBase):
        pass

    @semantic_table(
        description="EMIR trade state report",
        time_dimension="reporting_date",
        concept="trade_report",
    )
    class EmirTradeState(Base):
        __tablename__ = "emir_trade_state"
        id = SAColumn(Integer, primary_key=True)
        reporting_date = SAColumn(Date)
        counterparty = SAColumn(String)
        counterparty_concept = "counterparty_emir"

    @semantic_table(
        description="MiFIR transaction report",
        concept="trade_report",
    )
    class MifirTransaction(Base):
        __tablename__ = "mifir_transaction"
        id = SAColumn(Integer, primary_key=True)
        counterparty = SAColumn(String)
        counterparty_concept = "counterparty_mifir"

    return Base


class TestDecorator:
    def test_concept_param_sets_dunder(self):
        @semantic_table(description="x", concept="trade_report")
        class Model:
            pass

        assert Model.__semantic_concept__ == "trade_report"

    def test_conflicting_dunder_raises(self):
        with pytest.raises(ValueError, match="conflicts"):

            @semantic_table(description="x", concept="a")
            class Model:  # pylint: disable=unused-variable
                __semantic_concept__ = "b"

    def test_matching_dunder_is_fine(self):
        @semantic_table(description="x", concept="a")
        class Model:
            __semantic_concept__ = "a"

        assert Model.__semantic_concept__ == "a"


class TestSync:
    def test_concepts_attached_and_validated(self):
        base = _build_models()
        layer = base.sync_semantic_layer(concept_registry=_registry())

        emir = layer.tables["emir_trade_state"]
        assert emir.concept == "trade_report"
        cpty = {c.name: c for c in emir.columns}["counterparty"]
        assert cpty.concept == "counterparty_emir"

        mifir = layer.tables["mifir_transaction"]
        cpty2 = {c.name: c for c in mifir.columns}["counterparty"]
        assert cpty2.concept == "counterparty_mifir"

        assert layer.concept_registry is not None

    def test_unknown_reference_fails_sync(self):
        base = _build_models()
        registry = _registry()
        del registry.concepts["counterparty_mifir"]
        # removing the concept also breaks the DISTINCT_FROM edge, so
        # registry validation itself must fail first
        with pytest.raises(ValueError, match="counterparty_mifir"):
            base.sync_semantic_layer(concept_registry=registry)

    def test_dangling_model_reference_fails_sync(self):
        base = _build_models()
        registry = _registry()
        # registry is internally valid, but the model references a concept
        # the registry does not contain
        registry.concepts["counterparty_emir"].relations.clear()
        registry.concepts["counterparty_mifir"].relations.clear()
        del registry.concepts["counterparty_emir"]
        with pytest.raises(ValueError, match="emir_trade_state.counterparty"):
            base.sync_semantic_layer(concept_registry=registry)

    def test_sync_without_registry_unchanged(self):
        base = _build_models()
        layer = base.sync_semantic_layer()
        assert layer.concept_registry is None
        assert layer.tables["emir_trade_state"].concept == "trade_report"

    def test_layer_to_dict_includes_concepts(self):
        base = _build_models()
        layer = base.sync_semantic_layer(concept_registry=_registry())
        doc = layer.to_dict()
        assert "concepts" in doc
        assert "counterparty_emir" in doc["concepts"]["concepts"]
        table_doc = doc["tables"]["emir_trade_state"]
        assert table_doc["concept"] == "trade_report"

    def test_homonym_is_visible(self):
        registry = _registry()
        assert registry.find_homonyms() == {
            "counterparty": ["counterparty_emir", "counterparty_mifir"]
        }


class TestOsiExport:
    @staticmethod
    def _ext(entity):
        ext = entity["custom_extensions"][0]
        assert ext["vendor_name"] == "SEMANTIDO"
        assert set(ext) == {"vendor_name", "data"}
        return json.loads(ext["data"])

    def test_concepts_travel_in_extensions(self):
        base = _build_models()
        layer = base.sync_semantic_layer(concept_registry=_registry())
        doc = to_osi_dict(layer, model_name="regreport")
        model = doc["semantic_model"][0]

        # model-level: subset registry with only referenced concepts + sources
        model_ext = self._ext(model)
        embedded = model_ext["concept_registry"]
        assert set(embedded["concepts"]) == {
            "trade_report",
            "counterparty_emir",
            "counterparty_mifir",
        }
        assert set(embedded["sources"]) == {"fibo"}
        assert embedded["sources"]["fibo"]["version"] == "2025Q3"

        # dataset-level
        emir = next(ds for ds in model["datasets"] if ds["name"] == "emir_trade_state")
        assert self._ext(emir)["concept"] == "trade_report"

        # field-level
        fields = {f["name"]: f for f in emir["fields"]}
        assert self._ext(fields["counterparty"])["concept"] == "counterparty_emir"

    def test_no_registry_no_concept_payload(self):
        base = _build_models()
        layer = base.sync_semantic_layer()
        doc = to_osi_dict(layer, model_name="regreport")
        model_ext = self._ext(doc["semantic_model"][0])
        assert "concept_registry" not in model_ext
        assert model_ext["exporter"] == "semantido.exporters.osi"
