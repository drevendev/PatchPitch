$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $taskRoot
$taskPython = Join-Path $taskRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $taskPython)) { throw 'Create .venv and install requirements first. See README.' }
try {
    $null = Invoke-RestMethod 'http://127.0.0.1:11434/api/version' -TimeoutSec 2
} catch {
    $taskOllama = Join-Path $taskRoot '.tools\ollama\ollama.exe'
    if (-not (Test-Path -LiteralPath $taskOllama)) { throw 'Start your Ollama installation, or run scripts/bootstrap_local.py first.' }
    $taskInfo = New-Object System.Diagnostics.ProcessStartInfo
    $taskInfo.FileName = $taskOllama
    $taskInfo.Arguments = 'serve'
    $taskInfo.UseShellExecute = $false
    $taskInfo.CreateNoWindow = $true
    $taskInfo.EnvironmentVariables['OLLAMA_HOST'] = '127.0.0.1:11434'
    $taskInfo.EnvironmentVariables['OLLAMA_MODELS'] = Join-Path $taskRoot '.tools\models'
    $taskInfo.EnvironmentVariables['OLLAMA_NO_CLOUD'] = '1'
    $taskInfo.EnvironmentVariables['USERPROFILE'] = Join-Path $taskRoot '.tools\runtime-home'
    $taskProcess = [System.Diagnostics.Process]::Start($taskInfo)
    Write-Host "Started workspace Ollama PID $($taskProcess.Id)."
}
& $taskPython -m uvicorn patchpitch.app:app --host 127.0.0.1 --port 8000 --reload --reload-dir patchpitch
