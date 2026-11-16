param(
    [Parameter(Mandatory=$true)][string]$Payload,
    [Parameter(Mandatory=$true)][string]$Thumbprint
)
$ErrorActionPreference = 'Stop'
if ($Thumbprint -notmatch '^[0-9a-fA-F]{40}$') { throw 'Impronta certificato non valida.' }
$root = (Resolve-Path -LiteralPath $Payload).Path
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
Write-Output 'Firme runtime verificate.'
