<#
.SYNOPSIS
  Verifica la firma Authenticode di un file (REQ-105). Sola lettura.
.DESCRIPTION
  Stampa Status, soggetto, impronta del firmatario e ora della marca temporale
  (oppure "nessuna marca temporale"). Esce con 1 se lo stato non e' Valid.
  Non modifica file ne' archivi di certificati.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Path
)
$ErrorActionPreference = 'Stop'
if (-not (Get-Command Get-AuthenticodeSignature -ErrorAction SilentlyContinue)) {
    # Avviata da PowerShell 7: il PSModulePath ereditato nasconde il modulo di Windows PowerShell.
    $env:PSModulePath = [Environment]::GetEnvironmentVariable('PSModulePath', 'Machine')
    Import-Module Microsoft.PowerShell.Security
}

if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
    Write-Host "File non trovato: $Path"
    exit 1
}
$sig = Get-AuthenticodeSignature -LiteralPath $Path
Write-Host ("File:        {0}" -f $Path)
Write-Host ("Status:      {0}" -f $sig.Status)
if ($sig.SignerCertificate) {
    Write-Host ("Soggetto:    {0}" -f $sig.SignerCertificate.Subject)
    Write-Host ("Impronta:    {0}" -f $sig.SignerCertificate.Thumbprint)
} else {
    Write-Host 'Soggetto:    nessun firmatario'
    Write-Host 'Impronta:    nessun firmatario'
}
function Get-StampTime([string]$File) {
    # Ora della marca temporale dal blocco Authenticode del file (sola lettura): controfirma
    # classica (signingTime) oppure marca RFC 3161 (genTime di TSTInfo).
    try {
        $bytes = [System.IO.File]::ReadAllBytes($File)
        $pe = [BitConverter]::ToInt32($bytes, 0x3C)
        $magic = [BitConverter]::ToUInt16($bytes, $pe + 24)
        $dir = if ($magic -eq 0x20B) { $pe + 24 + 112 } else { $pe + 24 + 96 }
        $off = [BitConverter]::ToInt32($bytes, $dir + 4 * 8)
        $len = [BitConverter]::ToInt32($bytes, $dir + 4 * 8 + 4)
        if ($off -le 0 -or $len -le 8) { return $null }
        $blob = New-Object byte[] ($len - 8)
        [Array]::Copy($bytes, $off + 8, $blob, 0, $len - 8)
        $cms = New-Object System.Security.Cryptography.Pkcs.SignedCms
        $cms.Decode($blob)
        $signer = $cms.SignerInfos[0]
        foreach ($counter in $signer.CounterSignerInfos) {
            foreach ($attr in $counter.SignedAttributes) {
                if ($attr.Oid.Value -eq '1.2.840.113549.1.9.5') {
                    $t = New-Object System.Security.Cryptography.Pkcs.Pkcs9SigningTime (, $attr.Values[0].RawData)
                    return $t.SigningTime.ToUniversalTime()
                }
            }
        }
        foreach ($attr in $signer.UnsignedAttributes) {
            if ($attr.Oid.Value -eq '1.3.6.1.4.1.311.3.3.1') {
                $inner = New-Object System.Security.Cryptography.Pkcs.SignedCms
                $inner.Decode($attr.Values[0].RawData)
                $text = [System.Text.Encoding]::ASCII.GetString($inner.ContentInfo.Content)
                $m = [regex]::Match($text, '\d{14}Z')
                if ($m.Success) {
                    return [DateTime]::ParseExact($m.Value, 'yyyyMMddHHmmss\Z', [Globalization.CultureInfo]::InvariantCulture, [Globalization.DateTimeStyles]::AssumeUniversal -bor [Globalization.DateTimeStyles]::AdjustToUniversal)
                }
            }
        }
    } catch { }
    return $null
}

if ($sig.TimeStamperCertificate) {
    $when = Get-StampTime $Path
    if ($when) {
        Write-Host ("Marca temporale: {0:yyyy-MM-dd HH:mm:ss} UTC (emessa da {1})" -f $when, $sig.TimeStamperCertificate.Subject)
    } else {
        Write-Host ("Marca temporale: presente, ora non leggibile (emessa da {0})" -f $sig.TimeStamperCertificate.Subject)
    }
} else {
    Write-Host 'Marca temporale: nessuna marca temporale'
}
if ($sig.Status -ne 'Valid') { exit 1 }
exit 0
