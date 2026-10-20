"""
╔════════════════════════════════════════════════════════════════╗
║        BOT COMMANDES KASSIM — Serveur Flask (Replit)          ║
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
CORS(app)  # ✅ Activer CORS pour toutes les requêtes

# ════════════════════════════════════════
#  ⚙️ CONFIGURATION — Depuis variables d'environnement
# ════════════════════════════════════════

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8750946166:AAFAYR8urNauJEaNnlBSyWx3rPUSNfcFEyY")
ADMIN_ID = int(os.getenv("TELEGRAM_ADMIN_ID", "1118152695"))

# URL de base pour les API Telegram
TELEGRAM_API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

# ════════════════════════════════════════
#  💾 BASE DE DONNÉES
# ════════════════════════════════════════

def init_db():
    """Créer la table SQLite pour sauvegarder les commandes"""
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
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def sauvegarder_commande(data):
    """Sauvegarder une commande en base de données"""
    try:
        conn = sqlite3.connect('commandes.db')
        c = conn.cursor()
        c.execute('''
            INSERT INTO commandes (order_id, nom, tel, adresse, quartier, snapchat, articles, total)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data.get('orderId'),
            data.get('nom'),
            data.get('tel'),
            data.get('adresse'),
            data.get('quartier'),
            data.get('snapchat'),
            json.dumps(data.get('articles', [])),
            data.get('total')
        ))
        conn.commit()
        conn.close()
        print(f"✅ Commande {data.get('orderId')} sauvegardée en base de données")
    except sqlite3.IntegrityError:
        print(f"⚠️ Commande {data.get('orderId')} déjà existante")
    except Exception as e:
        print(f"❌ Erreur lors de la sauvegarde : {e}")

# ════════════════════════════════════════
#  📝 FORMATAGE DES MESSAGES
# ════════════════════════════════════════

def formater_message_commande(data):
    """
    Formater une commande en un beau message Telegram
    """
    nom = data.get('nom', '?')
    tel = data.get('tel', '?')
    adresse = data.get('adresse', '?')
    quartier = data.get('quartier', '?')
    snapchat = data.get('snapchat', 'Non fourni')
    notes = data.get('notes', '')
    articles = data.get('articles', [])
    total = data.get('total', 0)
    order_id = data.get('orderId', '?')
    timestamp = datetime.now().strftime('%d/%m/%Y à %H:%M')

    # Construire la liste des articles
    articles_text = ""
    for idx, article in enumerate(articles, 1):
        variante = article.get('variante', 'N/A')
        prix_unitaire = article.get('prix', 0)
        qte = article.get('qte', 0)
        montant = article.get('total', 0)

        articles_text += f"  {idx}. {article.get('nom')} ({variante})\n"
        articles_text += f"     {prix_unitaire} CHF × {qte} = <b>{montant:.2f} CHF</b>\n"

    # Construire le message final
    message = f"""<b>🎉 NOUVELLE COMMANDE !</b>
<code>━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</code>

<b>👤 CLIENT</b>
  Nom: <b>{nom}</b>
  Tél: <b>{tel}</b>
  Snapchat: <b>{snapchat}</b>

<b>📍 LIVRAISON</b>
  Adresse: <b>{adresse}</b>
  Quartier: <b>{quartier}</b>
{f'  📝 Notes: {notes}' if notes else ''}

<b>🛒 ARTICLES</b>
{articles_text}
<code>━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</code>

<b>💰 RÉSUMÉ</b>
  Sous-total: <b>{total:.2f} CHF</b>
  Livraison: <b>OFFERTE 🎁</b>
  <b>TOTAL: {total:.2f} CHF</b>

💵 Paiement: <b>Espèces à la livraison</b>

<code>━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</code>

