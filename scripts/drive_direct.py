#!/usr/bin/env python3
"""
Fast path opzionale via Google Drive API diretta (OAuth con refresh token),
alternativo alle chiamate MCP Google Drive per due soli passaggi del
playbook: download dei template Sheet/Slide (Step 5 punto 1, Step 6) e
upload del report elaborato con conversione automatica in Google
Sheet/Slides (Step 5 punto 3, Step 6e).

Vedi .claude/skills/claude_code/SKILL.md, sezione "Fast path opzionale:
download template / upload file elaborati via Google API diretta", per il
formato di google_auth.json e le regole di sicurezza sulla credenziale. Il
flusso via connettore MCP Google Drive resta il default e l'unico
obbligatorio: questo script è un percorso opt-in, mai proposto di
iniziativa da Claude.
"""
import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"
GOOGLE_DRIVE_EXPORT_URL = "https://www.googleapis.com/drive/v3/files/{file_id}/export"
GOOGLE_DRIVE_UPLOAD_URL = (
    "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&supportsAllDrives=true"
)
DEFAULT_GOOGLE_AUTH_FILE = str(Path.home() / ".config" / "report-search-intent-agent" / "google_auth.json")


def _load_google_credentials(auth_file: str) -> dict:
    path = Path(auth_file).expanduser()
    if not path.exists():
        print(f"Errore: credenziali Google non trovate in {path}")
        print("   Vedi SKILL.md, sezione 'Fast path opzionale: download template / upload file elaborati via Google API diretta'.")
        sys.exit(1)
    try:
        creds = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"Errore: {path} non è un JSON valido ({e}).")
        sys.exit(1)
    required = ["GOOGLE_OAUTH_CLIENT_ID", "GOOGLE_OAUTH_CLIENT_SECRET", "GOOGLE_OAUTH_REFRESH_TOKEN"]
    missing = [k for k in required if not creds.get(k)]
    if missing:
        print(f"Errore: {path} manca dei campi obbligatori: {', '.join(missing)}")
        sys.exit(1)
    return creds


def _get_google_access_token(creds: dict) -> str:
    payload = urllib.parse.urlencode({
        "client_id": creds["GOOGLE_OAUTH_CLIENT_ID"],
        "client_secret": creds["GOOGLE_OAUTH_CLIENT_SECRET"],
        "refresh_token": creds["GOOGLE_OAUTH_REFRESH_TOKEN"],
        "grant_type": "refresh_token",
    }).encode("utf-8")
    req = urllib.request.Request(GOOGLE_TOKEN_URI, data=payload, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"Errore: refresh del token Google fallito ({e.code}): {body}")
        sys.exit(1)
    access_token = data.get("access_token")
    if not access_token:
        print(f"Errore: risposta token Google senza access_token: {data}")
        sys.exit(1)
    return access_token


def mode_download_template(args):
    """
    Scarica un template Sheet/Slide (export) direttamente dalla Drive API,
    stesso risultato di mcp__claude_ai_Google_Drive__download_file_content
    con exportMimeType, senza far transitare il base64 dal contesto.
    """
    creds = _load_google_credentials(args.auth_file)
    access_token = _get_google_access_token(creds)
    api_key = creds.get("GOOGLE_API_KEY")

    url = GOOGLE_DRIVE_EXPORT_URL.format(file_id=args.file_id) + "?" + urllib.parse.urlencode(
        {"mimeType": args.export_mime, **({"key": api_key} if api_key else {})}
    )
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {access_token}"})
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            content = resp.read()
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"Errore: download template fallito ({e.code}): {body}")
        sys.exit(1)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(content)
    print(f"[OK] Template scaricato in {out_path} ({len(content)} bytes).")


def mode_upload_report(args):
    """
    Carica un xlsx/pptx generato in locale su Drive con conversione
    automatica in Google Sheet/Slides (--convert-mime), stesso risultato di
    mcp__claude_ai_Google_Drive__create_file, senza far transitare il
    base64 dal contesto.
    """
    creds = _load_google_credentials(args.auth_file)
    access_token = _get_google_access_token(creds)
    api_key = creds.get("GOOGLE_API_KEY")

    local_path = Path(args.file)
    if not local_path.exists():
        print(f"Errore: file da caricare non trovato: {local_path}")
        sys.exit(1)
    content = local_path.read_bytes()

    metadata = {"name": args.title, "parents": [args.parent_id], "mimeType": args.convert_mime}
    boundary = uuid.uuid4().hex
    body = (
        f"--{boundary}\r\n"
        f"Content-Type: application/json; charset=UTF-8\r\n\r\n"
        f"{json.dumps(metadata)}\r\n"
        f"--{boundary}\r\n"
        f"Content-Type: {args.source_mime}\r\n\r\n"
    ).encode("utf-8") + content + f"\r\n--{boundary}--".encode("utf-8")

    url = GOOGLE_DRIVE_UPLOAD_URL + (f"&key={api_key}" if api_key else "")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": f"multipart/related; boundary={boundary}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body_err = e.read().decode("utf-8", errors="replace")
        print(f"Errore: upload fallito ({e.code}): {body_err}")
        sys.exit(1)

    file_id = data.get("id")
    if not file_id:
        print(f"Errore: risposta upload senza id: {data}")
        sys.exit(1)
    print(json.dumps({"file_id": file_id}))


def main():
    parser = argparse.ArgumentParser(
        description="Fast path opzionale via Google Drive API diretta (download template / upload report elaborato)"
    )
    parser.add_argument("--mode", choices=["download-template", "upload-report"], required=True)
    parser.add_argument("--auth-file", default=DEFAULT_GOOGLE_AUTH_FILE,
                        help="Path di google_auth.json (fuori dal repo). Vedi SKILL.md per formato e regole di sicurezza.")
    parser.add_argument("--file-id", help="ID Drive del template da scaricare (mode download-template)")
    parser.add_argument("--export-mime", help="MIME di export, es. .../spreadsheetml.sheet o .../presentationml.presentation (mode download-template)")
    parser.add_argument("--out", help="Path locale di destinazione (mode download-template)")
    parser.add_argument("--parent-id", help="ID cartella Drive di destinazione (mode upload-report)")
    parser.add_argument("--title", help="Titolo del file su Drive (mode upload-report)")
    parser.add_argument("--file", help="Path locale del file xlsx/pptx da caricare (mode upload-report)")
    parser.add_argument("--source-mime", help="MIME del file locale, xlsx o pptx (mode upload-report)")
    parser.add_argument("--convert-mime", help="MIME Google Workspace di conversione, Sheet o Slides (mode upload-report)")
    args = parser.parse_args()

    if args.mode == "download-template":
        missing = [n for n in ("file_id", "export_mime", "out") if not getattr(args, n)]
        if missing:
            print(f"Errore: --{', --'.join(m.replace('_', '-') for m in missing)} richiesti per --mode download-template.")
            sys.exit(1)
        mode_download_template(args)
    elif args.mode == "upload-report":
        missing = [n for n in ("parent_id", "title", "file", "source_mime", "convert_mime") if not getattr(args, n)]
        if missing:
            print(f"Errore: --{', --'.join(m.replace('_', '-') for m in missing)} richiesti per --mode upload-report.")
            sys.exit(1)
        mode_upload_report(args)


if __name__ == "__main__":
    main()
