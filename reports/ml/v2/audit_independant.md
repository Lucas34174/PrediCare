# Audit indépendant du modèle v2 — note sur 20

**Modèle audité :** `v2.0.0-weak` (XGBoost pondéré, 60 variables comportementales)
**Date de l'audit :** 20/10/2026
**Jeu de test :** 10 453 factures, du 16/06/2026 au 18/09/2026, 893 positifs (8,54 %)
**Seuil de production :** probabilité calibrée 0,046103 (rappel cible 80 % sur validation)

> **Avertissement méthodologique.** Les labels sont des **labels faibles reconstruits par règles** à partir des 12 CSV et du référentiel des 14 types de fraude. Ce ne sont **pas des fraudes confirmées**. Les métriques ci-dessous mesurent la capacité du modèle à retrouver ces règles, pas sa performance sur la fraude réelle. Elles sont donc optimistes et partiellement circulaires.

---

## 1. Verdict

**Note globale : 15/20** (15,25/20 au détail, arrondi à 15/20 par prudence).

C'est un **bon modèle de triage**, solide techniquement : bonne discrimination, calibration excellente, absence de fuite directe, stabilité mensuelle, supériorité nette sur les règles à budget égal. Il n'atteint pas 18–20/20 parce que **la cible reste faible**, que **certains types de fraude sont mal couverts**, que **deux dimensions d'équité alertent**, qu'**une variable dérive** et que le modèle **dépend fortement de 5 variables**.

---

## 2. Performance globale (test)

| Métrique | Valeur |
|---|---:|
| PR-AUC | **0,7541** (IC95 0,7274–0,7782) |
| ROC-AUC | **0,9032** (IC95 0,8897–0,9144) |
| Rappel au seuil | **0,7805** (697 / 893) |
| Précision au seuil | **0,4199** (697 / 1 660) |
| F1 | **0,5460** |
| Alertes | 1 660 (15,88 % des factures) |
| Lift | **4,91** |
| Brier | **0,0358** |
| ECE | **0,0092** |

**Lecture.** Pour une prévalence de 8,54 %, une PR-AUC de 0,754 est très bonne : le modèle classe nettement mieux que le hasard. Le ROC-AUC de 0,903 confirme une bonne séparation. La calibration est excellente (ECE < 1 %). En revanche, au seuil de production, **58 % des alertes sont des faux positifs** (963 FP pour 697 TP), ce qui est le prix du rappel élevé. Le rappel test (78,1 %) est légèrement sous la cible de 80 % calibrée sur validation : c'est l'écart attendu sur un holdout chronologique.

### Performance à budget d'alertes fixé

| Budget | Alertes | Précision | Rappel | Lift |
|---:|---:|---:|---:|---:|
| 1 % | 105 | **1,000** | 0,118 | 11,71 |
| 2 % | 209 | **1,000** | 0,234 | 11,71 |
| 3 % | 314 | 0,978 | 0,344 | 11,44 |
| 5 % | 523 | **0,914** | 0,535 | 10,70 |
| 10 % | 1 045 | 0,623 | 0,729 | 7,29 |
| 15 % | 1 568 | 0,440 | 0,773 | 5,15 |
| 20 % | 2 091 | 0,347 | 0,812 | 4,06 |

**Lecture.** Le modèle est excellent en tête de liste : à 5 % d'alertes, 91,4 % de précision pour 53,5 % de rappel. C'est le régime opérationnel recommandé si l'équipe contrôle médical a une capacité limitée. Le seuil produit actuel (15,9 % d'alertes) privilégie le rappel, conformément au CDC.

---

## 3. Calibration

| Décile | Probabilité prédite moyenne | Prévalence observée | Écart |
|---:|---:|---:|---:|
| 1 | 0,0179 | 0,0067 | 0,0112 |
| 2 | 0,0182 | 0,0067 | 0,0115 |
| 5 | 0,0215 | 0,0258 | 0,0043 |
| 8 | 0,0323 | 0,0287 | 0,0036 |
| 9 | 0,0522 | 0,0708 | 0,0186 |
| 10 | 0,5994 | 0,6224 | 0,0230 |

**ECE = 0,0092 ; écart maximal = 0,0230.** La calibration de Platt est très bonne. Le modèle n'est pas seulement discriminant : ses probabilités sont exploitables pour prioriser et pour comparer des montants en jeu.

