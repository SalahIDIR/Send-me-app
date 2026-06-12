# Topili — Gestion de Crédit Mobile

Plateforme web de distribution de crédit téléphonique (flexy) en Algérie. Les points de vente rechargent leurs clients ; les clients envoient du crédit vers n'importe quel numéro de téléphone. Un worker autonome sur la machine du PdV exécute physiquement les commandes USSD via un modem GSM.

## Architecture

```text
[Serveur distant — internet]          [Machine PdV — locale]
  Flask + SQLite/PostgreSQL     ◄────  Worker Python
  Interface web                  HTTPS  Modem USB GSM
  API Worker interne                    Envoi USSD
```

## Fonctionnalités

### Point de Vente (PdV)

- Tableau de bord avec statistiques
- Gestion des clients (création, consultation)
- Transfert de crédit vers les clients
- Historique des transactions

### Client

- Tableau de bord avec solde en temps réel
- Envoi de crédit vers un numéro de téléphone (Djezzy, Ooredoo, Mobilis)
- Historique des transactions avec statuts (`pending`, `completed`, `failed`)

### Admin

- Gestion complète des utilisateurs et des soldes
- Vue de toutes les transactions
- Logs d'audit
- Paramètres système

### Sécurité

- Mots de passe hashés (Werkzeug)
- Protection CSRF (Flask-WTF)
- Déduction de solde atomique (protection race condition)
- Token d'idempotence par formulaire (protection double-clic)
- API worker protégée par token secret (`X-Worker-Token`)

## Installation

### Prérequis

- Python 3.10+
- pip

### 1. Environnement virtuel

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configuration

```bash
cp .env.example .env
# Éditer .env : SECRET_KEY et WORKER_TOKEN
```

### 3. Base de données

```bash
flask init-db
flask create-demo   # données de démonstration (optionnel)
```

### 4. Démarrage

```bash
python app.py
# http://localhost:5000
```

## Comptes de démonstration

| Rôle   | Username                | Mot de passe   |
|--------|-------------------------|----------------|
| Admin  | `admin`                 | `admin123456`  |
| PdV    | `pdv_ali`               | `pdv123456`    |
| Client | `client_1` à `client_5` | `client123456` |

## Worker (machine PdV)

Le worker surveille les transactions `pending` et envoie le crédit via le modem USB.

### Configuration (`.env` sur la machine PdV)

```env
TOPILI_SERVER=https://topili.monserveur.com
WORKER_TOKEN=le-meme-token-que-le-serveur
MODEM_PORT=/dev/ttyUSB0
POLL_INTERVAL=10
```

### Démarrage manuel

```bash
python worker.py
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
sudo apt install gammu python3-gammu
# Configurer /etc/gammurc avec le bon port série
```

Sans Gammu installé, le worker tourne en **mode simulation** (utile pour le développement).

## API Worker (interne)

Protégée par le header `X-Worker-Token`.

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| `GET` | `/api/worker/pending` | Retourne les transactions en attente |
| `POST` | `/api/worker/update/<id>` | Met à jour le statut (`completed` ou `failed`) |

### Test rapide

```bash
bash test_worker.sh
```

## Codes USSD par opérateur

| Opérateur | Préfixes | Template USSD |
|-----------|----------|---------------|
| Djezzy    | `06`     | `*222*{phone}*{amount}#` |
| Ooredoo   | `05`     | `*444*{phone}*{amount}#` |
| Mobilis   | `07`     | `*100*{phone}*{amount}#` |

## Structure du projet

```text
Topili/
├── app.py                    # Application Flask + API worker
├── worker.py                 # Worker PdV (modem GSM)
├── config.py                 # Configuration (charge .env)
├── models.py                 # Modèles SQLAlchemy
├── forms.py                  # Formulaires WTForms
├── requirements.txt          # Dépendances Python
├── .env                      # Secrets (non commité)
├── .env.example              # Template de configuration
├── topili-worker.service     # Service systemd pour le worker
├── test_worker.sh            # Script de test de l'API worker
└── templates/
    ├── base.html
    ├── auth/
    ├── pdv/
    ├── client/
    ├── admin/
    └── errors/
```

## Modèle Transaction

| Champ | Type | Description |
|-------|------|-------------|
| `id` | Integer | Identifiant unique |
| `sender_id` | FK User | Expéditeur |
| `receiver_id` | FK User | Destinataire interne |
| `recipient_phone` | String | Numéro externe (envoi crédit) |
| `amount` | Float | Montant en DA |
| `status` | String | `pending` / `completed` / `failed` |
| `description` | String | Description libre |
| `created_at` | DateTime | Horodatage UTC |

## Prochaines étapes

- [ ] Mise à jour automatique du statut dans l'UI (polling JS)
- [ ] Retry automatique dans le worker (3 tentatives avant `failed`)
- [ ] Notification admin quand une transaction passe en `failed`
- [ ] Migration vers PostgreSQL pour la production
- [ ] Rapports et export (PDF, Excel)
- [ ] Support multilingue (Arabe)

---

**Version:** 1.1.0 — **Mise à jour:** Juin 2026
