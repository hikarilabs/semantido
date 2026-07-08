"""Tests that semantic layer extraction order is deterministic.

``registry.mappers`` is a frozenset, so without explicit sorting the
table order would vary across Python processes (hash randomization),
making committed export artifacts churn on every regeneration.
"""

from sqlalchemy import Column, DateTime, ForeignKey, Integer
from sqlalchemy.orm import DeclarativeBase, relationship

from semantido import SemanticBase, semantic_table


class _Base(SemanticBase, DeclarativeBase):
    """Isolated registry for this test module."""


@semantic_table(description="zebras table — sorts last")
class _Zebra(_Base):
    __tablename__ = "zebras"
    id = Column(Integer, primary_key=True)
    herd_id = Column(Integer, ForeignKey("herds.id"))
    herd = relationship("_Herd", back_populates="zebras")


@semantic_table(description="herds table — sorts middle")
class _Herd(_Base):
    __tablename__ = "herds"
    id = Column(Integer, primary_key=True)
    zebras = relationship("_Zebra", back_populates="herd")


@semantic_table(description="areas table — sorts first")
class _Area(_Base):
    __tablename__ = "areas"
    id = Column(Integer, primary_key=True)
    seen_at = Column(DateTime)


def test_tables_extracted_in_sorted_order():
    layer = _Base.sync_semantic_layer()
    assert list(layer.tables) == ["areas", "herds", "zebras"]


def test_repeated_sync_is_stable():
    first = _Base.sync_semantic_layer().to_dict()
    second = _Base.sync_semantic_layer().to_dict()
    assert first == second
    assert list(first["tables"]) == sorted(first["tables"])
