param(
    [string]$ServiceName = 'AriaListener',
    [string]$PythonPath = '',
    [string]$ScriptPath = '',
    [string]$Host = '0.0.0.0',
    [int]$Port = 65432,
    [string]$LogFile = "$PSScriptRoot\..\logs\aria_listener.log",
    [string]$TlsCert = '',
    [string]$TlsKey = '',
    [switch]$Install,
    [switch]$Uninstall,
    [switch]$Update
)

function Write-Heading($msg){ Write-Host "==> $msg" -ForegroundColor Cyan }

Write-Heading "Windows NSSM service helper for aria_listener"

# Resolve defaults if not provided
if ([string]::IsNullOrWhiteSpace($PythonPath)) {
    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) { $PythonPath = $python.Path }
}

if ([string]::IsNullOrWhiteSpace($ScriptPath)) {
    $default = Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) '..\aria_listener.py' | Resolve-Path -ErrorAction SilentlyContinue
    if ($default) { $ScriptPath = $default.Path }
}

Write-Host "ServiceName: $ServiceName"
Write-Host "PythonPath: $PythonPath"
Write-Host "ScriptPath: $ScriptPath"
Write-Host "Host: $Host"
Write-Host "Port: $Port"
Write-Host "LogFile: $LogFile"
if ($TlsCert -and $TlsKey) { Write-Host "TLS: enabled (cert: $TlsCert, key: $TlsKey)" } else { Write-Host "TLS: disabled" }

# Validate required files
$errors = @()
if (-not (Test-Path $PythonPath)) { $errors += "Python executable not found at $PythonPath" }
if (-not (Test-Path $ScriptPath)) { $errors += "Script not found at $ScriptPath" }

if ($errors.Count -gt 0) {
    Write-Host "Validation errors:" -ForegroundColor Red
    $errors | ForEach-Object { Write-Host " - $_" -ForegroundColor Red }
}

# Find nssm
$nssm = Get-Command nssm -ErrorAction SilentlyContinue
if (-not $nssm) {
    $possible = "C:\\nssm\\win64\\nssm.exe", "C:\\nssm\\nssm.exe"
    foreach ($p in $possible) { if (Test-Path $p) { $nssm = (Get-Item $p).FullName; break } }
}

if (-not $nssm) {
    Write-Host "Warning: nssm.exe not found on PATH or common locations." -ForegroundColor Yellow
    Write-Host "Please install NSSM (https://nssm.cc/) and ensure 'nssm' is on PATH to use install/uninstall features." -ForegroundColor Yellow
}
else {
    Write-Host "Using NSSM: $($nssm.Path)" -ForegroundColor Green
}

# Build App parameters
$appArgs = "--host $Host --port $Port --log-file `"$LogFile`""
if ($TlsCert -and $TlsKey) {
    $appArgs += " --tls-cert `"$TlsCert`" --tls-key `"$TlsKey`""
}

# NSSM commands to print/execute
$installCmd = "& `"$($nssm.Path)`" install $ServiceName `"$PythonPath`" `"$ScriptPath`" $appArgs"
$setAppDir = "& `"$($nssm.Path)`" set $ServiceName AppDirectory `"$(Split-Path -Parent $ScriptPath)`""
$setStdout = "& `"$($nssm.Path)`" set $ServiceName AppStdout `"$LogFile`""
$setStderr = "& `"$($nssm.Path)`" set $ServiceName AppStderr `"$LogFile`""
$setStart = "& `"$($nssm.Path)`" set $ServiceName Start SERVICE_AUTO_START"
$startCmd = "& `"$($nssm.Path)`" start $ServiceName"
$stopCmd = "& `"$($nssm.Path)`" stop $ServiceName"
$removeCmd = "& `"$($nssm.Path)`" remove $ServiceName confirm"

Write-Heading "Planned NSSM commands"
Write-Host $installCmd
Write-Host $setAppDir
Write-Host $setStdout
Write-Host $setStderr
Write-Host $setStart
Write-Host $startCmd

if ($Uninstall) {
    if (-not $nssm) { Write-Host "Cannot uninstall: nssm not found." -ForegroundColor Red; exit 2 }
    Write-Heading "Uninstalling service $ServiceName"
    Write-Host $stopCmd
    Write-Host $removeCmd
    if ($nssm -and -not $WhatIfPreference) {
        Invoke-Expression $stopCmd
        Invoke-Expression $removeCmd
        Write-Host "Service removed." -ForegroundColor Green
    }
    exit 0
}

if ($Install) {
    if (-not $nssm) { Write-Host "Cannot install: nssm not found." -ForegroundColor Red; exit 2 }
    Write-Heading "Installing service $ServiceName"
    Write-Host "Running install and configuration commands..."
    Invoke-Expression $installCmd
    Invoke-Expression $setAppDir
    Invoke-Expression $setStdout
    Invoke-Expression $setStderr
    Invoke-Expression $setStart
    Invoke-Expression $startCmd
    Write-Host "Service installed and started." -ForegroundColor Green
    exit 0
}

if ($Update) {
    if (-not $nssm) { Write-Host "Cannot update: nssm not found." -ForegroundColor Red; exit 2 }
    Write-Heading "Updating service $ServiceName"
    Write-Host $setAppDir
    Write-Host $setStdout
    Write-Host $setStderr
    Invoke-Expression $setAppDir
    Invoke-Expression $setStdout
    Invoke-Expression $setStderr
    Invoke-Expression $stopCmd
    Invoke-Expression $startCmd
    Write-Host "Service updated and restarted." -ForegroundColor Green
    exit 0
}

Write-Heading "No action requested"
Write-Host "To install the service, re-run this script with -Install" -ForegroundColor Yellow
Write-Host "To uninstall: re-run with -Uninstall" -ForegroundColor Yellow
Write-Host "To update parameters: re-run with -Update" -ForegroundColor Yellow
