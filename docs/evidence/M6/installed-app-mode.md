# Modalità applicazione con runtime installabile

Il 2026-11-16, su una copia 0.6.1 nella cache e con LOCALAPPDATA temporaneo, la modalità applicazione è stata avviata con apertura della finestra sostituita da una funzione finta. `/app/info` riportava versione 0.6.1, Python 3.13.18 e runtime verificato; il comando Esci con token e Origin locali ha restituito 200, il processo è terminato e la porta è risultata libera. Non è una prova visiva di Edge né dei collegamenti Start.

Primo tentativo: POST respinto 403 perché la prova ometteva Origin; corretto il client. Il secondo tentativo ha letto l'indicatore temporaneo rimasto dalla prova forzatamente chiusa e ha contattato una porta non più in ascolto; rimosso il solo indicatore della cartella di prova prima del terzo tentativo, riuscito.
