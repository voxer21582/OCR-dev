# Firma dell'installer

La firma richiede un certificato di firma del codice affidabile con chiave privata disponibile al proprietario e un servizio di marcatura temporale compatibile. Il proprietario ha comunicato di non disporne: nessuna firma è stata prodotta e REQ-105 resta aperto.

Una volta disponibili, il proprietario può eseguire `installer/sign.ps1 -Installer <file.exe> -Thumbprint <impronta> -TimestampUrl <indirizzo-https>` e verificare con `installer/verify-signature.ps1 -Installer <file.exe>`. Non inserire chiavi private nel progetto. Lo script NSIS richiede per le build di rilascio un comando di firma esplicito (`OCR2_SIGN_COMMAND`), che applica sia al disinstallatore sia all’installer tramite i passaggi di finalizzazione; il comando deve chiamare `sign.ps1` passando il file prodotto, impronta e servizio temporale. I due agganci sono stati provati con un firmatario finto, inclusa una prova di errore, ma non con un certificato: firmare il solo installer non soddisfa il requisito.

Il manifest interno può rilevare variazioni accidentali, ma non è una radice di fiducia indipendente: chi può alterare insieme codice e manifest può aggirarlo. Una firma dell'installer non dimostra da sola l'integrità dei file installati dopo l'installazione.