---

## 4. Performance par niveau de confiance du label

| Tier | n | Positifs | Alertes | Taux d'alerte | Rappel du tier | Précision | Faux positifs |
|---|---:|---:|---:|---:|---:|---:|---:|
| `aucune` | 6 214 | 0 | 240 | 3,9 % | — | — | 240 |
| `candidate_faible` | 3 156 | 0 | 688 | 21,8 % | — | — | 688 |
| `candidate_moyenne` | 190 | 0 | 35 | 18,4 % | — | — | 35 |
| `haute` | 766 | 766 | 602 | 78,6 % | **0,786** | **1,000** | 0 |
| `moyenne_retenue` | 127 | 127 | 95 | 74,8 % | **0,748** | **1,000** | 0 |

**Lecture.** Le modèle retrouve 78,6 % des positifs haute confiance et 74,8 % des positifs moyenne confiance. Les 963 faux positifs se répartissent entre les candidats (688 + 35) et les factures sans signal (240). C'est cohérent : les candidats sont des négatifs incertains, pas des négatifs confirmés. Le modèle alerte 21,8 % des candidats faibles, ce qui peut être acceptable en triage mais gonfle la charge.

---

## 5. Rappel par type de fraude (multi-label)

| Type | Positifs test | Alertés | Rappel |
|---|---:|---:|---:|
| SURFACTURATION | 529 | 439 | **0,830** |
| LIGNES_NON_PRESCRITES | 155 | 152 | **0,981** |
| SURCONSOMMATION | 132 | 129 | **0,977** |
| FRACTIONNEMENT | 125 | 75 | 0,600 |
| DOUBLON | 109 | 62 | 0,569 |
| ORDONNANCE_EXPIREE | 79 | 43 | 0,544 |
| SUBSTITUTION_PRODUIT | 70 | 70 | **1,000** |
| QUANTITE_EXCESSIVE | 68 | 68 | **1,000** |
| PRESTATAIRE_RADIE | 68 | 31 | 0,456 |
| SOINS_JOUR_FERME | 52 | 36 | 0,692 |
| INCOHERENCE_PROFIL | 45 | 38 | 0,844 |
| ACTE_FICTIF | 20 | 20 | **1,000** |
| HORS_COUVERTURE | 11 | 5 | 0,455 |
| CONTROLE_MEDICAL | 8 | 5 | 0,625 |
| UPCODING | 7 | 5 | 0,714 |

**Lecture.** Le modèle est très bon sur les types majoritaires (surfacturation, lignes non prescrites, surconsommation, substitution, quantité excessive). Il est **moyen à faible** sur `FRACTIONNEMENT` (0,600), `DOUBLON` (0,569), `ORDONNANCE_EXPIREE` (0,544), `PRESTATAIRE_RADIE` (0,456). Les effectifs de `HORS_COUVERTURE`, `CONTROLE_MEDICAL` et `UPCODING` sont trop faibles (7–11) pour conclure, mais ils restent à surveiller. Ces gaps sont une des raisons de la note de 15/20.

---

## 6. Stabilité mensuelle

| Mois | n | Positifs | Prévalence | PR-AUC | Rappel | Précision | Taux d'alerte |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2026-06 | 1 773 | 145 | 8,2 % | 0,730 | 0,786 | 0,403 | 16,0 % |
| 2026-07 | 3 476 | 279 | 8,0 % | 0,747 | 0,763 | 0,398 | 15,4 % |
| 2026-08 | 3 143 | 298 | 9,5 % | 0,774 | 0,809 | 0,468 | 16,4 % |
| 2026-09 | 2 061 | 171 | 8,3 % | 0,752 | 0,754 | 0,394 | 15,9 % |

**Lecture.** La performance est stable sur les quatre mois du test : PR-AUC 0,73–0,77, rappel 0,75–0,81. Pas de dégradation temporelle visible sur cette fenêtre. C'est un point fort.

---

## 7. Équité

| Dimension | Écart TPR max-min | Écart FPR max-min | Alerte |
|---|---:|---:|---|
| Sexe | 0,0003 | 0,0038 | Non |
| Tranche d'âge | 0,0906 | 0,0353 | Non |
| Formule | 0,0794 | 0,0176 | Non |
| Ville assuré | **0,1061** | 0,0555 | **Oui** (> 0,1) |
| Ville prestataire | **0,1375** | 0,0721 | **Oui** (> 0,1) |

