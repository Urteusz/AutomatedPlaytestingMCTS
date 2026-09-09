<#
.SYNOPSIS
Pelny protokol Tabeli II z arXiv:1802.06881 w konwencji PE = manhattan.

Stale protokolu (NIE zmieniac - one decyduja o porownywalnosci z artykulem):
  --time-limit 300   300 s budzetu na jedno drzewo, czyli na mape
  --trials 50        50 partii na (persona, mapa) -> 2200 partii na ramie
  --utility-pe manhattan   PE w uzytecznosciach person: 1 - dystans_manhattan/maks,
                           1 na wyjsciu, BEZ wiedzy o scianach
  --pe-mode manhattan      to samo w terminalu PE ewoluowanej tree policy, zeby
                           zadne ramie nie mialo oracle'a (dotyczy tylko evolved)
  --fallback visits        "best sequence of actions it discovered" (sekcja V)
                           czytana jako zejscie po liczbie odwiedzin

Ramie evolved idzie na PyPy (2,57x szybciej, wyniki bit w bit zgodne z CPythonem),
baseline na CPythonie. Nierownosc dziala PRZECIWKO evolved: baseline dostaje
447 tys. wezlow w 300 s, evolved ~60 tys., wiec jego przewaga nie pochodzi
z budzetu obliczeniowego.

Przebiegi sa WZNAWIALNE i przyrostowe - po Ctrl+C albo zaniku pradu uruchom
ponownie te sama komende, policzone partie nie liczy sie po raz drugi.

Kolejnosc krokow nie jest przypadkowa: zadania powstaja jako persona -> mapa ->
proba, wiec przy --trials 50 Runner dostalby wszystkie 50 prob, zanim Monster
Killer zaczalby cokolwiek. Krok 1 dobija najpierw WSZYSTKIE persony do 10 prob,
zeby po ~1,5 h istniala kompletna, pokazywalna para.

Czasy zmierzone na Ryzenie 7 7700, 12 workerow:
  krok 1 (evolved do 10 prob)   ~1,5 h
  krok 2 (evolved do 50 prob)   ~8 h
  krok 3 (baseline do 50 prob)  ~10,5 h
#>
[CmdletBinding()]
param(
    [int]$Workers = 12,
    [ValidateSet('1', '2', '3', 'all')]
    [string]$Step = 'all',
    [string]$Pypy = 'C:\Users\mateu\pypy3.11\pypy.exe'
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$cpython = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path $cpython)) { throw "Brak interpretera CPython: $cpython" }
if (-not (Test-Path $Pypy)) { throw "Brak interpretera PyPy: $Pypy" }

Set-Location $root
$env:PYTHONUNBUFFERED = '1'
$env:PYTHONIOENCODING = 'utf-8'

$harness = 'scratchpad\final_experiment.py'
$common = @('--time-limit', '300', '--workers', $Workers, '--fallback', 'visits')

function Invoke-Arm {
    param([string]$Interpreter, [string[]]$Arguments, [string]$Label)

    Write-Host ''
    Write-Host "=== $Label ===" -ForegroundColor Cyan
    Write-Host "$Interpreter $($Arguments -join ' ')"
    $started = Get-Date
    & $Interpreter @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Label zakonczylo sie kodem $LASTEXITCODE" }
    Write-Host ("$Label gotowe w {0:N1} h" -f ((Get-Date) - $started).TotalHours) -ForegroundColor Green
}

$evolved = @($harness, '--tag', 'T300_EVO_PYPY', '--policy', 'evolved',
             '--utility-pe', 'manhattan', '--pe-mode', 'manhattan') + $common
$baseline = @($harness, '--tag', 'T300_manhattan', '--policy', 'ucb1',
              '--utility-pe', 'manhattan') + $common

if ($Step -in '1', 'all') {
    Invoke-Arm $Pypy ($evolved + @('--trials', '10')) 'KROK 1: evolved, 10 prob (440 partii)'
}
if ($Step -in '2', 'all') {
    Invoke-Arm $Pypy ($evolved + @('--trials', '50')) 'KROK 2: evolved, 50 prob (2200 partii)'
}
if ($Step -in '3', 'all') {
    Invoke-Arm $cpython ($baseline + @('--trials', '50')) 'KROK 3: baseline, 50 prob (2200 partii)'
}

Write-Host ''
Write-Host 'Tabela II - porownanie z artykulem:' -ForegroundColor Cyan
Write-Host ('  {0} scratchpad\make_table.py --baseline scratchpad\final_T300_manhattan.csv ' -f $cpython) -NoNewline
Write-Host '--evolved scratchpad\final_T300_EVO_PYPY.csv --out scratchpad\final_table_manhattan.md'
