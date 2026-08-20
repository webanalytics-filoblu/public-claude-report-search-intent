#!/usr/bin/env python3
"""
Step "Fetch dipendenze" della skill report-search-intent (prerequisito, prima di Step 3/4).

Risolve i percorsi locali di claude-clustering-agent e app-script-semrush-keyword-cleaner
usati rispettivamente da Step 4 (clustering) e Step 3 (pulizia keyword):

- Se CLUSTERING_AGENT_PATH / KEYWORD_CLEANER_PATH sono valorizzate nel .env, usa quel
  percorso cosi' com'e' (override locale, utile per testare modifiche non ancora pushate) e
  non tocca git.
- Altrimenti clona (la prima volta) o aggiorna (`git fetch` + `reset --hard` sul branch
  configurato) il repo GitHub in `.cache/<nome-repo>/` dentro questo progetto — cosi' non
  serve piu' mantenere a mano un checkout "fratello" dei due repo, e ogni run usa sempre
  l'ultima versione pubblicata su GitHub.

`.cache/` e' una copia di sola lettura per la skill: non lavorarci dentro a mano, verra'
sempre riportata allo stato di origin/<branch> al prossimo fetch.

Se il repo e' privato e le credenziali git di questa macchina non bastano (es. ambiente
headless senza credential manager configurato), imposta GITHUB_TOKEN nel .env: viene
iniettato nell'URL di clone/fetch solo per questo comando.

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
        "default_repo": "https://github.com/webanalytics-filoblu/claude-clustering-agent.git",
        "cache_dirname": "claude-clustering-agent",
        "marker_file": "scripts/cluster.py",
    },
    "keyword_cleaner": {
        "path_env": "KEYWORD_CLEANER_PATH",
        "repo_env": "KEYWORD_CLEANER_REPO",
        "branch_env": "KEYWORD_CLEANER_BRANCH",
        "default_repo": "https://github.com/webanalytics-filoblu/app-script-semrush-keyword-cleaner.git",
        "cache_dirname": "app-script-semrush-keyword-cleaner",
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
            "Se il repo e' privato, verifica le credenziali git di questa macchina "
            "(git credential manager / `gh auth login`) oppure imposta GITHUB_TOKEN nel "
            ".env. In alternativa, punta *_PATH a un checkout locale gia' funzionante."
        )
    return result.stdout.strip()


def _git_commit(path: Path):
    result = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "--short", "HEAD"],
        capture_output=True, text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def _inject_token(repo_url: str, token: str) -> str:
    if token and repo_url.startswith("https://"):
        return f"https://{token}@{repo_url[len('https://'):]}"
    return repo_url


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
        return {"path": str(path), "source": "override locale (.env)", "commit": _git_commit(path)}

    repo_url = os.environ.get(spec["repo_env"], spec["default_repo"])
    branch = os.environ.get(spec["branch_env"], "main")
    token = os.environ.get("GITHUB_TOKEN")
    clone_url = _inject_token(repo_url, token)
    target = CACHE_DIR / spec["cache_dirname"]

    if (target / ".git").exists():
        _run(["git", "fetch", "--quiet", "origin", branch], cwd=str(target))
        _run(["git", "checkout", "--quiet", branch], cwd=str(target))
        _run(["git", "reset", "--quiet", "--hard", f"origin/{branch}"], cwd=str(target))
    else:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _run(["git", "clone", "--quiet", "--branch", branch, clone_url, str(target)])

    if not (target / spec["marker_file"]).exists():
        raise SystemExit(
            f"Clonato {repo_url} (branch {branch}) ma manca {spec['marker_file']} — "
            "repo o branch sbagliati?"
        )
    return {"path": str(target), "source": f"git ({branch})", "commit": _git_commit(target)}


def main():
    resolved = {name: resolve_dependency(spec) for name, spec in DEPENDENCIES.items()}
    print(json.dumps(resolved, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
