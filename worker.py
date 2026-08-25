"""
Worker Topili — machine du Point de Vente
• Traite les transactions pending via USSD (2 étapes : envoi + confirmation)
• Expose un mini serveur HTTP pour les requêtes "check offers" à la demande

Variables d'environnement (.env) :
  TOPILI_SERVER        : URL du serveur Flask
  WORKER_TOKEN         : Token secret partagé avec Flask

  MODEM_URL_DJEZZY     : URL HiLink modem Djezzy   [défaut: http://192.168.8.1/]
  MODEM_URL_OOREDOO    : URL HiLink modem Ooredoo  [défaut: http://192.168.9.1/]
  MODEM_URL_MOBILIS    : URL HiLink modem Mobilis  [défaut: http://192.168.10.1/]
  MODEM_PIN_DJEZZY / MODEM_PIN_OOREDOO / MODEM_PIN_MOBILIS

  WORKER_HTTP_PORT     : Port du mini serveur HTTP  [défaut: 8080]
  POLL_INTERVAL        : Secondes entre deux polls  [défaut: 10]
  MAX_RETRIES          : Tentatives avant failed    [défaut: 3]
  RETRY_DELAY          : Secondes entre tentatives  [défaut: 5]
  TX_DELAY             : Pause entre transactions   [défaut: 3]
  USSD_WAIT            : Attente réponse USSD       [défaut: 4]
  SIMULATE             : 1 = mode test              [défaut: 0]
"""
import os
import time
import threading
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
SERVER_URL        = os.environ.get('TOPILI_SERVER', 'http://localhost:5000').rstrip('/')
WORKER_TOKEN      = os.environ.get('WORKER_TOKEN', 'worker-secret-token-change-in-production')
WORKER_HTTP_PORT  = int(os.environ.get('WORKER_HTTP_PORT', '8080'))
POLL_INTERVAL     = int(os.environ.get('POLL_INTERVAL', '10'))
MAX_RETRIES       = int(os.environ.get('MAX_RETRIES', '3'))
RETRY_DELAY       = int(os.environ.get('RETRY_DELAY', '5'))
TX_DELAY          = int(os.environ.get('TX_DELAY', '3'))
USSD_WAIT         = int(os.environ.get('USSD_WAIT', '4'))
SIMULATE          = os.environ.get('SIMULATE', '0') == '1'

HEADERS = {'X-Worker-Token': WORKER_TOKEN}

# Un modem HiLink par opérateur
MODEMS = {
    'djezzy': {
        'url': os.environ.get('MODEM_URL_DJEZZY',  'http://192.168.8.1/'),
        'pin': os.environ.get('MODEM_PIN_DJEZZY',  ''),
    },
    'ooredoo': {
        'url': os.environ.get('MODEM_URL_OOREDOO', 'http://192.168.9.1/'),
        'pin': os.environ.get('MODEM_PIN_OOREDOO', ''),
    },
    'mobilis': {
        'url': os.environ.get('MODEM_URL_MOBILIS', 'http://192.168.10.1/'),
        'pin': os.environ.get('MODEM_PIN_MOBILIS', ''),
    },
}

# Un verrou par modem pour éviter les appels USSD simultanés
MODEM_LOCKS = {op: threading.Lock() for op in MODEMS}

# ──────────────────────────────────────────────
# Templates USSD
# ──────────────────────────────────────────────
USSD_TEMPLATES = {
    'djezzy': {
        'flexy': {
            'code':    '*760*{phone}*{amount}*200#',
            'confirm': '1',
        },
        'facture': {
            'code':    '*761*{phone}*{amount}*2008#',
            'confirm': '1',
        },
        'check_offers': '*760*{phone}*2008#',
    },
    'ooredoo': {
        'flexy': {
            'code':    '*580*{phone}*{amount}*2008#',
            'confirm': '1',
        },
        'facture': {
            # Ooredoo facture : remplacer le préfixe 05 par 01
            'code':    '*580*{phone_facture}*{amount}*2008#',
            'confirm': '1',
        },
        'check_offers': '*585*{phone}#',
    },
    'mobilis': {
        # À définir
    },
}

OPERATOR_PREFIXES = {
    '05': 'ooredoo',
    '06': 'mobilis',
    '07': 'djezzy',
}

SUCCESS_KEYWORDS = ['success', 'succès', 'effectué', 'envoyé', 'confirmé',
                    'reussi', 'réussi', 'bien été', 'transféré', 'credit']
FAILURE_KEYWORDS = ['echec', 'échec', 'erreur', 'error', 'insuffisant',
                    'invalid', 'refusé', 'refused', 'failed', 'impossible']


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────
def detect_operator(phone: str) -> str | None:
    return OPERATOR_PREFIXES.get(phone[:2])


def phone_facture(phone: str) -> str:
    """Ooredoo facture : remplace le préfixe 05 par 01."""
    if phone.startswith('05'):
        return '01' + phone[2:]
    return phone


