"""Tests for SL009 — joins that equate concepts asserted DISTINCT_FROM."""

from sqlalchemy import Column, String
from sqlalchemy.orm import DeclarativeBase

from semantido import ConceptRegistry, OntologySource, SemanticBase, semantic_table
from semantido.generators.semantic_layer import Relationship
from semantido.lint import Severity, lint_layer


def _layer(*, distinct: bool = True, same_grain: bool = True):
    class Base(SemanticBase, DeclarativeBase):
        pass

    registry = ConceptRegistry(namespace="reg")
    registry.add_source(
        OntologySource(name="reg", namespace="urn:reg", version="1.0.0")
    )
    emir = registry.concept(
        "counterparty.emir",
        "Either entity party to a derivative contract (EMIR Article 9).",
        label="Counterparty",
        synonyms=["counterparty"],
        grain="legal_entity",
    )
    registry.concept(
        "counterparty.mifir",
        "The market-side entity faced in a transaction (MiFIR RTS 22).",
        label="Counterparty",
        synonyms=["counterparty"],
        grain="legal_entity" if same_grain else "account",
        distinct_from=emir if distinct else None,
    )

    @semantic_table(description="EMIR reports.", concept="counterparty.emir")
    class Emir(Base):
        __tablename__ = "emir_report"
        uti = Column(String(52), primary_key=True)
        cpty_lei = Column(String(20))
        cpty_lei_concept = "counterparty.emir"

    @semantic_table(description="MiFIR reports.", concept="counterparty.mifir")
    class Mifir(Base):
        __tablename__ = "mifir_report"
        tvtic = Column(String(52), primary_key=True)
        cpty_lei = Column(String(20))
        cpty_lei_concept = "counterparty.mifir"

    registry.validate()
    return Base.get_semantic_bridge().sync_from_models(concept_registry=registry)


def _join(layer, condition):
    layer.add_relationship(
        Relationship(
            from_table="emir_report",
            to_table="mifir_report",
            join_condition=condition,
            relationship_type="many_to_many",
            description="test join",
        )
    )
    return layer


def test_sl009_fires_on_distinct_from_join():
    layer = _join(_layer(), "emir_report.cpty_lei = mifir_report.cpty_lei")
    findings = [f for f in lint_layer(layer) if f.code == "SL009"]
    assert len(findings) == 1
    assert findings[0].severity is Severity.ERROR
    assert "counterparty.emir" in findings[0].message
    assert "counterparty.mifir" in findings[0].message


def test_sl009_silent_without_distinct_from_edge():
    layer = _join(
        _layer(distinct=False), "emir_report.cpty_lei = mifir_report.cpty_lei"
    )
    assert not [f for f in lint_layer(layer) if f.code == "SL009"]


def test_sl009_silent_on_same_concept_join():
    layer = _layer()
    layer.add_relationship(
        Relationship(
            from_table="emir_report",
            to_table="emir_report",
            join_condition="emir_report.cpty_lei = emir_report.cpty_lei",
            relationship_type="one_to_one",
            description="self join",
        )
    )
    assert not [f for f in lint_layer(layer) if f.code == "SL009"]


def test_sl009_independent_of_grain():
    """Same grain, different denotation: SL008 stays quiet, SL009 fires."""
    layer = _join(_layer(), "emir_report.cpty_lei = mifir_report.cpty_lei")
    codes = {f.code for f in lint_layer(layer)}
    assert "SL009" in codes
    assert "SL008" not in codes


def test_sl008_and_sl009_both_fire_when_both_hold():
    layer = _join(
        _layer(same_grain=False), "emir_report.cpty_lei = mifir_report.cpty_lei"
    )
    codes = [f.code for f in lint_layer(layer)]
    assert codes.count("SL008") == 1
    assert codes.count("SL009") == 1


def test_sl009_needs_a_registry():
    layer = _join(_layer(), "emir_report.cpty_lei = mifir_report.cpty_lei")
    layer.concept_registry = None
    assert not [f for f in lint_layer(layer) if f.code == "SL009"]
