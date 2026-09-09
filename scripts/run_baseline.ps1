<#
.SYNOPSIS
Baseline MCTS-UCB1 wedlug protokolu Tabeli II z arXiv:1802.06881.

Stale protokolu (NIE zmieniac - one decyduja o porownywalnosci z artykulem):
  --trials 50        50 partii na (persona, mapa)
  --time-limit 300   300 s budzetu na jedno drzewo, czyli na mape
  4 persony x 11 map x 50 prob = 2200 partii
  rollout 10 ruchow, c = sqrt(2), utility eq. 2-5 - zaszyte w kodzie, bez flag

Sprawnosc: partia jest ograniczona CZASEM, wiec zegar scienny ~ 2200 * 300 s / workers.
  workers 8 -> ~23 h     workers 12 -> ~15 h     workers 15 -> ~12 h
Wiecej workerow = mniej iteracji na partie (SMT), ale metryki Tabeli II sie od tego
nie zmieniaja (zmierzone: 375 tys. vs 585 tys. iteracji daly identyczne wyniki).

Przebieg jest WZNAWIALNY: po Ctrl+C uruchom ponownie te sama komende.
#>
[CmdletBinding()]
param(
    [int]$Workers = 12,
    [int]$Trials = 50,
    [double]$TimeLimit = 300.0,
    [ValidateSet('ucb1', 'evolved', 'ours')]
    [string]$Policy = 'ucb1',
    [switch]$Traces,      # slady partii kosztuja I/O; domyslnie wylaczone
    [switch]$Restart,     # nadpisz CSV od zera zamiast wznawiac
    [switch]$ReportOnly,  # tylko wypisz Tabele II z istniejacego CSV
    [string]$Out = ''     # inny plik wynikow niz data/results/<policy>_tree_terminal.csv
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) { throw "Brak interpretera: $python" }

$module = 'src.minidungeons.cli.mcts_experiment'
if ($ReportOnly) {
    $cmdArgs = @('-m', $module, '--policy', $Policy, '--report-only')
} else {
    $cmdArgs = @(
        '-m', $module,
        '--policy', $Policy,
        '--trials', $Trials,
        '--time-limit', $TimeLimit,
        '--workers', $Workers
    )
    if (-not $Traces) { $cmdArgs += '--no-traces' }
    if ($Restart)     { $cmdArgs += '--restart' }
}
if ($Out) { $cmdArgs += @('--out', $Out) }

Set-Location $root
$env:PYTHONUNBUFFERED = '1'
# Tabela II ma polskie naglowki i znak +/-; bez tego konsola pokazuje krzaki.
$env:PYTHONIOENCODING = 'utf-8'
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
try { [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false) } catch { }

$logDir = Join-Path $root 'data\results'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$log = Join-Path $logDir ("baseline_{0}_{1}.log" -f $Policy, (Get-Date -Format 'yyyyMMdd_HHmmss'))

if (-not $ReportOnly) {
    $eta = [math]::Round(($Trials * 11 * 4 * $TimeLimit) / $Workers / 3600.0, 1)
    Write-Host "policy=$Policy trials=$Trials time-limit=$TimeLimit workers=$Workers"
    Write-Host "gorna granica zegara sciennego: ~$eta h (wygrane partie koncza sie wczesniej)"
    Write-Host "log: $log"
}

# Strumien postepu laduje i na ekran, i do logu - przebieg trwa godziny, a Tabela II
# z jego konca zostaje w logu razem z kazdym wierszem postepu.
& $python @cmdArgs | Tee-Object -FilePath $log
exit $LASTEXITCODE
