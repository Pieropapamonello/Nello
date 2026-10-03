# Repository unificato

Il repository di riferimento è https://github.com/Pieropapamonello/Nello.
Contiene il bot dalla radice e il servizio di estrazione in `downloader/`.
Le cronologie Git di entrambi i progetti sono conservate nel merge subtree.
Le nuove modifiche vanno pubblicate su questo repository.

## Servizi Render esistenti

| Servizio | Repository | Root Directory | Dockerfile | Build context |
| --- | --- | --- | --- | --- |
| Nello | Pieropapamonello/Nello | vuota | ./Dockerfile | . |
| nello-downloader | Pieropapamonello/Nello | downloader | ./Dockerfile | . |

Entrambi mantengono il piano Free e il branch `main`. Il bot ignora per
l'autodeploy le modifiche alla sola cartella `downloader/`; il downloader
considera soltanto i file della propria Root Directory. I percorsi Docker
sono relativi alla Root Directory del servizio.

La migrazione aggiorna i servizi esistenti: non creare nuovi Blueprint per
migrare, perché creerebbero istanze aggiuntive. URL, ID dei servizi, variabili
d'ambiente, Secret Files e dati Firestore rimangono gli stessi. I vecchi
repository restano disponibili come riferimento e per un eventuale rollback.
`render.yaml` descrive la struttura anche per una nuova installazione; i
segreti vanno configurati separatamente e il token downloader deve coincidere
fra bot e downloader. Non generarne uno nuovo per il solo downloader.

## Verifiche locali

Esegui i test dalla cartella del componente, così gli import Python usano i
moduli corretti:

```powershell
cd Nello-unified
python -m unittest test_link_keys test_wa_qr test_wa_admin
node --test wa/test_admin_menu.js
cd downloader
python -m unittest test_hf_youtube test_youtube_job test_youtube_duration test_cookie_health test_remote_downloader
```

La separazione dei due processi mantiene le elaborazioni video fuori dalla
memoria usata dai bot. Groq gestisce la trascrizione configurata sul piano
Free; il backend YouTube su Hugging Face resta separato e già configurato.
