"""Tests for the ``time_dimension`` parameter on ``@semantic_table``."""

import pytest

from sqlalchemy import Column, DateTime, Integer
from sqlalchemy.orm import DeclarativeBase

from semantido import SemanticBase, semantic_table


class _Base(SemanticBase, DeclarativeBase):
    """Isolated registry for this test module."""


def test_decorator_time_dimension_sets_primary_axis():
    @semantic_table(description="events", time_dimension="occurred_at")
    class _Event(_Base):
        __tablename__ = "events_deco"
        id = Column(Integer, primary_key=True)
        occurred_at = Column(DateTime)

    layer = _Base.sync_semantic_layer()
    table = layer.tables["events_deco"]
    assert table.time_dimension == "occurred_at"
    assert [c.name for c in table.columns if c.is_time_dimension] == ["occurred_at"]


def test_dunder_still_supported():
    @semantic_table(description="events")
    class _Event(_Base):
        __tablename__ = "events_dunder"
        __semantic_time_dimension__ = "occurred_at"
        id = Column(Integer, primary_key=True)
        occurred_at = Column(DateTime)

    layer = _Base.sync_semantic_layer()
    assert layer.tables["events_dunder"].time_dimension == "occurred_at"


def test_matching_decorator_and_dunder_is_allowed():
    @semantic_table(description="events", time_dimension="occurred_at")
    class _Event(_Base):
        __tablename__ = "events_both"
        __semantic_time_dimension__ = "occurred_at"
        id = Column(Integer, primary_key=True)
        occurred_at = Column(DateTime)

    layer = _Base.sync_semantic_layer()
    assert layer.tables["events_both"].time_dimension == "occurred_at"


def test_conflicting_decorator_and_dunder_raises():
    with pytest.raises(ValueError, match="conflicts with"):

        @semantic_table(description="events", time_dimension="occurred_at")
        class _Event(_Base):
            __tablename__ = "events_conflict"
            __semantic_time_dimension__ = "created_at"
            id = Column(Integer, primary_key=True)
            occurred_at = Column(DateTime)
            created_at = Column(DateTime)
