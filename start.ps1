param([int]$Port = 8000, [string]$LanAddress = '')
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$taskBindAddress = '127.0.0.1'
if ($LanAddress) {
    $taskParsedAddress = $null
    if (-not [System.Net.IPAddress]::TryParse($LanAddress, [ref]$taskParsedAddress) -or $taskParsedAddress.AddressFamily -ne [System.Net.Sockets.AddressFamily]::InterNetwork) {
        throw 'LanAddress must be your computer''s IPv4 address, such as 192.168.1.5.'
    }
    $taskBindAddress = $taskParsedAddress.ToString()
    $env:BLUEZONE_ORIGIN = "http://${taskBindAddress}:$Port"
}
if (-not (Test-Path -LiteralPath '.venv/Scripts/python.exe')) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.11+ is required.' }
}
& ./.venv/Scripts/python.exe -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
$env:BLUEZONE_ORIGIN = "http://${taskBindAddress}:$Port"
Write-Host "Open $($env:BLUEZONE_ORIGIN) in your browser. Keep this terminal running."
& ./.venv/Scripts/python.exe -m uvicorn app.main:app --host $taskBindAddress --port $Port
