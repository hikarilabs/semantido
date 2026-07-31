# Groundings: meaning travels, groundings don't

The concept registry serializes **meaning only** — definitions, relations,
external anchors (`registry.to_yaml()`). That artifact is safe to publish,
exchange, and version across organizational boundaries: a counterparty sends
you their concepts file; they never send you their column names.

The **groundings file** is the complementary artifact: where each concept is
physically realized in *one specific deployment*.

```python
from semantido.exporters import to_groundings_file

to_groundings_file(layer, "groundings.yaml")
```

```yaml
format: semantido/groundings
version: "1"
namespace: secmaster
groundings:
  isin:
    definition_checksum: "3f8a…"
    columns:
      - anna_dsb_reference.dsb_isin
      - bbg_instrument_feed.id_isin
      - security_master.primary_isin
```

Each entry records the concept's `definition_checksum` at recording time, so
staleness is checkable in **both directions** by `semantido.lint` (SL007):

- **Schema drift** — an anchor table or column no longer exists in the layer.
- **Meaning drift** — the definition changed after the grounding was
  recorded, so the binding needs human re-review before the checksum is
  re-stamped.

## The split, operationally

| Artifact | Contains | Travels? | Checked by |
|----------|----------|----------|------------|
| `concepts.yaml` (`registry.to_yaml()`) | definitions, relations, external mappings, grain | yes — the unit of exchange | `registry.validate()` |
| `groundings.yaml` (`to_groundings_file()`) | concept → tables/columns, checksums | no — stays with the deployment | `semantido.lint` SL007 |

Regenerate the groundings file whenever the schema or bindings change;
treat an SL007 checksum-drift error as a review task, not a regeneration
task — the point is that meaning changed under a live binding.