def parse_ussd_response(response: str) -> bool:
    text = response.lower()
    for kw in FAILURE_KEYWORDS:
        if kw in text:
            log.warning("Réponse USSD indique un ÉCHEC : %s", response)
            return False
    for kw in SUCCESS_KEYWORDS:
        if kw in text:
            return True
    log.warning("Réponse USSD non reconnue (supposé ok) : %s", response)
    return True


# ──────────────────────────────────────────────
# Envoi USSD brut (une seule étape)
# ──────────────────────────────────────────────
def _ussd_send_and_get(client, code: str) -> str:
    """Envoie un code USSD et attend la réponse."""
    client.ussd.send(content=code)
    time.sleep(USSD_WAIT)
    return str(client.ussd.get())


# ──────────────────────────────────────────────
# Flexy en 2 étapes (flexy / facture)
# ──────────────────────────────────────────────
def send_flexy(operator: str, phone: str, amount: int, ussd_type: str = 'flexy') -> dict:
    op_templates = USSD_TEMPLATES.get(operator, {})
    template = op_templates.get(ussd_type)

    if not template:
        return {'ok': False, 'error': f'Type "{ussd_type}" non supporté pour {operator}'}

    # Construction du code USSD
    phone_f = phone_facture(phone) if ussd_type == 'facture' else phone
    ussd_code = template['code'].format(phone=phone, phone_facture=phone_f, amount=amount)
    confirm   = template.get('confirm', '1')

    # ── Simulation ──────────────────────────────
    if SIMULATE:
        log.info("[SIM] %s %s — étape 1 : %s", operator.title(), ussd_type, ussd_code)
        time.sleep(0.5)
        log.info("[SIM] Réponse : 'Confirmez-vous ? (1=oui)'")
        log.info("[SIM] étape 2 : %s → 'Transfert OK'", confirm)
        return {'ok': True, 'response': 'SIMULATION OK'}

    # ── Envoi réel ──────────────────────────────
    lock = MODEM_LOCKS[operator]
    try:
        from huawei_lte_api.Connection import Connection
        with lock:
            log.info("Modem %s — USSD étape 1 : %s", operator.title(), ussd_code)
            with Connection(MODEMS[operator]['url']) as conn:
                from huawei_lte_api.Client import Client
                client = Client(conn)
                if MODEMS[operator]['pin']:
                    try:
                        client.pin.operate(operate_type="0", current_pin=MODEMS[operator]['pin'])
                    except Exception:
                        pass

                resp1 = _ussd_send_and_get(client, ussd_code)
                log.info("Réponse étape 1 : %s", resp1)

                resp2 = _ussd_send_and_get(client, confirm)
                log.info("Réponse étape 2 : %s", resp2)

            success = parse_ussd_response(resp2)
            return {'ok': success, 'response': resp2}

    except ImportError:
        return {'ok': False, 'error': 'huawei-lte-api non installé'}
    except Exception as e:
        log.error("Erreur USSD [%s] : %s", operator.title(), e)
        return {'ok': False, 'error': str(e)}


# ──────────────────────────────────────────────
# Vérification des offres (1 seule étape)
# ──────────────────────────────────────────────
def check_offers_ussd(operator: str, phone: str) -> dict:
    op_templates = USSD_TEMPLATES.get(operator, {})
    check_code_tpl = op_templates.get('check_offers')

    if not check_code_tpl:
        return {'ok': False, 'error': f'Vérification offres non disponible pour {operator}'}

    ussd_code = check_code_tpl.format(phone=phone)

    if SIMULATE:
        log.info("[SIM] check_offers %s %s : %s", operator.title(), phone, ussd_code)
        fake = (
            "1. HAYLA BEZZEF 1000 - 1000 DA\n"
            "2. LEGEND 2000 illimité - 2000 DA\n"
            "3. IZZY 50 Da - 50 DA\n"
            "4. Internet 15Go=1000DA - 1000 DA"
        )
        return {'ok': True, 'response': fake, 'operator': operator}

    lock = MODEM_LOCKS[operator]
    try:
        from huawei_lte_api.Connection import Connection
        from huawei_lte_api.Client import Client
        with lock:
            log.info("check_offers %s : %s", operator.title(), ussd_code)
            with Connection(MODEMS[operator]['url']) as conn:
                client = Client(conn)
                if MODEMS[operator]['pin']:
                    try:
                        client.pin.operate(operate_type="0", current_pin=MODEMS[operator]['pin'])
                    except Exception:
                        pass
                response = _ussd_send_and_get(client, ussd_code)
                log.info("Offres %s : %s", operator.title(), response)
                return {'ok': True, 'response': response, 'operator': operator}

    except ImportError:
        return {'ok': False, 'error': 'huawei-lte-api non installé'}
    except Exception as e:
        log.error("Erreur check_offers [%s] : %s", operator.title(), e)
        return {'ok': False, 'error': str(e)}


