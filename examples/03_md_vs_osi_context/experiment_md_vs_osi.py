"""Experiment: semantido Markdown vs. OSI YAML as LLM context for text-to-SQL.

Design
------
One semantic layer, three serializations fed as the ONLY schema context to a
text-to-SQL prompt:

    MD — semantido's Markdown export as shipped today.
    OSI — semantido's OSI YAML export as shipped today.
    MD_ENRICHED — the Markdown export plus a plain-text block containing the
                   structured signals MD does not yet emit (primary time axis,
                   grains, audit warnings, sql_filters, glossary).

The third condition is the control that decomposes the comparison: MD vs. OSI
differ in BOTH format and information content, so a raw A/B cannot say which
mattered. MD vs. MD_ENRICHED isolates the content effect at (near) constant
format; MD_ENRICHED vs. OSI isolates the format effect at (near) constant
content.

Six probe questions each target one metadata signal, scored deterministically
with regex checks on the generated SQL (requires = all must match,
forbids = none may match). The primary metric is the per-condition pass rate.

Usage
-----
    python experiment_md_vs_osi.py # builds contexts + structural report
    ANTHROPIC_API_KEY=... python experiment_md_vs_osi.py --trials 5
                                                   # + runs the live evaluation

Without a key the script still produces the three context files and the
structural comparison; with a key it calls the Anthropic API directly
(no SDK needed) and writes results.csv + a summary.
"""

import argparse
import csv
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

from semantido import SemanticDeclarativeBase
from semantido.exporters import to_markdown, to_osi_yaml

# Models live in example 02 — single source of truth, no duplication.
sys.path.insert(0, str(Path(__file__).parent.parent / "02_osi_time_dimension"))
import models.core_banking  # noqa: E402,F401 (registers the mapped classes)

OUT = Path(__file__).parent / "exports"
API_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = (
    "You are a text-to-SQL engine. Using ONLY the schema context provided, "
    "translate the user's question into a single ANSI SQL query. Output the "
    "SQL and nothing else — no explanation, no markdown fences."
)

QUESTIONS = [
    {
        "id": "monthly_volume",
        "signal": "primary time axis",
        "question": "How many transactions were posted each month in 2025? "
        "Return the month and the count.",
        "requires": [r"booking_date"],
        "forbids": [r"created_at", r"updated_at", r"value_date", r"settlement_date"],
    },
    {
        "id": "daily_audit_trap",
        "signal": "audit demotion",
        "question": "Show the number of transactions per day for the last 30 days.",
        "requires": [r"booking_date"],
        "forbids": [r"created_at", r"updated_at"],
    },
    {
        "id": "default_filter",
        "signal": "sql_filters / application context",
        "question": "How many accounts do we have per currency?",
        "requires": [r"account_status\s*=\s*'ACTIVE'"],
        "forbids": [],
    },
    {
        "id": "value_dating",
        "signal": "secondary axis routing",
        "question": "What is the total amount becoming interest-effective "
        "per account in March 2026?",
        "requires": [r"value_date"],
        "forbids": [r"booking_date", r"settlement_date", r"created_at"],
    },
    {
        "id": "debit_sign",
        "signal": "sign convention (context prose)",
        "question": "How much money was debited in total across all accounts "
        "in January 2026?",
        "requires": [
            r"booking_date",
            r"(amount\s*<\s*0|abs\s*\(|-\s*sum|sum\s*\(\s*case)",
        ],
        "forbids": [r"created_at", r"updated_at"],
    },
    {
        "id": "net_flow_join",
        "signal": "relationships + axis + glossary",
        "question": "What is the net flow per currency for 2025?",
        "requires": [r"booking_date", r"sum\s*\(", r"currency_code"],
        "forbids": [r"created_at", r"updated_at"],
    },
]


def build_contexts() -> dict[str, str]:
    """Builds the three context conditions from one synchronized layer."""
    layer = SemanticDeclarativeBase.sync_semantic_layer()
    layer.application_glossary.update(
        {
            "booking date": "date a movement is booked to the account (the axis)",
            "value date": "date a movement becomes interest-effective",
            "net flow": "signed sum of amounts over a period (not turnover)",
        }
    )

    md = to_markdown(layer)
    osi = to_osi_yaml(
        layer,
        model_name="core_banking_analytics",
        instructions=(
            "Wholesale/retail core banking model. Respect each dataset's "
            "application context and default filters."
        ),
    )

    # MD_ENRICHED: append the structured signals MD does not yet emit,
    # phrased as plain text so the format stays Markdown-like.
    extra = ["", "## Time semantics and defaults", ""]
    for table_name, table in layer.tables.items():
        if table.time_dimension:
            extra.append(
                f"- {table_name}: PRIMARY time dimension = {table.time_dimension} "
                f"(use for any per-day/month/quarter aggregation)"
            )
        for column in table.columns:
            if column.time_grain:
                extra.append(
                    f"- {table_name}.{column.name}: native grain "
                    f"{column.time_grain.value}"
                )
            if column.is_time_dimension and column.name != table.time_dimension:
                extra.append(f"- {table_name}.{column.name}: secondary time dimension")
            if column.name in ("created_at", "updated_at"):
                extra.append(
                    f"- {table_name}.{column.name}: operational audit timestamp "
                    f"— do not use as a time axis"
                )
        if table.sql_filters:
            extra.append(
                f"- {table_name}: default filter -> {' AND '.join(table.sql_filters)}"
            )
    extra += ["", "## Glossary", ""]
    extra += [f"- {k}: {v}" for k, v in layer.application_glossary.items()]
    md_enriched = md + "\n".join(extra) + "\n"

    contexts = {"md": md, "osi": osi, "md_enriched": md_enriched}
    OUT.mkdir(exist_ok=True)
    (OUT / "context_md.md").write_text(md)
    (OUT / "context_osi.yaml").write_text(osi)
    (OUT / "context_md_enriched.md").write_text(md_enriched)
    return contexts


