# public-claude-report-search-intent

Skill Claude Code che, dato un URL di brand e un periodo, produce un report di search
intent completo:

1. **Riceve** i CSV grezzi di posizioni organiche esportati manualmente da Semrush (caricati
   in chat dall'utente — non più via chiamate API dirette, per contenere i costi)
2. **Pulisce** i dati richiamando lo script reale di
   [public-claude-semrush-keyword-cleaner](https://github.com/webanalytics-filoblu/public-claude-semrush-keyword-cleaner)
   (`scripts/semrush_cleaner.py`, lo stesso dietro il comando `/pulisci-keyword` di
   quel progetto), clonato/aggiornato automaticamente da GitHub
3. **Clusterizza** le keyword con [public-claude-clustering-agent](https://github.com/webanalytics-filoblu/public-claude-clustering-agent), clonato/aggiornato automaticamente da GitHub
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

I tre repo coinvolti in questo flusso (questo, `public-claude-clustering-agent`,
`public-claude-semrush-keyword-cleaner`) sono tutti pubblici: sia su Claude Code sia sulla
variante claude.ai l'accesso è un semplice `git clone` via HTTPS, senza alcun token o
connettore GitHub (non ne esiste uno in questo workspace) — vedi
`claude-skill/bootstrap.md`.

## Setup una tantum

### 1. Dipendenze Python

```bash
pip install -r requirements.txt
```

### 2. Dipendenze GitHub (public-claude-clustering-agent / public-claude-semrush-keyword-cleaner)

Non serve clonarle a mano: `scripts/fetch_dependencies.py` le clona/aggiorna
automaticamente da GitHub in `.cache/` ad ogni run della skill (Step 0 di `SKILL.md`).
Entrambi i repo sono pubblici, quindi non serve alcuna credenziale:

```bash
python scripts/fetch_dependencies.py
```

Deve stampare un JSON con `path` e `commit` per entrambi i repo. Se vuoi lavorare su un tuo
checkout locale (es. per testare modifiche non ancora pushate), valorizza
`CLUSTERING_AGENT_PATH`/`KEYWORD_CLEANER_PATH`: in quel caso lo script usa il percorso così
com'è e non tocca git.

### 3. Cartella Drive radice e template

Niente da configurare: i 5 ID sono già committati in [`drive_config.json`](drive_config.json)
alla root del repo (non sono segreti, solo ID di file/cartella Drive — l'autenticazione
resta sempre a carico del tool MCP Google Drive collegato alla sessione).
`GOOGLE_DRIVE_ROOT_FOLDER_ID` è la cartella Drive radice raggiungibile dall'MCP.
`GOOGLE_SHEET_TEMPLATE_ID`/`GOOGLE_SLIDE_TEMPLATE_ID` sono gli ID dei due template esistenti
— non serve duplicarli in anticipo né autorizzarli via Picker: Claude li scarica ed esporta
in xlsx/pptx al bisogno (Step 5/6 del playbook). `GOOGLE_DRIVE_BRAND_ROOT_FOLDER_ID`
(facoltativa) sposta la creazione delle cartelle `<Brand>/` sotto un'altra sottocartella
invece che sotto la radice. `GOOGLE_SLIDE_EXAMPLE_ID` (facoltativa) è la presentazione di
riferimento per tono/stile editoriale.

Per puntare a una cartella/template diverso (es. un ambiente di test), modifica
`drive_config.json` in locale.

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
`git clone` su repo pubblici, senza alcun token né connettore GitHub (non ne esiste uno in
questo workspace: se `git clone` viene bloccato dal sandbox, la skill si ferma e lo segnala).
Questa procedura scarica manifest, playbook canonico e codice per tutti i repo coinvolti —
un solo `git clone` per repo, riusato sia per i file piccoli letti con `cat`
(`read_in_context`) sia per il codice copiato sul filesystem senza attraversare il contesto
(`fetch_to_sandbox`).

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
- **Nessun segreto in questo flusso**: i tre repo coinvolti (questo,
  `public-claude-clustering-agent`, `public-claude-semrush-keyword-cleaner`) sono tutti
  pubblici, quindi niente `GITHUB_TOKEN`. Nessun OAuth Google: l'unica cosa da verificare è
  che il tool MCP Google Drive sia collegato in sessione — nessun JSON di credenziali Google
  da recuperare, nessun refresh token da rinnovare.
- **Prerequisito non aggirabile**: il sandbox di code execution di claude.ai filtra gli host
  in uscita, quindi un admin del workspace deve allowlistare gli host elencati in
  `required_sandbox_hosts` del manifest (`pypi.org`/`files.pythonhosted.org` per il
  `pip install`, `github.com` per il `git clone`). Non serve invece allowlistare alcun host
  Google API: tutte le chiamate Drive/Sheets/Slides passano dal tool MCP Google Drive
  collegato alla chat, non da chiamate HTTP dirette del code execution.

**Perché `git clone` e non un connettore GitHub**: gli script (~330 KB, ≈85k token) devono
andare da GitHub al filesystem senza attraversare il contesto — un connettore che legge un
file alla volta farebbe transitare comunque il contenuto dal contesto prima di poter essere
scritto su disco, cosa che satureresti la sessione. Non esiste comunque un connettore GitHub
in questo workspace: se `git clone` viene bloccato dal sandbox, la skill si ferma e lo
segnala all'utente, senza fallback.

## Struttura repo

```text
public-claude-report-search-intent/
├── .claude/skills/claude_code/SKILL.md   ← orchestrazione end-to-end
├── scripts/
│   ├── fetch_dependencies.py     ← clona/aggiorna da GitHub public-claude-clustering-agent e
│   │                                 public-claude-semrush-keyword-cleaner in .cache/
│   ├── run_meta.py                ← crea/aggiorna runs/<slug>/run_meta.json (locale, nessuna chiamata Drive)
│   ├── xlsx_to_clean_csv.py       ← converte l'xlsx del keyword-cleaner nel CSV per il clustering
│   ├── build_sheet_xlsx.py        ← genera l'xlsx del report offline (partendo dal template Sheet scaricato)
│   ├── build_slides_pptx.py       ← genera il pptx del deck offline (partendo dal template Slides scaricato)
│   ├── inspect_template_xlsx.py   ← diagnostica read-only su un template Sheet esportato in xlsx
│   └── inspect_template_pptx.py   ← diagnostica read-only su un template Slides esportato in pptx
├── .cache/                    ← copie GitHub di public-claude-clustering-agent /
│                                  public-claude-semrush-keyword-cleaner (gitignored, auto-generate)
├── runs/                      ← output per-run (gitignored: dati keyword dei clienti)
├── drive_config.json          ← ID statici Drive/Sheet/Slide Template (committato, non un segreto)
└── .env                        ← override locali facoltativi (path/repo/branch dipendenze, gitignored)
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
- **Clustering e Pulizia — nessuna procedura duplicata qui**: `fetch_dependencies.py` clona/
  aggiorna `public-claude-clustering-agent` e `public-claude-semrush-keyword-cleaner` da
  GitHub in `.cache/` (git clone/pull, non l'API Contents del `claude-skill/SKILL.md` di
  quei repo — pensato per girare su claude.ai senza filesystem persistente; qui invece
  giriamo su Claude Code con git disponibile, quindi un clone locale è più semplice; i repo
  sono pubblici, nessun token richiesto). `SKILL.md` (Step 3/4) non trascrive i passaggi di
  quei progetti: dice a Claude di **leggere integralmente** il comando `/pulisci-keyword`
  (`.claude/commands/pulisci-keyword.md`) e il `CLAUDE.md` del clustering da quelle copie, e
  di seguirli per intero — con solo una piccola tabella di equivalenza percorsi
  (`input/`/`output/` di quei repo → `runs/<slug>/...` di questo run) e un paio di eccezioni
  esplicite (brand/settore già raccolti a monte, `--tipo-query tutte` fisso). Se quei due
  progetti cambiano il proprio flusso (nuove modalità, step aggiuntivi), questo repo resta
  allineato automaticamente, senza bisogno di aggiornare `SKILL.md`. `clustering-config.json`
  (l'ID della cartella Drive "Clustering rules" richiesto dal `CLAUDE.md` del clustering)
  arriva già clonato da `public-claude-clustering-agent`: è committato in quel repo (la
  cartella non è più condivisa "chiunque abbia il link", quindi l'ID non è più un segreto),
  non serve generarlo qui. Lo script di
  pulizia produce un `.xlsx` multi-foglio (pensato per revisione umana); `SKILL.md` lo
  converte con `xlsx_to_clean_csv.py` nel CSV piatto (+ colonne `Brand`/`Country`) che il
  clustering si aspetta.
