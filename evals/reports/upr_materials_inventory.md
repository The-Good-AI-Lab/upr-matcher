# UPR Materials Inventory

Source folder: `/home/arthur/Documents/gail/UPR Materials - TheGoodAILab-20260615T015654Z-3-001/UPR Materials - TheGoodAILab`

This folder contains raw UPR materials, not validation workbooks. Treat these cases as unlabeled regression/eval coverage unless a separate human-labeled sheet is added.

Language fields in this report are heuristic hints from sampled text, not human labels.

## Summary

- Total files: 282
- File types: .doc=10, .docx=47, .pdf=225
- Parsed cases: 90
- Source + recommendation-matrix pairs: 55
- Pairs with stakeholder summary and working-group report: 15
- Matrix formats among pairs: .doc=9, .docx=46
- Detected source languages among pairs: en=33, es=19, fr=3
- Detected reference languages among pairs: en=46, unknown=9

## Parsed Role Counts

- `source_pdf`: 88
- `reference_doc`: 55
- `stakeholder_file`: 75
- `working_group_report_pdf`: 36
- `addendum_pdf`: 27

## Unlabeled Document Pairs

JSONL manifest: `evals/datasets/upr_materials_document_pairs.jsonl`

| case_id | country | year | src_lang | ref_lang | source | matrix | stakeholder | report | addendum |
| --- | --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| argentina_2022 | Argentina | 2022 | es | unknown | yes | yes | yes |  |  |
| australia_2015 | Australia | 2015 | en | en | yes | yes | yes |  |  |
| australia_2020 | Australia | 2020 | en | en | yes | yes | yes | yes | yes |
| bangladesh_2023 | Bangladesh | 2023 | en | unknown | yes | yes | yes |  |  |
| bolivia_2014 | Bolivia | 2014 | es | unknown | yes | yes | yes |  |  |
| bolivia_2019 | Bolivia | 2019 | es | en | yes | yes | yes | yes | yes |
| bolivia_2024 | Bolivia | 2024 | es | en | yes | yes | yes |  |  |
| brazil_2012 | Brazil | 2012 | en | en | yes | yes | yes |  |  |
| cameroon_2023 | Cameroon | 2023 | en | unknown | yes | yes | yes |  |  |
| central_african_republic_2013 | Central African Republic | 2013 | en | en | yes | yes | yes |  |  |
| chile_2014 | Chile | 2014 | es | en | yes | yes | yes |  |  |
| chile_2018 | Chile | 2018 | es | en | yes | yes | yes | yes | yes |
| colombia_2023 | Colombia | 2023 | es | unknown | yes | yes | yes |  |  |
| costa_rica_2018 | Costa Rica | 2018 | es | en | yes | yes | yes | yes | yes |
| costa_rica_2024 | Costa Rica | 2024 | es | en | yes | yes | yes |  |  |
| drc_2014 | DRC | 2014 | en | en | yes | yes | yes |  |  |
| drc_2024 | DRC | 2024 | fr | en | yes | yes | yes |  |  |
| el_salvador_2019 | El Salvador | 2019 | es | en | yes | yes | yes | yes | yes |
| fiji_2024 | Fiji | 2024 | en | en | yes | yes | yes |  |  |
| guatemala_2012 | Guatemala | 2012 | en | en | yes | yes | yes |  |  |
| italy_2014 | Italy | 2014 | en | en | yes | yes | yes |  |  |
| italy_2019 | Italy | 2019 | en | en | yes | yes | yes | yes | yes |
| italy_2024 | Italy | 2024 | es | en | yes | yes | yes |  |  |
| ivory_coast_2018 | Ivory Coast | 2018 | fr | en | yes | yes | yes | yes | yes |
| madagascar_2014 | Madagascar | 2014 | en | unknown | yes | yes | yes |  |  |
| madagascar_2019 | Madagascar | 2019 | fr | en | yes | yes | yes | yes | yes |
| madagascar_2024 | Madagascar | 2024 | en | en | yes | yes | yes |  |  |
| malawi_2020 | Malawi | 2020 | en | en | yes | yes | yes | yes | yes |
| mexico_2018 | Mexico | 2018 | es | en | yes | yes | yes | yes | yes |
| mexico_2023 | Mexico | 2023 | en | en | yes | yes | yes |  |  |
| mozambique_2020 | Mozambique | 2020 | en | en | yes | yes | yes | yes |  |
| nicaragua_2014 | Nicaragua | 2014 | en | unknown | yes | yes | yes |  |  |
| nicaragua_2018 | Nicaragua | 2018 | es | en | yes | yes | yes | yes |  |
| nigeria_2013 | Nigeria | 2013 | en | en | yes | yes | yes |  |  |
| nigeria_2023 | Nigeria | 2023 | en | en | yes | yes | yes |  |  |
| pakistan_2012 | Pakistan | 2012 | en | en | yes | yes | yes |  |  |
| papua_new_guinea_2016 | Papua New Guinea | 2016 | en | en | yes | yes | yes |  |  |
| papua_new_guinea_2021 | Papua New Guinea | 2021 | en | en | yes | yes | yes |  |  |
| paraguay_2016 | Paraguay | 2016 | es | en | yes | yes | yes |  |  |
| paraguay_2020 | Paraguay | 2020 | es | en | yes | yes | yes |  |  |
| peru_2012 | Peru | 2012 | en | en | yes | yes | yes |  |  |
| philippines_2012 | Philippines | 2012 | en | en | yes | yes | yes |  |  |
| portugal_2018 | Portugal | 2018 | es | en | yes | yes | yes | yes | yes |
| portugal_2024 | Portugal | 2024 | es | en | yes | yes | yes |  |  |
| rwanda_2015 | Rwanda | 2015 | en | en | yes | yes | yes |  |  |
| south_africa_2022 | South Africa | 2022 | en | unknown | yes | yes | yes |  |  |
| spain_2020 | Spain | 2020 | es | en | yes | yes | yes |  |  |
| sri_lanka_2012 | Sri Lanka | 2012 | en | en | yes | yes | yes |  |  |
| tanzania_2016 | Tanzania | 2016 | en | en | yes | yes | yes |  |  |
| thailand_2016 | Thailand | 2016 | en | en | yes | yes | yes |  |  |
| uruguay_2018 | Uruguay | 2018 | en | en | yes | yes | yes | yes | yes |
| uruguay_2023 | Uruguay | 2023 | es | en | yes | yes | yes |  |  |
| vanuatu_2018 | Vanuatu | 2018 | en | en | yes | yes | yes | yes |  |
| vanuatu_2023 | Vanuatu | 2023 | en | en | yes | yes | yes |  |  |
| zambia_2022 | Zambia | 2022 | en | unknown | yes | yes | yes |  |  |

