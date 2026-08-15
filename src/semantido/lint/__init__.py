"""semantido.lint — static checks for the seams between claim systems.

Every subsystem in a semantic layer validates itself: SQLAlchemy checks
the schema, the concept registry checks its graph, exporters check their
formats. What nothing checks are the *seams* — the cross-references
between systems that drift silently: a ``sql_filter`` naming a renamed
column, a join condition pointing at a dropped table, a sample value
that stopped matching its column type, a grounding file recorded
against a definition that has since changed.

The linter owns the seams. It is a Tier-2 *static* check: it never
connects to a database and never calls a model. SQL is parsed with
`sqlglot <https://github.com/tobymao/sqlglot>`_ (install with
``pip install semantido[lint]``).

Checks
------

======  ========  ======================================================
Code    Severity  Meaning
======  ========  ======================================================
SL001   error     ``sql_filter`` is not parseable SQL (prose leakage).
SL002   error     ``sql_filter`` references a column not on its table.
SL003   error     Relationship join condition is unparseable or
                  references an unknown table/column.
SL004   warning   ``sample_values`` inconsistent with the declared
                  column type.
SL005   warning   The same synonym is claimed by multiple tables or by
                  multiple columns bound to different concepts.
SL006   warning   Registry surface-form collision (homonym) without a
                  declared ``DISTINCT_FROM`` edge between the claimants.
SL007   error     Groundings staleness: a recorded physical anchor no
                  longer exists in the layer, or a recorded
                  ``definition_checksum`` no longer matches the
                  registry (meaning drift).
SL008   error     Grain-mismatched join: a join condition equates
                  columns bound to concepts with different declared
                  ``grain`` (e.g., an issue-level identifier joined to a
                  listing-level identifier).
SL009   error     Denotation-mismatched join: a join condition equates
                  two concepts asserted ``DISTINCT_FROM``. Independent
                  of grain — concepts may share a grain and still
                  denote different things.
SL010   error     Contradictory external mapping: two concepts asserted
                  ``DISTINCT_FROM`` both claim ``skos:exactMatch`` to
                  the same target. exactMatch is transitive, so this
                  entails they are interchangeable.
======  ========  ======================================================

Usage:

    from semantido.lint import lint_layer

    findings = lint_layer(layer)                      # SL001-SL006, SL008
    findings = lint_layer(layer, groundings=path)     # + SL007
    for f in findings:
        print(f)
"""

from semantido.lint.linter import Finding, Severity, lint_layer

__all__ = ["Finding", "Severity", "lint_layer"]
