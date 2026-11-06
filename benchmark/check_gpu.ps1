<#
.SYNOPSIS
  Report GPU / Ollama / bench status before starting VRAM-heavy work.

.DESCRIPTION
  The machine's GPU is shared with other sessions (e.g. an OpenCode agent
  benching local models). Check this before local Ollama runs, training, or
  GUI soaks. Exit codes: 0 = clear, 1 = likely in use, 2 = no NVIDIA GPU.

.EXAMPLE
  .\check_gpu.ps1
#>
$ErrorActionPreference = "SilentlyContinue"
$busy = $false

$line = & nvidia-smi --query-gpu=name,memory.total,memory.used,utilization.gpu --format=csv,noheader,nounits
if (-not $line) {
    Write-Host "No NVIDIA GPU visible to nvidia-smi." -ForegroundColor Yellow
    exit 2
}
$parts = ($line -join " ") -split ","
$name = $parts[0].Trim()
$total = [int]$parts[1]
$used = [int]$parts[2]
$util = [int]$parts[3]
Write-Host ("GPU: {0} - {1} MB / {2} MB used, {3}% util" -f $name, $used, $total, $util)
if ($used -gt 2048 -or $util -gt 20) {
    Write-Host "  -> GPU memory or utilization elevated" -ForegroundColor Yellow
    $busy = $true
}

try {
    $ps = Invoke-RestMethod http://localhost:11434/api/ps -TimeoutSec 5
    if ($ps.models -and @($ps.models).Count -gt 0) {
        Write-Host "Ollama loaded models:"
        foreach ($m in $ps.models) {
            Write-Host ("  {0}  vram={1} GB" -f $m.name, [math]::Round($m.size_vram / 1GB, 1))
        }
        $busy = $true
    }
    else {
        Write-Host "Ollama: no models loaded"
    }
}
catch {
    Write-Host "Ollama: not reachable (fine if you only use cloud refs)"
}

$bench = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -match 'fixture_bench|freecad_s1\.evaluate|freecad_s1\.ui|freecad_s1\.datagen|train_sft' }
if ($bench) {
    Write-Host "Bench / training processes:"
    foreach ($p in $bench) {
        $cmd = if ($p.CommandLine) { $p.CommandLine.Substring(0, [Math]::Min(120, $p.CommandLine.Length)) } else { "(no cmdline)" }
        Write-Host ("  PID {0}: {1}" -f $p.ProcessId, $cmd)
    }
    $busy = $true
}
else {
    Write-Host "No Fixture/Taiga bench processes found"
}

if ($busy) {
    Write-Host "VERDICT: GPU likely in use or local runs active - coordinate before starting VRAM-heavy work." -ForegroundColor Yellow
    exit 1
}
Write-Host "VERDICT: clear." -ForegroundColor Green
exit 0