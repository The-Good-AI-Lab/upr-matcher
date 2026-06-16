# Extraction Stability Eval: costa_rica_2024

- Run ID: `pr1_extraction_stability_default_20260616`
- Trace JSON: `/home/arthur/Documents/gail/upr-matcher/evals/traces/live/pr1_extraction_stability_default_20260616.json`
- Source language: `es`
- OpenRouter calls: 3 (~$0.142374 estimated)
- Repeats completed: 3
- Successful repeats: 1
- Failed repeats: 2

## Aggregate

| Metric | Min | Mean | Max |
| --- | ---: | ---: | ---: |
| Extracted recommendations | 0.0 | 9.3333 | 28.0 |
| Gold coverage | 0.0 | 0.3333 | 1.0 |
| Average best similarity | 0.0 | 0.3333 | 1.0 |
| Duplicate count | 0.0 | 0.0 | 0.0 |
| Pairwise recommendation Jaccard | 0.0 | 0.3333 | 1.0 |

## Repeats

| Repeat | Extracted | Gold coverage | Average best similarity | Duplicates | Chunks |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 28 | 1.0 | 1.0 | 0 | 1 |
| 2 | 0 | 0.0 | 0.0 | 0 | 0 |
| 3 | 0 | 0.0 | 0.0 | 0 | 0 |

## Failed Repeats

| Repeat | Error |
| ---: | --- |
| 2 | JSONDecodeError: Expecting value: line 1 column 1 (char 0) |
| 3 | JSONDecodeError: Expecting property name enclosed in double quotes: line 86 column 2 (char 4380) |
