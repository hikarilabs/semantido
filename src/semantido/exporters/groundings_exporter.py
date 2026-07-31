"""Groundings exporter: the deployment half of the meaning/deployment split.

The concept registry serializes *meaning only* — definitions, relations,
external anchors — and is safe to publish, exchange, and version across
organizational boundaries (``registry.to_yaml()``). This module exports
the complementary artifact: *where* each concept is physically grounded
in one specific deployment — which tables and columns realize it.

Design rule: **meaning travels, groundings don't.** A counterparty sends
you their concept file; they never send you their column names. The
grounding file stays with the deployment it describes, and
``semantido.lint`` checks it for staleness against both sides:

* every physical anchor must still exist in the layer (schema drift), and
* every recorded ``definition_checksum`` must still match the registry
  (meaning drift — the definition changed after the grounding was
  recorded, so the binding needs review).
"""

from typing import Any, Optional, Union

from semantido.generators.semantic_layer import SemanticLayer

#: Format identifier written into every grounding document.
GROUNDINGS_FORMAT = "semantido/groundings"
GROUNDINGS_VERSION = "1"


def to_groundings_dict(layer: SemanticLayer) -> dict[str, Any]:
    """Extracts concept groundings from a semantic layer.

    Args:
        layer: The layer whose physical concept bindings to extract.
            Table-level bindings come from ``@semantic_table(concept=...)``
            and column-level bindings from ``{column}_concept`` attributes.

    Returns:
        dict: Deterministically ordered groundings document::

            {
              "format": "semantido/groundings",
              "version": "1",
              "namespace": <registry namespace, if any>,
              "groundings": {
                "<concept_id>": {
                  "definition_checksum": "...", # if registry attached
                  "tables": ["..."], # table-level anchors
                  "columns": ["table.column"], # column-level anchors
                }
              }
            }
    """
    registry = layer.concept_registry
    anchors: dict[str, dict[str, list[str]]] = {}

    def _bucket(concept_id: str) -> dict[str, list[str]]:
        return anchors.setdefault(concept_id, {"tables": [], "columns": []})

    layer_dict = layer.to_dict(include_empty=True)
    for table_name, table_dict in sorted(layer_dict.get("tables", {}).items()):
        if concept_id := table_dict.get("concept"):
            _bucket(concept_id)["tables"].append(table_name)
        for column in table_dict.get("columns", []):
            if col_concept := column.get("concept"):
                _bucket(col_concept)["columns"].append(f"{table_name}.{column['name']}")

    groundings: dict[str, Any] = {}
    for concept_id in sorted(anchors):
        entry: dict[str, Any] = {}
        if registry is not None and concept_id in registry.concepts:
            entry["definition_checksum"] = registry.concepts[
                concept_id
            ].definition_checksum
        if anchors[concept_id]["tables"]:
            entry["tables"] = sorted(anchors[concept_id]["tables"])
        if anchors[concept_id]["columns"]:
            entry["columns"] = sorted(anchors[concept_id]["columns"])
        groundings[concept_id] = entry

    namespace: Optional[str] = registry.namespace if registry else None
    return {
        "format": GROUNDINGS_FORMAT,
        "version": GROUNDINGS_VERSION,
        **({"namespace": namespace} if namespace else {}),
        "groundings": groundings,
    }


def to_groundings_yaml(layer: SemanticLayer) -> str:
    """Serializes the groundings document as YAML text.

    Requires PyYAML (``pip install semantido[osi]``).
    """
    try:
        import yaml  # pylint: disable=C0415
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "PyYAML is required for YAML export. "
            "Install it with: pip install semantido[osi]"
        ) from exc
    return yaml.safe_dump(
        to_groundings_dict(layer), sort_keys=False, allow_unicode=True, width=88
    )


def to_groundings_file(layer: SemanticLayer, file_path: str) -> None:
    """Writes the groundings document to ``file_path`` as YAML."""
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(to_groundings_yaml(layer))


def load_groundings(source: Union[str, dict[str, Any]]) -> dict[str, Any]:
    """Loads and shape-checks a groundings document.

    Args:
        source: A filesystem path to a grounding YAML file, or an
            already-parsed document dict.

    Returns:
        dict: The validated document.

    Raises:
        ValueError: If the document does not carry the expected format
            marker or grounding mapping.
    """
    if isinstance(source, str):
        try:
            import yaml  # pylint: disable=C0415
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "PyYAML is required to load groundings files. "
                "Install it with: pip install semantido[osi]"
            ) from exc
        with open(source, "r", encoding="utf-8") as f:
            document = yaml.safe_load(f)
    else:
        document = source

    if not isinstance(document, dict) or document.get("format") != GROUNDINGS_FORMAT:
        raise ValueError(
            "Not a semantido groundings document: expected "
            f"format={GROUNDINGS_FORMAT!r}"
        )
    if not isinstance(document.get("groundings"), dict):
        raise ValueError("Groundings document has no 'groundings' mapping")
    return document
