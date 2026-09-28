$ErrorActionPreference = 'Stop'
$toolRoot = $PSScriptRoot
$runtime = Join-Path $toolRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $runtime)) {
    python -m venv (Join-Path $toolRoot '.venv')
    if ($LASTEXITCODE -ne 0) { throw 'Не удалось создать окружение Python.' }
}
& $runtime -c "import importlib.util, sys; sys.exit(0 if all(importlib.util.find_spec(m) for m in ('fluent', 'yaml')) else 1)"
if ($LASTEXITCODE -ne 0) {
    & $runtime -m pip install -r (Join-Path $toolRoot 'requirements.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Не удалось установить парсер Fluent.' }
}
& $runtime (Join-Path $toolRoot 'server.py') --open
