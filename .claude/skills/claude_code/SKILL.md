---
name: report-search-intent
description: Dato un brand e un periodo (se non forniti, chiedili all'utente), inizializza la creazione del report SEO di search intent. Non accettare in alcun modo file CSV caricati direttamente in chat (blocca l'esecuzione e di' di caricarli su Google Drive). Esegui il setup di Google Drive, scarica i file CSV dalla cartella Drive creata, pulisci e clusterizza i dati, popola il Google Sheet e genera la presentazione Google Slides.
---

# Report Search Intent (Semrush → Cluster → Google Sheet → Google Slides)

> **Questo file è la fonte di verità del flusso, per entrambi gli ambienti.** Oltre a
> Claude Code, lo legge da GitHub anche il loader `claude-skill/SKILL.md` (variante
> claude.ai), che lo esegue applicando una piccola tabella di equivalenze di percorsi.
> Quindi: modifica il flusso **solo qui** — non serve (e non va fatto) duplicare le
> modifiche nella skill claude.ai. Se aggiungi o rinomini uno script, aggiorna
> `claude-skill/manifest.json`, che è la lista dei file che quella variante scarica.

Orchestri un flusso end-to-end che parte da un brand + un periodo (se l'utente non li fornisce nel messaggio iniziale, **devi chiederli immediatamente prima di fare qualunque altra cosa**) e produce un Google Sheet e una Google Presentation pronti da condividere. Parli italiano di default.
Sei operativo: appena hai il nome del brand e il periodo, inizi subito il setup della cartella Drive (Step 1) — **non aspettare** dominio, mercato o ambito Brand/Not Brand per farlo, quelle domande arrivano dopo, mentre l'utente carica già i CSV nella cartella `semrush_files/` appena creata. Non accettare file CSV caricati in chat.

## Prerequisiti (verifica SEMPRE come Step 0)

1. Il tool MCP Semrush deve essere collegato (lo è già, vedi istruzioni MCP di sessione) —
   serve solo per lo Step 2b (volumi brand secco, poche chiamate leggere): l'estrazione
   massiva delle posizioni organiche (Step 2a) non passa più da qui, vedi sotto.
2. Il tool MCP Google Drive (`mcp__claude_ai_Google_Drive__*`) deve essere collegato: è
   l'unico canale verso Drive/Sheets/Slides in questo flusso, non esiste più
   un'autenticazione OAuth Google gestita da questo repo (niente `scripts/google_clients.py`,
   niente `credentials/token.json`, niente refresh token da rinnovare). `.env` in questo
   repo deve avere solo `GOOGLE_DRIVE_ROOT_FOLDER_ID` (e facoltativamente
   `GOOGLE_DRIVE_BRAND_ROOT_FOLDER_ID`), `GOOGLE_SHEET_TEMPLATE_ID`,
   `GOOGLE_SLIDE_TEMPLATE_ID` — riferimenti statici a ID di file/cartella, non credenziali.
   Se il tool MCP Drive non è disponibile in questa sessione, **fermati** e dillo
   all'utente: non esiste un fallback verso token/curl per Drive/Sheets/Slides in questo
   flusso.
3. `claude-clustering-agent` e `app-script-semrush-keyword-cleaner` (Step 4 e Step 3) non
   vanno clonati a mano: esegui SEMPRE, come parte di questo Step 0,
   ```bash
   python scripts/fetch_dependencies.py
   ```
   Clona (la prima volta) o aggiorna (`git fetch` + `reset --hard` sul branch configurato,
   default `main`) i due repo GitHub in `.cache/` dentro questo progetto, e stampa un JSON
   con `path` e `commit` risolti per ciascuno — annota questi due path (li userai al posto
   di `<CLUSTERING_AGENT_PATH>` / `<KEYWORD_CLEANER_PATH>` negli step 3 e 4) e i due commit
   (li riporterai nel riepilogo di Step 7, utile per sapere quale versione della logica di
   pulizia/clustering ha girato in questo run). Se `CLUSTERING_AGENT_PATH` /
   `KEYWORD_CLEANER_PATH` sono valorizzate nel `.env`, lo script le usa cosi' come sono
   (override locale per testare modifiche non ancora pushate) senza toccare git. Se il
   comando fallisce per un repo privato senza credenziali git configurate su questa
   macchina, configura le credenziali git di questa macchina (credential manager / `gh auth
   login`) — non serve `GITHUB_TOKEN` nel `.env` per questo scenario (vedi variante
   claude.ai in `claude-skill/bootstrap.md`, che usa `git clone` con token nell'URL, o il
   connettore GitHub come fallback, per lo stesso scopo).
4. `GOOGLE_SLIDE_EXAMPLE_ID` in `.env` (facoltativo ma consigliato) è una presentazione di
   riferimento già compilata (tono/stile editoriale reale) — la leggi in sola lettura in
   Step 6 con `mcp__claude_ai_Google_Drive__read_file_content`, non va mai duplicata né
   modificata.

## Cosa chiedere SEMPRE (ogni run, non solo se ambiguo)

- **Ambito Brand/Not Brand**: chiedi sempre, con `AskUserQuestion`, se l'utente esporterà da
  Semrush *"Solo keyword Brand"* (contengono il nome/varianti del brand), *"Solo Not Brand"*
  (generiche, nessuna menzione brand) o *"Entrambe"* (default consigliato). La risposta
  determina quanti CSV attendere in Step 2a: 1 CSV (solo Brand o solo Not Brand) oppure 2
  CSV (Entrambe, uno per filtro) **per ogni mese** del periodo richiesto — non chiederlo una
  volta sola e riusare per sempre, le esigenze cambiano da report a report.

## Cosa chiarire con l'utente (solo se non deducibile o mancante)

- **Brand**: Se non specificato nel messaggio iniziale, **chiedilo immediatamente**.
- **Periodo**: Se non specificato nel messaggio iniziale, **chiedilo immediatamente**. Normalizzalo a uno o più mesi (`YYYYMM`). Se l'utente dice "questo trimestre" o un intervallo, espandilo nei mesi coperti.
- **Dominio del brand**: Chiedi o conferma il dominio associato al brand (es. `yamamay.com`). Non blocca lo Step 1 (`run_meta.py init` accetta `--domain` vuoto): chiedilo/confermalo **dopo** aver creato la cartella del run, e appena noto aggiornalo con `python scripts/run_meta.py set --run-meta runs/<slug>/run_meta.json --key domain --value "<dominio>"` — serve prima dello Step 2b/3.
- **Mercato/database Semrush**: se il TLD del dominio è inequivoco (`.it`→`it`, `.fr`→`fr`, `.de`→`de`, `.es`→`es`, `.co.uk`→`uk`) usalo. Se il dominio è generico (`.com`) e non è ovvio dal contesto della conversazione, **chiedi**: *"Su quale mercato/database Semrush devo lavorare (es. it, us, uk)?"*
- **Varianti del brand secco**: parti dal nome brand ripulito (lowercase, es. `yamamay`). Se conosci typo/varianti ricorrenti chiedile all'utente, altrimenti procedi con la sola variante principale (potrai raffinare dopo aver visto `output/rules_suggestions.json` del clustering).
- **Settore** (per il clustering, Step 4): se non è deducibile con certezza dal brand/URL (es. un e-commerce moda è ovvio, un dominio generico o multi-categoria no), **chiedi**: *"Per quale settore sono queste keyword?"* — stessa domanda del `CLAUDE.md` di `claude-clustering-agent` quando il settore non è chiaro. Usi il valore raccolto qui in `--sector` allo Step 4, non un valore di comodo.

## Step 1 — Setup cartelle Drive + copie dei template

Nessuno script Python parla più direttamente con Drive (nessun client autenticato lato
script): la creazione di cartelle/copie template è fatta da **te**, in conversazione, con le
chiamate MCP Google Drive, poi registrata in `run_meta.json`.

1. Crea lo scheletro locale del run:
   ```bash
   python scripts/run_meta.py init --brand "Yamamay" --period "Luglio 2026" --domain "yamamay.com"
   ```
   Annota `run_slug` e `run_dir` dall'output: sono la working dir di questo run.
2. Trova/crea la cartella brand (`search_files` con query
   `title = '<Brand>' and mimeType = 'application/vnd.google-apps.folder' and parentId = '<root_folder_id>'`,
   dove `root_folder_id` è `GOOGLE_DRIVE_BRAND_ROOT_FOLDER_ID` se impostata, altrimenti
   `GOOGLE_DRIVE_ROOT_FOLDER_ID`; se non trovata, `create_file` con
   `mimeType="application/vnd.google-apps.folder"` e quel `parentId`). Scrivi l'id ottenuto:
   ```bash
   python scripts/run_meta.py set --run-meta runs/<slug>/run_meta.json --key brand_folder_id --value "<id>"
   ```
3. Crea la cartella del run dentro la cartella brand (nome tipo `"<data> - <periodo>"`, stesso
   meccanismo `create_file` mimeType folder), poi al suo interno la sottocartella
   `semrush_files/` (dove l'utente caricherà i CSV allo Step 2a). Registra entrambi gli ID
   (`run_folder_id`, `semrush_folder_id`) con `run_meta.py set`, e componi
   `semrush_folder_url` come `https://drive.google.com/drive/folders/<semrush_folder_id>`
   (scrivilo anch'esso nel meta con `set`, così i passi successivi non devono ricostruirlo).
Non c'è più nulla da duplicare qui: i template Sheet/Slide non vengono copiati in anticipo,
perché il report finale sarà un file xlsx/pptx generato da zero (Step 5/6) e caricato
direttamente nella cartella del run — è quell'upload a creare `sheet_id`/`slide_id`
(`sheet_url`/`slide_url`), non una copia fatta qui. I template restano solo un riferimento di
**struttura/stile** da ispezionare (Step 6a) prima di generare le slide.

Esegui questo step **subito dopo** aver raccolto brand e periodo, prima ancora di chiedere
dominio/mercato/ambito — così puoi già indicare all'utente il link della cartella dove
caricare i CSV.

## Step 2 — Estrazione dati da Semrush

**2a. Posizioni organiche complete del brand** (input per pulizia + clustering): **non più
via MCP**. Chiamare `domain_organic` per l'intero storico costava troppe unità API: ogni
`display_date` non corrente attiva il tariffario Semrush "dati storici", ~5 volte quello
standard (circa 50 unità/riga invece di 10) — su domini con decine di migliaia di keyword
questo bruciava centinaia di migliaia di unità API in una manciata di chiamate. Ora è
l'utente a esportare i CSV direttamente dall'interfaccia web di Semrush (Organic Research →
`<dominio>` → tab Positions, filtrando su mese e, se richiesto, su Brand/Not Brand) e a
caricarli in questa chat.

Numero di CSV attesi, in base alla risposta alla domanda "Ambito Brand/Not Brand" qui sopra,
**per ciascun mese** del periodo richiesto:
- **Solo Brand** o **Solo Not Brand**: 1 CSV.
- **Entrambe**: 2 CSV (uno per filtro).

Prima di aspettare i file, indica chiaramente all'utente cosa esportare per ciascun CSV
atteso (mese, mercato/database, ed eventuale filtro: Brand = keyword che contengono
`<variante brand>`, Not Brand = keyword che non la contengono). Se il periodo copre più
mesi, l'utente dovrà ripetere l'export per ogni mese (stesso numero di CSV per mese): la
deduplica/consolidamento in Step 3 (a carico di `app-script-semrush-keyword-cleaner`)
gestisce le sovrapposizioni fra mesi, non serve concatenare nulla a mano.

Quando l'utente allega un CSV in chat (oppure tenta di caricarlo direttamente):
1. **BLOCCO DI SICUREZZA**: Se l'utente allega un file CSV direttamente alla chat, **fermati immediatamente** e non processarlo. Spiega all'utente che il caricamento diretto dei file in chat è disabilitato poiché satura il contesto di Claude (token limit) e rallenta drasticamente la sessione. Invitalo ad utilizzare Google Drive seguendo la procedura sotto.

**Procedura di caricamento corretta (obbligatoria)**:
1. Spiega all'utente quali file esportare da Semrush e chiedigli di caricarli nella sottocartella `semrush_files/` dentro la cartella del run creata allo Step 1 (link diretto: `semrush_folder_url` da `run_meta.json`). Non serve rinominare i file: l'export standard di Semrush produce già nomi parlanti (dominio, database, filtro, data), sufficienti per il QA manuale allo Step 3.
2. Una volta che l'utente conferma di aver caricato i file su Drive, scaricali tu stesso via MCP (nessuno script Python intermedio: non c'è più un client Drive autenticato lato script):
   - `mcp__claude_ai_Google_Drive__search_files` con query `parentId = '<semrush_folder_id>' and mimeType = 'text/csv'` per elencare i CSV presenti;
   - per ciascun risultato, `mcp__claude_ai_Google_Drive__download_file_content(fileId=...)` e scrivi il contenuto (decodificato da base64) in `runs/<slug>/raw/<nome file>.csv` con Write/Bash locale.
3. Verifica che i file scaricati in `runs/<slug>/raw/` rispettino il formato atteso. Se non ci sono file CSV validi o se mancano le colonne necessarie, segnalalo all'utente.

L'intera cartella `runs/<slug>/raw/` diventa poi `--input-dir` per lo Step 3. (Nota: non è più necessario lo step di upload dei file grezzi a posteriori, in quanto i file risiedono già su Drive).

**2b. Volumi del brand secco, ultimi 3 anni, per il periodo richiesto:**
Il tab "brand-secco" del template (verificato dal vivo) è **una riga sola**: un numero di
volume per l'anno corrente e uno per ciascuno dei 2 anni precedenti, tutti riferiti allo
stesso periodo (es. maggio 2026 vs maggio 2025 vs maggio 2024) — non una serie mensile.
Per ciascuno dei 3 anni, richiama:
```
execute_report(report="phrase_this", params={
  phrase: "<variante brand>", database: "<mercato>",
  display_date: "<YYYY><MM>15"     # stesso mese/periodo, anno diverso
})
```
Se il periodo copre più mesi, ripeti per ogni mese di quell'anno e somma; se ci sono più
varianti brand, usa `phrase_these` con `phrase="var1;var2"` e somma i volumi restituiti.
Ottieni così **esattamente 3 numeri** (uno per anno). Scrivi
`runs/<slug>/volumes.csv` con colonne `Anno,Search Volume` e **esattamente 3 righe**
(`build_sheet.py` lo richiede rigidamente) — è l'input del Tab "brand-secco" (Step 5), che
scriverà anche le formule Sheets per le variazioni % YoY (non calcolarle tu).

## Step 3 — Pulizia (app-script-semrush-keyword-cleaner)

Richiami direttamente `scripts/semrush_cleaner.py` **di quel repo** (path risolto da
`fetch_dependencies.py` in Step 0, `keyword_cleaner.path` — stesso script dietro il comando
`/pulisci-keyword` di quel progetto), sull'intera cartella
`runs/<slug>/raw/` prodotta in 2a — niente concatenazione manuale dei mesi, ci pensa lui
(consolidamento + dedup per keyword/data/URL):
```bash
python "<KEYWORD_CLEANER_PATH>/scripts/semrush_cleaner.py" \
  --mode clean \
  --input-dir runs/<slug>/raw \
  --output runs/<slug>/clean/report.xlsx \
  --raggruppamento consolidato \
  --tipo-query tutte \
  --brand-varianti "<variante1,variante2>"
```
Nota: passa sempre `--tipo-query tutte` qui — l'eventuale filtro Brand/Not Brand scelto
dall'utente (vedi "Cosa chiedere SEMPRE") è già stato applicato a monte via
`display_filter` nello Step 2a; `--brand-varianti` serve solo a valorizzare la colonna
`Brand/Not Brand` nell'output, non a filtrare di nuovo. Segnala all'utente eventuali file
`⏭ Ignorato` o colonne mancanti loggati dallo script (stesso comportamento del comando
`/pulisci-keyword`).

`runs/<slug>/clean/report.xlsx` è un output leggibile (un foglio "Tutti i Dati" globale +
un foglio per brand/mercato + LOG) utile per QA manuale, ma non ha ancora le colonne
`Brand`/`Country` richieste dal clustering (Step 4) e da `build_sheet.py` (Step 5).
Convertilo con:
```bash
python scripts/xlsx_to_clean_csv.py \
  --xlsx runs/<slug>/clean/report.xlsx \
  --output runs/<slug>/clean/all_clean.csv \
  --brand "Yamamay"
```
Legge il foglio "Tutti i Dati", aggiunge `Brand` (valore fisso, dal nome brand) e
`Country` (bucket lingua per `<mercato>`, usato dalle regole di claude-clustering-agent) e
scrive `runs/<slug>/clean/all_clean.csv` — è l'input del clustering.

## Step 4 — Clustering (claude-clustering-agent)

Usa il path risolto da `fetch_dependencies.py` in Step 0 (`clustering_agent.path`, di
default `.cache/claude-clustering-agent/`): richiami direttamente `scripts/cluster.py`
**di quel repo**, passando come `--input/--output/--workdir` i percorsi di **questo** run.

**Il ruleset non è più committato in quel repo** (`rules/` è in `.gitignore` lì, quindi
`fetch_dependencies.py` non lo porta mai in `.cache/`): vive in Google Sheet condivisi su
Drive, cartella **"Clustering rules"** (id `1sBd0k1QSc23E_5ii6Nc1DtZ0oD1GjusS`). Prima di
`--mode prepare` chiedi sempre all'utente quale **vertical** usare — elenca le sottocartelle
reali sotto quella cartella Drive (`search_files`, escludendo quelle con prefisso `_`), non
indovinarlo dal nome del brand — poi sincronizza le regole di quel vertical/lingua nel
workdir di **questo** run seguendo alla lettera la sezione "Sincronizza da Google Drive" del
`CLAUDE.md` di quel repo (letto in Step 0): scarica ogni Sheet come `.csv` sotto
`runs/<slug>/clustering/workdir/sheets_raw/...`, poi materializza:
```bash
python "<CLUSTERING_AGENT_PATH>/scripts/cluster.py" --mode sync-rules \
  --workdir runs/<slug>/clustering/workdir
```
Le regole materializzate finiscono sotto `runs/<slug>/clustering/workdir/rules/` (risolto
relativamente al `--workdir` passato, non più alla posizione dello script): risincronizza
solo se cambi vertical/lingua o se lo Sheet è stato aggiornato dopo l'ultima sync di questa
sessione.

Poi segui gli step descritti nel `CLAUDE.md` di quel repo (prepare → analyze → eventuale
add-rules → process-batches → merge) — nota: se aggiunge nuove regole (`--mode add-rules`),
scrive solo nella copia effimera `runs/<slug>/clustering/workdir/rules/` (utile per
riclassificare subito in questo run) e produce un blocco pronto da incollare a mano nello
Sheet Drive giusto (sezione "Proponi regole/brand" del `CLAUDE.md` di quel repo) — non c'è
più alcuna scrittura/commit automatica su GitHub per le regole:

```bash
python "<CLUSTERING_AGENT_PATH>/scripts/cluster.py" --mode prepare \
  --input runs/<slug>/clean/all_clean.csv --sector "<settore>" \
  --workdir runs/<slug>/clustering/workdir

python "<CLUSTERING_AGENT_PATH>/scripts/cluster.py" --mode analyze \
  --workdir runs/<slug>/clustering/workdir
# presenta i pattern non coperti (count >= 3) e proponi cluster/sotto cluster all'utente

python "<CLUSTERING_AGENT_PATH>/scripts/cluster.py" --mode add-rules \
  --workdir runs/<slug>/clustering/workdir
# (solo se l'utente approva nuove regole — riclassifica in locale, non tocca il repo condiviso salvo richiesta esplicita)

python "<CLUSTERING_AGENT_PATH>/scripts/cluster.py" --mode process-batches \
  --workdir runs/<slug>/clustering/workdir
# per ogni batch: leggi il prompt in workdir/prompts/, clusterizza TU le keyword secondo
# la tabella di regole del CLAUDE.md di claude-clustering-agent, scrivi il JSON in
# workdir/results/

python "<CLUSTERING_AGENT_PATH>/scripts/cluster.py" --mode merge \
  --output runs/<slug>/clustering/clustered.csv --workdir runs/<slug>/clustering/workdir
```

Risultato: `runs/<slug>/clustering/clustered.csv` con colonne `Cluster` e `Sotto Cluster`
aggiunte. Se lo script segnala nuovi brand competitor (`brands_suggestions.json`),
presentali all'utente come da CLAUDE.md di quel repo — non serve fare push automatico.

## Step 4bis — Selezione cluster (e split per Genere) per il report finale

Prima di lanciare `build_sheet.py`, calcola da `clustered.csv` un riepilogo per Cluster
(volume totale, numero keyword) ordinato per volume decrescente e presentalo all'utente.
Chiedigli — con `AskUserQuestion` su Claude Code, direttamente in chat su claude.ai —
**quali Cluster includere nel report finale**: solo quelli scelti qui compariranno nel
grafico a torta aggregato del tab "cluster-overview" e (salvo ulteriore restrizione
editoriale allo Step 6a) nelle slide di dettaglio. Il tab "clusters" del Sheet (dato
grezzo) resta comunque **completo**, con tutte le keyword di tutti i Cluster trovati:
questa selezione riguarda solo il grafico aggregato, i tab-per-cluster e le slide, non il
dato grezzo — è il meccanismo con cui l'utente decide quanti cluster nel report finale, al
posto di un limite arbitrario di numero di slide/fette.

Per ciascun Cluster scelto, se la colonna `Genere` di `clustered.csv` ha più di un valore
non banale per quel Cluster (es. `Donna`/`Uomo`/`Kids` oltre alle righe con Genere vuoto),
chiedi anche se l'utente vuole **suddividerlo per Genere** invece di tenerlo come un unico
tab/fetta — e se sì, quali valori tenere (può accorpare, es. `Kids` dentro "Generico", o
escluderne uno del tutto). Esempio: "Abbigliamento" con Genere ∈ {Donna, Uomo, Kids,
(vuoto)}, se l'utente conferma lo split tenendo Donna/Uomo/Generico, diventa 3 entry nel
piano invece di 1 ("Abbigliamento Donna", "Abbigliamento Uomo", "Abbigliamento Generico").

Scrivi la scelta in `runs/<slug>/cluster_plan.json`, lista di `{"label", "cluster",
"genere"}`:
- `label`: nome del tab/fetta nel report finale (es. `"Abbigliamento Donna"`).
- `cluster`: valore esatto della colonna `Cluster` da cui pescare le righe.
- `genere`: `null` se non va suddiviso (tutte le righe di quel Cluster in un tab unico),
  altrimenti la lista dei valori esatti di `Genere` da tenere per quella label (usa `""`
  per le righe con Genere vuoto/non specificato).

```json
[
  {"label": "Abbigliamento Donna", "cluster": "Abbigliamento", "genere": ["Donna"]},
  {"label": "Abbigliamento Uomo", "cluster": "Abbigliamento", "genere": ["Uomo"]},
  {"label": "Abbigliamento Generico", "cluster": "Abbigliamento", "genere": ["", "Kids"]},
  {"label": "Calzature", "cluster": "Calzature", "genere": null},
  {"label": "Accessori", "cluster": "Accessori", "genere": null}
]
```
Un Cluster trovato da `clustered.csv` ma assente da questo piano semplicemente non genera
nessun tab né fetta. `build_sheet.py` segnala (senza bloccarsi) se, per un Cluster
splittato per Genere, alcune keyword restano fuori da tutte le label indicate (un valore
di Genere presente nei dati ma dimenticato nel piano) — verifica se è voluto.

## Step 5 — Generare e caricare il Google Sheet

Non c'è più un Google Sheet remoto da riempire in-place via API: generi un xlsx completo
offline, partendo dal template scaricato da Drive, poi lo carichi tu stesso (Claude) su Drive
via MCP, che lo converte automaticamente in Google Sheet.

1. Scarica il template Sheet (una volta per sessione, cache in `.cache/template/`, non per
   ogni run — il template cambia raramente):
   ```
   mcp__claude_ai_Google_Drive__download_file_content(
     fileId=<GOOGLE_SHEET_TEMPLATE_ID>,
     exportMimeType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
   ```
   Scrivi il base64 risultante in `.cache/template/sheet_template.xlsx`.
2. Genera l'xlsx del report:
   ```bash
   python scripts/build_sheet_xlsx.py \
     --template-xlsx .cache/template/sheet_template.xlsx \
     --volumes-csv runs/<slug>/volumes.csv \
     --clustered-csv runs/<slug>/clustering/clustered.csv \
     --xlsx-out runs/<slug>/output/report.xlsx \
     --charts-meta-out runs/<slug>/charts_meta.json \
     --cluster-plan runs/<slug>/cluster_plan.json
   ```
   Scrive, partendo dal template (preservando ogni suo tab non gestito da questo script): il
   tab "brand-secco" (3 colonne Volume anno/anno-1/anno-2 + riga di formule Excel YoY), il tab
   "clusters" (le 8 colonne fisse del template — `--clustered-csv` deve averle tutte,
   altrimenti lo script si ferma con errore esplicito — dato grezzo **completo**, non
   filtrato dal piano di Step 4bis; le colonne attributo dinamiche di claude-clustering-agent
   seguono senza un elenco fisso: vedi `attribute_columns_after_sotto_cluster` in
   `build_sheet_xlsx.py`), un tab "cluster-overview" con un'**aggregazione statica** (pandas
   groupby, non più una PivotTable nativa di Sheets) sulla selezione di `cluster_plan.json` +
   grafico a torta **embedded** (openpyxl, non più un grafico Sheets "linked": non si
   aggiorna da solo se i dati cambiano dopo il caricamento) con la ripartizione del volume
   tra i cluster/split scelti, e un tab per ciascuna entry del piano con la stessa
   aggregazione+torta filtrata su quella label. Rimuove automaticamente eventuali tab di
   esempio residui del template (`LEGACY_EXAMPLE_TABS`).

   Per ciascuna colonna attributo dinamica non interamente vuota, scrive un tab "Extra
   <Colonna>" con la stessa aggregazione+torta ma **senza alcun filtro** (sorgente sempre
   l'intero tab "clusters") — stessa logica di disaccoppiamento di prima.

   Scrive `runs/<slug>/charts_meta.json` con `{overview: {sheetTitle, totalVolume,
   subClusters}, clusters: {label: {sheetTitle, totalVolume, subClusters}}, breakdowns:
   {colonna: {sheetTitle, totalVolume, values}}}` (schema ridotto rispetto a prima: niente
   più `sheetId`/`chartId` Google, non esistono a questo punto), che userai nello Step 6 e
   nel riepilogo finale.
3. Carica il file generato su Drive, nella cartella del run:
   ```
   mcp__claude_ai_Google_Drive__create_file(
     title="Search Intent - <Brand> - <Periodo>",
     parentId=<run_folder_id>,
     contentMimeType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
     base64Content=<contenuto di runs/<slug>/output/report.xlsx>)
   ```
   La conversione automatica in Google Sheet è il comportamento di default (non passare
   `disableConversionToGoogleType`). Registra l'id risultante:
   ```bash
   python scripts/run_meta.py set --run-meta runs/<slug>/run_meta.json --key sheet_id --value "<id>"
   python scripts/run_meta.py set --run-meta runs/<slug>/run_meta.json --key sheet_url --value "https://docs.google.com/spreadsheets/d/<id>/edit"
   ```

**Limite noto**: niente più PivotTable interattive né grafici auto-aggiornanti. Se i dati
cambiano dopo il caricamento, l'unico modo per riflettere la modifica è rigenerare l'xlsx e
ricaricarlo (creerà un nuovo file: non esiste un'operazione MCP di aggiornamento in-place —
ogni run/ricarica produce un nuovo `sheet_id`).

## Step 6 — Generare la presentazione

Non c'è più una presentazione remota da riempire in due fasi (duplica slide vuote → scrivi
testo con `replaceAllText` post-caricamento): l'MCP Drive non offre un editing incrementale
su un file già esistente. Il pptx va quindi generato **completo, in un solo passaggio
offline**, dopo che tutto il contenuto editoriale è stato deciso — lo Step si articola in
tre fasi sequenziali (6a scelta formato → 6b scrittura testo → 6c generazione meccanica),
più 6d per le immagini.

