# Validation Inventory

## Costa Rica 2024

- Source recommendations: 27
- Match labels: 90
- Similar labels: 69
- Very similar labels: 21

| Theme | Source recommendations | Similar labels | Very similar labels |
| --- | ---: | ---: | ---: |
| DISCRIMINATION | 3 | 22 | 4 |
| RIGHT TO EDUCATION | 5 | 14 | 9 |
| RIGHT TO HEALTH | 5 | 1 | 1 |
| SEXUAL EXPLOITATION AND TRAFFICKING | 3 | 13 | 2 |
| TRANSPORT AND INFRASTRUCTURE | 3 | 1 | 0 |
| VIOLENCE AGAINST CHILDREN | 4 | 16 | 4 |
| YOUNG PEOPLE'S RIGHTS | 4 | 2 | 1 |

Generated from:

- `/home/arthur/Documents/gail/un-recommendations/data/fmsi-poc-data/validation/Tabla de Recomendaciones_Costa Rica_ENG.xlsx`
- `/home/arthur/Documents/gail/un-recommendations/data/fmsi-poc-data/validation/Tabla de Recomendaciones_Costa Rica.xlsx`

Notes:

- The source PDF is Spanish. The English workbook appears to contain translated source recommendations.
- Keep both Spanish and English labels. They let us compare cross-lingual matching (`es-en`) against translated-source controls (`en-en`).
- Match labels are anchored on UPR recommendation IDs when present.
- Bangladesh and Papua New Guinea validation workbooks still need manual interpretation before normalization.

## Bangladesh 2023

- Label kind: `lobbying_impact`
- Label granularity: theme source block -> current-cycle UPR recommendation
- Source blocks: 3
- Current-cycle impact links: 38
- Weak positive links (`impact_score > 0`): 31
- Partial impact links (`0.5`): 28
- Direct impact links (`1`): 3
- Weak negative/no-impact links (`0`): 7

| Theme | Source blocks | Current-cycle links | Weak positive links |
| --- | ---: | ---: | ---: |
| Corporal Punishment | 1 | 1 | 1 |
| Child Labour & Education | 1 | 25 | 19 |
| Forced Child Marriages | 1 | 12 | 11 |

Notes:

- These labels are weaker than Costa Rica's direct similar/very-similar labels.
- Use them for impact analysis or coarse retrieval checks, not as exact source-recommendation match labels.
## Papua New Guinea 2021

- Label kind: `lobbying_impact`
- Label granularity: theme source block -> current-cycle UPR recommendation
- Source blocks: 4
- Current-cycle impact links: 90
- Weak positive links (`impact_score > 0`): 61
- Partial impact links (`0.5`): 54
- Direct impact links (`1`): 7
- Weak negative/no-impact links (`0`): 29

| Theme | Source blocks | Current-cycle links | Weak positive links |
| --- | ---: | ---: | ---: |
| Womens rights | 1 | 42 | 31 |
| Persons with disabilities | 1 | 8 | 7 |
| Childrens rights | 1 | 31 | 17 |
| Environmental issues | 1 | 9 | 6 |

Notes:

- These labels are weaker than Costa Rica's direct similar/very-similar labels.
- Use them for impact analysis or coarse retrieval checks, not as exact source-recommendation match labels.
