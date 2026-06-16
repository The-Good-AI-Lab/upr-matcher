# UPR Materials Extraction Comparison

Manifest: `evals/datasets/upr_materials_document_pairs.jsonl`

This compares deterministic extraction only. These 55 cases have no direct match labels, so this is a robustness and coverage report, not an accuracy report.

Recommendation ID coverage uses the first leading UPR recommendation ID in each raw table row, which avoids counting theme taxonomy codes like `14.5` as target recommendations.

## Summary

- Document pairs: 55
- Source PDF text extraction non-empty: 55/55 (1.0)
- Reference text extraction non-empty: 47/55 (0.8545)
- Reference row extraction non-empty: 47/55 (0.8545)
- Reference formats: .doc=9, .docx=46
- Detected source languages: en=33, es=19, fr=3
- DOCX row count median: 230.5
- DOCX row count min/max: 8/346
- DOCX median raw-text-ID to parsed-row-ID coverage: 1.0

## By Reference Format

| Format | Cases | Text OK | Rows OK | Median rows | Median ID coverage |
| --- | ---: | ---: | ---: | ---: | ---: |
| `.doc` | 9 | 1 | 1 | 293 | 1.0 |
| `.docx` | 46 | 46 | 46 | 230.5 | 1.0 |

## By Source Language

| Source language | Cases | Source text OK | Reference rows OK | Median rows |
| --- | ---: | ---: | ---: | ---: |
| `en` | 33 | 33 | 28 | 214.0 |
| `es` | 19 | 19 | 16 | 261.5 |
| `fr` | 3 | 3 | 3 | 264 |

## Extraction Failures

| case_id | format | source status | reference text status | row status | error |
| --- | --- | --- | --- | --- | --- |
| `argentina_2022` | `.doc` | ok | error | error | ValueError: Legacy .doc files are not supported: /home/arthur/Documents/gail/UPR Materials - TheGoodAILab-20260615T015654Z-3-001/UPR Materials - TheGoodAILab/Matrix of recommendations_Argentina_2022.doc. Convert the file to .docx before upl |
| `bangladesh_2023` | `.doc` | ok | error | error | ValueError: Legacy .doc files are not supported: /home/arthur/Documents/gail/UPR Materials - TheGoodAILab-20260615T015654Z-3-001/UPR Materials - TheGoodAILab/Matrix of recommendations_Bangladesh_2023.doc. Convert the file to .docx before up |
| `bolivia_2014` | `.doc` | ok | error | error | ValueError: Legacy .doc files are not supported: /home/arthur/Documents/gail/UPR Materials - TheGoodAILab-20260615T015654Z-3-001/UPR Materials - TheGoodAILab/Matrix of recommendations_Bolivia_2014.doc. Convert the file to .docx before uploa |
| `cameroon_2023` | `.doc` | ok | error | error | ValueError: Legacy .doc files are not supported: /home/arthur/Documents/gail/UPR Materials - TheGoodAILab-20260615T015654Z-3-001/UPR Materials - TheGoodAILab/Matrix of recommendations_Cameroon_2023.doc. Convert the file to .docx before uplo |
| `colombia_2023` | `.doc` | ok | error | error | ValueError: Legacy .doc files are not supported: /home/arthur/Documents/gail/UPR Materials - TheGoodAILab-20260615T015654Z-3-001/UPR Materials - TheGoodAILab/Matrix of recommendations_Colombia_2023.doc. Convert the file to .docx before uplo |
| `madagascar_2014` | `.doc` | ok | error | error | ValueError: Legacy .doc files are not supported: /home/arthur/Documents/gail/UPR Materials - TheGoodAILab-20260615T015654Z-3-001/UPR Materials - TheGoodAILab/Matrix of recommendations_Madagascar_2014.doc. Convert the file to .docx before up |
| `nicaragua_2014` | `.doc` | ok | error | error | ValueError: Legacy .doc files are not supported: /home/arthur/Documents/gail/UPR Materials - TheGoodAILab-20260615T015654Z-3-001/UPR Materials - TheGoodAILab/Matrix or recommendations_Nicaragua_2014.doc. Convert the file to .docx before upl |
| `zambia_2022` | `.doc` | ok | error | error | ValueError: Legacy .doc files are not supported: /home/arthur/Documents/gail/UPR Materials - TheGoodAILab-20260615T015654Z-3-001/UPR Materials - TheGoodAILab/Matrix of recommendations_Zambia_2022.doc. Convert the file to .docx before upload |

## Row Count Outliers

| case_id | language | format | rows | text target IDs | row target IDs | ID coverage |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `tanzania_2016` | `en` | `.docx` | 8 | 8 | 8 | 1.0 |
| `philippines_2012` | `en` | `.docx` | 88 | 88 | 88 | 1.0 |
| `peru_2012` | `en` | `.docx` | 129 | 129 | 129 | 1.0 |
| `vanuatu_2018` | `en` | `.docx` | 135 | 135 | 135 | 1.0 |
| `guatemala_2012` | `en` | `.docx` | 138 | 138 | 138 | 1.0 |
| `italy_2019` | `en` | `.docx` | 306 | 306 | 306 | 1.0 |
| `mexico_2023` | `en` | `.docx` | 319 | 318 | 318 | 1.0 |
| `italy_2024` | `es` | `.docx` | 340 | 340 | 340 | 1.0 |
| `australia_2020` | `en` | `.docx` | 344 | 344 | 344 | 1.0 |
| `nigeria_2023` | `en` | `.docx` | 346 | 346 | 346 | 1.0 |

## Low DOCX ID Coverage

None below 0.98 coverage among DOCX cases with target IDs.

## Outputs

- JSONL details: `evals/reports/upr_materials_extraction_comparison.jsonl`
