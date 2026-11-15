# M4 Revisione Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans for this plan. Steps use checkbox syntax.

**Goal:** Completare tracciabilità, revisione accessibile e verifiche M4.

**Architecture:** Estendere il registro esistente e i percorsi locali, preservando eventi e hash storici; proiettare la storia negli export. Verificare UI con fixture sintetiche e browser.

**Tech Stack:** Python 3.13, pytest, JavaScript, Windows, browser locale.

**Spec:** `docs/superpowers/specs/2026-11-15-m4-revisione-design.md`

## Global Constraints

Solo fixture sintetiche; niente nuove dipendenze o cambi Windows; R7/R8 soggetti a DEC-001; stop/no-retry; evidenze in `docs/evidence/M4/`; nessun merge senza approvazione.

## Review Focus

- Eventi storici: conservare attore, timestamp e catena hash.
- Nome utente Windows indisponibile: fallire senza attribuzioni inventate.
- CSV: neutralizzare dati interpretabili come formule.
- Selezione area: mantenere coordinate ed evidenza sul documento corretto.
- Accessibilità: focus visibile e percorso completo anche senza mouse.

## Task 1 — Inventario

- [ ] Esaminare creatori degli eventi e relativi test, export e percorso UI, oltre alle PR M4 elencate nel triage.
- [ ] Registrare le lacune e le decisioni necessarie nelle evidenze; evitare modifiche ai componenti già conformi.

## Task 2 — Identità e cronologia

- [ ] Aggiungere test sintetici fallenti alle suite di revisione per utente server, UTC, errore identità e conservazione eventi precedenti.
- [ ] Sostituire l'attore segnaposto nell'interfaccia usando una singola funzione di identità locale; usare timestamp UTC; rieseguire le suite pertinenti e salvare output RED/GREEN.
- [ ] Aggiungere test di export JSON/CSV per tutti gli eventi, inclusi record senza eventi e valori sensibili alle formule; estendere la proiezione CSV senza alterare JSON o eventi storici. Verificare compatibilità e salvare output.
- [ ] Aggiornare stato e fare commit del passo verificato.

## Task 3 — Revisione accessibile

- [ ] Inventariare test e comportamento esistente di evidenze, alternative, area con mouse e tastiera; scrivere test fallenti per le lacune effettive.
- [ ] Correggere le lacune con modifiche minime, rieseguire test e registrare evidenze; aggiornare selettori CI se si introducono moduli.
- [ ] Aggiornare stato e fare commit del passo verificato.

## Task 4 — Accettazione

- [ ] Percorrere il flusso su dati sintetici nel browser, registrando passaggi e screenshot; compilare checklist tastiera, contrasto e Assistente vocale di Windows.
- [ ] Eseguire test pertinenti e revisione indipendente, correggere difetti e rieseguire verifiche.
- [ ] Registrare criteri ed evidenze in `docs/evidence/M4/acceptance.md`; aggiornare stato solo secondo risultati dimostrati.