## Parsed Cases Without A Source+Matrix Pair

| case_id | country | year | src_lang | ref_lang | source | matrix | stakeholder | report | addendum |
| --- | --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| argentina_2017 | Argentina | 2017 | es |  | yes |  | yes | yes | yes |
| australia_2011 | Australia | 2011 | en |  | yes |  | yes | yes | yes |
| australia_2025 | Australia | 2025 | en |  | yes |  |  |  |  |
| belgium_2025 | Belgium | 2025 | en |  | yes |  |  |  |  |
| brazil_2017 | Brazil | 2017 | es |  | yes |  | yes | yes | yes |
| cambodia_2009 | Cambodia | 2009 | en |  | yes |  | yes | yes |  |
| cambodia_2014 | Cambodia | 2014 | en |  | yes |  | yes | yes | yes |
| ghana_2017 | Ghana | 2017 | en |  | yes |  | yes | yes | yes |
| guatemala_2007 | Guatemala | 2007 | es |  | yes |  |  |  |  |
| guatemala_2008 | Guatemala | 2008 |  |  |  |  | yes | yes |  |
| honduras_2025 | Honduras | 2025 | es |  | yes |  |  |  |  |
| kenya_2010 | Kenya | 2010 | en |  | yes |  | yes | yes |  |
| kenya_2024 | Kenya | 2024 | en |  | yes |  | yes | yes | yes |
| kiribati_2010 | Kiribati | 2010 | en |  | yes |  |  | yes | yes |
| kiribati_2024 | Kiribati | 2024 | en |  | yes |  | yes | yes | yes |
| lebanon_2025 | Lebanon | 2025 | en |  | yes |  |  |  |  |
| liberia_2025 | Liberia | 2025 | en |  | yes |  |  |  |  |
| malawi_2010 | Malawi | 2010 | en |  | yes |  | yes | yes |  |
| malawi_2025 | Malawi | 2025 | en |  | yes |  |  |  |  |
| mozambique_2025 | Mozambique | 2025 | en |  | yes |  |  |  |  |
| papua_new_guinea_2011 | Papua New Guinea | 2011 |  |  |  |  | yes | yes | yes |
| papua_new_guinea_2012 | Papua New Guinea | 2012 | en |  | yes |  |  |  |  |
| paraguay_2025 | Paraguay | 2025 | es |  | yes |  |  |  |  |
| peru_2017 | Peru | 2017 | es |  | yes |  | yes | yes | yes |
| rwanda_2025 | Rwanda | 2025 | en |  | yes |  |  |  |  |
| singapore_2025 | Singapore | 2025 | en |  | yes |  |  |  |  |
| solomon_islands_2011 | Solomon Islands | 2011 | en |  | yes |  | yes | yes |  |
| solomon_islands_2025 | Solomon Islands | 2025 | en |  | yes |  |  |  |  |
| spain_2024 | Spain | 2024 | es |  | yes |  | yes | yes | yes |
| tanzania_2011 | Tanzania | 2011 | en |  | yes |  | yes | yes | yes |
| timor_leste_2011 | Timor Leste | 2011 | en |  | yes |  | yes | yes | yes |
| usa_2025 | USA | 2025 | en |  | yes |  |  |  |  |
| vanuatu_2009 | Vanuatu | 2009 | en |  | yes |  | yes | yes | yes |
| zambia_2017 | Zambia | 2017 | en |  | yes |  | yes | yes | yes |
| zimbabwe_2011 | Zimbabwe | 2011 | en |  | yes |  | yes | yes |  |

## Unparsed Files

- `/home/arthur/Documents/gail/UPR Materials - TheGoodAILab-20260615T015654Z-3-001/UPR Materials - TheGoodAILab/Explanation.docx`
