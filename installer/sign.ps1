<#
.SYNOPSIS
  Firma un eseguibile OCR2 con Authenticode (REQ-105). Lo esegue il proprietario.
.DESCRIPTION
  Cerca il certificato solo in Cert:\CurrentUser\My per impronta; richiede chiave privata e
  uso "Firma del codice" (1.3.6.1.5.5.7.3.3). Firma con SHA-256 e marca temporale.
  Esce con 0 solo se lo stato della firma e' Valid (1 in ogni altro caso). Non importa, non crea e non installa
  certificati; non tocca gli archivi di certificati della macchina.
  Usato anche da makensis (!finalize / !uninstfinalize) quando build_installer.py riceve
  --sign-thumbprint e --timestamp-url.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Installer,
    [Parameter(Mandatory = $true)][string]$Thumbprint,
    [Parameter(Mandatory = $true)][string]$TimestampServer,
    [string]$FailureMarker = ''
)
$ErrorActionPreference = 'Stop'
# Il marcatore dà a build_installer.py un messaggio leggibile (makensis comunque si ferma: `= 0`); passa
# -FailureMarker e blocca la costruzione se il file esiste.
trap {
    if ($FailureMarker) { try { Set-Content -LiteralPath $FailureMarker -Value ([string]$_) -Encoding UTF8 } catch { } }
    Write-Host ([string]$_)
    exit 1
}
if (-not (Get-Command Get-AuthenticodeSignature -ErrorAction SilentlyContinue)) {
    # Avviata da PowerShell 7: il PSModulePath ereditato nasconde il modulo di Windows PowerShell.
    $env:PSModulePath = [Environment]::GetEnvironmentVariable('PSModulePath', 'Machine')
    Import-Module Microsoft.PowerShell.Security
}

if (-not (Test-Path -LiteralPath $Installer -PathType Leaf)) {
    Write-Error "File da firmare non trovato: $Installer"
}
$clean = ($Thumbprint -replace '\s', '').ToUpperInvariant()
if ($clean -notmatch '^[0-9A-F]{40}$') {
    Write-Error 'Impronta non valida: attesi 40 caratteri esadecimali.'
}
$cert = Get-ChildItem -Path 'Cert:\CurrentUser\My' | Where-Object { $_.Thumbprint -eq $clean } | Select-Object -First 1
if (-not $cert) {
    Write-Error 'Certificato non trovato in Cert:\CurrentUser\My con questa impronta.'
}
if (-not $cert.HasPrivateKey) {
    Write-Error 'Il certificato non ha la chiave privata.'
}
$codeSigning = '1.3.6.1.5.5.7.3.3'
$usages = @($cert.EnhancedKeyUsageList | ForEach-Object { $_.ObjectId })
if ($usages -notcontains $codeSigning) {
    Write-Error 'Il certificato non ha l''uso "Firma del codice".'
}

$result = Set-AuthenticodeSignature -FilePath $Installer -Certificate $cert -HashAlgorithm SHA256 -TimestampServer $TimestampServer
Write-Host ("Stato: {0}  File: {1}" -f $result.Status, $Installer)
if ($result.Status -ne 'Valid') {
    Write-Error ("Firma non valida: {0} {1}" -f $result.Status, $result.StatusMessage)
}
exit 0
