# Download sorgente Python 3.13.18

2026-11-16: tentativo da `https://www.python.org/ftp/python/3.13.18/Python-3.13.18.tar.xz` fallito: `Invoke-WebRequest: Host sconosciuto.` Nessun hash del file ottenuto; il confronto con SHA-256 ufficiale non è stato possibile. Nessuna compilazione è stata avviata. Non sono stati effettuati tentativi alternativi (GOAL V6).

2026-11-16, su richiesta di ripristino: verifica diagnostica in sola lettura `Resolve-DnsName python.org` fallita con `Accesso negato`. La causa precisa non è stata stabilita; non sono state modificate impostazioni di rete o Windows e non è stato ripetuto il download.

Su richiesta esplicita del proprietario, il 2026-11-16 il download ufficiale è riuscito. SHA-256 calcolato `abb0102e6d4ae027509bcb82327d9dd85515b44a3ba8ad538cfc5e9847029f68`, coincidente con python.org. L’archivio verificato contiene PCbuild e il file LICENSE PSF; estratto nella cache del worktree. Le dipendenze esterne non sono ancora verificate né utilizzate.