**Il template Slides contiene testi placeholder marcati col prefisso `####`** (sia nel
corpo delle slide sia nelle note relatore, per le istruzioni sulle immagini) — non è più
un report reale con dati di esempio. Scarica ed ispeziona SEMPRE il template fresco prima
di ogni run (una volta per sessione, cache in `.cache/template/`, non per ogni run):
```
mcp__claude_ai_Google_Drive__download_file_content(
  fileId=<GOOGLE_SLIDE_TEMPLATE_ID>,
  exportMimeType="application/vnd.openxmlformats-officedocument.presentationml.presentation")
```
Scrivi il base64 in `.cache/template/slide_template.pptx`, poi:
```bash
python scripts/inspect_template_pptx.py --pptx .cache/template/slide_template.pptx
```
Non fidarti di indici/placeholder visti in run precedenti: il template può essere stato
modificato nel frattempo. Se configurato, leggi anche `GOOGLE_SLIDE_EXAMPLE_ID` in sola
lettura con `mcp__claude_ai_Google_Drive__read_file_content` — un report reale già scritto,
riferimento di tono/stile, mai duplicato né modificato.

**6a. Scegli il formato per ogni cluster (tu, giudizio editoriale — non uno script)**: il
template ha **più slide-formato alternative** per il dettaglio-cluster (differiscono per
posizione del grafico e numero di esempi keyword mostrati), individuabili dall'output di
`inspect_template_pptx.py` (testo dei placeholder, note relatore). Per ciascuna label in
`charts_meta.json` (già la selezione scelta dall'utente allo Step 4bis) scegli il formato
che valorizza meglio i suoi dati e alterna liberamente per dare varietà visiva al deck — non
usare sempre lo stesso formato per tutte le slide. Scrivi la scelta in
`runs/<slug>/stencil_map.json`, con l'**indice di slide** (0-based, come stampato da
`inspect_template_pptx.py`) al posto del vecchio objectId:
```json
{
  "Calzature": 7,
  "Abbigliamento Donna": 9
}
```
Di norma una voce per ciascuna label di `charts_meta.json` (una slide di dettaglio per
ogni cluster incluso nel report, stessa selezione dell'overview). Le chiavi di
`stencil_map.json` selezionano anche *quali* label ottengono una slide: puoi comunque
scriverne un sottoinsieme più ristretto (`build_slides_pptx.py` tollera un `stencil_map`
parziale — l'errore esplicito scatta solo se citi una label assente da
`charts_meta.json`, non il contrario).

**Colonne extra: chiedi, non valutare tu.** Elenca all'utente (con `AskUserQuestion`,
multiSelect) le colonne di `charts_meta.json["breakdowns"]` non risultate vuote e chiedi
quali vuole in slide di dettaglio — **non leggere/valutare tu la distribuzione di ciascuna
per deciderlo**. Per le sole colonne scelte, scegli uno dei formati "dettaglio cluster" e
alternalo con quelli già usati per i cluster. Scrivi la scelta in
`runs/<slug>/breakdown_stencil_map.json`, stesso schema (indice di slide):
```json
{"Genere": 8, "Materiale/Colore": 10}
```

