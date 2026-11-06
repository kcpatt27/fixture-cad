# Fixture model benchmarks

See [benchmark/README.md](../benchmark/README.md).

Harness-level (no FreeCAD/Blender GUI): compare Ollama and opt-in OpenRouter models on tool choice, args, schema safety, and confirm meta.

```powershell
$env:PYTHONPATH = "benchmark"
python -m fixture_bench list
python -m fixture_bench list-models
python -m fixture_bench run --all-models
python -m fixture_bench run --models-file benchmark/models.txt
python -m fixture_bench run --models qwen2.5:7b-instruct-q8_0 --app freecad
python -m fixture_bench run --models qwen2.5:7b-instruct-q8_0,qwen3.5:4b
python -m fixture_bench run --models-file benchmark/models.txt --tool-rerank 6
python -m fixture_bench report --latest
```

`--all-models` (or `--models all`) discovers every chat-capable tag Ollama has on disk via `/api/tags`. Embedding models are skipped unless you pass `--include-embed`. `--models-file` reads one ref per line (`benchmark/models.txt`), with bare names as Ollama tags and `openrouter:` refs for the opt-in cloud lane. `--tool-rerank N` prunes the tool catalog to the N best keyword matches per case.
