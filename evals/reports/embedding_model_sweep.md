# Embedding Model Sweep

This report compares semantic retrieval metrics while changing only the embedding model.

| Model | Provider | Pair | Sources | Links | hit@10 | recall@10 | precision@10 | MRR | NDCG@10 | Embed seconds |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `openai/text-embedding-3-large` | `openrouter` | `en-en` | 18 | 90 | 0.8889 | 0.5842 | 0.2222 | 0.57 | 0.5182 | 12.225 |
| `openai/text-embedding-3-large` | `openrouter` | `es-en` | 18 | 90 | 0.8333 | 0.5715 | 0.2056 | 0.5426 | 0.4895 | 12.223 |
| `openai/text-embedding-3-small` | `openrouter` | `en-en` | 18 | 90 | 0.7778 | 0.5239 | 0.2179 | 0.5139 | 0.4483 | 10.586 |
| `openai/text-embedding-3-small` | `openrouter` | `es-en` | 18 | 90 | 0.8889 | 0.5309 | 0.1944 | 0.5099 | 0.4451 | 10.058 |
| `qwen/qwen3-embedding-4b` | `openrouter` | `en-en` | 18 | 90 | 0.8889 | 0.6334 | 0.25 | 0.6921 | 0.5979 | 12.756 |
| `qwen/qwen3-embedding-4b` | `openrouter` | `es-en` | 18 | 90 | 0.9444 | 0.6514 | 0.25 | 0.682 | 0.6069 | 11.569 |
| `qwen/qwen3-embedding-8b` | `openrouter` | `en-en` | 18 | 90 | 0.9444 | 0.6667 | 0.2611 | 0.663 | 0.592 | 27.921 |
| `qwen/qwen3-embedding-8b` | `openrouter` | `es-en` | 18 | 90 | 0.8889 | 0.6296 | 0.2389 | 0.6065 | 0.5664 | 16.542 |

## Language Gaps

| Model | Recall@10 gap | MRR gap | NDCG@10 gap |
| --- | ---: | ---: | ---: |
| `openai/text-embedding-3-large` | 0.0127 | 0.0274 | 0.0287 |
| `openai/text-embedding-3-small` | -0.007 | 0.004 | 0.0032 |
| `qwen/qwen3-embedding-4b` | -0.018 | 0.0101 | -0.009 |
| `qwen/qwen3-embedding-8b` | 0.0371 | 0.0565 | 0.0256 |

## Failed Runs

| Model | Pair | Return code | Error |
| --- | --- | ---: | --- |
| `google/gemini-embedding-001` | `es-en` | 1 | ValueError: No embedding data received |
| `google/gemini-embedding-001` | `en-en` | 1 | ValueError: No embedding data received |
