# Firma dell'installer

La firma richiede un certificato di firma del codice affidabile con chiave privata disponibile al proprietario e un servizio di marcatura temporale compatibile. Il proprietario ha comunicato di non disporne: nessuna firma è stata prodotta e REQ-105 resta aperto.

Una volta disponibili, il proprietario può eseguire `installer/sign.ps1 -Installer <file.exe> -Thumbprint <impronta> -TimestampUrl <indirizzo-https>` e verificare con `installer/verify-signature.ps1 -Installer <file.exe>`. Non inserire chiavi private nel progetto. La firma del disinstallatore durante la costruzione NSIS va ancora integrata e verificata prima della distribuzione: firmare il solo installer non soddisfa il requisito.

Il manifest interno può rilevare variazioni accidentali, ma non è una radice di fiducia indipendente: chi può alterare insieme codice e manifest può aggirarlo. Una firma dell'installer non dimostra da sola l'integrità dei file installati dopo l'installazione.
