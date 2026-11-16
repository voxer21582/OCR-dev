# Installer NSIS: prove iniziali

Il 2026-11-16 NSIS portabile 3.13, verificato con SHA-256 da SourceForge, ha compilato due installer di prova con OCR2_TEST, senza collegamenti. Esecuzione silenziosa esclusivamente in `installer/.cache/installer-dev-test`: installazione 0.6.0 uscita 0 e active.json `active=0.6.0`; aggiornamento 0.6.1 uscito 0 e stato `active=0.6.1, previous=0.6.0`; comando Python di rollback uscito 0 e stato `active=0.6.0, previous=0.6.1`. Il Python installato ha riportato versione applicativa 0.6.0.

Sono prove parziali su dati sintetici, non una verifica completa del ciclo di vita. Mancano disinstallazione, aggiornamento interrotto, collegamenti di ripristino, firma, prova su PC pulito e revisione indipendente. Lo script attuale è un lavoro in corso e non va distribuito.
