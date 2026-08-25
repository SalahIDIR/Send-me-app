"""
Script de seed — remplit la base avec ~300 opérations réalistes pour valider l'UI.

Usage:
    python seed_test.py
    python seed_test.py --reset   # supprime TOUT sauf l'admin, repart de zéro
"""
import sys
import random
from datetime import datetime, timezone, timedelta

# ─── Setup Flask app context ───────────────────────────────────────────────────
from app import app, db
from models import User, Transaction, AuditLog

# ─── Données de test ───────────────────────────────────────────────────────────
OPERATORS = ['djezzy', 'ooredoo', 'mobilis']
OPERATOR_PREFIXES = {'djezzy': '07', 'ooredoo': '05', 'mobilis': '06'}
USSD_TYPES = ['flexy', 'facture']
TX_STATUSES = ['completed', 'completed', 'completed', 'completed', 'failed', 'pending']
AMOUNTS = [50, 100, 100, 150, 200, 300, 500, 1000]
DESCRIPTIONS = [
    'Recharge mensuelle', 'Rechargement urgent', 'Transfert client fidèle',
    'Promotion spéciale', 'Rechargement normal', 'Envoi crédit ami',
]

PDV_USERS = [
    {'username': 'pdv_alger',   'email': 'pdv.alger@topili.dz',   'password': 'pdv123456'},
    {'username': 'pdv_oran',    'email': 'pdv.oran@topili.dz',    'password': 'pdv123456'},
    {'username': 'pdv_constantine', 'email': 'pdv.constantine@topili.dz', 'password': 'pdv123456'},
]

CLIENTS_PER_PDV = [
    # PDV Alger
    [
        {'username': 'karim_b',    'email': 'karim.b@mail.dz',    'phone': '0771234501'},
        {'username': 'amira_s',    'email': 'amira.s@mail.dz',    'phone': '0551234502'},
        {'username': 'youcef_m',   'email': 'youcef.m@mail.dz',   'phone': '0661234503'},
        {'username': 'nadia_r',    'email': 'nadia.r@mail.dz',    'phone': '0771234504'},
        {'username': 'said_t',     'email': 'said.t@mail.dz',     'phone': '0551234505'},
    ],
    # PDV Oran
    [
        {'username': 'farid_k',    'email': 'farid.k@mail.dz',    'phone': '0661234511'},
        {'username': 'leila_d',    'email': 'leila.d@mail.dz',    'phone': '0771234512'},
        {'username': 'mourad_a',   'email': 'mourad.a@mail.dz',   'phone': '0551234513'},
        {'username': 'sonia_h',    'email': 'sonia.h@mail.dz',    'phone': '0661234514'},
    ],
    # PDV Constantine
    [
        {'username': 'bilal_f',    'email': 'bilal.f@mail.dz',    'phone': '0771234521'},
        {'username': 'wafa_c',     'email': 'wafa.c@mail.dz',     'phone': '0551234522'},
        {'username': 'amine_z',    'email': 'amine.z@mail.dz',    'phone': '0661234523'},
        {'username': 'hasna_b',    'email': 'hasna.b@mail.dz',    'phone': '0771234524'},
    ],
]

# Numéros externes (cibles des envois client→téléphone)
EXTERNAL_PHONES = {
    'djezzy':  ['0712345600', '0712345601', '0712345602', '0712345603', '0712345604'],
    'ooredoo': ['0512345600', '0512345601', '0512345602', '0512345603', '0512345604'],
    'mobilis': ['0612345600', '0612345601', '0612345602', '0612345603', '0612345604'],
}


def rnd_date(days_back: int) -> datetime:
    offset = random.randint(0, days_back * 24 * 60)
    return datetime.now(timezone.utc) - timedelta(minutes=offset)


def get_or_create_user(username, email, password, role, pdv=None):
    u = User.query.filter_by(username=username).first()
    if u:
        return u, False
    u = User(username=username, email=email, role=role)
    u.set_password(password)
    if pdv:
        u.pdv_id = pdv.id
    db.session.add(u)
    db.session.flush()
    return u, True


