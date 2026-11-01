param([string]$Destination = '')
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$dist = Join-Path $root 'dist'
$manifest = Get-Content -LiteralPath (Join-Path $dist 'manifest.json') -Raw | ConvertFrom-Json
$package = Get-Content -LiteralPath (Join-Path $root 'package.json') -Raw | ConvertFrom-Json
if ($manifest.version -ne $package.version) { throw 'Build version differs from package.json; build first.' }
$releaseNotes = Join-Path $root "docs/release-$($manifest.version).md"
if (-not (Test-Path -LiteralPath $releaseNotes -PathType Leaf)) { throw "Missing release notes: $releaseNotes" }
if ($manifest.host_permissions -match 'localhost|127\.0\.0\.1') { throw 'Local permissions found; use build:prod.' }
if ($manifest.content_scripts.js -contains 'site-auth.js') { throw 'Local website bridge found in production manifest.' }
if (Test-Path -LiteralPath (Join-Path $dist 'site-auth.js')) { throw 'Unused local website bridge found; rebuild production package.' }
foreach ($file in @('popup.html', 'support.html', 'background.js', 'content.js', 'injected.js')) {
  if (-not (Test-Path -LiteralPath (Join-Path $dist $file) -PathType Leaf)) { throw "Missing build asset: $file" }
}
if (-not $Destination) { $Destination = Join-Path $root 'releases' }
$null = New-Item -ItemType Directory -Path $Destination -Force
$name = "gongkao-extension-$($manifest.version)-production"
$stage = Join-Path $Destination $name
$archive = Join-Path $Destination "$name.zip"
if ((Test-Path -LiteralPath $stage) -or (Test-Path -LiteralPath $archive) -or (Test-Path -LiteralPath "$archive.sha256")) {
  throw "Release already exists. Choose another -Destination; existing files will not be overwritten."
}
$null = New-Item -ItemType Directory -Path $stage
Copy-Item -Path (Join-Path $dist '*') -Destination $stage -Recurse
Copy-Item -LiteralPath $releaseNotes -Destination (Join-Path $stage '安装说明.md')
Copy-Item -LiteralPath (Join-Path $root 'docs/export-delivery.md') -Destination (Join-Path $stage '交付联调说明.md')
Copy-Item -LiteralPath (Join-Path $root 'docs/wrong-import-timing.md') -Destination (Join-Path $stage '错题与练习归档说明.md')
Compress-Archive -Path (Join-Path $stage '*') -DestinationPath $archive -CompressionLevel Optimal
$hash = Get-FileHash -LiteralPath $archive -Algorithm SHA256
Set-Content -LiteralPath "$archive.sha256" -Value "$($hash.Hash.ToLower())  $name.zip" -Encoding utf8
Write-Output "ZIP: $archive"
Write-Output "SHA256: $($hash.Hash.ToLower())"
Write-Output "Unpacked: $stage"
