# DEALHost — Architecture d’hébergement modulaire (Django 6 + APISIX + GitHub)

Ce dépôt contient un socle **Django 6 ASGI** (servi par **Granian**) pour exposer une plateforme d’hébergement modulaire reliée au dépôt GitHub **`dealiot/smartappli`** et pilotée via **Apache APISIX**.

## Objectif

- Découper l’hébergement en **modules activables** (`apps.hosting.Module`).
- Synchroniser l’état applicatif avec GitHub (`/api/gateway/github/sync/`).
- Publier dynamiquement les routes APISIX (`/api/gateway/apisix/publish/`).
- Recevoir un webhook GitHub et déclencher un routage (`/api/gateway/github/webhook/`).

## Architecture proposée

```text
GitHub (dealiot/smartappli)
        │
        │ webhook / API
        ▼
Django 6 ASGI + Granian (dealhost)
 ├── apps.hosting  -> registre de modules déployables
 └── apps.gateway  -> orchestration GitHub + APISIX
        │
        │ Admin API
        ▼
Apache APISIX
        │
        ▼
Upstream modules (containers/services Django)
        │
        └── Valkey (cache Redis)
```

## Structure

- `dealhost/settings/` : configuration modulaire (`base`, `dev`, `prod`, `env`).
- `apps/hosting/` : domaine hébergement (modèles, API REST des modules).
- `apps/gateway/` : services d’intégration GitHub + APISIX et endpoints d’orchestration.
- `infra/apisix/` : exemple de route APISIX standalone.

## Endpoints clés

- `GET /api/gateway/health/` : état du service gateway.
- `POST /api/gateway/github/sync/` : récupère le dernier commit d’une branche.
- `POST /api/gateway/apisix/publish/` : crée/met à jour une route APISIX.
- `POST /api/gateway/github/webhook/` : webhook signé GitHub -> publication de route.
- `GET/POST /api/hosting/modules/` : CRUD des modules hébergés.
- `GET/POST /api/hosting/tools/` : CRUD des outils (chaque outil peut lier plusieurs modules).
- `GET/POST /api/hosting/applications/` : CRUD des applications hébergées (chaque application peut lier plusieurs modules).
- `POST /api/hosting/autodiscover/` : auto découverte depuis les manifests tools/apps.
- `GET /hosting/manage/` : interface de gestion (tableaux modules, tools, applications + déclenchement auto découverte).
- `POST /i18n/setlang/` : changement de langue de l’interface de gestion.
- `GET/POST /api/iam/users/` : gestion des utilisateurs (avec groupes/permissions + endpoint `set-password`).
- `GET/POST /api/iam/groups/` : gestion des groupes (rôles) et permissions associées.
- `GET /api/iam/permissions/` : catalogue des permissions Django.
- `GET /iam/manage/` : interface IAM (utilisateurs, groupes, permissions).



### SDK R (tools et applications)

Un SDK R minimal est disponible dans `sdk/r/dealhostR` pour piloter l’API hosting.

Fonctions exposées :
- `dealhost_client(base_url, token)`
- `create_tool(...)`, `update_tool(...)`, `list_tools(...)`
- `create_application(...)`, `update_application(...)`, `list_applications(...)`

Exemple rapide :

```r
# install.packages(c("httr2", "jsonlite"))
source("sdk/r/dealhostR/R/client.R")

client <- dealhost_client("http://localhost:8000", token = "YOUR_TOKEN")

create_tool(
  client,
  name = "Backoffice",
  slug = "backoffice",
  description = "Outil d'administration",
  module_ids = c(1, 2),
  enabled = TRUE
)

create_application(
  client,
  name = "Storefront",
  slug = "storefront",
  description = "Application e-commerce",
  module_ids = c(1),
  enabled = TRUE
)
```

### Auto découverte des tools et applications

- Les manifests de découverte sont lus depuis:
  - `manifests/tools/*.json`
  - `manifests/applications/*.json`
- Champs attendus: `name`, `slug`, `description` (optionnel), `enabled` (optionnel), `module_slugs` (optionnel), `version` (optionnel, semver), `version_notes` (optionnel).
- L’auto découverte crée/met à jour automatiquement les objets `Tool` et `HostedApplication`, synchronise leurs liens modules, et enregistre l'historique des versions quand `version` est fourni.

### Internationalisation de l’interface

