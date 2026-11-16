# Firma dell'installer

La firma richiede un certificato di firma del codice affidabile con chiave privata disponibile al proprietario e un servizio di marcatura temporale compatibile. Il proprietario ha comunicato di non disporne: nessuna firma è stata prodotta e REQ-105 resta aperto.

Una volta disponibili, il proprietario può eseguire `installer/sign.ps1 -Installer <file.exe> -Thumbprint <impronta> -TimestampUrl <indirizzo-https>` e verificare con `installer/verify-signature.ps1 -Installer <file.exe>`. Non inserire chiavi private nel progetto. Lo script NSIS richiede per le build di rilascio un comando di firma esplicito (`OCR2_SIGN_COMMAND`), che applica sia al disinstallatore sia all’installer tramite i passaggi di finalizzazione; il comando deve chiamare `sign.ps1` passando il file prodotto, impronta e servizio temporale. I due agganci sono stati provati con un firmatario finto, inclusa una prova di errore, ma non con un certificato: firmare il solo installer non soddisfa il requisito.

Il manifest interno può rilevare variazioni accidentali, ma non è una radice di fiducia indipendente: chi può alterare insieme codice e manifest può aggirarlo. Una firma dell'installer non dimostra da sola l'integrità dei file installati dopo l'installazione.

La procedura non è ancora completa per REQ-105: i binari Python compilati localmente non sono ancora firmati. `sign.ps1` accetta ora `.exe`, `.dll` e `.pyd`. Il costruttore del payload accetta un callback `local_runtime_signer` e l’impronta `local_runtime_thumbprint`: quando specificati, controlla che l’archivio Python corrisponda alla build approvata, verifica l’elenco dei binari locali, invoca il callback su ciascuno, verifica indipendentemente che la firma sia valida, marcata temporalmente e associata all’impronta prevista, e genera il manifest solo dopo. Non modifica le DLL dei fornitori fuori da tale elenco. Il firmatario rifiuta file già firmati. Il callback deve eseguire `sign.ps1 -Installer <file> -Thumbprint <impronta> -TimestampUrl <url>` e sollevare un errore se il processo fallisce, ad esempio usando `subprocess.run([...], check=True)` senza shell. L’opzione è assente per le build di prova: non è un controllo automatico di rilascio, e i ganci NSIS da soli non la attivano. Il flusso con un certificato reale, l’insieme esatto dei binari di terze parti e la firma indipendente del manifest restano da verificare prima del rilascio.

Esempio di callback da passare al costruttore, in una sessione del proprietario con certificato e servizio temporale già disponibili:

```python
import subprocess
from pathlib import Path

thumbprint = "<impronta-certificato>"
timestamp_url = "<servizio-https>"
sign_script = Path("installer/sign.ps1").resolve()

def sign_local_binary(path):
    subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-File",
                    str(sign_script), "-Installer", str(path),
                    "-Thumbprint", thumbprint, "-TimestampUrl", timestamp_url], check=True)

# Passare a build_payload: local_runtime_signer=sign_local_binary,
# local_runtime_thumbprint=thumbprint. Usare una nuova cartella di destinazione.
```

Il confronto dell’impronta nel verificatore usa il certificato firmatario e non sostituisce la verifica della proprietà o della validità della catena sul PC destinatario. La lista è legata all’archivio Python approvato; una nuova build richiede un nuovo inventario.
