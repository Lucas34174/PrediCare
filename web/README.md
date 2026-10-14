# PrediCare TPA — interface web

Application React, TypeScript et Vite pour une plateforme de tiers payant santé à Madagascar. Les données d’exemple sont synthétiques.

## Démarrer

Depuis `apps/web` :

- `npm install`
- `npm run dev`
- `npm test`
- `npm run lint`
- `npm run build`

## Configuration

Copiez `.env.example` vers `.env.local` puis ajustez les valeurs :

- `VITE_USE_MOCK=true` utilise les comptes et réponses simulés.
- `VITE_USE_MOCK=false` active les appels HTTP vers `VITE_API_URL`.

Le contrat API utilisé par cette première étape comprend `POST /auth/login`, `GET /dashboard/kpis` et `GET /predictions/latest`. Le jeton est conservé en mémoire et dans `sessionStorage`, jamais dans `localStorage`.

## Comptes de démonstration

Mot de passe commun : `Demo2026!`

- Gestionnaire : `gestionnaire@predicare.mg`
- Professionnel de santé : `sante@predicare.mg`
- Assuré : `assure@predicare.mg`
- Administrateur : `admin@predicare.mg`

Les contrôles de rôle dans l’interface servent à la navigation. L’API doit toujours appliquer les autorisations réelles.
