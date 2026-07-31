# Linting the layer

`semantido.lint` is a static checker for the *seams* between claim systems.
Every subsystem in a semantic layer validates itself — SQLAlchemy checks the
schema, the concept registry checks its graph, exporters check their formats.
What nothing checks are the cross-references between them, and those rot
silently: a `sql_filter` naming a renamed column, a join condition pointing
at a dropped table, a groundings file recorded against a definition that has
since changed.

The linter is **Tier-2 static**: it never connects to a database and never
calls a model. SQL is parsed with [sqlglot](https://github.com/tobymao/sqlglot):

```bash
pip install semantido[lint]
```

## Usage

```python
from semantido.lint import lint_layer

findings = lint_layer(layer)                            # SL001–SL006, SL008
findings = lint_layer(layer, groundings="groundings.yaml")  # adds SL007

for finding in findings:
    print(finding)

errors = [f for f in findings if f.severity.value == "error"]
assert not errors, "semantic layer lint failed"
```

Findings are returned in deterministic order (errors first), so the output
diffs cleanly in CI. Errors should gate the build; warnings should not.

## Checks

| Code  | Severity | Meaning |
|-------|----------|---------|
| SL001 | error    | `sql_filter` is not parseable SQL (prose leakage). |
| SL002 | error    | `sql_filter` references a column that does not exist. |
| SL003 | error    | Join condition unparseable, unqualified, or unresolvable. |
| SL004 | warning  | `sample_values` inconsistent with the declared type. |
| SL005 | warning  | Synonym claimed by multiple tables, or by columns bound to different concepts. |
| SL006 | warning  | Registry homonym without a declared `DISTINCT_FROM` edge. |
| SL007 | error    | Groundings staleness: missing anchor or `definition_checksum` drift. |
| SL008 | error    | Grain-mismatched join (see below). |

## Grain-mismatched joins (SL008)

Concepts can declare a **grain** — the level at which they identify or
measure their subject:

```python
isin = registry.concept(
    "isin", "Issue-level instrument identifier.", grain="issue")
figi = registry.concept(
    "figi", "Venue-level instrument identifier.",
    grain="listing", distinct_from=isin)
```

Grain is free-form: the registry imposes no vocabulary. But declared grains
are compared **verbatim** by the linter: any join equality between columns
bound to concepts of different grain is an SL008 error. This is the static
form of the classic reference-data trap — joining an issue-level identifier
(one ISIN) to a listing-level identifier (many FIGIs) fans out or drops rows,
and nothing at the schema tier can see it. The linter can, because the
grains are declared.

## What the linter deliberately does not do

Coherence of prose descriptions, intent-to-column matching, and definition
quality are advisory concerns for an LLM judge — never CI gates. The linter
checks only what is mechanically decidable.
