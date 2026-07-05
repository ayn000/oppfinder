# OppFinder

OppFinder est une appli de veille d'offres d'emploi et de stages que je fais
tourner sur mon propre serveur. On crée des alertes (mots-clés, lieu, type de
contrat, zone géographique), l'appli interroge plusieurs job boards toutes les
24 h et remonte les annonces classées par pertinence. Un assistant IA
facultatif, basé sur l'API Claude, aide ensuite à décortiquer une offre,
adapter son CV ou préparer l'entretien.

L'objectif était d'avoir quelque chose de léger à auto-héberger : une seule
image Docker, une base SQLite, aucune dépendance lourde. Ça tient sur la plus
petite droplet.

## Ce que ça fait

- Des alertes personnalisées : mots-clés, lieu, contrat (CDI, CDD, stage,
  alternance) et choix des sources à interroger.
- Une recherche multi-pays via Adzuna (19 pays). On choisit la zone comme la France,
  Europe, Amérique du Nord, Amérique latine, Asie-Pacifique, Afrique ou monde
  entier, et le pays s'affiche sur chaque annonce.
- Un score de correspondance de 0 à 100 entre l'annonce et les mots-clés. Un
  mot trouvé dans le titre compte plus que dans la description, et les accents
  sont ignorés.
- Un rafraîchissement automatique toutes les 24 h, plus un bouton pour le
  déclencher à la main.
- Un nettoyage automatique des annonces de plus de 7 jours. Les favoris, eux,
  sont conservés, ce qui garde la base SQLite minuscule.
- Favoris, masquage d'annonces, filtres et recherche côté interface.
- Des comptes privés : pas d'inscription publique, les utilisateurs se créent
  en ligne de commande.

Quatre sources sont branchées : France Travail et Adzuna (clés gratuites à
créer) ainsi que Remotive et Arbeitnow (sans clé).

## Stack technique

Le backend est en FastAPI avec SQLAlchemy sur SQLite. Le front est en
JavaScript vanilla, sans étape de build. Un scheduler interne s'occupe des
rafraîchissements planifiés. L'assistant IA appelle l'API Claude en streaming
et se désactive tout seul quand aucune clé n'est renseignée. Le tout est
packagé dans une image Docker unique.

## Lancer en local

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py create-user demo
uvicorn app.main:app --reload
# http://127.0.0.1:8000
```

## En production

L'appli tourne derrière un reverse proxy nginx avec HTTPS (certificat Let's
Encrypt). Le conteneur n'expose son port qu'en local ; nginx fait le lien avec
l'extérieur.

```bash
cp .env.example .env          # renseigner les clés et passer COOKIE_SECURE=true
docker compose up -d --build
docker compose exec oppfinder python manage.py create-user <nom>
```

## Configuration (`.env`)

| Variable | Défaut | Description |
|---|---|---|
| `COOKIE_SECURE` | `false` | `true` en production (HTTPS) |
| `REFRESH_INTERVAL_HOURS` | `24` | Cadence de mise à jour des alertes |
| `JOB_RETENTION_DAYS` | `7` | Durée de conservation des annonces non favorites |
| `MIN_SCORE` | `10` | Score minimal pour conserver une annonce |
| `FT_CLIENT_ID` / `FT_CLIENT_SECRET` | X | API France Travail (gratuit) |
| `ADZUNA_APP_ID` / `ADZUNA_APP_KEY` | X | API Adzuna (gratuit) |
| `ANTHROPIC_API_KEY` | — | Active l'assistant IA |
| `ANTHROPIC_MODEL` | `claude-opus-4-8` | Modèle utilisé (`claude-haiku-4-5` pour réduire les coûts) |

## Gestion des comptes

```bash
python manage.py create-user <nom> [--name "Prénom"]
python manage.py set-password <nom>
python manage.py delete-user <nom>
python manage.py list-users
```

En production, préfixer ces commandes par `docker compose exec oppfinder`.
