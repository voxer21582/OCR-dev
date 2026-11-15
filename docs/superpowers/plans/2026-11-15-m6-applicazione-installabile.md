# M6 — Applicazione installabile: piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** OCR2 si installa per l'utente da un unico installer offline, senza privilegi di amministratore; si apre in una finestra di Edge in modalità app dal menu Start, si chiude con «Esci» o da sola quando nessuna finestra è aperta; si aggiorna, torna alla versione precedente e si disinstalla conservando i dati, con runtime verificato, SBOM, notice e firma del proprietario.

**Architecture:** il lancio in finestra è un modo del launcher esistente (`--app-window`): un server su porta libera, un'istanza sola per utente, Edge avviato con un profilo dedicato in `%LOCALAPPDATA%\OCR2\edge-profile`. La presenza delle finestre arriva da un battito (`GET /app/heartbeat`) e da un avviso di chiusura (`pagehide`), iniettati da `_page` in ogni pagina; un thread di guardia chiama `server.shutdown()`. L'installer NSIS copia una cartella per versione (`%LOCALAPPDATA%\Programs\OCR2\versions\<versione>\` con Python embeddable, pacchetti del lock e applicazione), la verifica con un manifest di impronte e solo alla fine sposta i collegamenti sulla nuova versione; la versione precedente resta per il ritorno indietro.

**Tech Stack:** Python 3.13 (stdlib), CPython 3.13 embeddable x64 (R-001), NSIS 3.x portabile (R-002), PowerShell integrato per firma e verifica (`Set-AuthenticodeSignature`, `Get-AuthenticodeSignature`). Nessun'altra dipendenza.

**Spec:** [`docs/superpowers/specs/2026-11-15-ocr2-product-completion-design.md`](../specs/2026-11-15-ocr2-product-completion-design.md) §5.2, §6, §7; [`docs/plan.md`](../../plan.md) §M6; requisiti REQ-100…107 in [`docs/requirements.md`](../../requirements.md).

## Decisioni del proprietario (2026-11-15, in chat)

- R-001 (Python 3.13 embeddable) e R-002 (NSIS 3.x portabile) **approvate**.
- Q-001: FFmpeg di OpenCV **escluso** dall'installer, dopo un test che l'OCR funziona senza.
- Q-003: **nessun** backup portabile; resta DEC-029.
- Matrice del ciclo di vita sull'altro PC: la **esegue il proprietario** con una procedura scritta.

## Global Constraints

- **V4:** nessuna modifica a registro, impostazioni, servizi o file di sistema. L'installer scrive solo in `%LOCALAPPDATA%\Programs\OCR2` e crea collegamenti nel menu Start dell'utente. Nessuna voce `HKCU\...\Uninstall` (DEC-032): la disinstallazione si avvia dal menu Start.
- **A5 / REQ-103:** nessun download all'installazione, all'avvio o all'aggiornamento; l'aggiornamento è un nuovo installer.
- Edge si avvia sempre con `--user-data-dir=%LOCALAPPDATA%\OCR2\edge-profile`, così le impostazioni di Edge dell'utente non cambiano.
- Il server ascolta solo su `127.0.0.1`.
- I dati dell'utente (`%LOCALAPPDATA%\OCR2\`) sono separati dal programma (`%LOCALAPPDATA%\Programs\OCR2\`) e restano dopo aggiornamento, ritorno indietro e disinstallazione, salvo scelta esplicita «elimina anche i dati».
- Nessun `opencv_videoio_ffmpeg*.dll` nella cartella installata (DEC-030).
- Solo dati sintetici; prove locali con `LOCALAPPDATA` temporaneo, mai l'archivio dell'utente.
- Ogni modulo di test nuovo va in entrambi i job CI (`test_ci_workflow.py` lo controlla).
- Testi dell'interfaccia in italiano.
- **Stop:** se un download (embeddable, NSIS, wheel) non corrisponde all'impronta fissata, ci si ferma e si registra; nessun nuovo tentativo con altre fonti (V6).

## Review Focus

1. **Due finestre aperte, una si chiude:** il server resta acceso finché ne resta una, anche se è ridotta a icona (Edge rallenta i timer delle schede nascoste fino a un battito al minuto).
2. **Secondo clic sul collegamento con l'app già aperta:** si apre una nuova finestra sullo stesso server; nessun secondo server sullo stesso archivio.
3. **Ritorno indietro dopo che la versione nuova ha migrato l'archivio:** la versione vecchia rifiuta l'archivio più recente con un messaggio chiaro e non lo modifica.
4. **Aggiornamento interrotto (installer chiuso a metà o file alterato):** la versione attiva resta quella vecchia e parte.
5. **Edge non trovato:** l'app si apre nel browser predefinito e lo dice; non resta un server senza finestra.

---

### Task 1: Decisioni e dipendenze registrate

**Files:** `docs/decisions.md`, `docs/questions.md`, `docs/dependencies-request.md`, `docs/dependencies-approved.md`, `docs/STATUS.md`

- [ ] Aggiungere in `decisions.md`: **DEC-030** FFmpeg escluso dall'installer (Q-001); **DEC-031** nessun backup portabile, DEC-029 confermata (Q-003); **DEC-032** nessuna registrazione in «App installate» (V4), disinstallazione dal menu Start, una cartella per versione con al massimo due versioni conservate.
- [ ] Spostare R-001 e R-002 in `dependencies-approved.md` come «approvate il 2026-11-15, impronta da fissare al primo download (Task 6)»; in `questions.md` Q-001 e Q-003 passano a «risolte».
- [ ] Commit `docs(M6): record owner decisions on R-001, R-002, Q-001 and Q-003`.

### Task 2: Presenza delle finestre e spegnimento automatico (REQ-101)

**Files:** Create `application/src/alfa_document_intelligence/app_lifetime.py`; Test `application/tests/test_app_lifetime.py`

**Interfaces — Produces:**
- `class WindowPresence(clock: Callable[[], float] = time.monotonic, *, heartbeat_expiry_seconds=180.0, closing_grace_seconds=10.0, startup_grace_seconds=120.0)`
  - `heartbeat(window_id: str) -> None` (id di 1–64 caratteri `[A-Za-z0-9_-]`, altrimenti `ValueError`)
  - `closing(window_id: str) -> None`
  - `activity() -> None` (qualsiasi richiesta)
  - `should_stop() -> bool`
- `class AppLifetime(presence: WindowPresence, stop_server: Callable[[], None], *, poll_seconds=1.0)` con `start()`, `request_exit()`, `stopped: threading.Event`.

Regole: una finestra è viva se il suo ultimo battito ha meno di 180 s. `should_stop()` è vero quando non c'è nessuna finestra viva **e** non ci sono richieste da 10 s dopo l'ultimo `closing`, oppure da 180 s dall'ultimo battito, oppure (nessuna finestra mai vista) da 120 s dall'avvio. Le finestre throttled (un battito al minuto) restano vive.

- [ ] Test con orologio finto: `test_no_window_ever_stops_after_startup_grace`; `test_closing_last_window_stops_after_ten_seconds`; `test_navigation_within_window_does_not_stop` (closing e battito dello stesso id entro 10 s); `test_second_window_keeps_server_alive_when_first_closes` (seconda finestra con battiti ogni 60 s, prima chiusa: `should_stop()` falso a 10, 70, 130 s); `test_silent_window_expires_after_180_seconds`; `test_invalid_window_id_is_rejected`; `test_request_exit_stops_once` (`stop_server` chiamato una volta sola anche con due `request_exit`).
- [ ] Verificare che falliscano, implementare, verificare che passino: `python -B -m pytest -q application/tests/test_app_lifetime.py`.
- [ ] Aggiungere il modulo ai due job CI; commit `feat(M6): window presence and automatic shutdown (REQ-101)`.

### Task 3: «Esci», battito e pagina Informazioni nelle pagine (REQ-101, REQ-106)

**Files:** Modify `local_intake_app.py` (`_page`, `app`, `create_expense_report_app`, `serve_expense_report_local`); Test `application/tests/test_app_window_routes.py`

**Interfaces — Consumes:** `WindowPresence`, `AppLifetime` (Task 2). **Produces:**
- `create_expense_report_app(..., app_lifetime: AppLifetime | None = None, app_info: AppInfo | None = None)` e lo stesso parametro in `serve_expense_report_local`.
- `@dataclass(frozen=True) class AppInfo: version: str; python_version: str; ocr_engine: str | None; runtime_status: str` (in `app_lifetime.py`).
- Rotte, attive solo se `app_lifetime` non è `None` (altrimenti 404): `GET /app/heartbeat?w=<id>` → 204; `POST /app/closing` (campo `w`, CSRF) → 204; `POST /app/exit` (CSRF) → pagina «OCR2 si è chiuso. Puoi chiudere questa finestra.» e poi `request_exit()`; `GET /app/info` → «Informazioni» con versione, Python, motore OCR e stato della verifica del runtime (sempre attiva).

In `_page`, solo per risposte `text/html` e con `app_lifetime` attivo (passato in `environ["_ocr2_app_lifetime"]`): prima di `</main>` (o in coda se manca) un `<form method="post" action="/app/exit"><button type="submit">Esci</button></form>`, un link «Informazioni» e uno `<script nonce="__CSP_NONCE__">` che crea l'id finestra in `sessionStorage`, chiama il battito al caricamento e ogni 20 s, e su `pagehide` invia `navigator.sendBeacon('/app/closing', FormData{w, _ocr2_csrf})`. Ogni richiesta chiama `presence.activity()`.

- [ ] Test: `test_every_html_page_has_exit_button_and_heartbeat_in_app_mode` (home, `/archive`, `/cases`, `/catalog`, pagina d'errore 403); `test_no_exit_button_without_app_mode`; `test_heartbeat_returns_204_and_marks_window`; `test_exit_requires_csrf` (403 senza token, `stop_server` non chiamato); `test_exit_stops_server_after_response` con server reale su porta 0: dopo `POST /app/exit` la porta si libera entro 5 s; `test_info_page_shows_version_python_and_engine`; `test_script_respects_csp_nonce`.
- [ ] Rossi, implementazione, verdi; suite completa invariata (`python -B -m pytest -q application/tests`).
- [ ] CI e commit `feat(M6): exit button, window heartbeat and info page (REQ-101, REQ-106)`.

### Task 4: Istanza unica e finestra Edge in modalità app (REQ-100)

**Files:** Create `app_instance.py`, `app_window.py`; Modify `__main__.py`; Test `application/tests/test_app_instance.py`, `application/tests/test_app_window.py`, `application/tests/test_local_launcher.py`

**Interfaces — Produces:**
- `app_instance.acquire(data_dir: Path) -> InstanceLock | None`: lock esclusivo su `data_dir/instance.lock` (`msvcrt.locking` su Windows, `fcntl.flock` altrove); `None` se un'altra istanza lo tiene. `InstanceLock.publish(port: int, instance_id: str)` scrive `instance.json`; `release()`.
- `app_instance.running_instance(data_dir: Path, timeout=2.0) -> int | None`: legge `instance.json` e conferma con `GET /app/info?id=<instance_id>` su `127.0.0.1:<port>`; altrimenti `None`.
- `app_window.find_edge() -> Path | None`: cerca `msedge.exe` in `%ProgramFiles(x86)%` e `%ProgramFiles%` `\Microsoft\Edge\Application\`, poi la chiave **in sola lettura** `HKLM\...\App Paths\msedge.exe`.
- `app_window.open_window(url: str, data_dir: Path) -> str`: avvia `msedge.exe --app=<url> --user-data-dir=<data_dir>\edge-profile --no-first-run --no-default-browser-check` e ritorna `"edge"`; senza Edge usa `webbrowser.open(url)` e ritorna `"browser"`.
- `__main__.py`: opzione `--app-window` (porta predefinita 0). Se `running_instance` trova un server: apre una finestra su quello ed esce con 0. Altrimenti: lock, server, `publish`, finestra, `AppLifetime.start()`, `serve_forever`; alla fine `ocr2_close`, `release`.

- [ ] Test: `test_second_acquire_returns_none_while_first_holds` (sottoprocesso che tiene il lock); `test_running_instance_ignores_stale_file` (porta chiusa o id diverso → `None`); `test_open_window_uses_dedicated_profile` (`subprocess.Popen` finto: argomenti esatti, nessun altro argomento); `test_open_window_falls_back_to_default_browser`; `test_find_edge_never_writes_registry` (nessuna chiamata a funzioni `winreg` di scrittura); `test_launcher_app_window_reuses_running_instance` (secondo `main(["--app-window"])` apre la finestra sulla porta della prima istanza e non crea un server); `test_launcher_app_window_stops_when_lifetime_requests_exit`.
- [ ] Prova manuale sul PC di sviluppo con `LOCALAPPDATA` temporaneo: finestra senza barra degli indirizzi, secondo avvio, «Esci», chiusura della finestra → porta libera e processo terminato entro 15 s. Registrare passi ed esiti in `docs/evidence/M6/app-window.md` (niente screenshot con dati veri).
- [ ] CI e commit `feat(M6): single instance and Edge app window (REQ-100)`.

### Task 5: Manifest del runtime e verifica all'avvio (REQ-103, REQ-106, DEC-030)

**Files:** Create `runtime_manifest.py`; Modify `__main__.py`; Test `application/tests/test_runtime_manifest.py`

**Interfaces — Produces:**
- `build_manifest(root: Path, *, version: str, excluded_globs: Sequence[str]) -> dict` → `{"format": 1, "version": str, "files": {"<percorso relativo con />": {"sha256": str, "size": int}}}`; rifiuta link simbolici e percorsi fuori da `root`.
- `verify_installation(root: Path, manifest_path: Path) -> RuntimeVerification` con `ok: bool`, `problems: tuple[str, ...]` (al massimo 20 elencati), `seconds: float`. Un file mancante, alterato o **in più** sotto `python/` e `app/` è un problema.
- `FORBIDDEN_GLOBS = ("**/opencv_videoio_ffmpeg*.dll",)`: la presenza è un problema anche se il manifest la elencasse.
- `__main__.py`: se esiste `<cartella del programma>/runtime-manifest.json` verifica prima di aprire la porta; se `ok` è falso stampa i problemi, apre (in modalità finestra) una pagina locale statica d'errore e termina con 2. L'esito va in `AppInfo.runtime_status`.

- [ ] Test: `test_manifest_round_trip_ok`; `test_altered_missing_and_extra_files_are_reported`; `test_ffmpeg_dll_is_always_a_problem`; `test_symlink_is_refused`; `test_launcher_refuses_to_start_on_failed_verification` (nessuna porta aperta, codice 2).
- [ ] **OCR senza FFmpeg (Q-001):** test `test_rapidocr_runs_without_ffmpeg_dll`, saltato con motivo se il runtime non c'è, che rinomina il DLL in una copia temporanea del runtime e riconosce una fixture sintetica con gli stessi risultati del benchmark M1. Eseguirlo sul PC di sviluppo e salvare l'output in `docs/evidence/M6/ocr-without-ffmpeg.txt`.
- [ ] CI e commit `feat(M6): runtime manifest verified at start, FFmpeg excluded (REQ-103)`.

### Task 6: Costruzione del contenuto dell'installer

**Files:** Create `installer/build_payload.py`, `installer/pins.json`, `installer/README.md`; Test `application/tests/test_build_payload.py`

**Interfaces — Consumes:** `build_manifest` (Task 5). **Produces:** `build_payload(*, embeddable_zip: Path, wheel_dir: Path, app_src: Path, out_dir: Path, version: str) -> Path` che crea:

```
out_dir/<version>/
  python/            # embeddable estratto; python313._pth con: python313.zip, ., ..\app, Lib\site-packages, import site
  python/Lib/site-packages/   # wheel del lock installate con pip --target --no-deps --no-index --require-hashes
  app/alfa_document_intelligence/   # solo i sorgenti, senza test né __pycache__
  runtime-manifest.json
```

- `pins.json`: nome file, URL ufficiale e SHA-256 dell'embeddable 3.13.x e dello zip di NSIS 3.x; si scaricano **una volta** sul PC di sviluppo in `installer/.cache/` (ignorata da git) e si verificano; impronta diversa → stop (V6). Le impronte vanno anche in `dependencies-approved.md`.
- Le wheel vengono da `pip download --only-binary=:all: --require-hashes -r requirements/ocr2-runtime-cp313-win-amd64.lock --platform win_amd64 --python-version 3.13 -d installer/.cache/wheels`.
- I `opencv_videoio_ffmpeg*.dll` vengono rimossi dopo l'installazione delle wheel.

- [ ] Test con embeddable e wheel sintetici (zip minimi fatti nel test): `test_pth_enables_site_and_app`; `test_tests_and_pycache_are_not_copied`; `test_ffmpeg_dll_is_removed`; `test_wrong_pin_stops_build`; `test_manifest_matches_payload`.
- [ ] Costruzione reale sul PC di sviluppo; poi `out/<v>/python/python.exe -m alfa_document_intelligence --ocr-engine rapidocr-v6 --port 0` avvia con verifica del runtime riuscita. Registrare dimensione, numero di file e tempo di verifica all'avvio in `docs/evidence/M6/payload.md`.
- [ ] CI e commit `build(M6): installer payload with embeddable Python and locked runtime`.

### Task 7: SBOM e notice di licenza (REQ-107)

**Files:** Create `installer/sbom.py`, `installer/notices.py`; Test `application/tests/test_sbom_and_notices.py`

**Interfaces — Produces:**
- `build_sbom(payload_root: Path, lock: Path, pins: Path) -> dict`: CycloneDX 1.5 JSON; un componente per ogni pacchetto del lock (nome, versione, `purl` `pkg:pypi/...`, SHA-256 della wheel, licenza dichiarata nei metadati), per CPython embeddable, per i due modelli PP-OCRv6 (SHA-256 della factory) e per OCR2; NSIS compare come strumento di costruzione (`"scope": "excluded"`).
- `build_notices(payload_root: Path) -> str`: `THIRD_PARTY_NOTICES.txt` con, per ogni `*.dist-info`, nome, versione e il testo di ogni file di licenza dichiarato (`License-File` o `licenses/`), più `LICENSE.txt` di Python e `MODEL_LICENSES.md` di RapidOCR.
- Entrambi i file vanno nella cartella della versione e nel manifest.

- [ ] Test: `test_every_locked_package_is_in_sbom` (22 su 22, versioni e impronte identiche al lock); `test_sbom_has_no_ffmpeg_component`; `test_every_dist_info_has_licence_text_in_notices` (un pacchetto senza file di licenza fa fallire il build con il suo nome); `test_sbom_is_deterministic` (due build, byte identici).
- [ ] Generare sul contenuto reale; elenco dei pacchetti senza testo di licenza (se ce ne sono) in `docs/evidence/M6/notices.md` e stop per decisione del proprietario.
- [ ] CI e commit `build(M6): SBOM and third-party notices from the lock (REQ-107)`.

### Task 8: Installer NSIS, aggiornamento, ritorno indietro, disinstallazione (REQ-102, REQ-104, REQ-106)

**Files:** Create `installer/ocr2.nsi`, `application/src/alfa_document_intelligence/install_state.py`; Test `application/tests/test_install_state.py`, `application/tests/test_nsis_script.py`

**Interfaces — Produces:** `install_state.py` (eseguito dal Python installato), cartella base `%LOCALAPPDATA%\Programs\OCR2`:
- `activate(base: Path, version: str) -> None`: verifica la versione con `verify_installation`; se ok scrive `active.json` (`{"active": v, "previous": vecchia}`) in modo atomico (`os.replace`); altrimenti `InstallStateError` e `active.json` invariato.
- `rollback(base: Path) -> str`: torna a `previous` (verificata) e ritorna la versione attiva.
- `prune(base: Path) -> list[str]`: tiene solo `active` e `previous`.
- `main(argv)`: sottocomandi `activate <v>`, `rollback`, `prune`, `uninstall [--remove-data]`.

`ocr2.nsi`: `RequestExecutionLevel user`; `InstallDir "$LOCALAPPDATA\Programs\OCR2"`; `SetShellVarContext current`; estrae in `versions\<v>\`, esegue `python.exe -m alfa_document_intelligence.install_state activate <v>`; se fallisce mostra l'errore, cancella solo `versions\<v>\` e lascia attiva la vecchia. Solo dopo il successo crea o aggiorna nel menu Start la cartella «OCR2» con «OCR2» (`pythonw.exe -m alfa_document_intelligence --app-window --ocr-engine rapidocr-v6` della versione attiva), «Torna alla versione precedente» e «Disinstalla OCR2». La disinstallazione chiede se eliminare anche `%LOCALAPPDATA%\OCR2` (predefinito: no). Opzione di costruzione `-DOCR2_TEST` che salta i collegamenti per le prove locali con `/D=<cartella temporanea>`.

Archivio più recente: se lo store segnala uno schema superiore a quello supportato, il launcher mostra «Questo archivio è stato aggiornato da una versione più recente di OCR2. Reinstalla quella versione.» e termina senza scrivere.

- [ ] Test `install_state`: `test_activate_switches_only_after_verification`; `test_activate_failure_keeps_previous_active` (file alterato); `test_interrupted_activation_leaves_valid_active_json` (errore iniettato prima di `os.replace`); `test_rollback_returns_to_previous`; `test_prune_keeps_two_versions`; `test_uninstall_keeps_data_by_default` e `test_uninstall_remove_data_deletes_only_ocr2_data`; `test_older_version_refuses_newer_archive_schema` (archivio sintetico con `user_version` maggiore: nessuna scrittura, impronta del file identica).
- [ ] Test statico `test_nsis_script`: nessun `WriteReg*`, `DeleteReg*`, `RequestExecutionLevel admin`, `$PROGRAMFILES`, `$WINDIR`, `SetShellVarContext all`, URL `http`; presenti `RequestExecutionLevel user` e `$LOCALAPPDATA\Programs\OCR2`.
- [ ] Costruire con `makensis` portabile (versioni 0.6.0 e 0.6.1) e provare sul PC di sviluppo con `-DOCR2_TEST` e `/D=` temporaneo: installazione, avvio, aggiornamento, aggiornamento interrotto (processo terminato durante l'estrazione), ritorno indietro, disinstallazione con e senza dati. Esiti in `docs/evidence/M6/installer-dev-pc.md`.
- [ ] CI e commit `feat(M6): per-user NSIS installer with update, rollback and uninstall (REQ-102, REQ-104)`.

### Task 9: Firma del proprietario (REQ-105)

**Files:** Create `docs/runtime/signing.md`, `installer/sign.ps1`, `installer/verify-signature.ps1`

- [ ] **Stop e domanda al proprietario (Q-004):** quale certificato di firma del codice usa (certificato commerciale o di un'organizzazione; un certificato autofirmato richiede di aggiungerlo all'archivio certificati del PC che verifica, cosa che V4 vieta sul PC di destinazione). Registrare la risposta in `decisions.md`.
- [ ] `sign.ps1 -Installer <exe> -Thumbprint <impronta>`: firma installer e disinstallatore (NSIS `!uninstfinalize`) con `Set-AuthenticodeSignature -HashAlgorithm SHA256` e marca temporale indicata dal proprietario; lo esegue il proprietario.
- [ ] `verify-signature.ps1`: stampa `Status`, soggetto, impronta del certificato e ora della marca temporale; esce con 1 se lo stato non è `Valid`.
- [ ] Limite dichiarato in `signing.md`: i file `.py` non sono firmabili; la loro integrità è garantita dal manifest dentro l'installer firmato; i binari di Python e delle wheel mantengono le firme dei loro autori, dove presenti.
- [ ] Evidenza `docs/evidence/M6/signature.md`: chi ha firmato, quando, output di `verify-signature.ps1`. Commit `docs(M6): owner signing procedure (REQ-105)`.

### Task 10: Procedura per l'altro PC e impronta dell'utente (REQ-102, REQ-104)

**Files:** Create `docs/runtime/m6-lifecycle-procedure.md`, `installer/user-footprint.ps1`, `docs/evidence/M6/lifecycle-matrix.md` (modello da compilare)

- `user-footprint.ps1 -Out <file>`: elenca file e cartelle sotto `%LOCALAPPDATA%`, `%APPDATA%\Microsoft\Windows\Start Menu` e i **nomi** delle chiavi sotto `HKCU\Software` (nessun valore); `-Compare <prima> <dopo>` stampa solo le differenze. Solo PowerShell integrato, nessuna scrittura fuori da `-Out`.
- Procedura passo per passo, in italiano semplice, per il proprietario: impronta prima; installazione 0.6.0; avvio dal menu Start (finestra, versione in «Informazioni», un fascicolo sintetico dalle fixture del repository); «Esci»; chiusura della finestra e porta libera; aggiornamento a 0.6.1 (dati presenti); aggiornamento interrotto; ritorno a 0.6.0; disinstallazione senza dati e reinstallazione (dati ritrovati); disinstallazione con dati; impronta dopo e confronto. Per ogni passo: cosa fare, cosa si deve vedere, casella esito.
- Il confronto delle impronte si rilegge prima di condividerlo: nel repository entrano solo righe che riguardano OCR2.
- [ ] Prova della procedura sul PC di sviluppo con il build `-DOCR2_TEST` (solo i passi possibili senza collegamenti), poi consegna al proprietario. Commit `docs(M6): lifecycle procedure for the clean PC`.
- [ ] **Attesa del proprietario:** esegue la procedura sull'altro PC e riporta gli esiti; si compila `lifecycle-matrix.md`.

### Task 11: Accettazione, revisione, stato

**Files:** `docs/evidence/M6/acceptance.md`, `docs/evidence/M6/review.md`, `docs/requirements.md`, `docs/STATUS.md`, `docs/plan.md`

- [ ] `acceptance.md` con la tabella REQ-100…107 (criterio, esito `SYN-CI` / `LOCAL-RUN` / `OWNER-PC`, evidenza) e i limiti dichiarati.
- [ ] Revisione indipendente del ramo (agente senza contesto, `superpowers:requesting-code-review`); correzioni; esito in `review.md`.
- [ ] Suite completa e CI Ubuntu e Windows verdi; aggiornare `requirements.md`, `STATUS.md` e la checklist dell'issue #137; PR in bozza. Chiusura dell'issue #9 solo con il sì del proprietario.
