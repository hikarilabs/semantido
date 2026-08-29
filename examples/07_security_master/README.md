# 07 — Security master: grain, fan-out, and the limits of static checks

The worked example behind the v0.5 release article, as a computation rather
than a claim. The twelve-row matrix is derived from the fixture, not typed out.

```bash
pip install 'semantido[lint]>=0.5.3'
python run_example.py
```

## The domain

A security master reconciles Bloomberg, Refinitiv and ANNA into one golden
record. Three identifiers, three grains:

| Concept | Grain | Identifies |
|---------|---------|------------|
| `isin` | `issue` | One security as issued, wherever it trades |
| `figi` | `listing` | One instrument on one venue |
| `ric` | `listing` | One instrument on one venue, with vendor quote conventions |

These are not synonyms. Vodafone Group plc ordinary shares — `GB00BH4HKS39` —
is one issue, three Bloomberg listings and four Refinitiv listings.

## The result

`ON b.isin = r.isin` returns twelve rows for one instrument. Three are
meaningful like-for-like comparisons. Seven raise as breaks because they
compare London against Xetra. Two agree by coincidence and pass silently —
and if either had held a genuine discrepancy it would have cleared the check.

Signal: 25%, decaying to 7% by the time vendor coverage reaches 12 × 15.

Nothing objects, because nothing is technically broken. ISIN is not a key on
either side; it is an issue-grain value repeated once per listing, so the
equi-join emits every matching pair. The reconciliation wanted the diagonal
and computed the whole matrix.

## The uncomfortable part

| Join | Grains | Lint | Rows |
|------|--------|------|------|
| `figi = ric` | listing vs listing | silent | 0, no overlap |
| `isin = ric` | issue vs listing | **SL008 + SL009 fire** | 0, empty set |
| `isin = isin` | issue vs issue | silent | **12, fan-out** |

The linter fires on the join that returns nothing and stays silent on the join
that returns twelve wrong rows.

That is not a bug. A grain *mismatch* implies different value spaces, so the
equality never matches — loud, obvious, fixed in minutes. The fan-out requires
the same concept on both sides, which is precisely the case a grain comparison
cannot see.

Cardinality is the missing axis. Grain expressed as a single string cannot
carry it; it needs the column tuple that makes a row unique. That is a v0.6
question.

## Also worth reading

`business_context` on `BloombergFeed` records that the feed is
licence-encumbered and that redistributing `px_last` outside the licensed desk
is an audit exposure. And `px_last_description` on `RefinitivFeed` records that
UK equity RICs quote in pence while the ISIN-level record is GBP.

No DDL will ever contain those sentences, and no schema registry will infer
them. Without the second one, every cross-venue price comparison produces a
hundred-fold break.
