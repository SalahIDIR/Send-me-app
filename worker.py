"""
Worker Topili — machine du Point de Vente
Surveille les transactions pending et envoie le crédit via le modem USB.

Configuration via variables d'environnement :
  TOPILI_SERVER   : URL du serveur Flask  (ex: https://topili.monserveur.com)
  WORKER_TOKEN    : Token secret partagé avec le serveur
  MODEM_PORT      : Port série du modem USB (ex: /dev/ttyUSB0)  [optionnel]
  POLL_INTERVAL   : Secondes entre deux vérifications            [défaut: 10]
"""
import os
import time
import logging
import requests
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
log = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────
SERVER_URL     = os.environ.get('TOPILI_SERVER', 'http://localhost:5000').rstrip('/')
WORKER_TOKEN   = os.environ.get('WORKER_TOKEN', 'worker-secret-token-change-in-production')
MODEM_PORT     = os.environ.get('MODEM_PORT', '/dev/ttyUSB0')
POLL_INTERVAL  = int(os.environ.get('POLL_INTERVAL', '10'))

HEADERS = {'X-Worker-Token': WORKER_TOKEN}

# Codes USSD par opérateur (à confirmer avec chaque opérateur)
USSD_TEMPLATES = {
    'djezzy':  '*222*{phone}*{amount}#',
    'ooredoo': '*444*{phone}*{amount}#',
    'mobilis': '*100*{phone}*{amount}#',
}

OPERATOR_PREFIXES = {
    '05': 'ooredoo',
    '06': 'mobilis',
    '07': 'djezzy',
}


# ──────────────────────────────────────────────
# Détection de l'opérateur
# ──────────────────────────────────────────────
def detect_operator(phone: str) -> str | None:
    return OPERATOR_PREFIXES.get(phone[:2])


# ──────────────────────────────────────────────
# Envoi USSD via Gammu
# ──────────────────────────────────────────────
def send_ussd(ussd_code: str) -> dict:
    """
    Envoie un code USSD via le modem branché sur MODEM_PORT.
    Nécessite gammu et python-gammu installés :
        sudo apt install gammu python3-gammu
    Et un fichier /etc/gammurc :
        [gammu]
        port = /dev/ttyUSB0
        connection = at
    """
    try:
        import gammu
        sm = gammu.StateMachine()
        sm.ReadConfig()
        sm.Init()
        response = sm.GetUSSD(ussd_code)
        sm.Terminate()
        log.info("USSD réponse : %s", response)
        return {'ok': True, 'response': str(response)}
    except ImportError:
        log.warning("gammu non installé — mode simulation")
        return {'ok': True, 'response': 'SIMULATION (gammu absent)'}
    except Exception as e:
        log.error("Erreur USSD : %s", e)
        return {'ok': False, 'error': str(e)}


# ──────────────────────────────────────────────
# Traitement d'une transaction
# ──────────────────────────────────────────────
def process_transaction(tx: dict) -> bool:
    tx_id   = tx['id']
    phone   = tx['recipient_phone']
    amount  = int(tx['amount'])

    operator = detect_operator(phone)
    if not operator:
        log.error("TX %d — opérateur inconnu pour le numéro %s", tx_id, phone)
        report_result(tx_id, 'failed')
        return False

    template = USSD_TEMPLATES[operator]
    ussd_code = template.format(phone=phone, amount=amount)
    log.info("TX %d — %s → %s %d DA via %s : %s", tx_id, phone, operator, amount, MODEM_PORT, ussd_code)

    result = send_ussd(ussd_code)
    status = 'completed' if result['ok'] else 'failed'
    report_result(tx_id, status)
    return result['ok']


# ──────────────────────────────────────────────
# Communication avec le serveur Flask
# ──────────────────────────────────────────────
def fetch_pending() -> list:
    try:
        r = requests.get(f'{SERVER_URL}/api/worker/pending', headers=HEADERS, timeout=10)
        r.raise_for_status()
        return r.json().get('transactions', [])
    except Exception as e:
        log.error("Impossible de récupérer les transactions : %s", e)
        return []


def report_result(tx_id: int, status: str):
    try:
        r = requests.post(
            f'{SERVER_URL}/api/worker/update/{tx_id}',
            headers=HEADERS,
            json={'status': status},
            timeout=10,
        )
        r.raise_for_status()
        log.info("TX %d marquée %s", tx_id, status)
    except Exception as e:
        log.error("Impossible de mettre à jour TX %d : %s", tx_id, e)


# ──────────────────────────────────────────────
# Boucle principale
# ──────────────────────────────────────────────
def main():
    log.info("Worker démarré — serveur : %s | intervalle : %ds", SERVER_URL, POLL_INTERVAL)

    while True:
        transactions = fetch_pending()

        if transactions:
            log.info("%d transaction(s) en attente", len(transactions))
            for tx in transactions:
                process_transaction(tx)
        else:
            log.debug("Aucune transaction pending")

        time.sleep(POLL_INTERVAL)


if __name__ == '__main__':
    main()
