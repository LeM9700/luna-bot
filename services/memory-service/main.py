from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import json
import psycopg2
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
oai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

app = FastAPI(title="Memory Service")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db():
    url = os.getenv("DATABASE_URL")
    if "sslmode" not in url:
        url += "?sslmode=require"
    return psycopg2.connect(url)


# ── Embeddings ─────────────────────────────────────────────────────────
def get_embedding(text: str) -> list[float]:
    resp = oai.embeddings.create(input=text, model="text-embedding-3-small")
    return resp.data[0].embedding


# ── Analyse intelligente du message ───────────────────────────────────
def analyze_message(message: str) -> dict:
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
- preference : ce qu'il aime/déteste
- emotion : état émotionnel, humeur
- fact : fait personnel (métier, ville, âge, famille)
- goal : objectif, projet, rêve
- relationship : info sur ses proches
- general : autre info utile

Importance :
- 1 : info anecdotique
- 2 : info utile à retenir
- 3 : info critique (prénom, métier, événement majeur)

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


# ── Déduplication ──────────────────────────────────────────────────────
def is_duplicate(user_id: str, summary: str, threshold: float = 0.92) -> bool:
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
    return bool(row and row[0] > threshold)


# ── Sauvegarde intelligente ────────────────────────────────────────────
def smart_save_memory(user_id: str, message: str) -> dict | None:
    analysis = analyze_message(message)
    if not analysis.get("should_save"):
        return None

    summary = analysis.get("summary", message[:100])
    category = analysis.get("category", "general")
    importance = analysis.get("importance", 1)

    if is_duplicate(user_id, summary):
        return None

    embedding = get_embedding(summary)
    metadata = {"category": category, "importance": importance, "original": message[:200]}

    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO memories (user_id, content, embedding, metadata, category, importance)
            VALUES (%s, %s, %s::vector, %s, %s, %s)
            RETURNING id
        """, (user_id, summary, str(embedding), json.dumps(metadata), category, importance))
        memory_id = cur.fetchone()[0]
    conn.commit()
    conn.close()

    return {"id": memory_id, "summary": summary, "category": category}


# ── Recherche sémantique ───────────────────────────────────────────────
def search_memories(user_id: str, query: str, limit: int = 5) -> list[str]:
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
            ORDER BY (1 - (embedding <=> %s::vector)) * importance DESC
            LIMIT %s
        """, (str(query_vec), user_id, str(query_vec), limit))
        rows = cur.fetchall()
    conn.close()
    return [f"[{row[3]}] {row[0]}" for row in rows if row[1] > 0.65]


# ── Résumé groupé ──────────────────────────────────────────────────────
def get_memory_summary(user_id: str) -> dict:
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


# ── Utilisateurs ───────────────────────────────────────────────────────
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


# ── Endpoints ──────────────────────────────────────────────────────────
class EnsureUserRequest(BaseModel):
    user_id: str
    username: str
    public_key: str


class SaveMemoryRequest(BaseModel):
    user_id: str
    message: str


class SearchMemoryRequest(BaseModel):
    user_id: str
    query: str
    limit: int = 5


@app.post("/users/ensure")
async def ensure_user_endpoint(req: EnsureUserRequest):
    ensure_user(req.user_id, req.username, req.public_key)
    return {"status": "ok"}


@app.post("/memories/save")
async def save_memory_endpoint(req: SaveMemoryRequest):
    result = smart_save_memory(req.user_id, req.message)
    return {"saved": result is not None, "memory": result}


@app.post("/memories/search")
async def search_memories_endpoint(req: SearchMemoryRequest):
    memories = search_memories(req.user_id, req.query, req.limit)
    return {"memories": memories}


@app.get("/memories/{user_id}")
async def get_memories_endpoint(user_id: str):
    grouped = get_memory_summary(user_id)
    return {"memories": grouped}


@app.get("/health")
async def health():
    return {"status": "ok", "service": "memory-service"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
