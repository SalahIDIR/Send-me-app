# Topili — Gestion de Crédit Mobile (Flexy)

Plateforme web de distribution de crédit téléphonique (flexy) en Algérie. Les points de vente rechargent leurs clients ; les clients envoient du crédit vers n'importe quel numéro de téléphone. Un worker autonome sur la machine du PdV exécute physiquement les commandes USSD via trois modems HiLink (un par opérateur).

## Architecture

```text
┌─────────────────────────────────┐      Tailscale VPN      ┌──────────────────────────────────────────┐
│     Serveur distant (cloud)     │ ◄────────────────────── │         Mini PC local (PdV)              │
│                                 │                          │                                          │
│  Flask + SQLite                 │  HTTPS / API Worker      │  worker.py  ──►  Modem USB Djezzy        │
│  Interface web (3 rôles)        │                          │             ──►  Modem USB Ooredoo       │
│  API Worker interne             │                          │             ──►  Modem USB Mobilis       │
│                                 │ ◄────────────────────── │  Mini HTTP :8080  (check-offers)         │
└─────────────────────────────────┘                          └──────────────────────────────────────────┘
```

**Modems :** Huawei E3372h en mode HiLink (API HTTP `192.168.x.1`) — bibliothèque `huawei-lte-api`, pas de port série.  
**VPN :** Tailscale pour que le serveur atteigne le mini serveur HTTP du worker.

## Fonctionnalités

### Point de Vente (PdV)

- Tableau de bord : soldes par opérateur, statistiques, transactions récentes
- Gestion des clients (création, consultation, pagination)
- Transfert de crédit multi-opérateurs vers les clients (Djezzy / Ooredoo / Mobilis)
- Historique complet des transactions

### Client

- Tableau de bord avec solde en temps réel par opérateur
- Envoi de crédit vers un numéro de téléphone
  - **Type Flexy** — recharge standard
  - **Type Paiement Facture** — paiement de facture opérateur
  - Détection automatique de l'opérateur via le préfixe du numéro
  - Bouton **Vérifier les offres** — interroge l'opérateur via USSD en temps réel
- Historique des transactions avec statuts colorés

### Admin

- Gestion complète des utilisateurs et ajustement des soldes
- Vue de toutes les transactions (filtres par statut / opérateur)
- Logs d'audit couvrant toutes les actions de l'application
- Paramètres système et gestion des opérateurs

### Worker

- Polling des transactions `pending` toutes les 10 secondes
- Exécution USSD en **2 étapes** : envoi du code → attente → confirmation `"1"` → lecture résultat
- **3 modems indépendants** — un par opérateur, un verrou par modem (pas de collision)
- Réclamation atomique (`claimed_at`) — protection anti double-traitement en cas de plusieurs instances
- Remboursement automatique du solde si la transaction passe en `failed`
- Récupération des transactions bloquées (`processing` > 5 min → retour en `pending`)
- Mini serveur HTTP sur le port 8080 pour les requêtes à la demande (`check-offers`)
- **Mode simulation** (`SIMULATE=1`) — pour développer sans modems branchés

### Sécurité

- Mots de passe hashés (Werkzeug)
- Protection CSRF (Flask-WTF)
- Déduction de solde atomique (protection race condition SQL)
- Token d'idempotence par formulaire (protection double-clic / double-submit)
- API worker protégée par token secret (`X-Worker-Token`)
- Mini serveur HTTP worker protégé par le même token

## Installation

### Prérequis

- Python 3.10+

### 1. Environnement virtuel

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configuration

```bash
cp .env.example .env
# Éditer .env : SECRET_KEY et WORKER_TOKEN obligatoires
```

### 3. Base de données

```bash
flask init-db
flask create-demo      # optionnel : compte admin + pdv de démo
flask migrate-db       # ajoute les colonnes manquantes sur une DB existante
```

### 4. Démarrage

```bash
python app.py
# Accessible sur http://localhost:5000
```

### 5. Données de test (développement)

```bash
python seed_test.py           # insère ~400 transactions + 330 logs d'audit
python seed_test.py --reset   # repart de zéro (garde l'admin)
```

## Comptes de démonstration

| Rôle   | Username                                      | Mot de passe |
|--------|-----------------------------------------------|--------------|
| Admin  | `admin`                                       | `admin123456` |
| PdV    | `pdv_alger`, `pdv_oran`, `pdv_constantine`    | `pdv123456`  |
| Client | `karim_b`, `amira_s`, `youcef_m`, …           | `client123`  |

## Worker (machine PdV)

### Configuration (`.env` sur la machine PdV)

```env
TOPILI_SERVER=https://topili.monserveur.com   # URL du serveur Flask
WORKER_TOKEN=le-meme-token-que-le-serveur

# URLs HiLink de chaque modem (adapter selon vos adresses réseau)
MODEM_URL_DJEZZY=http://192.168.8.1/
MODEM_URL_OOREDOO=http://192.168.9.1/
MODEM_URL_MOBILIS=http://192.168.10.1/

# PIN SIM (laisser vide si aucun)
MODEM_PIN_DJEZZY=
MODEM_PIN_OOREDOO=
MODEM_PIN_MOBILIS=

WORKER_HTTP_PORT=8080    # port du mini serveur HTTP
POLL_INTERVAL=10         # secondes entre deux polls
MAX_RETRIES=3            # tentatives avant de marquer failed
RETRY_DELAY=5            # secondes entre tentatives
USSD_WAIT=4              # secondes d'attente après envoi USSD
SIMULATE=0               # mettre à 1 pour développer sans modems
```

