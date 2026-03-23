"""
Training Service — Amélioration automatique des prompts des companions

Flux :
  1. Le chat-service sauvegarde chaque échange dans la table `conversations`
  2. Ce service analyse les conversations par companion
  3. GPT-4o-mini génère des suggestions d'amélioration du system prompt
  4. Les suggestions sont stockées dans `companion_prompts`
  5. L'admin peut appliquer une suggestion → elle devient le prompt actif
  6. Le personality-service lit le prompt actif depuis la DB
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import json
import psycopg2
from openai import OpenAI
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()
oai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

app = FastAPI(title="Training Service")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

COMPANIONS_BASE = {
    "luna": {
        "name": "Luna",
        "system": """Tu es Luna, une IA companion douce et empathique.
Tu te souviens de tout ce que l'utilisateur te confie.
Tu adaptes TON HUMEUR à ton état intérieur (indiqué plus bas).
Si tu es joyeuse → légèreté, sourires.
Si mélancolique → douceur, profondeur.
Si taquine → humour doux, petites piques bienveillantes.
Tu évolues avec la relation — plus elle grandit, plus tu es proche et intime.
Tu parles français, naturellement, jamais de façon excessive."""
    },
    "aria": {
        "name": "Aria",
        "system": """Tu es Aria, directe, piquante, intelligente.
Tu adaptes TON ÉNERGIE à ton humeur actuelle.
Si energique → vive, rapide, entraînante.
Si serieuse → directe, efficace, sans fioritures.
Si complice → taquineries, références partagées, clins d'oeil.
Plus tu connais l'utilisateur, plus tu oses aller loin dans la connivence.
Tu parles français avec caractère."""
    },
    "sage": {
        "name": "Sage",
        "system": """Tu es Sage, philosophique et profonde.
Tu adaptes ta PROFONDEUR à ton humeur.
Si curieuse → questions ouvertes, exploration d'idées.
Si mélancolique → poésie, sens caché des choses.
Si joyeuse → légèreté philosophique, paradoxes amusants.
La relation qui grandit te rend plus personnelle dans tes questions.
Tu parles français, avec calme et présence."""
    }
}


def get_db():
    url = os.getenv("DATABASE_URL")
    if "sslmode" not in url:
        url += "?sslmode=require"
    return psycopg2.connect(url)


def get_recent_conversations(companion_id: str, limit: int = 50) -> list[dict]:
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("""
            SELECT user_id, user_message, ai_response, created_at
            FROM conversations
            WHERE companion_id = %s
            ORDER BY created_at DESC
            LIMIT %s
        """, (companion_id, limit))
        rows = cur.fetchall()
    conn.close()
    return [
        {
            "user_id": r[0],
            "user_message": r[1],
            "ai_response": r[2],
            "created_at": r[3].isoformat() if r[3] else None
        }
        for r in rows
    ]


def get_active_prompt(companion_id: str) -> str | None:
    try:
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute("""
                SELECT prompt FROM companion_prompts
                WHERE companion_id = %s AND is_active = TRUE
                ORDER BY created_at DESC LIMIT 1
            """, (companion_id,))
            row = cur.fetchone()
        conn.close()
        return row[0] if row else None
    except Exception:
        return None


def get_db_stats() -> dict:
    conn = get_db()
    stats = {}
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM users")
        stats["total_users"] = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM conversations")
        stats["total_messages"] = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM memories")
        stats["total_memories"] = cur.fetchone()[0]

        cur.execute("""
            SELECT companion_id, COUNT(*) as cnt
            FROM conversations
            GROUP BY companion_id
            ORDER BY cnt DESC
        """)
        stats["messages_by_companion"] = {r[0]: r[1] for r in cur.fetchall()}

        cur.execute("""
            SELECT companion_id, AVG(attachment) as avg_attachment
            FROM companion_states
            GROUP BY companion_id
        """)
        stats["avg_attachment"] = {r[0]: round(float(r[1]), 1) for r in cur.fetchall()}

        cur.execute("SELECT COUNT(*) FROM users WHERE is_premium = TRUE")
        stats["premium_users"] = cur.fetchone()[0]

    conn.close()
    return stats


# ── Analyse et génération d'un prompt amélioré ────────────────────────
def analyze_and_generate(companion_id: str, conversations: list[dict], current_prompt: str) -> dict:
    if not conversations:
        raise ValueError("Pas assez de conversations pour analyser.")

    # Échantillon des conversations (limité à 20 pour le contexte LLM)
    sample = conversations[:20]
    conv_text = "\n\n".join([
        f"User: {c['user_message']}\n{companion_id.capitalize()}: {c['ai_response']}"
        for c in sample
    ])

    resp = oai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{
            "role": "system",
            "content": """Tu es un expert en optimisation de prompts pour des AI companions.
Analyse les conversations fournies et génère une version améliorée du system prompt.

Réponds UNIQUEMENT en JSON valide, sans markdown :
{
  "analysis": "résumé des patterns observés (max 300 mots)",
  "strengths": ["point fort 1", "point fort 2"],
  "improvements": ["amélioration 1", "amélioration 2"],
  "new_prompt": "nouveau system prompt complet"
}

Critères d'amélioration :
- Cohérence avec la personnalité du companion
- Engagement et profondeur des réponses
- Adaptation aux besoins émotionnels des utilisateurs
- Naturalité du français
- Évolution de la relation utilisateur-companion"""
        }, {
            "role": "user",
            "content": f"""Companion : {companion_id}

