# Fixture head-to-head — leaderboard (2026-10-06 23:27 UTC)

| # | model | raw accuracy | served accuracy | served n | genuine fails | avg s | provider errors | run |
|--:|---|---:|---:|---:|---:|---:|---:|---|
| 1 | `openrouter:google/gemini-3.8-flash` | 99.8% | 99.8% | 60/60 | 1 | 6.71 | 0 | 20261006T160314Z |
| 2 | `openrouter:deepseek/deepseek-v4-pro` | 99.8% | 99.8% | 60/60 | 1 | 11.89 | 0 | 20261006T160826Z |
| 3 | `openrouter:deepseek/deepseek-v4.1-flash` | 99.8% | 99.8% | 60/60 | 1 | 22.43 | 0 | 20261006T023121Z |
| 4 | `qwen2.5:14b-instruct-q4_K_M` | 99.4% | 99.4% | 60/60 | 3 | 6.70 | 0 | 20261006T215810Z |
| 5 | `openrouter:z-ai/glm-5.3-flash` | 99.2% | 99.2% | 60/60 | 2 | 4.97 | 0 | 20261006T021353Z |
| 6 | `openrouter:qwen/qwen3.8-27b` | 99.2% | 99.2% | 60/60 | 2 | 13.05 | 0 | 20261006T160935Z |
| 7 | `mannix/gemma4-98e-v7-coderx:Q4_K_L` | 96.8% | 96.8% | 60/60 | 4 | 9.68 | 0 | 20261006T220854Z |
| 8 | `qwen3.8:latest` | 86.7% | 99.8% | 51/60 | 1 | 59.36 | 9 | 20261006T230919Z |
| 9 | `openrouter:openai/gpt-6.1-sol-pro` | 70.4% | 100.0% | 40/60 | 0 | 10.85 | 20 | 20261006T023241Z |
| 10 | `openrouter:inclusionai/ling-3.0-flash-vl` | 61.9% | 61.9% | 60/60 | 27 | 3.09 | 0 | 20261006T155937Z |
| 11 | `openrouter:inclusionai/ling-3.1-flash` | 1.9% | 100.0% | 1/60 | 0 | 0.58 | 59 | 20261006T022410Z |
| 12 | `openrouter:qwen/qwen3.7-flash` | 0.0% | 0.0% | 0/60 | 0 | 0.22 | 60 | 20261006T155645Z |

Ranked by **raw accuracy** (provider errors count against practical use). **Served accuracy** excludes provider-error rows, so it isolates model quality on requests that were actually answered.
