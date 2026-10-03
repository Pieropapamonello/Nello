# Nello ? bot e downloader

Repository unico: **[Pieropapamonello/Nello](https://github.com/Pieropapamonello/Nello)**.

Il bot Telegram, WhatsApp e Discord vive nella radice; il servizio di estrazione ? nella cartella `downloader/`. Entrambi si distribuiscono dallo stesso repository, su due servizi Render Free distinti.

- [Struttura e configurazione Render](MONOREPO.md)
- [Amministrazione WhatsApp e QR su Telegram](WHATSAPP_ADMIN.md)
- [Downloader, sottotitoli e API](downloader/README.md)

## Funzioni

Estrazione di contenuti dai social, descrizioni e sottotitoli italiani, trascrizione dei vocali italiani, classifiche e reazioni condivise. La gestione dei cookie avviene tramite `/cookies` nella chat privata admin Telegram e vale per tutti i frontend. `/whatsapp` permette all?admin Telegram di richiedere il QR di collegamento. Su WhatsApp, `/admin PASSWORD` apre il menu amministratore privato e `/menu` lo riapre.

## Configurazione

Usare i Dockerfile dei rispettivi componenti. Le variabili e i Secret Files rimangono su Render; non inserire nel repository token, cookie o credenziali Firebase. Il bot e il downloader devono condividere `DOWNLOADER_TOKEN`, e il bot deve puntare al downloader tramite `DOWNLOADER_URL`. Groq e il backend YouTube Hugging Face sono configurati tramite le rispettive variabili d?ambiente.

Per migrare i servizi esistenti seguire [MONOREPO.md](MONOREPO.md): mantenere URL, segreti e ID attuali. Non serve creare nuovi servizi n? aumentare il piano.