**Lecture.** Sexe, âge et formule sont sous le seuil d'alerte de 0,1. Les deux dimensions géographiques dépassent le seuil : 0,106 pour la ville de l'assuré et 0,138 pour la ville du prestataire. Cela ne prouve pas une discrimination injustifiée (les villes peuvent avoir des profils de risque différents), mais **aucune mitigation n'est encore appliquée** au-delà de l'audit. C'est un point à traiter avant une mise en production à grande échelle.

---

## 8. Dérive

- 60 variables surveillées, 14 exclues pour cause de tendance.
- **45 OK**, **0 vigilance**, **1 alerte**.
- Variable en alerte : `assure_taux_rejet_hist_lisse`, **PSI = 0,3664**.
- Verdict : **`derive_significative`**.

**Lecture.** Une seule variable dérive fortement, mais elle est liée au comportement de rejet des assurés. Il faut vérifier si la dérive est réelle ou liée à un changement de processus de rejet, puis définir un déclencheur de réentraînement. Le reste du modèle est stable.

---

## 9. Robustesse et absence de fuite

| Contrôle | Résultat |
|---|---|
| Cible `cible` dans les variables | **Non** |
| `motif_rejet` dans les variables | **Non** |
| Variables de règles dans les variables | **Aucune** (0 / 60) |
| Chevauchement `facture_id` train/test | **0** |
| Doublons stricts avec date | **0** |
| Chevauchement clés larges (assuré, prestataire, montant) | 1 993 clés, 2 671 lignes test |
| Performance sur clés larges déjà vues | PR-AUC 0,381 ; rappel 0,545 ; précision 0,162 |
| Performance sur clés jamais vues | PR-AUC 0,778 ; rappel 0,796 ; précision 0,452 |
| Assuré jamais vu (604 lignes) | PR-AUC 0,788 ; rappel 0,783 ; précision 0,420 |
| Prestataire jamais vu | 9 lignes, 0 positif — non concluant |

**Lecture.** Il n'y a **aucune fuite directe** : la cible, `motif_rejet` et les 39 variables de règles sont exclues. Les 1 993 clés larges ne sont pas des doublons : elles disparaissent dès qu'on ajoute la date. Ce sont des factures récurrentes (même assuré, même prestataire, même montant), et le modèle y est **moins** performant, pas meilleur. Le chevauchement ne gonfle donc pas les métriques. Le cold start assuré est correct. Le cold start prestataire n'est pas testable (9 lignes).

### Dépendance aux variables (permutation)

| Variable | Baisse de PR-AUC si permutée |
|---|---:|
| `quantite_max_ligne` | 0,129 |
| `nb_lignes_ordonnance` | 0,125 |
| `ratio_montant_moy_hist_prest` | 0,115 |
| `montant_total` | 0,096 |
| `type_ordonnance` | 0,078 |
| `delai_facture_reception_j` | 0,059 |
| `type_facture` | 0,040 |
| `montant_moyen_ligne` | 0,039 |

**Permutation conjointe des 5 premières variables : baisse de PR-AUC de 0,516** (0,754 → 0,238).

