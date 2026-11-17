param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$Folder,

    [string]$Destination = 'C:\Program Files\PulseView\share\libsigrokdecode\decoders'
)

$ErrorActionPreference = 'Stop'

if ([System.IO.Path]::IsPathRooted($Folder)) {
    $source = $Folder
} else {
    $source = Join-Path $PSScriptRoot $Folder
}

if (-not (Test-Path -LiteralPath $source -PathType Container)) {
    throw "Decoder folder not found: $source"
}
if (-not (Test-Path -LiteralPath $Destination -PathType Container)) {
    throw "Decoder destination folder not found: $Destination"
}

Copy-Item -LiteralPath $source -Destination $Destination -Recurse -Force
Write-Host "Copied '$source' to '$Destination'."
