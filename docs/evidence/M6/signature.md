# Firma dell’installer

Il 2026-11-16 il proprietario ha dichiarato di non disporre di un certificato di firma del codice né di un servizio di marcatura temporale. Nessun installer è stato firmato e REQ-105 rimane aperto.

Test tecnico sintetico: un firmatario finto è stato richiamato due volte dalla build NSIS (installer e disinstallatore); un firmatario finto che restituisce errore ha fatto fallire la build. Nessuna firma reale né marca temporale sono state create o verificate.

Inventario successivo del payload di prova ripulito: su 45 file `.exe`, `.dll` e `.pyd` nelle wheel, 40 risultano senza firma e 5 con firma valida e marca temporale del fornitore. Il gate esistente controlla l'impronta del proprietario solo sui 25 binari elencati del Python compilato localmente, non sui binari delle wheel. Questo non dimostra il rispetto di REQ-105 per tutti i binari. Firmare quelli non firmati modifica i file rispetto alle wheel originali; sostituire le firme valide dei fornitori modifica anche l'identità della firma. Nessuna di queste operazioni è stata effettuata e occorre definire come soddisfare il requisito preservando provenienza e licenze. Questi numeri riguardano il solo payload di prova esaminato, non una build firmata finale.
