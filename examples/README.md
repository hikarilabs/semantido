# Examples

Each folder is self-contained and runnable. 01 is the full walkthrough and is
current with v0.5; 02–05 demonstrate earlier feature sets; 06–08 cover grain,
groundings and lint in depth.

|    | Example                   | Demonstrates                                           | Needs                   |
|----|---------------------------|--------------------------------------------------------|-------------------------|
| 01 | `01_getting_started`      | Concepts, grain, exports, lint gate, EMIR/MiFIR schema | `semantido[lint,ossie]` |
| 02 | `02_ossie_time_dimension` | `time_dimension`, time grain, three OSI strategies     | —                       |
| 03 | `03_md_vs_ossie_context`  | Markdown vs Ossie YAML as text-to-SQL context          | `ANTHROPIC_API_KEY`     |
| 04 | `04_federated_agents`     | Concept registry, cross-institution alignment          | —                       |
| 05 | `05_toolchain_drift`      | External mappings, drift across a toolchain            | —                       |
| 06 | `06_groundings_and_lint`  | Groundings, SL007, SL009, SL010                        | `semantido[lint]`       |
| 07 | `07_security_master`      | Grain, fan-out, and the limits of static checks        | `semantido[lint]`       |
| 08 | `08_release_timeline`     | What each release could express and enforce            | git checkout            |

## Where to start

**New to the library** → `01_getting_started`, then `07_security_master`.

**Evaluating whether a semantic layer is worth it** → `07_security_master`
for the failure mode, then `08_release_timeline` for what it costs in context
tokens (629 → 660 across the whole release history).

**Setting up a CI gate** → `06_groundings_and_lint`.

## A note on scope

`07_security_master` and `08_release_timeline` both show a failure the linter
does **not** catch: a join where the same concept keys both sides at the same
grain fans out, and no shipped check has ever caught it. That is deliberate.
Cardinality is a separate axis from grain and needs the column tuple that
makes a row unique — a v0.6 question.

Examples that assert what the library catches are only useful if they are
equally clear about what it does not.
