# Firma dell’installer

Il 2026-11-16 il proprietario ha dichiarato di non disporre di un certificato di firma del codice né di un servizio di marcatura temporale. Nessun installer è stato firmato e REQ-105 rimane aperto.

Test tecnico sintetico: un firmatario finto è stato richiamato due volte dalla build NSIS (installer e disinstallatore); un firmatario finto che restituisce errore ha fatto fallire la build. Nessuna firma reale né marca temporale sono state create o verificate.
