# OSI export and the time dimension — a three-strategy comparison

Exports a small core-banking model (`account_info`, `transaction_info`) to
[Open Semantic Interchange](https://github.com/open-semantic-interchange/OSI)
YAML under three time-dimension strategies, and reports what an OSI consumer
— an agent or a BI tool — sees under each.

The `transaction_info` table is deliberately adversarial: five temporal
columns (`booking_date`, `value_date`, `settlement_date`, `created_at`,
`updated_at`), of which exactly one is the axis an agent should `GROUP BY`
for "monthly transaction volume". The primary axis is declared with the
first-class `@semantic_table(time_dimension="booking_date")` keyword
(new in 0.3), with `<col>_time_grain` and `<col>_is_time_dimension`
sibling attributes for grain and secondary axes.

## Run it

```bash
pip install semantido pyyaml
cd examples/02_osi_time_dimension
python compare_osi_strategies.py
```

## What you'll see

| strategy                              | `is_time` flags                                                                                                      | for the agent                                 |
|---------------------------------------|----------------------------------------------------------------------------------------------------------------------|-----------------------------------------------|
| **off** — no time metadata            | 0                                                                                                                    | booking vs value vs settlement is a coin toss |
| **naive** — flag every DATE/TIMESTAMP | 8 (incl. `created_at`, `updated_at`)                                                                                 | 1-in-5 signal-to-noise on transactions        |
| **curated** — semantido default       | 4 business dates; `booking_date` PRIMARY, grain `day`; audit columns demoted with an explicit do-not-use instruction | one unambiguous axis                          |

Outputs land in `exports/`: the three OSI YAML files (diffable side by side)
and `comparison_report.txt`.

## Files

- `models/core_banking.py` — the two models with primary axis, a secondary
  axis, grains, privacy levels, and audit columns declared.
- `compare_osi_strategies.py` — builds the layer once, exports it three ways
  with the real exporter, validates YAML round-trips, writes the report.

For the full analysis of *why* the strategies differ — which metadata signal
does the work, and what `TimeGrain` does and does not contribute — see the
companion article, and `examples/03_md_vs_osi_context` for the follow-on
question of how the OSI export compares with semantido's Markdown export as
LLM prompt context.
