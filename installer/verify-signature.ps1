param([Parameter(Mandatory=$true)][string]$Installer)
$ErrorActionPreference = 'Stop'
$file = (Resolve-Path -LiteralPath $Installer).Path
$signature = Get-AuthenticodeSignature -LiteralPath $file
Write-Output "Status: $($signature.Status)"
Write-Output "Soggetto: $($signature.SignerCertificate.Subject)"
Write-Output "Impronta: $($signature.SignerCertificate.Thumbprint)"
Write-Output "Certificato marca temporale: $($signature.TimeStamperCertificate.Subject)"
if ($signature.Status -ne 'Valid' -or -not $signature.TimeStamperCertificate) { exit 1 }
