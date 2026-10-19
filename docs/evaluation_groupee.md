# Évaluation groupée par prestataire

## Validation croisée groupée (train)

| Protocole | PR-AUC moyenne | Écart-type | Plis |
|---|---:|---:|---:|
| GroupKFold par prestataire | 0.1438 | 0.0105 | 5 |
| StratifiedKFold aléatoire (référence) | 0,1461 | 0,0143 | 15 |

Les plis groupés empêchent le modèle de mémoriser un prestataire : l'écart avec la CV aléatoire mesure la dépendance à l'identité de l'acteur.

## Démarrage à froid sur le test

| Prestataire vu en train | n | Part | Positifs | Prévalence | PR-AUC (IC95) |
|---|---:|---:|---:|---:|---|
| **non (nouveau)** | 64 | 0.6% | 0 | 0.00% | n/a (aucun positif) |
| oui | 10264 | 99.4% | 128 | 1.25% | 0.1561 [0.123–0.213] |

## Lecture

- Si la PR-AUC groupée reste proche de la CV aléatoire, le modèle s'appuie sur des signaux transférables (comportement de facturation) et non sur l'identité du prestataire.
- Les prestataires nouveaux sont le cas critique en production : leur performance conditionne l'utilité réelle du système.
- Les effectifs par pli restent modestes (≈ 140 positifs par pli) : les intervalles sont larges.

## Limites

- Données synthétiques : la structure des prestataires peut être plus régulière que dans la réalité.
- La cible reste un proxy administratif, pas une fraude confirmée.