**6b. Scrivi TUTTO il contenuto editoriale prima di generare il pptx (tu, non uno
script)**: a differenza del flusso precedente, qui non vedrai gli slide reali finché non
lo generi — scrivi il testo guardando solo i dati (`charts_meta.json`, `volumes.csv`,
`clustered.csv`) e i placeholder-tipo letti da `inspect_template_pptx.py` (sempre uguali
per ogni istanza dello stesso formato-stencil). Per ciascuna label/colonna che avrà una
slide (più le slide fisse: cover, brand-secco, cluster-overview, main insights, warnings),
scrivi in `runs/<slug>/slide_content.json`:
```json
{
  "clusters": {
    "Calzature": {
      "replacements": {
        "#### NOME CLUSTER": "Calzature",
        "#### Esempi di combinazione:\n...": "Esempi di combinazione:\nkw1\nkw2\nkw3\nkw4",
        "#### paragrafo (3 frasi) di insight sul cluster ...": "Paragrafo di insight scritto da te sui dati reali."
      }
    }
  },
  "breakdowns": {
    "Genere": {"replacements": {"...": "..."}}
  },
  "fixed": {
    "brand_secco": {
      "slide_index": 2,
      "replacements": {"...": "..."},
      "delta_colors": {"+12,3%": "green", "-4,1%": "red"}
    },
    "cluster_overview": {"replacements": {"...": "..."}},
    "cover": {"slide_index": 0, "replacements": {"...": "..."}},
    "main_insights": {"slide_index": 3, "replacements": {"...": "..."}},
    "warnings": {"slide_index": 4, "replacements": {"...": "..."}}
  }
}
```
Ogni voce di `replacements` è `{"<testo placeholder esatto, incluso ####>": "<testo
reale>"}`, letto 1:1 da `inspect_template_pptx.py` (i placeholder sono run di testo unici
all'interno della slide-stencil, verificalo). Scrivi il paragrafo insight guardando i
numeri reali (`totalVolume`, `subClusters` in `charts_meta.json`, quota % sul totale
keyword del brand). Per il tono — giornalistico-analitico, frasi brevi, chiusura con un
suggerimento SEO — prendi ispirazione da `GOOGLE_SLIDE_EXAMPLE_ID` (sola lettura). Per le
slide di breakdown, usa `charts_meta.json["breakdowns"][colonna]` (`totalVolume`,
`values`) — titolo tipo "Distribuzione per <Colonna>", insight sul valore dominante e la
sua quota %, eventuali esempi di keyword rappresentative letti da `clustered.csv`. Ricorda:
questi grafici sono calcolati su **tutte** le keyword clusterizzate, non sulla selezione di
Step 4bis — se lo scarto rispetto ai numeri delle slide-cluster è rilevante, menzionalo nel
testo.

**Colore del delta YoY (slide "brand secco")**: nel flusso precedente il colore esatto
(verde/rosso) si leggeva da un rich-text nelle note relatore del template Slides — qui
decidilo tu in base al segno del delta (positivo → verde, negativo → rosso) e scrivilo in
`delta_colors` come `{"<testo esatto del delta, es. \"+12,3%\">": "green"|"red"}`:
`build_slides_pptx.py` applica quel colore al run di testo dopo la sostituzione.

**6c. Genera il pptx** (`build_slides_pptx.py` — duplicazione slide + testo + grafici,
meccanico, un solo passaggio offline):
```bash
python scripts/build_slides_pptx.py \
  --template-pptx .cache/template/slide_template.pptx \
  --charts-meta runs/<slug>/charts_meta.json \
  --stencil-map runs/<slug>/stencil_map.json \
  --breakdown-stencil-map runs/<slug>/breakdown_stencil_map.json \
  --slide-content runs/<slug>/slide_content.json \
  --new-brand-text "<Nome Brand>" \
  --cluster-overview-slide-index <indice slide 'EMERGONO ALCUNI CLUSTER DI RICERCA RILEVANTI'> \
  --pptx-out runs/<slug>/output/deck.pptx \
  --slides-meta-out runs/<slug>/slides_meta.json
```
`--breakdown-stencil-map` è facoltativo: omettilo se allo Step 6a non hai scelto nessuna
colonna extra da mettere in slide. Lo script, in un solo passaggio: applica testo/colore
alle slide fisse indicate in `slide_content.json["fixed"]`; per la slide "cluster overview"
(se `--cluster-overview-slide-index` è dato) applica testo/colore e vi inserisce il grafico
aggregato `charts_meta.json["overview"]`; duplica, per ogni cluster/colonna extra, la
slide-stencil assegnata, applica i placeholder/colore di `slide_content.json`, e sostituisce
l'immagine più grande con un grafico nativo pptx (torta, statico — non più un grafico
Sheets "linked": non si aggiorna se i dati cambiano dopo il caricamento); sostituisce il
placeholder del nome brand in tutto il deck. Scrive `slides_meta.json` con l'indice di ogni
nuova slide creata.

