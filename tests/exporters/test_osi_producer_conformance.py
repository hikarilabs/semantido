# Copyright 2025 Dragos Crintea - HikariLabs LTD
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
"""Producer-conformance regression tests for the OSI exporter.

Each test pins one defect found by running OSI Foundation section 6.4
cardinality inference against the exporter's own output:

1. Composite primary keys were truncated to their first column -- a false
   uniqueness assertion. Under OSI's trust-but-don't-validate principle an
   engine would infer 1:1 where reality is N:1 and skip fan-out protection,
   producing silently doubled aggregates (a Semantic 2 violation caused by
   the producer).
2. Unique constraints were never emitted, so relationships joining on a
   business key degraded to worst-case N:N inference.
3. Relationship direction followed ORM declaration order rather than FK
   topology; OSI section 4.4 requires ``from`` = many/FK side.
"""

import pytest

from sqlalchemy import Column, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, relationship

from semantido import SemanticBase, semantic_table
from semantido.generators.semantic_bridge import SQLAlchemySemanticBridge
from semantido.exporters import to_osi_dict


class _Base(SemanticBase, DeclarativeBase):
    """Isolated registry so these models don't leak into other tests."""


@semantic_table(description="Customer master.")
class _Customer(_Base):
    __tablename__ = "conf_customers"
    __table_args__ = (UniqueConstraint("customer_code", name="uq_conf_customer_code"),)

    id = Column(Integer, primary_key=True)
    customer_code = Column(String, nullable=False)

    orders = relationship("_Order", back_populates="customer")


@semantic_table(description="Orders, FK on the business key.")
class _Order(_Base):
    __tablename__ = "conf_orders"

    order_id = Column(Integer, primary_key=True)
    customer_code = Column(String, ForeignKey("conf_customers.customer_code"))
    amount = Column(Numeric)

    customer = relationship("_Customer", back_populates="orders")
    lines = relationship("_OrderLine", back_populates="order")


@semantic_table(description="Order lines with a composite primary key.")
class _OrderLine(_Base):
    __tablename__ = "conf_order_lines"

    order_id = Column(Integer, ForeignKey("conf_orders.order_id"), primary_key=True)
    line_id = Column(Integer, primary_key=True)
    qty = Column(Integer)

    order = relationship("_Order", back_populates="lines")


@pytest.fixture(scope="module")
def osi_model():
    bridge = SQLAlchemySemanticBridge(_Base)
    layer = bridge.sync_from_models()
    return to_osi_dict(layer, "producer_conformance")["semantic_model"][0]


@pytest.fixture(scope="module")
def datasets(osi_model):
    return {dataset["name"]: dataset for dataset in osi_model["datasets"]}


@pytest.fixture(scope="module")
def relationships(osi_model):
    return {rel["name"]: rel for rel in osi_model.get("relationships", [])}


def test_composite_primary_key_is_complete(datasets):
    """A composite PK must keep every member column; truncating it asserts
    a uniqueness the data does not have."""
    assert datasets["conf_order_lines"]["primary_key"] == ["order_id", "line_id"]


def test_single_column_primary_key_unchanged(datasets):
    assert datasets["conf_customers"]["primary_key"] == ["id"]
    assert datasets["conf_orders"]["primary_key"] == ["order_id"]


def test_unique_constraint_is_emitted(datasets):
    """UniqueConstraint must surface as OSI ``unique_keys`` so section 6.4
    infers N:1 on the business-key edge instead of worst-case N:N."""
    assert datasets["conf_customers"].get("unique_keys") == [["customer_code"]]


def test_tables_without_unique_constraints_omit_the_key(datasets):
    assert "unique_keys" not in datasets["conf_orders"]
    assert "unique_keys" not in datasets["conf_order_lines"]


def test_relationships_are_fk_side_from(relationships):
    """OSI section 4.4: ``from`` = many/FK side, ``to`` = one/PK-UK side,
    regardless of which class declared the ORM relationship."""
    business_key_edge = relationships["conf_orders_to_conf_customers"]
    assert business_key_edge["from"] == "conf_orders"
    assert business_key_edge["to"] == "conf_customers"
    assert business_key_edge["from_columns"] == ["customer_code"]
    assert business_key_edge["to_columns"] == ["customer_code"]

    line_edge = relationships["conf_order_lines_to_conf_orders"]
    assert line_edge["from"] == "conf_order_lines"
    assert line_edge["to"] == "conf_orders"


def test_no_inverted_relationships_emitted(relationships):
    """The parent-declared one-to-many must not surface as a separate,
    inverted edge; deduplication is orientation-independent."""
    assert "conf_customers_to_conf_orders" not in relationships
    assert "conf_orders_to_conf_order_lines" not in relationships


def test_foundation_cardinality_inference_matches_schema(datasets, relationships):
    """End-to-end: run OSI Foundation section 6.4 inference on the emitted
    model and require the cardinality the true schema implies."""

    def declared_keys(name):
        dataset = datasets[name]
        keys = []
        if dataset.get("primary_key"):
            keys.append(dataset["primary_key"])
        keys.extend(dataset.get("unique_keys", []))
        return keys

    def infer(rel):
        to_unique = rel["to_columns"] in declared_keys(rel["to"])
        from_unique = rel["from_columns"] in declared_keys(rel["from"])
        return f"{'1' if from_unique else 'N'}:{'1' if to_unique else 'N'}"

    assert infer(relationships["conf_orders_to_conf_customers"]) == "N:1"
    assert infer(relationships["conf_order_lines_to_conf_orders"]) == "N:1"