def add_balance(user, djezzy=0, ooredoo=0, mobilis=0):
    user.balance_djezzy  += djezzy
    user.balance_ooredoo += ooredoo
    user.balance_mobilis += mobilis


def make_pdv_to_client_tx(pdv, client, operator, amount, days_back):
    tx = Transaction(
        sender_id=pdv.id,
        receiver_id=client.id,
        operator=operator,
        amount=amount,
        description=random.choice(DESCRIPTIONS),
        status='completed',
        created_at=rnd_date(days_back),
    )
    db.session.add(tx)


def make_client_phone_tx(client, operator, amount, ussd_type, days_back):
    phone = random.choice(EXTERNAL_PHONES[operator])
    status = random.choice(TX_STATUSES)
    tx = Transaction(
        sender_id=client.id,
        receiver_id=client.id,
        operator=operator,
        recipient_phone=phone,
        amount=amount,
        ussd_type=ussd_type,
        description=f'Envoi crédit ({ussd_type}) -> {phone} ({operator.title()})',
        status=status,
        created_at=rnd_date(days_back),
    )
    db.session.add(tx)


def make_audit(user, action, description, status='success', days_back=30):
    log = AuditLog(
        user_id=user.id,
        action=action,
        description=description,
        ip_address=f'192.168.1.{random.randint(1, 254)}',
        status=status,
        created_at=rnd_date(days_back),
    )
    db.session.add(log)