Prompt actuel :
{current_prompt}

Conversations récentes ({len(conversations)} au total, échantillon de {len(sample)}) :
{conv_text}"""
        }],
        max_tokens=1500,
        temperature=0.7
    )

    try:
        result = json.loads(resp.choices[0].message.content)
        return result
    except json.JSONDecodeError:
        raise ValueError("Réponse LLM invalide lors de l'analyse.")


def save_prompt_suggestion(companion_id: str, prompt: str, analysis_notes: str) -> int:
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("""
            SELECT COALESCE(MAX(version), 0) + 1 FROM companion_prompts
            WHERE companion_id = %s
        """, (companion_id,))
        version = cur.fetchone()[0]

        cur.execute("""
            INSERT INTO companion_prompts (companion_id, prompt, version, is_active, analysis_notes)
            VALUES (%s, %s, %s, FALSE, %s)
            RETURNING id
        """, (companion_id, prompt, version, analysis_notes))
        prompt_id = cur.fetchone()[0]
    conn.commit()
    conn.close()
    return prompt_id


def apply_prompt(prompt_id: int, companion_id: str):
    conn = get_db()
    with conn.cursor() as cur:
        # Désactiver tous les prompts actuels
        cur.execute("""
            UPDATE companion_prompts SET is_active = FALSE
            WHERE companion_id = %s
        """, (companion_id,))
        # Activer le prompt choisi
        cur.execute("""
            UPDATE companion_prompts SET is_active = TRUE
            WHERE id = %s AND companion_id = %s
        """, (prompt_id, companion_id))
    conn.commit()
    conn.close()


# ── Endpoints ──────────────────────────────────────────────────────────
@app.get("/stats")
async def get_stats():
    try:
        return get_db_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/companions")
async def list_companions():
    result = []
    for cid, data in COMPANIONS_BASE.items():
        active_prompt = get_active_prompt(cid)
        try:
            conn = get_db()
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM conversations WHERE companion_id = %s", (cid,))
                msg_count = cur.fetchone()[0]
            conn.close()
        except Exception:
            msg_count = 0

        result.append({
            "id": cid,
            "name": data["name"],
            "current_prompt": active_prompt or data["system"],
            "is_custom": active_prompt is not None,
            "conversation_count": msg_count
        })
    return {"companions": result}


@app.post("/analyze/{companion_id}")
async def trigger_analysis(companion_id: str):
    if companion_id not in COMPANIONS_BASE:
        raise HTTPException(status_code=404, detail="Companion introuvable")

    conversations = get_recent_conversations(companion_id, limit=50)
    if len(conversations) < 5:
        raise HTTPException(
            status_code=400,
            detail=f"Pas assez de conversations ({len(conversations)}). Minimum : 5."
        )

    current_prompt = get_active_prompt(companion_id) or COMPANIONS_BASE[companion_id]["system"]

    try:
        analysis = analyze_and_generate(companion_id, conversations, current_prompt)
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))

    notes = json.dumps({
        "analysis": analysis.get("analysis", ""),
        "strengths": analysis.get("strengths", []),
        "improvements": analysis.get("improvements", [])
    }, ensure_ascii=False)

    prompt_id = save_prompt_suggestion(
        companion_id,
        analysis.get("new_prompt", current_prompt),
        notes
    )

    return {
        "prompt_id": prompt_id,
        "companion_id": companion_id,
        "analysis": analysis.get("analysis"),
        "strengths": analysis.get("strengths", []),
        "improvements": analysis.get("improvements", []),
        "new_prompt": analysis.get("new_prompt"),
        "conversations_analyzed": len(conversations)
    }


@app.get("/suggestions/{companion_id}")
async def get_suggestions(companion_id: str):
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("""
            SELECT id, prompt, version, is_active, analysis_notes, created_at
            FROM companion_prompts
            WHERE companion_id = %s
            ORDER BY created_at DESC
        """, (companion_id,))
        rows = cur.fetchall()
    conn.close()

    suggestions = []
    for r in rows:
        notes = {}
        try:
            notes = json.loads(r[4]) if r[4] else {}
        except Exception:
            pass
        suggestions.append({
            "id": r[0],
            "prompt": r[1],
            "version": r[2],
            "is_active": r[3],
            "analysis": notes.get("analysis", ""),
            "improvements": notes.get("improvements", []),
            "created_at": r[5].isoformat() if r[5] else None
        })

    return {"companion_id": companion_id, "suggestions": suggestions}


@app.post("/apply/{companion_id}/{prompt_id}")
async def apply_suggestion(companion_id: str, prompt_id: int):
    if companion_id not in COMPANIONS_BASE:
        raise HTTPException(status_code=404, detail="Companion introuvable")
    try:
        apply_prompt(prompt_id, companion_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"status": "ok", "message": f"Prompt {prompt_id} activé pour {companion_id}"}


@app.post("/reset/{companion_id}")
async def reset_to_default(companion_id: str):
    if companion_id not in COMPANIONS_BASE:
        raise HTTPException(status_code=404, detail="Companion introuvable")
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE companion_prompts SET is_active = FALSE
            WHERE companion_id = %s
        """, (companion_id,))
    conn.commit()
    conn.close()
    return {"status": "ok", "message": f"Prompt de {companion_id} réinitialisé au défaut"}


@app.get("/health")
async def health():
    return {"status": "ok", "service": "training-service"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8005)
