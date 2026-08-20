#!/usr/bin/env python3
"""
Step "Fetch dipendenze" della skill report-search-intent (prerequisito, prima di Step 3/4).

Risolve i percorsi locali di public-claude-clustering-agent e
public-claude-semrush-keyword-cleaner usati rispettivamente da Step 4 (clustering) e Step 3
(pulizia keyword):

- Se CLUSTERING_AGENT_PATH / KEYWORD_CLEANER_PATH sono valorizzate nel .env, usa quel
  percorso cosi' com'e' (override locale, utile per testare modifiche non ancora pushate) e
  non tocca git.
- Altrimenti clona (la prima volta) o aggiorna (`git fetch` + `reset --hard` sul branch
  configurato) il repo GitHub in `.cache/<nome-repo>/` dentro questo progetto — cosi' non
  serve piu' mantenere a mano un checkout "fratello" dei due repo, e ogni run usa sempre
  l'ultima versione pubblicata su GitHub.

`.cache/` e' una copia di sola lettura per la skill: non lavorarci dentro a mano, verra'
sempre riportata allo stato di origin/<branch> al prossimo fetch.

Entrambi i repo sono pubblici: nessuna credenziale/token e' richiesta per clonarli.

Per public-claude-clustering-agent, se il repo risolto non ha gia' un clustering-config.json
(gitignored li', quindi assente in un checkout fresco), lo scrive a partire dal valore
CLUSTERING_RULES_FOLDER_ID di drive_config.json — cosi' il CLAUDE.md di quel repo non deve
mai chiederlo all'utente.

Uso:
    python scripts/fetch_dependencies.py
"""

import json
import os
import subprocess
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(REPO_ROOT / ".env")

CACHE_DIR = REPO_ROOT / ".cache"

DEPENDENCIES = {
    "clustering_agent": {
        "path_env": "CLUSTERING_AGENT_PATH",
        "repo_env": "CLUSTERING_AGENT_REPO",
        "branch_env": "CLUSTERING_AGENT_BRANCH",
        "default_repo": "https://github.com/webanalytics-filoblu/public-claude-clustering-agent.git",
        "cache_dirname": "public-claude-clustering-agent",
        "marker_file": "scripts/cluster.py",
        "seed_config": ("clustering-config.json", "CLUSTERING_RULES_FOLDER_ID", "clustering_rules_folder_id"),
    },
    "keyword_cleaner": {
        "path_env": "KEYWORD_CLEANER_PATH",
        "repo_env": "KEYWORD_CLEANER_REPO",
        "branch_env": "KEYWORD_CLEANER_BRANCH",
        "default_repo": "https://github.com/webanalytics-filoblu/public-claude-semrush-keyword-cleaner.git",
        "cache_dirname": "public-claude-semrush-keyword-cleaner",
        "marker_file": "scripts/semrush_cleaner.py",
    },
}


def _resolve(path_str: str) -> Path:
    path = Path(path_str)
    return path if path.is_absolute() else REPO_ROOT / path


def _run(args, cwd=None):
    result = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(
            f"Comando fallito: {' '.join(args)}\n{result.stderr.strip() or result.stdout.strip()}\n\n"
            "Verifica che questa macchina abbia accesso di rete a github.com, o punta "
            "*_PATH a un checkout locale gia' funzionante."
        )
    return result.stdout.strip()


def _git_commit(path: Path):
    result = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "--short", "HEAD"],
        capture_output=True, text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def _seed_config(path: Path, filename: str, drive_config_key: str, field: str):
    """Scrive <path>/<filename> a partire da drive_config.json se non esiste già — solo per
    dipendenze che se lo aspettano (es. clustering-config.json di public-claude-clustering-agent,
    gitignored in quel repo: un checkout fresco non lo porta mai)."""
    target = path / filename
    if target.exists():
        return
    drive_config = json.loads((REPO_ROOT / "drive_config.json").read_text(encoding="utf-8"))
    folder_id = drive_config.get(drive_config_key)
    if not folder_id:
        return
    target.write_text(json.dumps({field: folder_id}, indent=2) + "\n", encoding="utf-8")


def resolve_dependency(spec: dict) -> dict:
    explicit_path = os.environ.get(spec["path_env"])
    if explicit_path:
        path = _resolve(explicit_path)
        if not path.exists():
            raise SystemExit(f"{spec['path_env']}={path} non esiste.")
        if not (path / spec["marker_file"]).exists():
            raise SystemExit(
                f"{spec['path_env']}={path} non contiene {spec['marker_file']} — controlla il percorso."
            )
        if spec.get("seed_config"):
            _seed_config(path, *spec["seed_config"])
        return {"path": str(path), "source": "override locale (.env)", "commit": _git_commit(path)}

    repo_url = os.environ.get(spec["repo_env"], spec["default_repo"])
    branch = os.environ.get(spec["branch_env"], "main")
    target = CACHE_DIR / spec["cache_dirname"]

    if (target / ".git").exists():
        _run(["git", "fetch", "--quiet", "origin", branch], cwd=str(target))
        _run(["git", "checkout", "--quiet", branch], cwd=str(target))
        _run(["git", "reset", "--quiet", "--hard", f"origin/{branch}"], cwd=str(target))
    else:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _run(["git", "clone", "--quiet", "--branch", branch, repo_url, str(target)])

    if not (target / spec["marker_file"]).exists():
        raise SystemExit(
            f"Clonato {repo_url} (branch {branch}) ma manca {spec['marker_file']} — "
            "repo o branch sbagliati?"
        )
    if spec.get("seed_config"):
        _seed_config(target, *spec["seed_config"])
    return {"path": str(target), "source": f"git ({branch})", "commit": _git_commit(target)}


def main():
    resolved = {name: resolve_dependency(spec) for name, spec in DEPENDENCIES.items()}
    print(json.dumps(resolved, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
