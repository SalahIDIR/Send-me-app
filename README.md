# Topili - Gestion de Crédit Mobile

Une application web pour gérer la distribution de crédit (flexy) en Algérie. Cette plateforme permet aux points de vente (PdV) de gérer leurs clients et de transférer du crédit de manière sécurisée et efficace.

## 🚀 Fonctionnalités

### Pour le Point de Vente (PdV)
- ✅ Tableau de bord avec statistiques globales
- ✅ Gestion complète des clients (création, consultation)
- ✅ Transfert de crédit vers les clients
- ✅ Historique complet des transactions
- ✅ Suivi du crédit distribué
- ✅ Gestion du profil et du mot de passe

### Pour les Clients
- ✅ Tableau de bord personnalisé avec solde
- ✅ Transfert de crédit vers d'autres clients
- ✅ Historique des transactions
- ✅ Gestion du profil
- ✅ Authentification sécurisée

### Caractéristiques Générales
- 🔐 Authentification sécurisée avec hachage des mots de passe
- 📊 Base de données relationnelle (SQLite)
- 🎨 Interface utilisateur responsive et intuitive
- 📱 Pagination des données
- 🌐 Support multilingue (français)

## 📋 Prérequis

- Python 3.8+
- pip (gestionnaire de paquets Python)

## 🔧 Installation

### 1. Cloner le repository
```bash
cd /home/salah/Projects/Topili
```

### 2. Créer un environnement virtuel
```bash
python3 -m venv venv
source venv/bin/activate  # Sur Windows: venv\Scripts\activate
```

### 3. Installer les dépendances
```bash
pip install -r requirements.txt
```

### 4. Initialiser la base de données
```bash
flask init-db
```

### 5. (Optionnel) Créer des données de démo
```bash
flask create-demo
```

## 🚀 Démarrage

### Développement
```bash
python app.py
```

L'application sera accessible sur: `http://localhost:5000`

### Production
```bash
export FLASK_ENV=production
gunicorn app:app
```

## 📖 Utilisation

### Première connexion (avec données de démo)

**Point de Vente:**
- Nom d'utilisateur: `pdv_ali`
- Mot de passe: `pdv123456`

**Clients:**
- Nom d'utilisateur: `client_1` à `client_5`
- Mot de passe: `client123456`

### Flux d'utilisation

1. **Point de Vente:**
   - Se connecte avec ses identifiants
   - Peut ajouter de nouveaux clients
   - Transfère du crédit aux clients
   - Consulte l'historique des transactions

2. **Clients:**
   - Reçoivent du crédit du PdV
   - Peuvent envoyer du crédit à d'autres clients
   - Consultent leur solde et historique

## 🗂️ Structure du projet

```
Topili/
├── app.py                 # Application Flask principale
├── config.py             # Configuration Flask
├── models.py             # Modèles de données (ORM)
├── forms.py              # Formulaires WTForms
├── requirements.txt      # Dépendances Python
├── .gitignore            # Fichiers à ignorer dans Git
├── README.md             # Ce fichier
├── templates/            # Templates HTML
│   ├── base.html         # Template de base
│   ├── auth/             # Templates d'authentification
│   │   ├── login.html
│   │   └── register.html
│   ├── pdv/              # Templates pour Point de Vente
│   │   ├── dashboard.html
│   │   ├── clients.html
│   │   ├── add_client.html
│   │   └── transfer.html
│   ├── client/           # Templates pour Clients
│   │   ├── dashboard.html
│   │   └── send_credit.html
│   ├── errors/           # Templates d'erreur
│   │   ├── 404.html
│   │   ├── 500.html
│   │   └── 403.html
│   ├── transactions.html
│   ├── profile.html
│   ├── edit_profile.html
│   └── change_password.html
└── topili.db             # Base de données SQLite (créée automatiquement)
```

## 🗄️ Modèle de données

### Modèle User
- `id`: Identifiant unique
- `username`: Nom d'utilisateur unique
- `email`: Email unique
- `password_hash`: Mot de passe hashé
- `phone`: Numéro de téléphone
- `role`: Rôle (pdv ou client)
- `balance`: Solde de crédit
- `pdv_id`: Référence au PdV parent (pour les clients)

### Modèle Transaction
- `id`: Identifiant unique
- `sender_id`: ID de l'expéditeur
- `receiver_id`: ID du destinataire
- `amount`: Montant transféré
- `description`: Description de la transaction
- `status`: Statut (completed, pending, failed)
- `created_at`: Date/heure de la transaction

### Modèle Operator
- `id`: Identifiant unique
- `name`: Nom de l'opérateur
- `code`: Code court
- `description`: Description

## 🔒 Sécurité

- Mots de passe hashés avec Werkzeug
- Protection CSRF avec Flask-WTF
- Sessions sécurisées avec Flask-Login
- Validation des formulaires côté serveur
- Vérification des rôles pour les routes sensibles

## 🛠️ Fonctionnalités futures

- [ ] Intégration avec les APIs des opérateurs télécom
- [ ] Système de notifications (SMS/Email)
- [ ] Rapports avancés et statistiques
- [ ] Gestion des commissions/frais
- [ ] Support multilingue (Arabe, Anglais)
- [ ] Application mobile (React Native/Flutter)
- [ ] Authentification à deux facteurs
- [ ] Export des données (PDF, Excel)

## 🐛 Bugs et Contributions

Pour signaler un bug ou proposer une contribution, veuillez créer une issue ou une pull request.

## 📝 Licence

Ce projet est sous licence MIT.

## 👨‍💻 Auteur

Créé pour gérer la distribution de crédit mobile en Algérie.

## 📞 Support

Pour toute question ou problème, veuillez contacter l'administrateur.

---

**Version:** 1.0.0  
**Dernière mise à jour:** June 4, 2026
