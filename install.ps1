# Usage: irm https://raw.githubusercontent.com/OWNER/REPO/main/install.ps1 | iex
[CmdletBinding()]
param([string]$Repository = 'Recamm/createapp', [string]$Version = 'latest', [switch]$NoLaunch)
$ErrorActionPreference = 'Stop'
if ($env:CREATEAPP_REPO) { $Repository = $env:CREATEAPP_REPO }
if ($env:CREATEAPP_VERSION) { $Version = $env:CREATEAPP_VERSION }
if ($Repository -notmatch '^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$' -or $Repository.Contains('..')) { throw 'Repositorio inválido.' }
if ($Version -notmatch '^[A-Za-z0-9_.-]+$') { throw 'Versión inválida.' }
$Architecture = if ($env:PROCESSOR_ARCHITEW6432) { $env:PROCESSOR_ARCHITEW6432 } else { $env:PROCESSOR_ARCHITECTURE }
if ($Architecture -ne 'AMD64') { throw 'Esta versión distribuye Windows x64. No hay build nativo para esta arquitectura.' }
$Asset = 'createapp-windows-x64.zip'
$Base = if ($Version -eq 'latest') { "https://github.com/$Repository/releases/latest/download" } else { "https://github.com/$Repository/releases/download/$Version" }
$Temp = Join-Path ([IO.Path]::GetTempPath()) ('createapp-' + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $Temp | Out-Null
try {
    Write-Host 'Descargando CreateApp para Windows x64…'
    $Archive = Join-Path $Temp $Asset
    $Sums = Join-Path $Temp 'SHA256SUMS'
    Invoke-WebRequest -UseBasicParsing -Uri "$Base/$Asset" -OutFile $Archive
    Invoke-WebRequest -UseBasicParsing -Uri "$Base/SHA256SUMS" -OutFile $Sums
    $Pattern = '(?m)^([a-fA-F0-9]{64})\s+\*?' + [Regex]::Escape($Asset) + '\s*$'
    $Match = [Regex]::Match([IO.File]::ReadAllText($Sums), $Pattern)
    $Actual = (Get-FileHash -Algorithm SHA256 -Path $Archive).Hash
    if (-not $Match.Success -or $Actual -ne $Match.Groups[1].Value) { throw 'El checksum no coincide. No se instaló.' }
    $Content = Join-Path $Temp 'content'
    Expand-Archive -Path $Archive -DestinationPath $Content
    if (-not $env:LOCALAPPDATA) { throw 'No se pudo resolver LOCALAPPDATA.' }
    $Bin = Join-Path $env:LOCALAPPDATA 'CreateApp\bin'
    New-Item -ItemType Directory -Path $Bin -Force | Out-Null
    $New = Join-Path $Bin 'createapp-new.exe'
    Copy-Item (Join-Path $Content 'createapp.exe') $New -Force
    & $New --version
    if ($LASTEXITCODE -ne 0) { throw 'El ejecutable no pudo iniciarse.' }
    $Installed = Join-Path $Bin 'createapp.exe'
    Move-Item $New $Installed -Force
    $Licenses = Join-Path $env:LOCALAPPDATA 'CreateApp\licenses'
    New-Item -ItemType Directory -Path $Licenses -Force | Out-Null
    foreach ($Item in @('LICENSE', 'THIRD_PARTY.md', 'third-party', 'runtime-licenses')) {
        $Source = Join-Path $Content $Item
        if (Test-Path $Source) { Copy-Item $Source $Licenses -Recurse -Force }
    }
    $UserPath = [Environment]::GetEnvironmentVariable('Path', 'User')
    if (($UserPath -split ';') -notcontains $Bin) {
        $Updated = if ($UserPath) { $UserPath.TrimEnd(';') + ';' + $Bin } else { $Bin }
        [Environment]::SetEnvironmentVariable('Path', $Updated, 'User')
    }
    if (($env:Path -split ';') -notcontains $Bin) { $env:Path = $Bin + ';' + $env:Path }
    Write-Host "Instalado: $Installed"
    Write-Host 'Terminal: createapp . | Navegador: createapp . --ui'
    if (-not $NoLaunch -and $env:CREATEAPP_NO_LAUNCH -ne '1') { & $Installed . }
} finally {
    Remove-Item $Temp -Recurse -Force -ErrorAction SilentlyContinue
}
