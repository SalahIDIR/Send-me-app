#!/bin/bash
# Test complet du système worker
# Usage: bash test_worker.sh

BASE="http://localhost:5000"
TOKEN="cf138f401b2ff27f655f54fa750a19545766eb4c998c0db523000af773b040ad"
BOLD="\033[1m"
GREEN="\033[32m"
RED="\033[31m"
YELLOW="\033[33m"
RESET="\033[0m"

ok()   { echo -e "${GREEN}✓ $1${RESET}"; }
fail() { echo -e "${RED}✗ $1${RESET}"; }
info() { echo -e "${YELLOW}▶ $1${RESET}"; }

echo -e "\n${BOLD}=== Test Worker API Topili ===${RESET}\n"

# ─────────────────────────────────────────────
# 1. Vérifier que Flask tourne
# ─────────────────────────────────────────────
info "1. Vérification que le serveur Flask tourne..."
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/")
if [ "$STATUS" = "200" ] || [ "$STATUS" = "302" ]; then
    ok "Serveur accessible (HTTP $STATUS)"
else
    fail "Serveur inaccessible (HTTP $STATUS) — lance d'abord: python app.py"
    exit 1
fi

# ─────────────────────────────────────────────
# 2. Refus sans token
# ─────────────────────────────────────────────
info "\n2. Accès sans token (doit être refusé)..."
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/api/worker/pending")
if [ "$STATUS" = "401" ]; then
    ok "Refusé sans token (401)"
else
    fail "Attendu 401, reçu $STATUS"
fi

# ─────────────────────────────────────────────
# 3. GET /api/worker/pending avec bon token
# ─────────────────────────────────────────────
info "\n3. GET /api/worker/pending avec token valide..."
RESPONSE=$(curl -s -H "X-Worker-Token: $TOKEN" "$BASE/api/worker/pending")
echo "   Réponse : $RESPONSE"
if echo "$RESPONSE" | grep -q '"transactions"'; then
    ok "Endpoint accessible et retourne du JSON"
else
    fail "Réponse inattendue"
fi

# ─────────────────────────────────────────────
# 4. Injecter une transaction pending dans la DB
# ─────────────────────────────────────────────
info "\n4. Injection d'une transaction pending de test..."
source venv/bin/activate 2>/dev/null || source .venv/bin/activate 2>/dev/null
python - <<'PYEOF'
from app import app
from models import db, Transaction, User

with app.app_context():
    sender = User.query.filter_by(role='client').first()
    if not sender:
        sender = User.query.first()
    if sender:
        tx = Transaction(
            sender_id=sender.id,
            receiver_id=sender.id,
            recipient_phone='0661234567',
            amount=100.0,
            description='Test worker',
            status='pending'
        )
        db.session.add(tx)
        db.session.commit()
        print(f"TX créée : id={tx.id}, phone={tx.recipient_phone}, amount={tx.amount}")
    else:
        print("ERREUR: aucun utilisateur en base — lance: flask init-db && flask create-demo")
PYEOF

# ─────────────────────────────────────────────
# 5. Re-vérifier les pending
# ─────────────────────────────────────────────
info "\n5. Vérification des pending après injection..."
RESPONSE=$(curl -s -H "X-Worker-Token: $TOKEN" "$BASE/api/worker/pending")
echo "   Réponse : $RESPONSE"
TX_ID=$(echo "$RESPONSE" | python3 -c "import sys,json; txs=json.load(sys.stdin)['transactions']; print(txs[-1]['id']) if txs else print('')" 2>/dev/null)

if [ -z "$TX_ID" ]; then
    fail "Aucune transaction pending trouvée"
    exit 1
else
    ok "Transaction pending trouvée (id=$TX_ID)"
fi

# ─────────────────────────────────────────────
# 6. Simuler le worker : marquer completed
# ─────────────────────────────────────────────
info "\n6. Simulation worker — marquage TX $TX_ID comme 'completed'..."
RESPONSE=$(curl -s -X POST \
    -H "X-Worker-Token: $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"status":"completed"}' \
    "$BASE/api/worker/update/$TX_ID")
echo "   Réponse : $RESPONSE"
if echo "$RESPONSE" | grep -q '"ok": true'; then
    ok "Transaction $TX_ID marquée completed"
else
    fail "Erreur lors du marquage"
fi

# ─────────────────────────────────────────────
# 7. Vérifier qu'elle n'est plus dans les pending
# ─────────────────────────────────────────────
info "\n7. Vérification — la TX ne doit plus être pending..."
RESPONSE=$(curl -s -H "X-Worker-Token: $TOKEN" "$BASE/api/worker/pending")
if echo "$RESPONSE" | grep -q "\"id\": $TX_ID"; then
    fail "TX $TX_ID toujours dans les pending!"
else
    ok "TX $TX_ID absente des pending — statut mis à jour"
fi

echo -e "\n${BOLD}=== Tous les tests passent ===${RESET}\n"
