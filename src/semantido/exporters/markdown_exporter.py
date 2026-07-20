"""Exports a SemanticLayer to Markdown format.

Two source-of-truth artifacts, one combinable render:

- ``to_markdown_tables`` — the physical semantic layer (tables,
  relationships). Anchored by physical names; owned by data engineering;
  changes when the schema changes.
- ``to_markdown_concepts`` — the concept registry (concepts,
  disambiguation). Anchored by business terms; owned by data governance;
  changes when the business understanding changes.
- ``to_markdown`` — the prompt-facing bundle: both artifacts concatenated
  with cross-references resolved (concept blocks list their physical
  anchors via *Realized by*; table blocks gain a *Realizes concepts*
  backlink). This is what gets injected into an LLM context.

Keep the sources separate for governance, retrieval chunking, and diff
history; merge them only at render time.
"""

from semantido.generators.concept_registry import ConceptRegistry
from semantido.generators.semantic_layer import SemanticLayer
from semantido.exporters.utils.markdown import (
    render_concept,
    render_disambiguation,
    render_relationship,
    render_table,
)

#: Valid section names for the ``include`` parameter, in render order.
#: The tiers are additive: *schema* is the bare physical structure
#: (tables, keys, column types, FK targets, relationships); *enriched*
#: adds the semantic annotations onto those same blocks (descriptions,
#: concept bindings, synonyms, contexts, time semantics, default
#: filters, glossary); *concepts* appends the concept registry sections.
#: ``"tables"`` is accepted as an alias for ``("schema", "enriched")``.
INCLUDE_SECTIONS = ("schema", "enriched", "concepts")

#: Back-compat alias: the pre-tier "tables" section is the fully
#: enriched physical layer.
_INCLUDE_ALIASES = {"tables": ("schema", "enriched")}

#: Valid values for the ``scope`` parameter of ``to_markdown_concepts``.
CONCEPT_SCOPES = ("bound", "all")


def _validate_include(include) -> tuple[str, ...]:
    """Normalizes and validates the ``include`` selection.

    Args:
        include: Iterable of section names.

    Returns:
        tuple: The selected sections in canonical render order.

    Raises:
        ValueError: On unknown section names or an empty selection.
    """
    expanded: list[str] = []
    for section in include:
        expanded.extend(_INCLUDE_ALIASES.get(section, (section,)))
    unknown = [s for s in expanded if s not in INCLUDE_SECTIONS]
    if unknown:
        raise ValueError(
            f"Unknown include section(s) {unknown!r}; valid: "
            f"{INCLUDE_SECTIONS} (alias: 'tables' = schema+enriched)"
        )
    if not expanded:
        raise ValueError("include must select at least one section")
    if "enriched" in expanded and "schema" not in expanded:
        raise ValueError(
            "'enriched' is additive over 'schema': enrichment annotates "
            "the structural table blocks and cannot render without them. "
            "Use include=('schema', 'enriched') or the 'tables' alias."
        )
    return tuple(s for s in INCLUDE_SECTIONS if s in expanded)


def _realized_by(layer: SemanticLayer) -> dict[str, list[str]]:
    """Maps concept id -> physical binding sites (table / table.column)."""
    realized: dict[str, list[str]] = {}
    for table in layer.tables.values():
        if table.concept:
            realized.setdefault(table.concept, []).append(table.name)
        for column in table.columns:
            if column.concept:
                realized.setdefault(column.concept, []).append(
                    f"{table.name}.{column.name}"
                )
    return realized


def _concept_refs_by_table(layer: SemanticLayer) -> dict[str, list[str]]:
    """Maps table name -> concept ids realized by its columns.

    The table's own ``concept`` is excluded (it has a dedicated
    ``Concept`` line); column order is preserved and duplicates removed,
    so the backlink line is deterministic.
    """
    refs: dict[str, list[str]] = {}
    for table in layer.tables.values():
        seen: list[str] = []
        for column in table.columns:
            if (
                column.concept
                and column.concept != table.concept
                and column.concept not in seen
            ):
                seen.append(column.concept)
        if seen:
            refs[table.name] = seen
    return refs


def _tables_sections(
    layer: SemanticLayer,
    include_empty: bool,
    with_backlinks: bool,
    enriched: bool = True,
) -> list[str]:
    """Builds the Database Entities, Relationships and Summary sections.

    Args:
        layer: The SemanticLayer instance being exported.
        include_empty: If False, omits null and empty collection values.
        with_backlinks: If True, table blocks carry a *Realizes
            concepts* line. Only the bundle render sets this — a
            tables-only artifact has no concept blocks to link to.
        enriched: If False, renders the *schema* tier only (structural
            facts); if True, adds the *enriched* tier annotations,
            including the Glossary section.

    Returns:
        list: Markdown lines.
    """
    data = layer.to_dict(include_empty=include_empty)
    tables = list(data.get("tables", {}).values())
    relationships = data.get("relationships", [])
    refs = _concept_refs_by_table(layer) if with_backlinks else {}

    lines: list[str] = [f"## Database Entities ({len(tables)} tables)\n"]
    for table in tables:
        lines.extend(
            render_table(table, refs.get(table.get("name")), enriched=enriched)
        )

    if relationships:
        lines.append(f"## Relationships ({len(relationships)} connections)\n")
        for rel in relationships:
            lines.extend(render_relationship(rel))

    if enriched and layer.application_glossary:
        lines.append(f"## Glossary ({len(layer.application_glossary)} terms)\n")
        for term, meaning in layer.application_glossary.items():
            lines.append(f"- **{term}**: {meaning}")
        lines.append("")

    total_columns = sum(len(t.get("columns", [])) for t in tables)
    lines += [
        "## Summary",
        f"- **Total Tables**: {len(tables)}",
        f"- **Total Columns**: {total_columns}",
        f"- **Total Relationships**: {len(relationships)}",
    ]
    return lines


