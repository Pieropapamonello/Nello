# Amministrazione da WhatsApp

Nella chat privata del numero del bot, invia `/admin PASSWORD` usando la
password `ADMIN_PASSWORD` già configurata per Telegram. L'accesso Telegram
non autentica automaticamente un numero WhatsApp.

Dopo l'accesso compare il pulsante **Comandi admin**, con queste opzioni:

- Stato cookie: mostra lo stato del downloader condiviso.
- Aggiorna cookie: indica come aprire `/cookies` nella chat admin Telegram.
- Chat del bot: mostra le chat registrate.
- Nuova sfida: spiega come impostarla con `/sfida tema`.
- Esci da admin: revoca la sessione WhatsApp.

Usa `/menu` per riaprire il menu. Sono disponibili anche `/cookies`, `/chats`,
`/sfida tema` e `/logout`, se il client non mostra i controlli interattivi.

I permessi vengono verificati per ogni comando e selezione. Il menu non viene
inviato ai gruppi, né agli utenti non autenticati. La sessione dura 12 ore,
termina al riavvio e viene revocata quando cambia la password. Dopo cinque
password errate, il numero deve attendere 15 minuti prima di riprovare.

Il QR di ricollegamento WhatsApp viene inviato soltanto all'admin Telegram in
privato, durante una sessione admin autenticata. Su Telegram, usa `/start` e
premi **Accedi come admin**, quindi invia la password nella chat privata.
Il menu permette anche di uscire: dopo logout, scadenza o riavvio del bot
non verranno inviati altri QR finché non accedi nuovamente.
Il comando `/whatsapp` su Telegram richiede il QR corrente; le rotazioni
aggiornano lo stesso messaggio e il collegamento riuscito rimuove il QR.
