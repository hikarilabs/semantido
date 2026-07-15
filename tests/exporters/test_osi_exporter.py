"""Tests for the OSI exporter.

``to_osi_dict`` tests run in every environment. ``to_osi_yaml`` tests are
skipped unless PyYAML is installed (the ``semantido[osi]`` extra), so a
contributor on a base install gets skips rather than failures.
"""

import pytest

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import DeclarativeBase, relationship

from semantido import SemanticBase, semantic_table
from semantido.exporters import to_osi_dict
from semantido.generators.semantic_layer import PrivacyLevel, TimeGrain


class _Base(SemanticBase, DeclarativeBase):
    """Isolated registry so these models don't leak into other tests."""


@semantic_table(
    description="Derivative trades",
    synonyms=["trades"],
    sql_filters=["action_type != 'E'"],
    business_context="Notional is unsigned.",
)
class _Trade(_Base):
    __tablename__ = "trades"
    __semantic_time_dimension__ = "executed_at"

    trade_id = Column(Integer, primary_key=True)
    executed_at = Column(DateTime, nullable=False)
    notional = Column(Numeric(20, 2), nullable=False)
    created_at = Column(DateTime, nullable=False)
    book_id = Column(Integer, ForeignKey("books.book_id"))

    executed_at_time_grain = TimeGrain.SECOND
    notional_description = "Unsigned trade notional."
    notional_privacy_level = PrivacyLevel.RESTRICTED
    notional_sample_values = ["1000000.00"]

    book = relationship("_Book", back_populates="trades")


@semantic_table(description="Trading books")
class _Book(_Base):
    __tablename__ = "books"

    book_id = Column(Integer, primary_key=True)
    name = Column(String(50))

    trades = relationship("_Trade", back_populates="book")


@pytest.fixture(name="layer")
def layer_fixture():
    layer = _Base.sync_semantic_layer()
    layer.application_glossary["notional"] = "unsigned contract size"
    return layer


def _ext_data(entity):
    """Decodes the SEMANTIDO custom extension payload (spec: JSON string in `data`)."""
    import json

    ext = entity["custom_extensions"][0]
    assert ext["vendor_name"] == "SEMANTIDO"
    assert set(ext) == {"vendor_name", "data"}, "extensions must be {vendor_name, data}"
    return json.loads(ext["data"])


def test_to_osi_dict_structure(layer):
    doc = to_osi_dict(layer, model_name="test_model")
    model = doc["semantic_model"][0]

    assert model["name"] == "test_model"
    assert {ds["name"] for ds in model["datasets"]} == {"trades", "books"}
    assert "Glossary" in model["ai_context"]["instructions"]
    assert doc["version"] == "0.2.0.dev0"
    assert _ext_data(model)["exporter"] == "semantido.exporters.osi"


def test_to_osi_dict_time_dimension_policy(layer):
    doc = to_osi_dict(layer, model_name="test_model")
    trades = next(
        ds for ds in doc["semantic_model"][0]["datasets"] if ds["name"] == "trades"
    )
    fields = {f["name"]: f for f in trades["fields"]}

    # Primary time axis flagged, grain serialized as plain string
    assert fields["executed_at"]["dimension"] == {"is_time": True}
    assert (
        "PRIMARY time dimension" in fields["executed_at"]["ai_context"]["instructions"]
    )
    ext = _ext_data(fields["executed_at"])
    assert ext["time_grain"] == "second"
    assert ext["is_primary_time_dimension"] is True

    # Audit column demoted with an explicit instruction
    assert "dimension" not in fields["created_at"]
    assert (
        "do not use as a time axis"
        in fields["created_at"]["ai_context"]["instructions"]
    )

    # Privacy level travels via vendor extension
    assert _ext_data(fields["notional"])["privacy_level"] == "restricted"


def test_to_osi_dict_relationship_dedup(layer):
    doc = to_osi_dict(layer, model_name="test_model")
    rels = doc["semantic_model"][0]["relationships"]

    # trades<->books is bidirectional in the ORM but exported once
    assert len(rels) == 1
    rel = rels[0]
    assert {rel["from"], rel["to"]} == {"trades", "books"}
    assert rel["from_columns"] and rel["to_columns"]


def test_to_osi_dict_is_yaml_safe(layer):
    """Every value must be a plain type — no enums, no str subclasses."""

    def assert_plain(obj, path="$"):
        if isinstance(obj, dict):
            for k, v in obj.items():
                assert type(k) is str, f"{path}.{k}: key type {type(k)}"
                assert_plain(v, f"{path}.{k}")
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                assert_plain(v, f"{path}[{i}]")
        elif obj is not None:
            assert type(obj) in (str, int, float, bool), f"{path}: {type(obj)}"

    assert_plain(to_osi_dict(layer, model_name="test_model"))


def test_to_osi_yaml_round_trip(layer, tmp_path):
    yaml = pytest.importorskip("yaml", reason="requires semantido[osi]")
    from semantido.exporters import to_osi_yaml

    out = tmp_path / "model.osi.yaml"
    text = to_osi_yaml(layer, model_name="test_model", path=str(out))

    parsed = yaml.safe_load(text)
    assert parsed == to_osi_dict(layer, model_name="test_model")
    assert yaml.safe_load(out.read_text(encoding="utf-8")) == parsed