def _concept_sections(layer: SemanticLayer, scope: str = "bound") -> list[str]:
    """Builds the Concepts and Disambiguation sections, if applicable.

    With ``scope="bound"`` (the default, and the bundle's embedding
    rule), only the ``subset()`` closure of concepts actually referenced
    by tables or columns is rendered, so an organization-wide registry
    does not bloat every schema export. The closure follows concept
    relations, which is what carries a bound concept's ``distinct_from``
    homonym partner into the export even when that partner is unrealized
    in this schema.

    With ``scope="all"``, the entire registry is rendered — the shape of
    a standalone governance artifact or an organization-wide concept
    scheme document.

    Args:
        layer: The SemanticLayer instance being exported.
        scope: ``"bound"`` for the referenced closure, ``"all"`` for the
            whole registry.

    Returns:
        list: Markdown lines, empty when no registry (or, for
        ``"bound"``, no bindings).
    """
    if scope not in CONCEPT_SCOPES:
        raise ValueError(f"Unknown scope {scope!r}; valid: {CONCEPT_SCOPES}")
    registry = layer.concept_registry
    if registry is None:
        return []

    realized_by = _realized_by(layer)
    if scope == "bound":
        referenced = set(realized_by)
        if not referenced:
            return []
        scoped_registry = registry.subset(referenced)
    else:
        scoped_registry = registry

    scoped = scoped_registry.to_dict()
    concepts = scoped.get("concepts", {})
    sources = scoped.get("sources", {})

    lines = [
        f"## Concepts ({len(concepts)} in scope)\n",
        "Business concepts realized by this schema. The concept id is the "
        "authoritative reference; labels may collide (see Disambiguation).\n",
    ]
    for concept_id, concept in concepts.items():
        lines.extend(
            render_concept(
                concept_id, concept, sources, realized_by.get(concept_id, [])
            )
        )

    if homonyms := scoped_registry.find_homonyms():
        lines.extend(render_disambiguation(homonyms, concepts, realized_by))
    return lines


def to_markdown(
    layer: SemanticLayer,
    include_empty: bool = False,
    include=INCLUDE_SECTIONS,
):
    """
    Converts the semantic layer into a structured Markdown document.
    Optimized for LLM understanding and natural language to SQL generation.

    By default this is the *bundle*: the physical layer and the concept
    registry concatenated with cross-references resolved. Pass
    ``include=("tables",)`` or ``include=("concepts",)`` to render a
    single artifact (or use the dedicated ``to_markdown_tables`` /
    ``to_markdown_concepts`` helpers).

    Args:
        layer: The SemanticLayer instance to export.
        include_empty: If False (default), omits null and empty collection values.
        include: Which sections to render; any non-empty subset of
            ``("tables", "concepts")``.

    Returns:
        str: A Markdown string representing the selected sections.
    """
    selected = _validate_include(include)
    with_backlinks = "enriched" in selected and "concepts" in selected

    lines: list[str] = [
        "# Semantic Layer\n",
        "Machine-readable database schema for natural language queries\n",
    ]
    if "schema" in selected:
        lines.extend(
            _tables_sections(
                layer,
                include_empty,
                with_backlinks=with_backlinks,
                enriched="enriched" in selected,
            )
        )
    if "concepts" in selected:
        concept_lines = _concept_sections(layer)
        if "schema" in selected and concept_lines:
            lines.append("")
        lines.extend(concept_lines)

    return "\n".join(lines)


def to_markdown_tables(layer: SemanticLayer, include_empty: bool = False) -> str:
    """
    Exports only the physical semantic layer: tables and relationships.

    This is the pre-concept-registry document shape — the artifact owned
    by data engineering, changing when the schema changes. Column-level
    ``concept`` bindings remain visible (they are part of the physical
    layer's metadata), but no concept definitions, external mappings, or
    disambiguation sections are rendered, and table blocks carry no
    *Realizes concepts* backlink (there is nothing in-document to link to).

    Args:
        layer: The SemanticLayer instance to export.
        include_empty: If False (default), omits null and empty collection values.

    Returns:
        str: A Markdown string of the physical layer.
    """
    return to_markdown(
        layer, include_empty=include_empty, include=("schema", "enriched")
    )


