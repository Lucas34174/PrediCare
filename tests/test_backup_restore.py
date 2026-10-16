"""Tests d'intégration et d'exploitabilité pour les scripts de sauvegarde et restauration"""

import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
BACKUP_SCRIPT = SCRIPTS_DIR / "backup.sh"
RESTORE_SCRIPT = SCRIPTS_DIR / "restore.sh"


def test_scripts_exist_and_are_executable():
    """Vérifie que les scripts backup.sh et restore.sh existent et sont exécutables."""
    assert BACKUP_SCRIPT.is_file(), f"{BACKUP_SCRIPT} doit exister"
    assert RESTORE_SCRIPT.is_file(), f"{RESTORE_SCRIPT} doit exister"

    assert os.access(BACKUP_SCRIPT, os.X_OK), "backup.sh doit avoir les droits d'exécution"
    assert os.access(RESTORE_SCRIPT, os.X_OK), "restore.sh doit avoir les droits d'exécution"


def test_scripts_syntax_bash():
    """Vérifie l'absence d'erreurs de syntaxe Bash avec bash -n."""
    for script in (BACKUP_SCRIPT, RESTORE_SCRIPT):
        res = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True)
        assert res.returncode == 0, f"Erreur de syntaxe dans {script.name} : {res.stderr}"


def test_restore_fails_gracefully_on_missing_file():
    """Vérifie que restore.sh renvoie un code 1 et un message clair si le fichier n'existe pas."""
    dummy_file = "backups/non_existent_dump_file_xyz.dump"
    res = subprocess.run(
        ["bash", str(RESTORE_SCRIPT), dummy_file],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 1, "restore.sh doit échouer si le fichier n'existe pas"
    assert "ERREUR" in res.stderr or "introuvable" in res.stderr


def test_backup_script_contains_required_options():
    """Vérifie la présence des options requises par le CDC (format custom -Fc, rétention)."""
    content = BACKUP_SCRIPT.read_text(encoding="utf-8")
    assert "-Fc" in content, "backup.sh doit utiliser le format Custom compressé (-Fc)"
    assert "RETENTION_DAYS" in content, "backup.sh doit gérer une politique de rétention"
    assert "POSTGRES_DB" in content, "backup.sh doit paramétrer la base cible"


def test_restore_script_contains_required_options():
    """Vérifie la présence des options requises pour la restauration propre (--clean)."""
    content = RESTORE_SCRIPT.read_text(encoding="utf-8")
    assert "pg_restore" in content, "restore.sh doit invoquer pg_restore"
    assert "--clean" in content, "restore.sh doit nettoyer les objets avant restauration (--clean)"