# ──────────────────────────────────────────────
# Mini serveur HTTP (Option B)
# ──────────────────────────────────────────────
def start_http_server():
    """Démarre un mini serveur Flask pour les requêtes à la demande."""
    from flask import Flask, request, jsonify
    api = Flask('worker_api')

    @api.route('/health', methods=['GET'])
    def health():
        return jsonify({'ok': True, 'simulate': SIMULATE})

    @api.route('/ussd/check-offers', methods=['POST'])
    def api_check_offers():
        # Vérification du token
        if request.headers.get('X-Worker-Token') != WORKER_TOKEN:
            return jsonify({'error': 'Non autorisé'}), 401
        data = request.get_json(silent=True) or {}
        operator = data.get('operator')
        phone    = data.get('phone', '')
        if not operator or not phone:
            return jsonify({'error': 'operator et phone requis'}), 400
        result = check_offers_ussd(operator, phone)
        return jsonify(result), (200 if result['ok'] else 500)

    log.info("Mini serveur HTTP démarré sur le port %d", WORKER_HTTP_PORT)
    # use_reloader=False important pour ne pas créer un 2ème thread de poll
    api.run(host='0.0.0.0', port=WORKER_HTTP_PORT, use_reloader=False, threaded=True)


# ──────────────────────────────────────────────
# Communication avec le serveur Flask
# ──────────────────────────────────────────────
def fetch_pending() -> list:
    try:
        r = requests.get(f'{SERVER_URL}/api/worker/pending', headers=HEADERS, timeout=10)
        r.raise_for_status()
        return r.json().get('transactions', [])
    except Exception as e:
        log.error("fetch_pending : %s", e)
        return []


def claim_transaction(tx_id: int) -> bool:
    try:
        r = requests.post(f'{SERVER_URL}/api/worker/claim/{tx_id}', headers=HEADERS, timeout=10)
        if r.status_code == 409:
            log.warning("TX %d — déjà prise.", tx_id)
            return False
        r.raise_for_status()
        return True
    except Exception as e:
        log.error("claim TX %d : %s", tx_id, e)
        return False


def report_result(tx_id: int, status: str):
    try:
        r = requests.post(
            f'{SERVER_URL}/api/worker/update/{tx_id}',
            headers=HEADERS, json={'status': status}, timeout=10,
        )
        r.raise_for_status()
        log.info("TX %d → %s", tx_id, status)
    except Exception as e:
        log.error("report TX %d : %s", tx_id, e)


# ──────────────────────────────────────────────
# Traitement d'une transaction
# ──────────────────────────────────────────────
def process_transaction(tx: dict) -> bool:
    tx_id     = tx['id']
    phone     = tx['recipient_phone']
    amount    = int(tx['amount'])
    ussd_type = tx.get('ussd_type', 'flexy')

    if not claim_transaction(tx_id):
        return False

    operator = detect_operator(phone)
    if not operator:
        log.error("TX %d — opérateur inconnu pour %s", tx_id, phone)
        report_result(tx_id, 'failed')
        return False

    if operator not in USSD_TEMPLATES or ussd_type not in USSD_TEMPLATES.get(operator, {}):
        log.error("TX %d — type '%s' non supporté pour %s", tx_id, ussd_type, operator)
        report_result(tx_id, 'failed')
        return False

    log.info("TX %d — %s %s %d DA → %s", tx_id, operator.title(), ussd_type, amount, phone)

    for attempt in range(1, MAX_RETRIES + 1):
        result = send_flexy(operator, phone, amount, ussd_type)
        if result['ok']:
            report_result(tx_id, 'completed')
            return True
        log.warning("TX %d — tentative %d/%d : %s", tx_id, attempt, MAX_RETRIES, result.get('error'))
        if attempt < MAX_RETRIES:
            time.sleep(RETRY_DELAY)

    log.error("TX %d — échec définitif.", tx_id)
    report_result(tx_id, 'failed')
    return False


# ──────────────────────────────────────────────
# Boucle principale
# ──────────────────────────────────────────────
def main():
    log.info("Worker démarré — serveur : %s | port HTTP : %d | retries : %d",
             SERVER_URL, WORKER_HTTP_PORT, MAX_RETRIES)
    if SIMULATE:
        log.warning("*** MODE SIMULATION — aucun USSD réel ***")
    else:
        for op, cfg in MODEMS.items():
            log.info("  Modem %-8s : %s", op.title(), cfg['url'])

    # Mini serveur HTTP dans un thread daemon
    http_thread = threading.Thread(target=start_http_server, daemon=True)
    http_thread.start()

    while True:
        transactions = fetch_pending()
        if transactions:
            log.info("%d transaction(s) en attente", len(transactions))
            for tx in transactions:
                process_transaction(tx)
                if TX_DELAY > 0:
                    time.sleep(TX_DELAY)
        else:
            log.debug("Aucune transaction pending")
        time.sleep(POLL_INTERVAL)


if __name__ == '__main__':
    main()