def to_markdown_schema(layer: SemanticLayer, include_empty: bool = False) -> str:
    """
    Exports the bare structural tier: tables, keys, column types,
    foreign-key targets, and relationships — no descriptions, contexts,
    concept bindings, time semantics, or glossary.

    This is Markdown-DDL parity: the cheapest per-token context an agent
    can request, and the natural first tool call in a progressive-
    disclosure flow (fetch structure, then request enrichment or
    concepts for the tables that matter).

    Args:
        layer: The SemanticLayer instance to export.
        include_empty: If False (default), omits null and empty collection values.

    Returns:
        str: A Markdown string of the structural tier.
    """
    return to_markdown(layer, include_empty=include_empty, include=("schema",))


def to_markdown_concepts(
    layer: "SemanticLayer | ConceptRegistry", scope: str | None = None
) -> str:
    """
    Exports the concept registry as a standalone document.

    This is the governance artifact — owned by the data governance
    function, changing when the business understanding changes (a new
    homonym discovered, a metric refined, an external mapping added).
    Concept blocks keep their *Realized by* physical anchors, so the
    document cross-references into the physical layer without embedding
    it.

    Accepts a bare ``ConceptRegistry`` directly — no layer needed — for
    the catalog-upload path (Collibra, Purview, ...): the registry is
    the source of truth for meaning and must be exportable without any
    schema attached.

    Args:
        layer: The SemanticLayer whose registry to export, or a
            ``ConceptRegistry`` on its own.
        scope: ``"bound"`` renders only the closure of concepts
            referenced by the schema — the same embedding rule as the
            bundle. ``"all"`` renders the entire registry, the shape of
            an organization-wide concept scheme document. Defaults to
            ``"bound"`` for a layer and ``"all"`` for a bare registry
            (a bare registry has no bindings to scope by).

    Returns:
        str: A Markdown string of the concept registry.
    """
    if isinstance(layer, ConceptRegistry):
        registry_layer = SemanticLayer()
        registry_layer.concept_registry = layer
        layer = registry_layer
        scope = "all" if scope is None else scope
    scope = "bound" if scope is None else scope
    lines: list[str] = [
        "# Concept Registry\n",
        "Business concept definitions, external mappings, and "
        "disambiguation. Physical anchors are listed per concept "
        "(*Realized by*); the physical layer is documented separately.\n",
    ]
    concept_lines = _concept_sections(layer, scope=scope)
    if not concept_lines:
        lines.append(
            "No concept registry is attached to this layer"
            if layer.concept_registry is None
            else "No concepts are bound in this schema."
        )
        return "\n".join(lines)
    lines.extend(concept_lines)
    return "\n".join(lines)


def to_markdown_table(layer: SemanticLayer, include_empty: bool = False) -> str:
    """
    Exports the semantic layer as a Markdown document.

    Args:
        layer: The SemanticLayer instance to export.
        include_empty: If False (default), omits null and empty collection values.

    Returns:
        str: A Markdown string representing the semantic layer.
    """
    data = layer.to_dict(include_empty=include_empty)
    lines: list[str] = ["# Semantic Layer\n"]

    for table_name, table in data.get("tables", {}).items():
        lines.append(f"## {table_name}\n")
        if desc := table.get("description"):
            lines.append(f"{desc}\n")

        columns = table.get("columns", [])
        if columns:
            lines.append("| Column | Type | Description | Privacy |")
            lines.append("| ------ | ---- | ----------- | ------- |")
            for col in columns:
                lines.append(
                    f"| {col.get('name', '')} "
                    f"| {col.get('data_type', '')} "
                    f"| {col.get('description', '')} "
                    f"| {col.get('privacy_level', '')} |"
                )
        lines.append("")

    relationships = data.get("relationships", [])
    if relationships:
        lines.append("## Relationships\n")
        lines.append("| From | To | Type | Join Condition |")
        lines.append("| ---- | -- | ---- | -------------- |")
        for rel in relationships:
            lines.append(
                f"| {rel.get('from_table', '')} "
                f"| {rel.get('to_table', '')} "
                f"| {rel.get('relationship_type', '')} "
                f"| `{rel.get('join_condition', '')}` |"
            )

    if concept_lines := _concept_sections(layer):
        lines.append("")
        lines.extend(concept_lines)

    return "\n".join(lines)


def to_markdown_file(
    layer: SemanticLayer,
    file_path: str,
    include_empty: bool = False,
    table=False,
    include=INCLUDE_SECTIONS,
) -> None:
    """
    Writes the semantic layer to a Markdown file.

    Args:
        layer: The SemanticLayer instance to export.
        file_path: Destination path for the Markdown file.
        include_empty: If False (default), omits null and empty collection values.
        table: if True exports the semantic layer in a table Markdown format
        include: Which sections to render (ignored when ``table`` is
            True); any non-empty subset of ``("tables", "concepts")``.
    """
    with open(file_path, "w", encoding="utf-8") as f:
        if table:
            f.write(to_markdown_table(layer, include_empty=include_empty))
        else:
            f.write(
                to_markdown(layer, include_empty=include_empty, include=include)
            )
