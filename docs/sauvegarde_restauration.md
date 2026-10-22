# Guide d'exploitation : Sauvegarde et Restauration (PB-28)

Ce document décrit les procédures opérationnelles de sauvegarde et de restauration de la base de données PostgreSQL de PrediCare TPA, conformément aux exigences du CDC (§2 Base persistante, §5 Exploitation).

---

## 1. Principes et format

- **Outil** : `pg_dump` et `pg_restore` natifs PostgreSQL.
- **Format** : Custom compressé (`-Fc`), garantissant une intégrité transactionnelle, une taille optimisée et la possibilité de réordonner les objets lors de la restauration.
- **Rétention** : 7 jours par défaut (paramétrable via `RETENTION_DAYS`).
- **Emplacement des sauvegardes** : dossier local `backups/` (ignoré par git).

---

## 2. Commandes manuelles

### Sauvegarde

```bash
make backup
# ou directement :
bash scripts/backup.sh
```

Le fichier généré est nommé selon le motif : `backups/predicare_<DB_NAME>_<YYYYMMDD_HHMMSS>.dump`.

### Restauration

Restauration de la sauvegarde la plus récente :

```bash
make restore
# ou directement :
bash scripts/restore.sh
```

Restauration d'une sauvegarde spécifique :

```bash
make restore FILE=backups/predicare_predicare_20261016_020000.dump
# ou directement :
bash scripts/restore.sh backups/predicare_predicare_20261016_020000.dump
```

**Note :** La restauration utilise le drapeau `--clean --if-exists` pour réinitialiser les tables et types existants avant réinjection.

---

## 3. Planification automatique (Cron)

Pour garantir une sauvegarde quotidienne à 02h00 du matin (heure creuse), ajoutez la ligne suivante à la crontab de la machine hôte :

```bash
crontab -e
```

Ajoutez la ligne :

```cron
0 2 * * * cd /chemin/vers/PrediCare && bash scripts/backup.sh >> /var/log/predicare_backup.log 2>&1
```

---

## 4. Plan de reprise après sinistre (PRA)

En cas de corruption ou perte de données :

1. **Arrêter les services API et Streamlit pour éviter de nouvelles écritures :**

   ```bash
   docker compose stop api web
   ```

2. **Vérifier l'état et la disponibilité du conteneur de base de données :**

   ```bash
   docker compose up -d db
   ```

3. **Exécuter la restauration de la dernière sauvegarde saine :**

   ```bash
   bash scripts/restore.sh backups/<nom_du_dump_sain>.dump
   ```

4. **Relancer l'ensemble des services :**

   ```bash
   docker compose up -d
   ```

5. **Vérifier la santé du système via l'endpoint de diagnostic :**

   ```bash
   curl -f http://localhost:8000/health
   ```