**Lecture.** Le modèle repose fortement sur 5 variables, toutes comportementales et légitimes (aucune n'est une règle directe). Ce n'est pas une fuite, mais c'est une **fragilité** : une panne de collecte, un changement de codage ou une dérive sur ces variables ferait chuter la performance. Une variable de secours ou un modèle de repli serait utile.

---

## 10. Lot jury de 20 factures

- 20 factures : 10 positives (5 haute + 5 moyenne confiance) et 10 négatives.
- 15 alertes : 10 TP, 5 FP.
- **Précision = 0,667 ; rappel = 1,000.**

**Lecture.** Le lot est **enrichi volontairement** (50 % de positifs) : il ne mesure pas la précision en production. Il montre que le modèle retrouve les 10 positifs et explicite ses décisions par SHAP. C'est un bon support de jury, pas une validation terrain.

---

## 11. Comparaison aux règles PB-09 à budget égal

| Approche | Alertes | Précision | Rappel | F1 |
|---|---:|---:|---:|---:|
| Règles PB-09 (toutes alertes) | 710 | 0,420 | 0,334 | 0,372 |
| Modèle v2 (top 710) | 710 | **0,813** | **0,646** | **0,720** |
| Modèle v2 (seuil produit) | 1 660 | 0,420 | **0,781** | 0,546 |

**Lecture.** À budget égal (710 alertes), le modèle fait **presque deux fois mieux** que les règles en précision (0,813 vs 0,420) et en rappel (0,646 vs 0,334). C'est le résultat le plus convaincant de l'audit. Au seuil produit, le modèle alerte davantage pour atteindre 78 % de rappel, avec une précision comparable aux règles.

---

## 12. Reproductibilité et tests

- Audit recalculé depuis l'artefact de production et le dataset v2, sans réutiliser `metrics.json`.
- Script : `src/predicare/ml/audit_v2.py`.
- Sorties : `reports/ml/v2/audit_independant.json`, `reports/ml/v2/importance_permutation.csv`.
- Tests ML exécutés : `test_ml_v2.py`, `test_ml_pb09.py`, `test_ml_pb12.py`, `test_ml_pb14.py`, `test_ml_targets.py` → **35 tests passés**.
- Versionnement : `v2.0.0-weak` en production, `v1.1.0` et `v1.0.0` archivées, rollback documenté.
- Limites : `data/` est gitignoré (dataset et labels à régénérer), le jeu de test a déjà servi à plusieurs rapports, et certains tests d'environnement sont dépendants de la machine.

---

## 13. Note détaillée

| Critère | Points max | Note | Justification |
|---|---:|---:|---|
| Performance discriminante | 3 | **3,00** | PR-AUC 0,754 ; ROC 0,903 ; lift 4,91 |
| Rappel / précision / charge | 3 | **2,50** | Rappel 78,1 % à 15,9 % d'alertes ; précision 42 % ; 91,4 % de précision à 5 % ; gaps par type |
| Calibration | 2 | **2,00** | ECE 0,0092 ; Brier 0,0358 ; déciles proches |
| Robustesse / fuites | 3 | **2,50** | Aucune fuite directe, aucun doublon strict, cold start OK ; forte dépendance aux 5 premières variables |
| Équité | 2 | **1,00** | Sexe/âge/formule OK ; 2 dimensions géographiques > 0,1 |
| Dérive / stabilité | 2 | **1,00** | 45 OK, 1 alerte PSI 0,366, verdict significatif |
| Explicabilité | 2 | **1,50** | SHAP par alerte et exemples concrets ; pas de validation humaine des explications |
| Reproductibilité | 1 | **0,75** | Script, graine, registre, rollback, tests ; données non versionnées, test réutilisé |
| Validité de la cible | 2 | **1,00** | Labels faibles, pas de vérité terrain, circularité résiduelle |
| **Total** | **20** | **15,25** | **15/20 arrondi** |

---

## 14. Ce qui ferait monter la note

1. **Audit humain de 100–200 factures stratifiées** (haute, moyenne, candidate) pour estimer la précision réelle et réduire la dépendance aux labels faibles. C'est le levier le plus important (+1 à +2 points).
2. **Améliorer le rappel sur les types faibles** : `PRESTATAIRE_RADIE` (0,456), `ORDONNANCE_EXPIREE` (0,544), `DOUBLON` (0,569), `FRACTIONNEMENT` (0,600). Ajouter des variables ou des règles dédiées, sans les injecter comme features du modèle.
3. **Traiter l'équité géographique** : analyser les écarts par ville, envisager une recalibration par sous-groupe ou documenter une justification métier. (+0,5 à +1)
4. **Traiter la dérive** de `assure_taux_rejet_hist_lisse` : vérifier la cause, définir un seuil de réentraînement, ajouter un modèle de repli. (+0,5)
5. **Réduire la dépendance aux 5 variables** : tester un modèle sans elles, ajouter des variables redondantes, ou prévoir un score de secours. (+0,5)
6. **Choisir un budget opérationnel** (5 % ou 10 %) et calibrer le seuil sur la capacité réelle de l'équipe. Cela améliorerait la précision perçue sans changer le modèle.

---

## 15. Conclusion

Le modèle `v2.0.0-weak` est un **bon modèle de triage**, nettement supérieur aux règles à budget égal, bien calibré, stable et explicable. Il est **apte à une démonstration et à un pilote encadré**, pas encore à une production à grande échelle sans audit humain, mitigation géographique et surveillance de la dérive. **Note : 15/20.**
