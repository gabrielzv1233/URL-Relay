$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot

$ProductName = "URL Relay Receiver"
$Version = "1.0.0.0"
$ExecutableName = "URLRelayReceiver.exe"

$IconPath = Join-Path $PSScriptRoot "url_receiver.ico"
$VersionInfoPath = Join-Path $PSScriptRoot "version_info.txt"
$DistFolder = Join-Path $PSScriptRoot "receiver.dist"
$Executable = Join-Path $DistFolder $ExecutableName

if (-not (Test-Path $IconPath)) {
    throw "Missing icon: $IconPath"
}

if (-not (Test-Path $VersionInfoPath)) {
    throw "Missing version info file: $VersionInfoPath"
}

Write-Host ""
Write-Host "Building $ProductName $Version..."
Write-Host ""

$NuitkaArgs = @(
    "-m", "nuitka",
    "--mode=standalone",
    "--assume-yes-for-downloads",
    "--windows-console-mode=disable",
    "--windows-icon-from-ico=$IconPath",

    "--include-data-file=config.json=config.json",
    "--include-data-file=url_receiver.ico=url_receiver.ico",

    "--output-filename=$ExecutableName",
    "receiver.py"
)

& python @NuitkaArgs

if ($LASTEXITCODE -ne 0) {
    throw "Nuitka build failed with exit code $LASTEXITCODE"
}

if (-not (Test-Path $Executable)) {
    throw "Built executable was not found: $Executable"
}

Write-Host ""
Write-Host "Applying version_info.txt..."
Write-Host ""

$SetVersion = Get-Command "pyi-set_version" -ErrorAction SilentlyContinue

if (-not $SetVersion) {
    $SetVersion = Get-Command "pyi-set_version.exe" -ErrorAction SilentlyContinue
}

if (-not $SetVersion) {
    throw "pyi-set_version was not found. Install PyInstaller with: python -m pip install pyinstaller"
}

& $SetVersion.Source $VersionInfoPath $Executable

if ($LASTEXITCODE -ne 0) {
    throw "Failed to apply version_info.txt"
}

Write-Host ""
Write-Host "Build complete:"
Write-Host $Executable
Write-Host ""
Write-Host "Embedded Windows metadata:"
Write-Host ""

(Get-Item $Executable).VersionInfo | Format-List `
    CompanyName,
    ProductName,
    FileDescription,
    FileVersion,
    ProductVersion,
    InternalName,
    OriginalFilename,
    LegalCopyright,
    Comments
