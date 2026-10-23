"""
╔════════════════════════════════════════════════════════════════╗
║        BOT COMMANDES KASSIM — Serveur Flask (Railway)         ║
║                                                                ║
║  Reçoit les commandes de la Mini App et envoie un beau        ║
║  message récapitulatif via Telegram                           ║
╚════════════════════════════════════════════════════════════════╝
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import json
import sqlite3
from datetime import datetime
import os

app = Flask(__name__)
CORS(app)

# ════════════════════════════════════════
#  ⚙️ CONFIGURATION
# ════════════════════════════════════════

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8750946166:AAGfietODi9pF2ZtjBySK2JT69efLQVjsGs")
ADMIN_ID = int(os.getenv("TELEGRAM_ADMIN_ID", "1118152695"))
FIREBASE_URL = os.getenv("FIREBASE_URL", "")  # optionnel si on utilise l'SDK JS côté client

TELEGRAM_API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

# Messages de statut envoyés au client
STATUS_MESSAGES = {
    "accepted": "✅ Ta commande a été <b>acceptée</b> ! On prépare ta livraison 🔥",
    "en_route": "🚗 <b>Kassim est en route !</b> Tu seras livré très bientôt, reste dispo 📍",
    "delivered": "✔️ <b>Commande livrée !</b> Merci pour ta confiance 🙏\nN'hésite pas à laisser un avis ou recommander à tes amis 🤝"
}

# ════════════════════════════════════════
#  💾 BASE DE DONNÉES
# ════════════════════════════════════════

def init_db():
    conn = sqlite3.connect('commandes.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS commandes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id TEXT UNIQUE,
            nom TEXT,
            tel TEXT,
            adresse TEXT,
            quartier TEXT,
            snapchat TEXT,
            articles TEXT,
            total REAL,
            status TEXT DEFAULT 'En attente',
            tg_user_id TEXT,
            tg_message_id INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # Migration: ajouter colonnes manquantes si ancienne DB
    try:
        c.execute("ALTER TABLE commandes ADD COLUMN status TEXT DEFAULT 'En attente'")
    except:
        pass
    try:
        c.execute("ALTER TABLE commandes ADD COLUMN tg_user_id TEXT")
    except:
        pass
    try:
        c.execute("ALTER TABLE commandes ADD COLUMN tg_message_id INTEGER")
    except:
        pass
    conn.commit()
    conn.close()

def sauvegarder_commande(data, tg_message_id=None):
    try:
        conn = sqlite3.connect('commandes.db')
        c = conn.cursor()
        c.execute('''
            INSERT OR IGNORE INTO commandes
            (order_id, nom, tel, adresse, quartier, snapchat, articles, total, tg_user_id, tg_message_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data.get('orderId', data.get('order_id')),
            data.get('name', data.get('nom')),
            data.get('phone', data.get('tel')),
            data.get('address', data.get('addr', data.get('adresse'))),
            data.get('quartier', ''),
            data.get('snapchat', ''),
            json.dumps(data.get('items', data.get('articles', []))),
            data.get('total', 0),
            str(data.get('userId', data.get('tgUserId', ''))),
            tg_message_id
        ))
        conn.commit()
        conn.close()
        print(f"✅ Commande {data.get('orderId')} sauvegardée")
    except Exception as e:
        print(f"❌ Erreur sauvegarde: {e}")

def get_order_by_id(order_id):
    conn = sqlite3.connect('commandes.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM commandes WHERE order_id = ?', (order_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def update_order_status(order_id, status):
    conn = sqlite3.connect('commandes.db')
    c = conn.cursor()
    c.execute('UPDATE commandes SET status = ? WHERE order_id = ?', (status, order_id))
    conn.commit()
    conn.close()

# ════════════════════════════════════════
#  📝 FORMATAGE DES MESSAGES
# ════════════════════════════════════════

def formater_message_mini_app(data):
    total = data.get('total', '?')
    items = data.get('items', [])
    if isinstance(items, list):
        items_str = '\n'.join(f"  • {i}" for i in items) if items else '  —'
    else:
        items_str = f"  {items}" if items else '  —'
    time_slot = data.get('time', '') or 'Dès que possible'
    tg_id = data.get('client_tg_id', '') or '—'
    username = data.get('client_username', '') or '—'
    address = data.get('address', data.get('addr', '')) or '—'
    maps_url = data.get('maps_url', '')
    return f"""🎉 NOUVELLE COMMANDE !

💬 {username}  |  🆔 {tg_id}
🛒 {items_str}
💰 {total} CHF
📍 {address}{f' — <a href="{maps_url}">Maps</a>' if maps_url else ''}
⏰ {time_slot}"""

def build_order_keyboard(order_id):
    """Boutons inline Telegram pour gérer le statut d'une commande"""
    return {
        "inline_keyboard": [[
            {"text": "✅ Accepter", "callback_data": f"status:{order_id}:accepted"},
            {"text": "🚗 En route", "callback_data": f"status:{order_id}:en_route"},
            {"text": "✔️ Livré",    "callback_data": f"status:{order_id}:delivered"}
        ]]
    }

