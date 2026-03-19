import os
import json
import psycopg2
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
oai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def get_db():
    url = os.getenv("DATABASE_URL")
    if "sslmode" not in url:
        url += "?sslmode=require"
    return psycopg2.connect(url)

# ── Embeddings ────────────────────────────────────────────────────────
def get_embedding(text: str) -> list[float]:
    resp = oai.embeddings.create(
        input=text,
        model="text-embedding-3-small"
    )
    return resp.data[0].embedding

# ── Analyse intelligente du message ──────────────────────────────────
def analyze_message(message: str) -> dict:
    """
    Utilise le LLM pour détecter si un message contient
    une info mémorisable, sa catégorie et son importance.
    Retourne un dict structuré.
    """
    resp = oai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{
            "role": "system",
            "content": """Tu es un extracteur d'informations pour un AI companion.
Analyse le message et réponds UNIQUEMENT en JSON valide, sans markdown.

Format de réponse :
{
  "should_save": true/false,
  "category": "preference|emotion|fact|goal|relationship|general",
  "importance": 1/2/3,
  "summary": "résumé concis de l'info à retenir (max 100 chars)"
}

Catégories :
- preference : ce qu'il aime/déteste (musique, nourriture, activités ou autres préférences)
- emotion : état émotionnel, humeur, ressenti ou changement d'humeur
- fact : fait personnel (métier, ville, âge, famille ou autre info factuelle sur sa vie ou sa personnalité)
- goal : objectif, projet, rêve ou aspiration exprimé
- relationship : info sur ses proches ou relations (amis, famille, collègues, etc.)
- general : autre info utile

Importance :
- 1 : info anecdotique
- 2 : info utile à retenir
- 3 : info critique (prénom, métier, événement majeur ou info récurrente)

Ne sauvegarde PAS : salutations, questions générales, small talk."""
        }, {
            "role": "user",
            "content": message
        }],
        max_tokens=150,
        temperature=0
    )

    try:
        return json.loads(resp.choices[0].message.content)
    except json.JSONDecodeError:
        return {"should_save": False}

# ── Déduplication ─────────────────────────────────────────────────────
def is_duplicate(user_id: str, summary: str, threshold: float = 0.92) -> bool:
    """
    Vérifie si un souvenir très similaire existe déjà.
    Seuil 0.92 = très similaire (évite les doublons stricts)
    """
    embedding = get_embedding(summary)
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("""
            SELECT 1 - (embedding <=> %s::vector) AS similarity
            FROM memories
            WHERE user_id = %s
            ORDER BY embedding <=> %s::vector
            LIMIT 1
        """, (str(embedding), user_id, str(embedding)))
        row = cur.fetchone()
    conn.close()

    if row and row[0] > threshold:
        return True
    return False

# ── Sauvegarde intelligente ───────────────────────────────────────────
def smart_save_memory(user_id: str, message: str) -> dict | None:
    """
    Analyse le message, décide si on sauvegarde,
    déduplique, puis stocke avec métadonnées enrichies.
    Retourne le souvenir sauvegardé ou None.
    """
    # 1. Analyse avec le LLM
    analysis = analyze_message(message)

    if not analysis.get("should_save"):
        return None

    summary   = analysis.get("summary", message[:100])
    category  = analysis.get("category", "general")
    importance = analysis.get("importance", 1)

    # 2. Déduplication
    if is_duplicate(user_id, summary):
        print(f"[Memory] Doublon détecté, skip : {summary[:50]}")
        return None

    # 3. Sauvegarde avec vecteur
    embedding = get_embedding(summary)
    metadata  = {
        "category":   category,
        "importance": importance,
        "original":   message[:200]
    }

    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO memories
                (user_id, content, embedding, metadata, category, importance)
            VALUES (%s, %s, %s::vector, %s, %s, %s)
            RETURNING id
        """, (
            user_id, summary, str(embedding),
            json.dumps(metadata), category, importance
        ))
        memory_id = cur.fetchone()[0]
    conn.commit()
    conn.close()

    print(f"[Memory] ✅ Sauvegardé [{category}] importance={importance} : {summary[:60]}")
    return {"id": memory_id, "summary": summary, "category": category}

# ── Recherche sémantique enrichie ─────────────────────────────────────
def search_memories(user_id: str, query: str, limit: int = 5) -> list[str]:
    """
    Recherche les souvenirs les plus pertinents.
    Priorise les souvenirs à haute importance.
    """
    query_vec = get_embedding(query)
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("""
            SELECT content,
                   1 - (embedding <=> %s::vector) AS similarity,
                   importance,
                   category
            FROM memories
            WHERE user_id = %s
            ORDER BY
                (1 - (embedding <=> %s::vector)) * importance DESC
            LIMIT %s
        """, (str(query_vec), user_id, str(query_vec), limit))
        rows = cur.fetchall()
    conn.close()

    # Filtre par pertinence minimale
    return [
        f"[{row[3]}] {row[0]}"
        for row in rows
        if row[1] > 0.65
    ]

# ── Résumé des souvenirs ──────────────────────────────────────────────
def get_memory_summary(user_id: str) -> dict:
    """
    Retourne les souvenirs groupés par catégorie.
    Utilisé pour la commande /memory du bot.
    """
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("""
            SELECT content, category, importance, created_at
            FROM memories
            WHERE user_id = %s
            ORDER BY importance DESC, created_at DESC
            LIMIT 20
        """, (user_id,))
        rows = cur.fetchall()
    conn.close()

    grouped = {}
    for content, category, importance, created_at in rows:
        if category not in grouped:
            grouped[category] = []
        grouped[category].append(content)

    return grouped

# ── Utilisateurs ──────────────────────────────────────────────────────
def ensure_user(user_id: str, username: str, public_key: str):
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO users (id, username, public_key)
            VALUES (%s, %s, %s)
            ON CONFLICT (id) DO NOTHING
        """, (user_id, username, public_key))
    conn.commit()
    conn.close()