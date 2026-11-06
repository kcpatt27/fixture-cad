param(
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$BenchArgs
)
$env:PYTHONPATH = $PSScriptRoot
python -m fixture_bench @BenchArgs
