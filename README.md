# 🔭 OppFinder

Application privée de veille d'offres d'emploi et de stages, pensée pour être
auto-hébergée sur une petite droplet.

## Fonctionnalités

- **Alertes par mots-clés** : nom, mots-clés, lieu, type de contrat (CDI / CDD / stage / alternance), choix des sources.
- **Zones de recherche internationales** : France, Europe, Amérique du Nord, Amérique latine,
  Asie-Pacifique, Afrique ou Monde entier — via les endpoints multi-pays d'Adzuna (19 pays),
  avec affichage du pays sur chaque annonce.
- **Mise à jour automatique toutes les 24 h** + rafraîchissement manuel.
- **Score de correspondance (0–100)** entre chaque annonce et les mots-clés de l'alerte
  (mot-clé trouvé dans le titre > dans la description, insensible aux accents).
- **Purge automatique** des annonces de plus de 7 jours (les favoris sont conservés) →
  base SQLite minuscule, adaptée à un petit disque.
- **4 sources** : France Travail et Adzuna (clés gratuites), Remotive et Arbeitnow (sans clé).
- **Favoris / masquage** d'annonces, filtres et recherche.
- **Conseiller IA optionnel** (API Claude) : analyse de l'offre, adaptation du CV,
  préparation d'entretien — en streaming, activé par la simple présence d'une clé API.
- **Comptes privés** : création uniquement via CLI, aucune inscription publique.

## Stack

FastAPI · SQLAlchemy · SQLite · vanilla JS (aucun build front) · Docker.

## Démarrage en développement

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py create-user demo
uvicorn app.main:app --reload
# → http://127.0.0.1:8000
```

## Déploiement en production

Voir **[tuto.md](tuto.md)** — guide pas à pas (DNS, Docker, nginx, HTTPS, comptes).

## Configuration (`.env`)

| Variable | Défaut | Description |
|---|---|---|
| `COOKIE_SECURE` | `false` | `true` en production (HTTPS) |
| `REFRESH_INTERVAL_HOURS` | `24` | Cadence de mise à jour des alertes |
| `JOB_RETENTION_DAYS` | `7` | Durée de conservation des annonces non favorites |
| `MIN_SCORE` | `10` | Score minimal pour conserver une annonce |
| `FT_CLIENT_ID` / `FT_CLIENT_SECRET` | — | API France Travail (gratuit) |
| `ADZUNA_APP_ID` / `ADZUNA_APP_KEY` | — | API Adzuna (gratuit) |
| `ANTHROPIC_API_KEY` | — | Active le conseiller IA |
| `ANTHROPIC_MODEL` | `claude-opus-4-8` | Modèle du conseiller (`claude-haiku-4-5` pour réduire les coûts) |

## Gestion des comptes

```bash
python manage.py create-user <nom> [--name "Prénom"]
python manage.py set-password <nom>
python manage.py delete-user <nom>
python manage.py list-users
```

(En production : préfixer par `docker compose exec oppfinder`.)