# ════════════════════════════════════════
#  📨 ENVOI DE MESSAGES
# ════════════════════════════════════════

def envoyer_message_telegram(chat_id, message, reply_markup=None):
    url = f"{TELEGRAM_API_URL}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text': message,
        'parse_mode': 'HTML'
    }
    if reply_markup:
        payload['reply_markup'] = json.dumps(reply_markup)
    try:
        resp = requests.post(url, json=payload, timeout=10)
        data = resp.json()
        if resp.status_code == 200 and data.get('ok'):
            msg_id = data.get('result', {}).get('message_id')
            print(f"✅ Message envoyé au chat {chat_id} (msg_id={msg_id})")
            return msg_id
        else:
            print(f"❌ Erreur Telegram: {resp.status_code} - {resp.text}")
            return None
    except Exception as e:
        print(f"❌ Erreur envoi: {e}")
        return None

def edit_message_keyboard(chat_id, message_id, new_text, new_keyboard=None):
    """Modifier un message existant (pour mettre à jour le statut)"""
    url = f"{TELEGRAM_API_URL}/editMessageText"
    payload = {
        'chat_id': chat_id,
        'message_id': message_id,
        'text': new_text,
        'parse_mode': 'HTML'
    }
    if new_keyboard:
        payload['reply_markup'] = json.dumps(new_keyboard)
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"⚠️ edit_message error: {e}")

def answer_callback_query(callback_query_id, text=""):
    """Répondre à un callback query (enlève le loader sur le bouton)"""
    url = f"{TELEGRAM_API_URL}/answerCallbackQuery"
    try:
        requests.post(url, json={
            'callback_query_id': callback_query_id,
            'text': text,
            'show_alert': False
        }, timeout=5)
    except:
        pass

def broadcast_to_all_clients(message_text):
    """Récupère tous les tg_user_id distincts et envoie le message"""
    conn = sqlite3.connect('commandes.db')
    c = conn.cursor()
    c.execute("SELECT DISTINCT tg_user_id FROM commandes WHERE tg_user_id IS NOT NULL AND tg_user_id != '' AND tg_user_id != 'browser'")
    rows = c.fetchall()
    conn.close()
    sent = 0
    failed = 0
    for row in rows:
        uid = row[0]
        try:
            uid_int = int(uid)
            result = envoyer_message_telegram(uid_int, message_text)
            if result:
                sent += 1
            else:
                failed += 1
        except:
            failed += 1
    return sent, failed

# ════════════════════════════════════════
#  🌐 ROUTES
# ════════════════════════════════════════

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        'status': '✅ Serveur Kassim actif',
        'version': '2.0',
        'features': ['commandes', 'chat', 'statuts', 'broadcast']
    })