- L’interface `/hosting/manage/` est traduisible et propose un sélecteur de langue.
- Langues officielles FAO supportées : **arabe, chinois (simplifié), anglais, français, russe, espagnol**.
- Fichiers de traduction : `locale/<lang>/LC_MESSAGES/django.po`.


### Gestion des versions tools/apps

- Chaque `Tool` et `HostedApplication` expose:
  - `current_version` (version active),
  - `released_at` (date de publication),
  - un historique de versions (`versions`).
- Endpoints de versionning:
  - `GET /api/hosting/tools/{id}/versions/`
  - `POST /api/hosting/tools/{id}/versions/` avec `{ "version": "1.2.3", "notes": "...", "source": "manual" }`
  - `GET /api/hosting/applications/{id}/versions/`
  - `POST /api/hosting/applications/{id}/versions/`
- Filtre de liste disponible: `?current_version=<semver>`.

### Gestion complète des tools/apps

- Filtres disponibles sur les listes:
  - `?enabled=true|false`
  - `?module_slug=<slug>`
  - `?search=<texte>` (nom, slug, description, slug module)
- Actions dédiées:
  - `POST /api/hosting/tools/{id}/attach-module/` avec `{ "module_id": <id> }`
  - `POST /api/hosting/tools/{id}/detach-module/` avec `{ "module_id": <id> }`
  - `GET /api/hosting/tools/{id}/modules/`
  - `POST /api/hosting/applications/{id}/attach-module/` avec `{ "module_id": <id> }`
  - `POST /api/hosting/applications/{id}/detach-module/` avec `{ "module_id": <id> }`
  - `GET /api/hosting/applications/{id}/modules/`

## Démarrage local

1. Copier les variables d’environnement :
   ```bash
   cp .env.example .env
   ```
2. Lancer la stack :
   ```bash
   docker compose up
   ```
3. API servie en ASGI par Granian sur `http://localhost:8000`.
   - le conteneur applique `migrate` + `collectstatic` au démarrage ;
   - `valkey` est démarré avec healthcheck + volume persistant ;
   - APISIX attend que l’API Django soit healthy avant exposition.

## Sécurité et production

- Remplacer toutes les valeurs `replace-me` / placeholders.
- Restreindre `ALLOWED_HOSTS` et exposer uniquement APISIX en edge.
- Protéger le webhook GitHub avec `GITHUB_WEBHOOK_SECRET`.
- Externaliser SQLite vers PostgreSQL en environnement de production.
- Sessions en backend `cached_db` (persistance DB + cache Valkey pour performance).


## Runtime ASGI

- Entrée applicative: `dealhost.asgi:application`.
- Serveur applicatif: `granian --interface asgi dealhost.asgi:application`.
- Le projet est **ASGI-only** et ne contient pas d’entrée WSGI.

## Cache et sessions

- `SESSION_ENGINE=django.contrib.sessions.backends.cached_db` : sessions persistées en base Django.
- `CACHES["default"]` pointe vers Valkey via `VALKEY_URL` (ex: `redis://valkey:6379/1`).
- `ServeStatic` est activé dans le middleware Django et via le storage `CompressedManifestStaticFilesStorage` pour servir les assets statiques en ASGI.

## GitHub Workflows

- `CI Django DEALHost` (`.github/workflows/ci.yml`) : exécute une matrice multi-plateforme (Linux/macOS/Windows) et multi-versions Python (3.12 à 3.14). Le projet cible Python >=3.13 : les jobs 3.12 sont marqués comme non supportés, et les jobs 3.13/3.14 installent avec `uv`, vérifient les migrations, exécutent les tests unitaires (`uv run python manage.py test tests --verbosity 2`) et le contrôle de compilation.
- `Validate APISIX Routes` (`.github/workflows/apisix-routes-validate.yml`) : valide la syntaxe JSON des routes APISIX et vérifie la présence d'une route coeur `module-core`.
- `Pre-commit` (`.github/workflows/pre-commit.yml`) : installe `pre-commit` via `uv` puis exécute `uv run pre-commit run --all-files --show-diff-on-failure` (incluant Ruff en mode `--select ALL` et `ruff-format`).

## Dependency Automation

- `Dependabot` est configuré via `.github/dependabot.yml` pour surveiller chaque semaine les dépendances Python et GitHub Actions.
- `Renovate` est configuré via `renovate.json` avec preset recommandé, regroupement des updates mineures/patch, et label spécifique pour les majors.
