# Componenti per la compilazione Python 3.13.18

Acquisiti dai repository `python/cpython-source-deps` e `python/cpython-bin-deps` tramite tag ufficiali e connessione HTTPS. Per ciascuno, il riferimento Git locale coincide con quello letto dal repository remoto; `git fsck` è riuscito e la copia non presenta modifiche. I valori sono identificatori di oggetti Git SHA-1, non impronte SHA-256 di release firmate; le librerie binarie sono distribuite dal repository Python e la loro riproducibilità dal sorgente non è stata verificata.

| Componente | Tag Git verificato | Licenza esaminata |
|---|---|---|
| bzip2 1.0.8 | `05301997b2f9590f49c672cf3dfd3d3dfa7ad521` | bzip2/libbzip2, file LICENSE |
| mpdecimal 4.0.0 | `780e21d43a92832d12c2add68fcc8e03cee38bcf` | BSD, COPYRIGHT.txt |
| SQLite 3.50.4.0 | `c8123bc55da6467f4ef3e9b70cdb67cecf33b937` | pubblico dominio, intestazione sqlite3.c |
| XZ 5.2.5 | `c6bc0c612605622aaef101a33a751f9de2ecc193` | licenze multiple; liblzma pubblico dominio, COPYING |
| zlib 1.3.1 | `4dc98e1909830e2bdc2a9cc2236e3c5d5037335b` | zlib, LICENSE |
| libffi 3.4.4 | `94cb9a1c7feb608adf2b9f8fe2dbd6925ffbf90d` | MIT, LICENSE |
| OpenSSL 3.5.9 | `ddb46a415b4995440723183e644f8d2c346567a2` | Apache 2.0, amd64/LICENSE.txt |

Tcl/Tk esclusi dalla build perché non richiesti dall'applicazione. La raccolta completa degli avvisi per la distribuzione resta da verificare nel task SBOM.
