#!/usr/bin/env python3
"""
Verifica ed estrae uno zip di CSV Semrush allegato direttamente in chat (variante
claude.ai dello Step 2a, vedi claude-skill/bootstrap.md — non usato nel flusso Claude
Code, che scarica i CSV da Drive).

Controlla il CRC32 interno di ogni file dello zip prima di estrarre (zipfile.testzip()):
un archivio con CRC non validi significa upload arrivato incompleto/troncato, e in quel
caso lo script si ferma senza estrarre nulla, invece di lasciare in giro un CSV parziale.

Uso:
    python scripts/extract_semrush_zip.py \
        --zip /mnt/user-data/uploads/semrush_export.zip \
        --output-dir runs/<slug>/raw
"""

import argparse
import sys
import zipfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Verifica CRC ed estrae uno zip di CSV Semrush")
    parser.add_argument("--zip", required=True, help="path locale dello zip allegato in chat")
    parser.add_argument("--output-dir", required=True, help="cartella di destinazione (es. runs/<slug>/raw)")
    args = parser.parse_args()

    zip_path = Path(args.zip)
    if not zip_path.exists():
        print(f"File non trovato: {zip_path}", file=sys.stderr)
        sys.exit(1)

    if not zipfile.is_zipfile(zip_path):
        print(f"Non è un archivio zip valido: {zip_path}", file=sys.stderr)
        sys.exit(1)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        if not names:
            print(f"Zip vuoto: {zip_path}", file=sys.stderr)
            sys.exit(1)

        bad_file = zf.testzip()
        if bad_file is not None:
            print(
                f"CRC non valido per '{bad_file}': l'upload è arrivato incompleto o troncato. "
                "Chiedi all'utente di ricaricare lo zip, non procedere con un'estrazione parziale.",
                file=sys.stderr,
            )
            sys.exit(1)

        non_csv = [n for n in names if not n.lower().endswith(".csv")]
        if non_csv:
            print(f"Attenzione: nello zip ci sono file non CSV, estratti comunque: {non_csv}", file=sys.stderr)

        zf.extractall(output_dir)

    print(f"CRC verificati, {len(names)} file estratti in {output_dir}:")
    for name in names:
        print(f"  {name}")


if __name__ == "__main__":
    main()
