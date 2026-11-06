@echo off
REM Run Fixture benchmarks from repo root
set PYTHONPATH=%~dp0
python -m fixture_bench %*