📌 N° Commande: <code>{order_id}</code>
⏰ {timestamp}
"""

    return message

# ════════════════════════════════════════
#  📨 ENVOI DE MESSAGES
# ════════════════════════════════════════

def envoyer_message_telegram(chat_id, message):
    """
    Envoyer un message via Telegram Bot API
    """
    url = f"{TELEGRAM_API_URL}/sendMessage"

    payload = {
        'chat_id': chat_id,
        'text': message,
        'parse_mode': 'HTML'
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            print(f"✅ Message envoyé au chat {chat_id}")
            return True
        else:
            print(f"❌ Erreur Telegram: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Erreur lors de l'envoi: {e}")
        return False

# ════════════════════════════════════════
#  🌐 ROUTES
# ════════════════════════════════════════

@app.route('/', methods=['GET'])
def home():
    """Page d'accueil"""
    return jsonify({
        'status': '✅ Serveur Kassim actif',
        'version': '1.0',
        'message': 'Webhook Telegram configuré et prêt à recevoir les commandes'
    })

@app.route('/webhook/telegram', methods=['POST'])
def webhook_telegram():
    """
    Endpoint Telegram WebApp
    Reçoit les données de commande depuis la Mini App
    """
    try:
        # Récupérer les données JSON
        data = request.get_json()

        if not data:
            return jsonify({'error': 'Pas de données reçues'}), 400

        print(f"\n📥 Nouvelle commande reçue: {data.get('orderId')}")
        print(f"   Client: {data.get('nom')}")
        print(f"   Total: {data.get('total')} CHF")

        # Sauvegarder en base de données
        sauvegarder_commande(data)

        # Formater le message
        message = formater_message_commande(data)

        # Envoyer au créateur (admin)
        if ADMIN_ID == 0:
            print("⚠️  ADMIN_ID non configuré - message non envoyé")
            print("   Configure ton ID Telegram dans le code pour recevoir les notifications")
        else:
            envoyer_message_telegram(ADMIN_ID, message)

        # Répondre à la Mini App
        return jsonify({
            'success': True,
            'orderId': data.get('orderId'),
            'message': 'Commande bien reçue'
        }), 200

    except Exception as e:
        print(f"❌ Erreur webhook: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/commandes', methods=['GET'])
def lister_commandes():
    """
    Endpoint pour lister toutes les commandes sauvegardées
    Utile pour vérifier que tout fonctionne
    """
    try:
        conn = sqlite3.connect('commandes.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute('SELECT * FROM commandes ORDER BY timestamp DESC LIMIT 50')
        rows = c.fetchall()
        conn.close()

        commandes = [dict(row) for row in rows]
        return jsonify({
            'total': len(commandes),
            'commandes': commandes
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ════════════════════════════════════════
#  🚀 LANCEMENT
# ════════════════════════════════════════

if __name__ == '__main__':
    print("\n" + "="*50)
    print("🚀 Démarrage du serveur Kassim")
    print("="*50)

    # Initialiser la base de données
    init_db()
    print("✅ Base de données initialisée")

    # Afficher les infos importantes
    print(f"\n⚙️  Configuration:")
    if ADMIN_ID == 0:
        print(f"   ⚠️  ADMIN_ID = 0 (À configurer!)")
    else:
        print(f"   ✅ ADMIN_ID = {ADMIN_ID}")
    print(f"   ✅ BOT_TOKEN configuré")

    print(f"\n📡 Endpoint webhook:")
    print(f"   POST /webhook/telegram")

    print(f"\n📊 Endpoints disponibles:")
    print(f"   GET  / — État du serveur")
    print(f"   GET  /commandes — Lister les commandes")
    print(f"   POST /webhook/telegram — Recevoir une commande")

    print("\n" + "="*50)
    print("✅ Serveur prêt ! En attente de commandes...")
    print("="*50 + "\n")

    # Lancer le serveur
    port = int(os.getenv('PORT', 3000))  # ✅ Railway assigne le port dynamiquement
    app.run(host='0.0.0.0', port=port, debug=False)