**6d. Immagini brand**: alcune slide (cover, main insights/warnings) hanno un placeholder
immagine da sostituire con una foto reale del brand (indicato nelle note relatore lette da
`inspect_template_pptx.py`). Procurati un'immagine adatta dal sito del brand (WebFetch),
salvala in locale, e passala a `build_slides_pptx.py` con
`--brand-images cover=<path>,main_insights=<path>` (lo script la inserisce al posto
dell'immagine segnaposto sulla slide fissa indicata, stessa posizione/dimensione). Se non
trovi un'immagine adatta, segnalalo all'utente invece di inventarla o lasciare l'immagine
generica del template.

Puoi rigenerare il pptx quante volte serve (operazione locale, economica) se vuoi rivedere
il testo dopo un self-check — non c'è un "preview" incrementale come nel flusso precedente,
ma rigenerare da capo è comunque più semplice del vecchio giro duplica→leggi ID→scrivi.

**6e. Carica il deck su Drive**:
```
mcp__claude_ai_Google_Drive__create_file(
  title="Search Intent - <Brand> - <Periodo>",
  parentId=<run_folder_id>,
  contentMimeType="application/vnd.openxmlformats-officedocument.presentationml.presentation",
  base64Content=<contenuto di runs/<slug>/output/deck.pptx>)
```
Registra l'id risultante:
```bash
python scripts/run_meta.py set --run-meta runs/<slug>/run_meta.json --key slide_id --value "<id>"
python scripts/run_meta.py set --run-meta runs/<slug>/run_meta.json --key slide_url --value "https://docs.google.com/presentation/d/<id>/edit"
```

**Limiti noti**: i grafici nel deck sono statici (nessun aggancio "linked" al Sheet); una
modifica ai dati dopo il caricamento richiede rigenerare pptx e xlsx e ricaricarli entrambi
(nuovi file, nessun update in-place). La conversione Google Slides→pptx (export del
template) e pptx→Google Slides (upload) può introdurre lievi differenze di formattazione
(font, posizionamento) rispetto all'originale nativo Google — verifica visivamente il
risultato prima di consegnarlo.

## Step 7 — Consegna

Riporta all'utente `sheet_url` e `slide_url` da `run_meta.json`, e un riepilogo di:
numero keyword totali, numero cluster trovati dalla clusterizzazione vs. numero
effettivamente incluso nel report (selezione di Step 4bis), volume totale per cluster
incluso, quali colonne extra (Genere, Materiale/Colore, ...) hanno avuto un tab/grafico
di breakdown e quali di queste sono finite anche in una slide dedicata (Step 6a),
eventuali brand competitor rilevati in Step 4, e i due `commit` risolti da
`fetch_dependencies.py` in Step 0 (versione di clustering-agent/keyword-cleaner usata in
questo run).

## Limiti noti

- Il ruleset di clustering vive in Google Sheet su Drive, non più in file committati in
  `claude-clustering-agent` (vedi Step 4). `--mode add-rules` scrive solo nella copia
  effimera `runs/<slug>/clustering/workdir/rules/`, valida per il resto di **questo** run:
  per renderle permanenti per tutto il team va incollato a mano nello Sheet Drive giusto il
  blocco che lo script produce (`paste_rules_<vertical>_<lingua>.txt`, sezione "Proponi
  regole/brand → incolla manuale su Google Sheet" del `CLAUDE.md` di quel repo) — non c'è
  (e non serve) un commit su GitHub per questo.
- Non esiste più un'autenticazione Google gestita da questo repo (niente OAuth, niente
  refresh token da rinnovare): l'unico canale verso Drive/Sheets/Slides è l'MCP Google
  Drive collegato in sessione. Se non è disponibile, la skill si ferma — non c'è fallback.
- Niente più PivotTable native né grafici Sheets/Slides "linked": xlsx e pptx sono
  generati offline con aggregazioni pre-calcolate e grafici embedded statici. Ogni run
  (o ricarica) crea nuovi file su Drive: non esiste un'operazione MCP di aggiornamento
  in-place di un file esistente.
- Il contenuto editoriale delle slide (Step 6a e 6b) richiede giudizio: non esiste un modo
  puramente meccanico per generarlo, né per scegliere il formato o scrivere il testo con
  la stessa qualità del riferimento in `GOOGLE_SLIDE_EXAMPLE_ID`. A differenza del flusso
  precedente, va scritto per intero PRIMA di generare il pptx (Step 6b), non più in un
  secondo giro su slide già duplicate.
