# 🌙 Luna Bot

> **Luna** est un bot Telegram de compagnon IA — une expérience de conversation intime et personnalisée, propulsée par LangChain & OpenAI, avec système de mémoire persistante, personnalités multiples et paiements Stripe intégrés.

---

## ✨ Fonctionnalités

- 💬 **Chat IA contextuel** — Conversations naturelles grâce à LangChain + OpenAI GPT
- 🧠 **Mémoire persistante** — L'IA se souvient de toi entre les sessions (stockage PostgreSQL)
- 🎭 **Personnalités multiples** — Plusieurs compagnons disponibles, chacun avec son propre caractère
- 💎 **Abonnement Premium** — Intégration Stripe complète (checkout, webhooks, activation/désactivation)
- 🔐 **Chiffrement end-to-end** — Les messages sont chiffrés côté bot avant envoi au serveur
- 🚀 **Architecture modulaire** — Bot Telegram (Node.js) + API Python (FastAPI) découplés

---

## 🏗️ Architecture

```
luna-bot/
├── bot-server/          # Bot Telegram (Node.js / Telegraf)
│   ├── index.js         # Logique principale du bot
│   ├── crypto.js        # Chiffrement des messages
│   └── api.js           # Client HTTP vers le serveur Python
│
└── server/              # API Backend (Python / FastAPI)
    ├── main.py          # Endpoints REST (chat, paiements, mémoires)
    ├── chain.py         # Pipeline LangChain (génération des réponses)
    ├── memory.py        # Gestion de la mémoire utilisateur (PostgreSQL)
    ├── personality.py   # Système d'états et de personnalité des compagnons
    ├── companions.py    # Définition des compagnons disponibles
    ├── payments.py      # Intégration Stripe
    └── requirements.txt # Dépendances Python
```

---

## 🛠️ Stack Technique

| Composant       | Technologie                          |
|-----------------|--------------------------------------|
| Bot Telegram    | Node.js, Telegraf, node-telegram-bot-api |
| API Backend     | Python, FastAPI, Uvicorn             |
| IA / LLM        | OpenAI GPT, LangChain                |
| Base de données | PostgreSQL (psycopg2)                |
| Paiements       | Stripe (Checkout + Webhooks)         |
| Chiffrement     | Crypto (AES, clés publiques/privées) |

---

## ⚙️ Installation

### Prérequis

- Node.js ≥ 18
- Python ≥ 3.10
- PostgreSQL
- Un compte [Stripe](https://stripe.com)
- Une clé API [OpenAI](https://platform.openai.com)
- Un bot Telegram (via [@BotFather](https://t.me/BotFather))

---

### 1. Cloner le repo

```bash
git clone https://github.com/LeM9700/luna-bot.git
cd luna-bot
```

---

### 2. Lancer le serveur Python (API)

```bash
cd server
pip install -r requirements.txt
```

Crée un fichier `.env` dans `server/` :

```env
OPENAI_API_KEY=sk-...
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
DATABASE_URL=postgresql://user:password@localhost:5432/luna
```

Démarre le serveur :

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

---

### 3. Lancer le bot Telegram (Node.js)

```bash
cd bot-server
npm install
```

Crée un fichier `.env` dans `bot-server/` :

```env
BOT_TOKEN=123456789:AAF...
API_URL=http://localhost:8000
```

Démarre le bot :

```bash
node index.js
```

---

## 📡 API Endpoints

| Méthode | Endpoint                              | Description                            |
|---------|---------------------------------------|----------------------------------------|
| `POST`  | `/chat`                               | Envoie un message, reçoit une réponse IA |
| `GET`   | `/memories/{user_id}`                 | Récupère le résumé mémoire d'un user   |
| `GET`   | `/companion/state/{user_id}/{companion_id}` | État émotionnel du compagnon    |
| `GET`   | `/user/{user_id}/premium`             | Vérifie le statut premium              |
| `POST`  | `/payment/create-checkout`            | Génère un lien Stripe Checkout         |
| `POST`  | `/webhook/stripe`                     | Reçoit les événements Stripe           |
| `GET`   | `/health`                             | Health check                           |

---

## 💳 Fonctionnement des Paiements

1. L'utilisateur demande le premium depuis Telegram
2. Le bot appelle `/payment/create-checkout` → reçoit une URL Stripe
3. L'utilisateur paie via Stripe Checkout
4. Stripe envoie un webhook → `/webhook/stripe`
5. Le serveur active le premium en base de données
6. En cas de résiliation → le webhook `customer.subscription.deleted` désactive le premium automatiquement

---

## 🧠 Système de Mémoire

Luna utilise un système de mémoire à deux niveaux :

- **Historique de session** — Stocké en mémoire vive pendant la conversation
- **Mémoire long terme** — Résumés persistants en PostgreSQL, récupérés à chaque nouvelle session pour donner du contexte à l'IA

---

## 🔐 Chiffrement

Les messages sont chiffrés côté bot (Node.js) avant d'être envoyés à l'API Python. Chaque utilisateur possède une paire de clés. Le serveur reçoit uniquement les messages déjà déchiffrés, garantissant que le transport est sécurisé.

---

## 📄 Licence

Ce projet est sous licence **ISC**.

---

<p align="center">Made with 🌙 by <a href="https://github.com/LeM9700">LeM9700</a></p>