### Démarrage manuel

```bash
python worker.py

# Mode simulation (sans modems) :
SIMULATE=1 python worker.py
```

### Installation comme service systemd

```bash
sudo cp topili-worker.service /etc/systemd/system/
sudo systemctl enable topili-worker
sudo systemctl start topili-worker
sudo journalctl -u topili-worker -f   # logs en direct
```

### Dépendances modem (production)

```bash
pip install huawei-lte-api
```

Les modems Huawei E3372h doivent être en **mode HiLink** (interface web sur `192.168.x.1`), pas en mode stick/AT.

## Codes USSD par opérateur

| Opérateur | Préfixes | Flexy | Paiement Facture | Vérifier offres |
|-----------|----------|-------|-----------------|-----------------|
| Djezzy    | `07`     | `*760*{num}*{montant}*200#` + confirm `1` | `*761*{num}*{montant}*2008#` + confirm `1` | `*760*{num}*2008#` |
| Ooredoo   | `05`     | `*580*{num}*{montant}*2008#` + confirm `1` | `*580*{num_01}*{montant}*2008#` + confirm `1` | `*585*{num}#` |
| Mobilis   | `06`     | À définir | À définir | À définir |

> **Ooredoo Facture** : le préfixe `05` du numéro est remplacé par `01` dans le code USSD.

## API Worker (interne)

Toutes les routes sont protégées par le header `X-Worker-Token`.

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| `GET`  | `/api/worker/pending` | Transactions en attente (inclut `ussd_type`) |
| `POST` | `/api/worker/claim/<id>` | Réclame atomiquement une transaction (→ `processing`) |
| `POST` | `/api/worker/update/<id>` | Met à jour le statut (`completed` ou `failed`) |
| `POST` | `/api/check-offers` | Proxy vers le mini serveur HTTP du worker |

### Mini serveur HTTP du worker (port 8080)

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| `GET`  | `/health` | Ping / statut simulation |
| `POST` | `/ussd/check-offers` | Lance un USSD et retourne les offres disponibles |

### Exemple de test

```bash
# Transactions pending
curl -H "X-Worker-Token: mon-token" http://localhost:5000/api/worker/pending

# Offres disponibles (via le mini serveur du worker)
curl -X POST http://localhost:8080/ussd/check-offers \
  -H "X-Worker-Token: mon-token" \
  -H "Content-Type: application/json" \
  -d '{"operator": "djezzy", "phone": "0712345678"}'
```

## Modèle Transaction

| Champ | Type | Description |
|-------|------|-------------|
| `id` | Integer | Identifiant unique |
| `sender_id` | FK User | Expéditeur |
| `receiver_id` | FK User | Destinataire interne |
| `recipient_phone` | String | Numéro externe (envoi flexy) |
| `operator` | String | `djezzy` / `ooredoo` / `mobilis` |
| `amount` | Float | Montant en DA |
| `ussd_type` | String | `flexy` ou `facture` |
| `status` | String | `pending` / `processing` / `completed` / `failed` |
| `claimed_at` | DateTime | Horodatage de réclamation par le worker (anti double-traitement) |
| `description` | String | Description libre |
| `created_at` | DateTime | Horodatage UTC (affiché en UTC+1 dans l'UI) |

## Structure du projet

```text
Topili/
├── app.py                    # Application Flask + API worker
├── worker.py                 # Worker PdV (3 modems HiLink + mini HTTP server)
├── config.py                 # Configuration (charge .env)
├── models.py                 # Modèles SQLAlchemy
├── forms.py                  # Formulaires WTForms
├── seed_test.py              # Script de peuplement pour les tests
├── requirements.txt          # Dépendances Python
├── .env                      # Secrets (non commité)
├── .env.example              # Template de configuration
├── topili-worker.service     # Service systemd pour le worker
└── templates/
    ├── base_pdv.html         # Template de base universel (sidebar par rôle)
    ├── auth/                 # Login, inscription
    ├── pdv/                  # Dashboard, clients, transfert
    ├── client/               # Dashboard, envoi crédit
    ├── admin/                # Dashboard, utilisateurs, audit, rapports…
    └── errors/               # 403, 404, 500
```

## Prochaines étapes

- [ ] Définir les codes USSD Mobilis
- [ ] Mise à jour automatique du statut dans l'UI (polling JS ou SSE)
- [ ] Notification admin quand une transaction passe en `failed`
- [ ] Export rapports (PDF / Excel)
- [ ] Migration vers PostgreSQL pour la production
- [ ] Support multilingue (Arabe / Tamazight)

---

**Version :** 1.2.0 — **Mise à jour :** Août 2026