def structural_report(contexts: dict[str, str]) -> str:
    """Signal-presence matrix and token estimates across conditions."""
    checks = {
        "data types (INTEGER/DATE/...)": r"\(INTEGER|\(DATE|\(DECIMAL",
        "primary time axis (structured)": r"is_primary_time_dimension|PRIMARY time dimension",
        "time grain": r"time_grain|[Nn]ative grain",
        "audit demotion warning": r"do not use as a time axis",
        "default sql filters": r"sql_filters|default filter",
        "privacy levels": r"restricted|confidential",
        "sample values": r"Examples\*|sample_values",
        "glossary": r"[Gg]lossary",
        "join conditions": r"account_id\s*=\s*transaction_info|columns:",
        "cardinality": r"one-to-many|relationship_type",
    }
    lines = ["STRUCTURAL COMPARISON — signal presence per context", "=" * 60]
    header = f"{'signal':38}" + "".join(f"{c:>13}" for c in contexts)
    lines.append(header)
    for name, pattern in checks.items():
        row = f"{name:38}"
        for text in contexts.values():
            row += f"{'Y' if re.search(pattern, text) else '-':>13}"
        lines.append(row)
    lines.append("")
    for name, text in contexts.items():
        lines.append(f"{name:12}: {len(text):5d} chars (~{len(text) // 4} tokens)")
    return "\n".join(lines)


def call_model(api_key: str, model: str, context: str, question: str) -> str:
    """Single Anthropic API call; returns the raw text answer."""
    payload = {
        "model": model,
        "max_tokens": 600,
        "system": SYSTEM_PROMPT,
        "messages": [
            {
                "role": "user",
                "content": f"Schema context:\n\n{context}\n\nQuestion: {question}",
            }
        ],
    }
    request = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode(),
        headers={
            "content-type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        data = json.loads(response.read())
    return "".join(block.get("text", "") for block in data.get("content", [])).strip()


def score(sql: str, spec: dict) -> bool:
    """Deterministic pass/fail: all requires match, no forbids match."""
    lowered = sql.lower()
    if any(re.search(p, lowered, re.IGNORECASE) for p in spec["forbids"]):
        return False
    return all(re.search(p, lowered, re.IGNORECASE) for p in spec["requires"])


def run_eval(contexts: dict[str, str], api_key: str, model: str, trials: int):
    """Full grid: condition x question x trial. Writes CSV + prints summary."""
    rows = []
    for condition, context in contexts.items():
        for spec in QUESTIONS:
            for trial in range(trials):
                sql = call_model(api_key, model, context, spec["question"])
                passed = score(sql, spec)
                rows.append(
                    {
                        "condition": condition,
                        "question_id": spec["id"],
                        "signal": spec["signal"],
                        "trial": trial,
                        "passed": passed,
                        "sql": sql.replace("\n", " "),
                    }
                )
                print(
                    f"[{condition:12}] {spec['id']:18} trial {trial}: "
                    f"{'PASS' if passed else 'FAIL'}"
                )

    with open(OUT / "results.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print("\nPASS RATE BY CONDITION")
    for condition in contexts:
        subset = [r for r in rows if r["condition"] == condition]
        rate = sum(r["passed"] for r in subset) / len(subset)
        print(
            f"  {condition:12}: {rate:6.1%}  ({sum(r['passed'] for r in subset)}"
            f"/{len(subset)})"
        )

    print("\nPASS RATE BY CONDITION x QUESTION")
    for spec in QUESTIONS:
        line = f"  {spec['id']:18}"
        for condition in contexts:
            subset = [
                r
                for r in rows
                if r["condition"] == condition and r["question_id"] == spec["id"]
            ]
            line += f"  {condition}={sum(r['passed'] for r in subset)}/{len(subset)}"
        print(line)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--trials", type=int, default=3)
    args = parser.parse_args()

    contexts = build_contexts()
    report = structural_report(contexts)
    (OUT / "structural_comparison.txt").write_text(report + "\n")
    print(report)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print(
            "\nNo ANTHROPIC_API_KEY set — contexts and structural report "
            "written; skipping the live evaluation."
        )
        return
    run_eval(contexts, api_key, args.model, args.trials)


if __name__ == "__main__":
    main()
