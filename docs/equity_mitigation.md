# Mitigation d'équité — seuils par sous-groupe

> **Statut : proposition documentée, non déployée.** Les seuils sont estimés sur la validation et évalués sur le test. La mitigation doit être confirmée sur une cohorte plus large avant activation.

## Méthode

1. Calcul du TPR global de validation au seuil de production.
2. Pour chaque groupe comptant au moins **10 positifs** en validation, choix du seuil qui ramène son TPR au TPR global.
3. Application des seuils au test et mesure de l'écart résiduel, du rappel, de la précision et du volume d'alertes.

Les groupes sous le seuil de positifs conservent le seuil global : estimer un seuil sur quelques cas produirait des alertes arbitraires.

## Résultats

| Dimension | Écart TPR avant | Écart TPR après | Rappel avant → après | Précision avant → après | Alertes avant → après |
|---|---:|---:|---|---|---|
| sexe | 0.085 | 0.116 | 0.789 → 0.789 | 0.138 → 0.136 | 732 → 740 (+8) |
| tranche_age | 0.198 | 0.217 | 0.789 → 0.789 | 0.138 → 0.140 | 732 → 719 (-13) |
| formule | 0.274 | 0.250 | 0.789 → 0.820 | 0.138 → 0.138 | 732 → 761 (+29) |

## Lecture

**La mitigation ne fonctionne pas de façon fiable sur ce jeu** : 2 dimension(s) sur 3 voient leur écart se dégrader, 1 s'améliore(nt).

- Un écart qui **augmente** après ajustement signifie que le seuil estimé sur la validation ne se transfère pas au test : avec 120 positifs, les seuils par groupe sont trop instables.
- L'écart n'est donc pas seulement un problème de seuil : il peut refléter des différences réelles de distribution entre groupes.
- Le surcoût d'alertes est faible, mais la correction est inefficace : ce n'est pas un bon compromis.

## Limites

- Validation : 120 positifs, répartis en sous-groupes parfois petits.
- Test : 128 positifs ; les intervalles de confiance sont larges.
- Données synthétiques : un écart peut refléter le générateur.
- Un seuil par groupe est une correction **statistique**, pas une réponse aux causes structurelles des inégalités d'accès aux soins.

## Décision recommandée

1. **Ne pas déployer** de seuils par groupe en production : le résultat est négatif sur deux dimensions.
2. Surveiller les TPR par groupe à chaque réentraînement (PB-12).
3. Réévaluer une mitigation (seuil ou recalibration) quand la cohorte dépasse quelques milliers de positifs.
4. Traiter les causes structurelles (accès aux soins, codage) hors du modèle, avec les équipes métier.