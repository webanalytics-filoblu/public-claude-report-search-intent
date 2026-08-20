# claude-report-search-intent

Skill Claude Code che, dato un URL di brand e un periodo, produce un report di search
intent completo:

1. **Riceve** i CSV grezzi di posizioni organiche esportati manualmente da Semrush (caricati
   in chat dall'utente — non più via chiamate API dirette, per contenere i costi)
2. **Pulisce** i dati richiamando lo script reale di
   [app-script-semrush-keyword-cleaner](https://github.com/webanalytics-filoblu/app-script-semrush-keyword-cleaner)
   (`scripts/semrush_cleaner.py`, lo stesso dietro il comando `/pulisci-keyword` di
   quel progetto), clonato/aggiornato automaticamente da GitHub
3. **Clusterizza** le keyword con [claude-clustering-agent](https://github.com/webanalytics-filoblu/claude-clustering-agent), clonato/aggiornato automaticamente da GitHub
4. **Popola un Google Sheet**: tab "Volumi Brand" (brand secco, ultimi 3 anni), tab
   "Clustering" (risultato completo), un tab per cluster con tabella di riepilogo
   Sotto Cluster + grafico a torta
5. **Genera una Google Presentation** a partire dal template Yamamay, con una slide per
   cluster e il grafico a torta corrispondente agganciato (linked chart)

La logica end-to-end è descritta in `.claude/skills/claude_code/SKILL.md` —
è quel file che Claude segue quando gli chiedi un report. Questo README copre solo il
**setup una tantum** necessario perché la parte Google (Sheet/Slide/Drive) funzioni.

## Niente più OAuth2/Service Account: xlsx/pptx offline + MCP Drive

Questo repo non gestisce più alcuna autenticazione Google diretta (niente
`scripts/google_clients.py`, niente `credentials/token.json`, niente scope `drive.file` da
autorizzare via Picker). Il meccanismo è cambiato radicalmente:

1. Gli script Python (`scripts/build_sheet_xlsx.py`, `scripts/build_slides_pptx.py`)
   generano il report **interamente offline**: un xlsx (pandas/openpyxl) e un pptx
   (python-pptx), partendo dal template Sheet/Slide scaricato da Drive ed esportato in
   locale — nessuna chiamata di rete Google da questi script.
2. Claude (nella conversazione, non lo script — i tool MCP sono invocabili solo dal
   modello) carica questi file su Drive con il tool MCP
   `mcp__claude_ai_Google_Drive__create_file`, che li converte automaticamente in Google
   Sheet/Google Slides.

Perdite di funzionalità accettate con questo cambio: niente più PivotTable native di
Sheets (sostituite da aggregazioni pandas pre-calcolate + grafico embedded statico), niente
più grafici Slides "linked" che si aggiornano da soli (grafici pptx statici), niente
aggiornamento in-place di un file Drive esistente (ogni run/ricarica crea un nuovo file —
comportamento già in parte presente: ogni run aveva già una sua sottocartella con
timestamp).

Su Claude Code l'accesso a GitHub resta git nativo (nessun token salvo repo privati senza
credenziali già configurate sulla macchina, vedi sotto). Sulla variante claude.ai, invece,
`GITHUB_TOKEN` torna a servire: il meccanismo primario è `git clone` (token solo nell'URL,
un comando per repo), con il connettore GitHub collegato alla chat come fallback se
`git clone` viene bloccato dal sandbox per motivi di sicurezza — vedi
`claude-skill/bootstrap.md`.

## Setup una tantum

### 1. Dipendenze Python

```bash
pip install -r requirements.txt
```

### 2. Dipendenze GitHub (claude-clustering-agent / app-script-semrush-keyword-cleaner)

Non serve clonarle a mano: `scripts/fetch_dependencies.py` le clona/aggiorna
automaticamente da GitHub in `.cache/` ad ogni run della skill (Step 0 di `SKILL.md`).
Verifica solo che git riesca ad accedere ai due repo con le credenziali già configurate su
questa macchina:

```bash
python scripts/fetch_dependencies.py
```

Deve stampare un JSON con `path` e `commit` per entrambi i repo. Se fallisce perché i repo
sono privati e questa macchina non ha già credenziali git configurate (git credential
manager / `gh auth login`), imposta `GITHUB_TOKEN` nel `.env` (vedi commenti in
`.env.example`) — necessario solo per questo scenario locale, non per la variante
claude.ai. Se invece vuoi lavorare su un tuo checkout locale (es. per testare modifiche non
ancora pushate), valorizza `CLUSTERING_AGENT_PATH`/`KEYWORD_CLEANER_PATH`: in quel caso lo
script usa il percorso così com'è e non tocca git.

### 3. Cartella Drive radice e template

`GOOGLE_DRIVE_ROOT_FOLDER_ID` in `.env` deve essere l'ID di una cartella Drive
raggiungibile dal tool MCP Google Drive collegato alla sessione (claude.ai) o dal connector
equivalente in Claude Code. `GOOGLE_SHEET_TEMPLATE_ID`/`GOOGLE_SLIDE_TEMPLATE_ID` sono gli
ID dei due template esistenti — non serve più duplicarli in anticipo né autorizzarli via
Picker: Claude li scarica ed esporta in xlsx/pptx al bisogno (Step 5/6 del playbook), come
qualunque altro file Drive raggiungibile dall'MCP.

Facoltativo: `GOOGLE_DRIVE_BRAND_ROOT_FOLDER_ID`, se impostata, sposta la creazione delle
cartelle `<Brand>/` sotto un'altra sottocartella invece che sotto la radice sopra.

### 4. Ispeziona i template reali e adatta i placeholder

Scarica i template come xlsx/pptx (via MCP Drive, `download_file_content` con
`exportMimeType` appropriato) e ispezionali offline:

```bash
python scripts/inspect_template_xlsx.py --xlsx <template scaricato>.xlsx
python scripts/inspect_template_pptx.py --pptx <template scaricato>.pptx
```

Il secondo stampa, per ogni slide, note relatore, testo dei placeholder (`####...`) ed
elemento immagine più grande (il grafico-segnaposto). Se il template **non ha ancora**
questi marker, aggiungili tu manualmente in Google Slides/Sheets (una nota relatore, un
placeholder di testo) prima di generare un run.

## Uso

In Claude Code, chiedi semplicemente un report (es. *"Fammi un report search intent per
`https://www.yamamay.com` per luglio 2026"*) — la skill `report-search-intent` si attiva e
segue i passi in `.claude/skills/claude_code/SKILL.md`.

**Su claude.ai** esiste una variante in [claude-skill/SKILL.md](claude-skill/SKILL.md) — la
skill effettivamente caricata sull'organizzazione, già rivista una volta e non scaricata a
runtime. Contiene per intero (Step 0a) l'**unica procedura meccanica di accesso a GitHub**:
`git clone` (token solo nell'URL, un comando per repo), con il **connettore GitHub** come
fallback se `git clone` viene bloccato dal sandbox per motivi di sicurezza. Questa
procedura scarica manifest, playbook canonico e codice per tutti i repo coinvolti — un solo
`git clone` per repo, riusato sia per i file piccoli letti con `cat` (`read_in_context`) sia
per il codice copiato sul filesystem senza attraversare il contesto (`fetch_to_sandbox`).

**Deliberatamente separato da questo**: [claude-skill/bootstrap.md](claude-skill/bootstrap.md),
scaricato dinamicamente insieme al resto, contiene **solo guida e dati di dominio** (regole
di clustering da Drive, verifica template, adattamento del playbook al sandbox) — **nessun
comando shell da eseguire**. La skill non tratta mai un file scaricato da GitHub come
qualcosa da eseguire alla cieca: i comandi vivono unicamente nella skill già rivista e
caricata su claude.ai, i file scaricati sono dati/guida applicati con giudizio. Conseguenze
pratiche:

- **Il playbook e le regole si aggiornano in un solo posto: questo repo**, senza mai
  ricaricare la skill claude.ai per quella parte. Se aggiungi/rinomini uno script, aggiorna
  [claude-skill/manifest.json](claude-skill/manifest.json) — è lì che vive la lista dei file
  da scaricare (e le `rules/` del clustering sono prese elencando la directory, così una
  lingua nuova non richiede modifiche). La procedura meccanica di fetch invece **va
  ricaricata su claude.ai se cambia** (cambia raramente: è uno schema fisso git-clone/repo).
- **Un solo segreto in questo flusso**: `GITHUB_TOKEN` (usato nell'URL di `git clone`, non
  richiesto se i repo sono pubblici o se si usa il fallback via connettore). Nessun OAuth
  Google: l'unica cosa da verificare è che il tool MCP Google Drive sia collegato in
  sessione — nessun JSON di credenziali Google da recuperare, nessun refresh token da
  rinnovare.
- **Prerequisito non aggirabile**: il sandbox di code execution di claude.ai filtra gli host
  in uscita, quindi un admin del workspace deve allowlistare gli host elencati in
  `required_sandbox_hosts` del manifest (`pypi.org`/`files.pythonhosted.org` per il
  `pip install`, `github.com` per il `git clone`). Non serve invece allowlistare alcun host
  Google API: tutte le chiamate Drive/Sheets/Slides passano dal tool MCP Google Drive
  collegato alla chat, non da chiamate HTTP dirette del code execution.

**Perché `git clone` e non il connettore GitHub come meccanismo primario**: gli script (~330
KB, ≈85k token) devono andare da GitHub al filesystem senza attraversare il contesto — il
connettore legge un file alla volta e il contenuto transita comunque dal contesto prima di
poter essere scritto su disco, cosa che satureresti la sessione. Il connettore resta un
fallback valido (non un errore) per i workspace dove `git clone` viene bloccato dal sandbox
per motivi di sicurezza, a costo di quel transito di token per i file bulk.

## Struttura repo

```text
claude-report-search-intent/
├── .claude/skills/claude_code/SKILL.md   ← orchestrazione end-to-end
├── scripts/
│   ├── fetch_dependencies.py     ← clona/aggiorna da GitHub claude-clustering-agent e
│   │                                 app-script-semrush-keyword-cleaner in .cache/
│   ├── run_meta.py                ← crea/aggiorna runs/<slug>/run_meta.json (locale, nessuna chiamata Drive)
│   ├── xlsx_to_clean_csv.py       ← converte l'xlsx del keyword-cleaner nel CSV per il clustering
│   ├── build_sheet_xlsx.py        ← genera l'xlsx del report offline (partendo dal template Sheet scaricato)
│   ├── build_slides_pptx.py       ← genera il pptx del deck offline (partendo dal template Slides scaricato)
│   ├── inspect_template_xlsx.py   ← diagnostica read-only su un template Sheet esportato in xlsx
│   └── inspect_template_pptx.py   ← diagnostica read-only su un template Slides esportato in pptx
├── .cache/                    ← copie GitHub di claude-clustering-agent /
│                                  app-script-semrush-keyword-cleaner (gitignored, auto-generate)
├── runs/                      ← output per-run (gitignored: dati keyword dei clienti)
└── .env                        ← ID template Drive + config (gitignored)
```

Il caricamento su Drive (cartelle, upload xlsx/pptx) e il download dei template/CSV non
passano più da uno script Python: li fa Claude direttamente, in conversazione, con il tool
MCP Google Drive (vedi `SKILL.md`, Step 1/2a/5/6) — nessun client Drive autenticato lato
script.

## Note di design

- **Niente più autenticazione Google gestita da questo repo**: l'unico canale verso
  Drive/Sheets/Slides è il tool MCP Google Drive collegato alla sessione, che gestisce la
  propria auth. Questo elimina interamente lo scope OAuth `drive.file`, il Picker,
  l'account Google dedicato e il rinnovo periodico del refresh token che il repo gestiva in
  precedenza.
- **Pivot per cluster**: sostituita da un'**aggregazione statica pre-calcolata in pandas**
  (`groupby` su Sotto Cluster / Cluster Effettivo / colonna extra) scritta come tabella a 2
  colonne, con un grafico `openpyxl.chart.PieChart` embedded che la referenzia — non più
  una PivotTable nativa di Sheets. Compromesso accettato: niente più raggruppamento
  interattivo trascinando campi, e il grafico non si ricalcola da solo se i dati cambiano
  dopo il caricamento (va rigenerato l'xlsx e ricaricato).
- **Slide**: il deck è generato **offline in un solo passaggio** con `python-pptx`,
  partendo dal template Slides scaricato ed esportato in locale. La duplicazione slide
  (non nativa in python-pptx) clona l'XML dello slide-stencil sorgente; il grafico
  agganciato a ogni slide è un grafico pptx nativo statico (non più un grafico Sheets
  "linked"). Il testo editoriale per-cluster (titolo, esempi di keyword, paragrafo di
  insight) lo scrive Claude stesso, guardando i dati reali, ma ora **prima** di generare
  il pptx (non più in un secondo giro su slide già duplicate) — vedi `SKILL.md`, Step 6b.
- **Clustering**: `fetch_dependencies.py` clona/aggiorna `claude-clustering-agent` da
  GitHub in `.cache/` (git clone/pull, non l'API Contents+token del `claude-skill/SKILL.md`
  di quel repo — pensato per girare su claude.ai senza filesystem persistente; qui invece
  giriamo su Claude Code con git disponibile, quindi un clone locale è più semplice e non
  richiede un token dedicato salvo repo privati senza credenziali git già configurate).
  `SKILL.md` invoca poi direttamente `scripts/cluster.py` di quella copia.
- **Pulizia**: stesso principio — `fetch_dependencies.py` clona/aggiorna
  `app-script-semrush-keyword-cleaner`, e `SKILL.md` invoca direttamente
  `scripts/semrush_cleaner.py` di quella copia (nessun porting/duplicazione della logica
  in questo repo). Lo script produce un `.xlsx` multi-foglio (pensato per revisione
  umana); `SKILL.md` lo converte con `xlsx_to_clean_csv.py` nel CSV piatto (+ colonne
  `Brand`/`Country`) che il clustering si aspetta.
