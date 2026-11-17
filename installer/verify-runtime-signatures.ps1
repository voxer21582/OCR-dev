param(
    [Parameter(Mandatory=$true)][string]$Payload,
    [Parameter(Mandatory=$true)][string]$Thumbprint
)
$ErrorActionPreference = 'Stop'
if ($Thumbprint -notmatch '^[0-9a-fA-F]{40}$') { throw 'Impronta certificato non valida.' }
# Children are listed from this same spelling (long or 8.3), so their FullName
# starts with it; the relative path is still checked to stay inside the payload.
$root = (Get-Item -LiteralPath $Payload -Force).FullName.TrimEnd('\')
$python = Join-Path $root 'python'
foreach ($dir in @($root, $python)) {
    if (-not (Test-Path -LiteralPath $dir -PathType Container) -or ((Get-Item -LiteralPath $dir -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw 'Cartella non valida o collegata.' }
}
$names = @(
    'python.exe',
    'pythonw.exe',
    'python3.dll',
    'python313.dll',
    'sqlite3.dll',
    '_asyncio.pyd',
    '_bz2.pyd',
    '_ctypes.pyd',
    '_decimal.pyd',
    '_elementtree.pyd',
    '_hashlib.pyd',
    '_lzma.pyd',
    '_multiprocessing.pyd',
    '_overlapped.pyd',
    '_queue.pyd',
    '_socket.pyd',
    '_sqlite3.pyd',
    '_ssl.pyd',
    '_uuid.pyd',
    '_wmi.pyd',
    '_zoneinfo.pyd',
    'pyexpat.pyd',
    'select.pyd',
    'unicodedata.pyd',
    'winsound.pyd'
)
$manifest = Get-Content -LiteralPath (Join-Path $root 'runtime-manifest.json') -Raw -Encoding UTF8 | ConvertFrom-Json
foreach ($name in $names) {
    $file = Join-Path $python $name
    $item = Get-Item -LiteralPath $file -Force
    if ($item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw "File non valido: $name" }
    $record = $manifest.files.PSObject.Properties["python/$name"].Value
    if (-not $record -or $record.size -ne $item.Length -or $record.sha256 -ne (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash) { throw "Manifest non corrispondente: $name" }
    $sig = Get-AuthenticodeSignature -LiteralPath $file
    if ($sig.Status -ne 'Valid' -or -not $sig.TimeStamperCertificate -or $sig.SignerCertificate.Thumbprint -ne $Thumbprint) { throw "Firma runtime non valida: $name" }
}
# Every binary in the payload must match the manifest. Only the local-build list
# above carries the owner's signature; third-party binaries keep their vendor's
# signature or none (sign.ps1 never re-signs them): a signature they carry must
# be Valid, NotSigned is allowed, any other status fails.
$localBuild = @{}
foreach ($name in $names) { $localBuild["python/$name"] = $true }
$items = @(Get-ChildItem -LiteralPath $root -Recurse -Force -ErrorAction Stop)
foreach ($item in $items) {
    if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Collegamento non consentito nel payload.' }
    if ($item.PSIsContainer -or $item.Extension.ToLowerInvariant() -notin @('.exe', '.dll', '.pyd')) { continue }
    $relative = [IO.Path]::GetRelativePath($root, $item.FullName)
    if ([IO.Path]::IsPathRooted($relative) -or $relative -eq '.' -or $relative -eq '..' -or $relative.StartsWith('..\')) { throw "Percorso fuori dal payload: $($item.FullName)" }
    $relative = $relative.Replace('\', '/')
    $record = $manifest.files.PSObject.Properties[$relative].Value
    if (-not $record -or $record.size -ne $item.Length -or $record.sha256 -ne (Get-FileHash -LiteralPath $item.FullName -Algorithm SHA256).Hash) { throw "Manifest non corrispondente: $relative" }
    if ($localBuild.ContainsKey($relative)) { continue }
    $status = [string](Get-AuthenticodeSignature -LiteralPath $item.FullName).Status
    if ($status -ne 'Valid' -and $status -ne 'NotSigned') { throw "Firma di terze parti non valida ($status): $relative" }
}
Write-Output 'Firme runtime verificate.'
