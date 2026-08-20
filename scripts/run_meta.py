#!/usr/bin/env python3
"""
Gestione locale di runs/<slug>/run_meta.json — nessuna chiamata Drive.

Sostituisce la parte non-Drive di drive_setup.py: crea solo la cartella del run e lo
scheletro del JSON (slug, brand, periodo, dominio). Gli ID Drive (cartella brand, cartella
run, cartella semrush_files, file Sheet/Slide) non vengono più creati da uno script Python
(nessun client Drive autenticato disponibile qui): è Claude, nella conversazione, a creare
quelle risorse con le chiamate MCP Google Drive (create_file/search_files) e a scrivere gli
ID risultanti in run_meta.json con il sotto-comando "set" qui sotto — così lo schema del
JSON resta in un solo posto invece di essere scritto/parsato a mano con Edit.

Uso:
    python scripts/run_meta.py init --brand Yamamay --period "Luglio 2026" [--domain yamamay.com]
    python scripts/run_meta.py set --run-meta runs/<slug>/run_meta.json --key sheet_id --value <id>
"""

import argparse
import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^\w\- ]", "", text).strip().lower()
    return re.sub(r"[\s_]+", "-", text)


def cmd_init(args):
    run_slug = f"{slugify(args.brand)}_{slugify(args.period)}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    run_dir = REPO_ROOT / "runs" / run_slug
    run_dir.mkdir(parents=True, exist_ok=True)

    meta = {
        "brand": args.brand,
        "period": args.period,
        "domain": args.domain or "",
        "run_slug": run_slug,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    meta_path = run_dir / "run_meta.json"
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps(meta, indent=2, ensure_ascii=False))
    print(f"\nrun_dir: {run_dir}")
    print(f"run_meta: {meta_path}")
    print(
        "\nProssimo passo: crea su Drive (chiamate MCP dirette, non questo script) la cartella "
        "brand, la cartella run, 'semrush_files/' e le copie di Sheet/Slide template, poi scrivi "
        "ogni ID con 'python scripts/run_meta.py set --run-meta ... --key ... --value ...'."
    )


def cmd_set(args):
    meta_path = Path(args.run_meta)
    if not meta_path.exists():
        raise SystemExit(f"run_meta non trovato: {meta_path}")

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta[args.key] = args.value
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(meta, indent=2, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description="Crea/aggiorna runs/<slug>/run_meta.json (nessuna chiamata Drive)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="Crea runs/<slug>/ e lo scheletro di run_meta.json")
    p_init.add_argument("--brand", required=True, help="Nome brand, es. Yamamay")
    p_init.add_argument("--period", required=True, help="Periodo richiesto, es. 'Luglio 2026'")
    p_init.add_argument("--domain", default="", help="Dominio del brand, es. yamamay.com (facoltativo)")
    p_init.set_defaults(func=cmd_init)

    p_set = sub.add_parser("set", help="Aggiorna una chiave in run_meta.json (es. dopo una chiamata MCP)")
    p_set.add_argument("--run-meta", required=True)
    p_set.add_argument("--key", required=True)
    p_set.add_argument("--value", required=True)
    p_set.set_defaults(func=cmd_set)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