# ─── Main ─────────────────────────────────────────────────────────────────────
def run(reset=False):
    with app.app_context():

        if reset:
            print("🔄  Reset : suppression des transactions, audits, et utilisateurs de test...")
            # Garde l'admin, supprime le reste
            admin = User.query.filter_by(role='admin').first()
            keep_ids = {admin.id} if admin else set()

            Transaction.query.delete()
            AuditLog.query.delete()
            for u in User.query.filter(~User.id.in_(keep_ids)).all():
                db.session.delete(u)
            db.session.commit()
            print("   ✓ Tables nettoyées.")

        print("\n📋  Création des utilisateurs PDV...")
        pdv_list = []
        for data in PDV_USERS:
            pdv, created = get_or_create_user(
                data['username'], data['email'], data['password'], 'pdv'
            )
            # Solde initial généreux pour les tests
            add_balance(pdv, djezzy=50000, ooredoo=50000, mobilis=50000)
            pdv_list.append(pdv)
            print(f"   {'✓ Créé' if created else '→ Existant'} PDV: {pdv.username}")
        db.session.flush()

        print("\n👥  Création des clients...")
        all_clients = []  # [(pdv, client)]
        for i, pdv in enumerate(pdv_list):
            clients_data = CLIENTS_PER_PDV[i] if i < len(CLIENTS_PER_PDV) else []
            for cd in clients_data:
                client, created = get_or_create_user(
                    cd['username'], cd['email'], 'client123', 'client', pdv=pdv
                )
                if cd.get('phone'):
                    client.phone = cd['phone']
                all_clients.append((pdv, client))
                print(f"   {'✓ Créé' if created else '→ Existant'} Client: {client.username} (PDV: {pdv.username})")
        db.session.commit()

        # ── Phase 1 : PDV → Client (transfers internes) ──────────────────────
        print("\n💸  Génération des transferts PDV→Client...")
        count = 0
        for pdv, client in all_clients:
            n = random.randint(8, 18)
            for _ in range(n):
                operator = random.choice(OPERATORS)
                amount   = random.choice(AMOUNTS)
                # PDV débité (déjà initialisé avec large solde, pas besoin de retrancher)
                client.add_balance(amount, operator)
                make_pdv_to_client_tx(pdv, client, operator, amount, days_back=60)
                count += 1

        print(f"   ✓ {count} transferts PDV→Client générés.")

        # ── Phase 2 : Client → Téléphone (envois externes) ───────────────────
        print("\n📱  Génération des envois client→téléphone...")
        count_phone = 0
        for pdv, client in all_clients:
            n = random.randint(10, 25)
            for _ in range(n):
                operator  = random.choice(OPERATORS)
                ussd_type = random.choice(USSD_TYPES)
                amount    = random.choice(AMOUNTS[:5])  # montants raisonnables
                make_client_phone_tx(client, operator, amount, ussd_type, days_back=45)
                count_phone += 1

        print(f"   ✓ {count_phone} envois client→téléphone générés.")

        # ── Phase 3 : Logs d'audit ────────────────────────────────────────────
        print("\n📝  Génération des logs d'audit...")
        count_audit = 0

        # Logins pour chaque PDV
        for pdv in pdv_list:
            for _ in range(random.randint(15, 30)):
                make_audit(pdv, 'LOGIN_SUCCESS', f'Connexion PDV {pdv.username}', days_back=60)
                count_audit += 1
            for _ in range(random.randint(1, 4)):
                make_audit(pdv, 'LOGIN_FAILED', 'Mot de passe incorrect', status='error', days_back=50)
                count_audit += 1
            for _ in range(random.randint(2, 6)):
                make_audit(pdv, 'LOGOUT', f'Déconnexion PDV {pdv.username}', days_back=55)
                count_audit += 1

        # Actions des clients
        for pdv, client in all_clients:
            for _ in range(random.randint(5, 15)):
                make_audit(client, 'LOGIN_SUCCESS', f'Connexion client {client.username}', days_back=45)
                count_audit += 1
            for _ in range(random.randint(0, 2)):
                make_audit(client, 'CLIENT_SEND_FAILED', 'Solde insuffisant', status='warning', days_back=40)
                count_audit += 1
            for _ in range(random.randint(1, 3)):
                make_audit(client, 'PASSWORD_CHANGE', 'Changement de mot de passe', days_back=30)
                count_audit += 1
            for _ in range(random.randint(0, 2)):
                make_audit(client, 'WORKER_REFUND', f'Remboursement automatique — transaction échouée', days_back=20)
                count_audit += 1

        # Actions admin
        admin = User.query.filter_by(role='admin').first()
        if admin:
            for _ in range(random.randint(20, 40)):
                make_audit(admin, 'LOGIN_SUCCESS', 'Connexion admin', days_back=60)
                count_audit += 1
            for pdv in pdv_list:
                amount = random.choice([5000, 10000, 20000, 50000])
                op     = random.choice(OPERATORS)
                make_audit(admin, 'ADMIN_ADJUST_BALANCE',
                           f'Ajustement +{amount} DA {op.title()} pour {pdv.username}', days_back=45)
                count_audit += 1

        print(f"   ✓ {count_audit} entrées d'audit générées.")

        db.session.commit()

        # ── Résumé ────────────────────────────────────────────────────────────
        total_tx    = Transaction.query.count()
        total_audit = AuditLog.query.count()
        total_users = User.query.count()

        print(f"""
╔══════════════════════════════════════╗
║         Seed terminé avec succès     ║
╠══════════════════════════════════════╣
║  Utilisateurs       : {total_users:<15} ║
║  Transactions       : {total_tx:<15} ║
║  Logs d'audit       : {total_audit:<15} ║
╠══════════════════════════════════════╣
║  PDV créés          : {len(pdv_list):<15} ║
║  Clients créés      : {len(all_clients):<15} ║
║  Transf. internes   : {count:<15} ║
║  Envois téléphone   : {count_phone:<15} ║
╚══════════════════════════════════════╝

Comptes PDV (mot de passe: pdv123456) :
""")
        for pdv in pdv_list:
            db.session.refresh(pdv)
            print(f"  {pdv.username:25} | Djezzy: {pdv.balance_djezzy:.0f} DA | "
                  f"Ooredoo: {pdv.balance_ooredoo:.0f} DA | Mobilis: {pdv.balance_mobilis:.0f} DA")
        print()
        print("Comptes clients (mot de passe: client123) :")
        for pdv, client in all_clients:
            db.session.refresh(client)
            print(f"  {client.username:25} | Total: {client.get_total_balance():.0f} DA (PDV: {pdv.username})")


if __name__ == '__main__':
    reset = '--reset' in sys.argv
    run(reset=reset)