@app.route('/webhook/telegram', methods=['POST'])
def webhook_telegram():
    """
    Endpoint double usage :
    - Reçoit les update Telegram (callback_query pour les boutons statuts)
    - Reçoit les commandes depuis la Mini App
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Pas de données'}), 400

        # ── Callback query (boutons inline statuts) ──
        if 'callback_query' in data:
            cq = data['callback_query']
            cq_id = cq['id']
            cq_data = cq.get('data', '')
            msg = cq.get('message', {})
            chat_id = msg.get('chat', {}).get('id')
            message_id = msg.get('message_id')

            if cq_data.startswith('status:'):
                parts = cq_data.split(':')
                if len(parts) == 3:
                    _, order_id, new_status = parts
                    order = get_order_by_id(order_id)

                    status_labels = {
                        'accepted': '✅ Acceptée',
                        'en_route': '🚗 En route',
                        'delivered': '✔️ Livrée'
                    }
                    label = status_labels.get(new_status, new_status)

                    # Update DB locale
                    update_order_status(order_id, label)
                    answer_callback_query(cq_id, f"{label} !")

                    # Modifier le message Telegram (remplace les boutons par le statut)
                    original_text = msg.get('text', '')
                    new_text = original_text + f"\n\n<b>Statut: {label}</b>"
                    # Garder les boutons sauf si livré
                    new_kb = None if new_status == 'delivered' else build_order_keyboard(order_id)
                    edit_message_keyboard(chat_id, message_id, new_text, new_kb)

                    # Notifier le client si on a son TG ID
                    if order and order.get('tg_user_id'):
                        try:
                            tg_uid = int(order['tg_user_id'])
                            client_msg = STATUS_MESSAGES.get(new_status, f"Statut: {label}")
                            envoyer_message_telegram(tg_uid, client_msg)
                        except Exception as e:
                            print(f"⚠️ Impossible de notifier le client: {e}")

                    # TODO: mettre à jour Firestore via Firebase Admin SDK
                    # Pour l'instant la mini app lit le statut depuis Firestore
                    # Le webhook reçoit la commande avec l'orderId → on peut appeler l'API REST Firebase

                    return jsonify({'ok': True}), 200

            return jsonify({'ok': True}), 200

        # ── Commande depuis la Mini App ──
        print(f"\n📥 Nouvelle commande: {data.get('orderId')}")

        # Formater le message
        message = formater_message_mini_app(data)
        keyboard = build_order_keyboard(data.get('orderId', data.get('order_id', '?')))

        # Envoyer à l'admin avec les boutons
        msg_id = None
        if ADMIN_ID:
            msg_id = envoyer_message_telegram(ADMIN_ID, message, reply_markup=keyboard)

        # Sauvegarder avec le message_id pour pouvoir éditer plus tard
        sauvegarder_commande(data, tg_message_id=msg_id)

        return jsonify({
            'success': True,
            'orderId': data.get('orderId'),
            'message': 'Commande bien reçue'
        }), 200

    except Exception as e:
        print(f"❌ Erreur webhook: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/chat', methods=['POST'])
def chat_from_client():
    """Relaie un message client vers le DM Telegram de Kassim"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Pas de données'}), 400

        user_id = data.get('userId', 'inconnu')
        name = data.get('name', 'Client')
        text = data.get('text', '')

        msg = f"💬 <b>Message de {name}</b>\n"
        msg += f"<code>ID: {user_id}</code>\n\n"
        msg += f"{text}\n\n"
        msg += f"<i>Réponds via l'admin panel du mini app</i>"

        envoyer_message_telegram(ADMIN_ID, msg)
        return jsonify({'success': True}), 200
    except Exception as e:
        print(f"❌ Erreur chat: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/chat/reply', methods=['POST'])
def chat_reply_to_client():
    """Notifie le client Telegram quand Kassim répond depuis l'admin panel"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Pas de données'}), 400

        tg_user_id = data.get('tgUserId')
        text = data.get('text', '')

        if tg_user_id:
            try:
                msg = f"💬 <b>Kassim_gka</b>\n{text}"
                envoyer_message_telegram(int(tg_user_id), msg)
            except Exception as e:
                print(f"⚠️ Impossible de notifier: {e}")

        return jsonify({'success': True}), 200
    except Exception as e:
        print(f"❌ Erreur chat reply: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/broadcast', methods=['POST'])
def broadcast():
    """
    Envoyer un message à tous les clients depuis l'admin panel
    Body: { "text": "...", "adminSecret": "kassim2024" }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Pas de données'}), 400

        # Vérification simple
        secret = data.get('adminSecret', '')
        admin_secret = os.getenv('ADMIN_SECRET', 'kassim2024')
        if secret != admin_secret:
            return jsonify({'error': 'Non autorisé'}), 403

        text = data.get('text', '').strip()
        if not text:
            return jsonify({'error': 'Message vide'}), 400

        # Ajouter un header promo
        full_msg = f"🔥 <b>Message de Kassim_gka</b>\n\n{text}"

        sent, failed = broadcast_to_all_clients(full_msg)
        print(f"📢 Broadcast: {sent} envoyés, {failed} échecs")

        return jsonify({'success': True, 'sent': sent, 'failed': failed}), 200
    except Exception as e:
        print(f"❌ Erreur broadcast: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/commandes', methods=['GET'])
def lister_commandes():
    try:
        conn = sqlite3.connect('commandes.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute('SELECT * FROM commandes ORDER BY timestamp DESC LIMIT 50')
        rows = c.fetchall()
        conn.close()
        return jsonify({'total': len(rows), 'commandes': [dict(r) for r in rows]}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ════════════════════════════════════════
#  🚀 LANCEMENT
# ════════════════════════════════════════

if __name__ == '__main__':
    print("\n" + "="*50)
    print("🚀 Démarrage du serveur Kassim v2.0")
    print("="*50)
    init_db()
    print("✅ Base de données initialisée")
    print(f"✅ ADMIN_ID = {ADMIN_ID}")
    print(f"\n📡 Routes:")
    print("   POST /webhook/telegram — Commandes + callbacks statuts")
    print("   POST /chat             — Message client → TG admin")
    print("   POST /chat/reply       — Réponse admin → TG client")
    print("   POST /broadcast        — Message à tous les clients")
    print("   GET  /commandes        — Lister les commandes")
    print("\n" + "="*50 + "\n")
    port = int(os.getenv('PORT', 3000))
    app.run(host='0.0.0.0', port=port, debug=False)
