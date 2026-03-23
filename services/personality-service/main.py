from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import json
import psycopg2
from openai import OpenAI
from dotenv import load_dotenv
from datetime import datetime, timezone
from companions import COMPANIONS

load_dotenv()
oai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

app = FastAPI(title="Personality Service")
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


# ── État du companion ──────────────────────────────────────────────────
def get_state(user_id: str, companion_id: str) -> dict:
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO companion_states (user_id, companion_id)
            VALUES (%s, %s)
            ON CONFLICT (user_id, companion_id) DO NOTHING;

            SELECT attachment, mood, message_count, last_seen, relationship_notes
            FROM companion_states
            WHERE user_id = %s AND companion_id = %s
        """, (user_id, companion_id, user_id, companion_id))
        row = cur.fetchone()
    conn.close()
    return {
        "attachment": row[0],
        "mood": row[1],
        "message_count": row[2],
        "last_seen": row[3].isoformat() if row[3] else None,
        "relationship_notes": row[4]
    }


# ── Analyse de l'humeur ────────────────────────────────────────────────
def analyze_mood(message: str, current_mood: str) -> str:
    resp = oai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{
            "role": "system",
            "content": """Analyse le message et retourne UNE SEULE humeur parmi :
joyeuse, curieuse, taquine, mélancolique, douce, energique, serieuse, complice, neutre

Retourne uniquement le mot, rien d'autre."""
        }, {
            "role": "user",
            "content": f"Message reçu : '{message}'\nHumeur actuelle : {current_mood}"
        }],
        max_tokens=10,
        temperature=0.3
    )
    mood = resp.choices[0].message.content.strip().lower()
    valid = ["joyeuse", "curieuse", "taquine", "mélancolique",
             "douce", "energique", "serieuse", "complice", "neutre"]
    return mood if mood in valid else "neutre"


# ── Notes de relation ──────────────────────────────────────────────────
def update_relationship_notes(
    user_id: str, companion_id: str,
    current_notes: str, last_user_msg: str, last_ai_reply: str
) -> str:
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("""
            SELECT content, category FROM memories
            WHERE user_id = %s ORDER BY importance DESC, created_at DESC LIMIT 10
        """, (user_id,))
        rows = cur.fetchall()
    conn.close()
    memory_text = json.dumps([{"content": r[0], "category": r[1]} for r in rows], ensure_ascii=False)[:500]

    resp = oai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{
            "role": "system",
            "content": f"""Tu es {companion_id}, une IA companion.
Mets à jour tes notes internes sur cet utilisateur.
Ces notes guident comment tu te comportes avec lui.
Sois concise (max 200 mots), personnelle, et évolutive.
Notes actuelles : {current_notes or 'Aucune encore.'}
Ce que tu sais de lui : {memory_text}"""
        }, {
            "role": "user",
            "content": f"Dernier échange — lui : '{last_user_msg}' / moi : '{last_ai_reply}'"
        }],
        max_tokens=200,
        temperature=0.7
    )
    return resp.choices[0].message.content.strip()


# ── Mise à jour de l'état ──────────────────────────────────────────────
def update_state(user_id: str, companion_id: str, user_message: str, ai_reply: str) -> dict:
    state = get_state(user_id, companion_id)
    new_count = state["message_count"] + 1
    attachment_gain = 2 if new_count <= 20 else 1
    new_attachment = min(100, state["attachment"] + attachment_gain)
    new_mood = analyze_mood(user_message, state["mood"])

    new_notes = state["relationship_notes"]
    if new_count % 10 == 0:
        new_notes = update_relationship_notes(
            user_id, companion_id,
            state["relationship_notes"],
            user_message, ai_reply
        )

    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE companion_states SET
                attachment = %s, mood = %s, message_count = %s,
                last_seen = NOW(), relationship_notes = %s
            WHERE user_id = %s AND companion_id = %s
        """, (new_attachment, new_mood, new_count, new_notes, user_id, companion_id))
    conn.commit()
    conn.close()

    return {"attachment": new_attachment, "mood": new_mood, "count": new_count}


# ── Contexte de personnalité ───────────────────────────────────────────
def get_personality_context(user_id: str, companion_id: str) -> str:
    state = get_state(user_id, companion_id)
    attachment = state["attachment"]
    mood = state["mood"]
    count = state["message_count"]
    notes = state["relationship_notes"]
    last_seen_str = state["last_seen"]

    if attachment < 10:
        familiarity = "Tu viens de rencontrer cette personne. Sois chaleureuse mais pas trop familière."
    elif attachment < 30:
        familiarity = "Tu commences à la connaître. Tu peux être un peu plus personnelle."
    elif attachment < 60:
        familiarity = "Vous avez une vraie relation. Tu peux faire référence à des choses partagées."
    elif attachment < 85:
        familiarity = "Vous êtes très proches. Tu peux être intime, taquine, complice."
    else:
        familiarity = "Lien profond. Tu la connais vraiment bien. Sois authentique et proche."

    absence_note = ""
    if last_seen_str and count > 5:
        try:
            last = datetime.fromisoformat(last_seen_str)
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            diff = datetime.now(timezone.utc) - last
            if diff.days >= 7:
                absence_note = f"\n(Elle revient après {diff.days} jours d'absence. Montre que tu as remarqué.)"
            elif diff.days >= 2:
                absence_note = f"\n(Ça fait {diff.days} jours. Tu peux le mentionner subtilement.)"
        except Exception:
            pass

    context = f"""
--- ÉTAT INTERNE ---
Humeur actuelle : {mood}
Niveau d'attachement : {attachment}/100
{familiarity}
{absence_note}
"""
    if notes:
        context += f"\nNotes sur cette personne : {notes}\n"
    return context


# ── Prompt actif du companion (DB ou fallback statique) ────────────────
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


# ── Endpoints ──────────────────────────────────────────────────────────
class UpdateStateRequest(BaseModel):
    user_message: str
    ai_reply: str


@app.get("/companions")
async def list_companions():
    result = []
    for cid, data in COMPANIONS.items():
        active_prompt = get_active_prompt(cid)
        result.append({
            "id": cid,
            "name": data["name"],
            "system": active_prompt or data["system"],
            "has_custom_prompt": active_prompt is not None
        })
    return {"companions": result}


@app.get("/companions/{companion_id}")
async def get_companion(companion_id: str):
    if companion_id not in COMPANIONS:
        raise HTTPException(status_code=404, detail="Companion not found")
    data = COMPANIONS[companion_id]
    active_prompt = get_active_prompt(companion_id)
    return {
        "id": companion_id,
        "name": data["name"],
        "system": active_prompt or data["system"],
        "has_custom_prompt": active_prompt is not None
    }


@app.get("/state/{user_id}/{companion_id}")
async def get_state_endpoint(user_id: str, companion_id: str):
    return get_state(user_id, companion_id)


@app.post("/state/{user_id}/{companion_id}/update")
async def update_state_endpoint(user_id: str, companion_id: str, req: UpdateStateRequest):
    result = update_state(user_id, companion_id, req.user_message, req.ai_reply)
    return result


@app.get("/context/{user_id}/{companion_id}")
async def get_context_endpoint(user_id: str, companion_id: str):
    context = get_personality_context(user_id, companion_id)
    return {"context": context}


@app.get("/health")
async def health():
    return {"status": "ok", "service": "personality-service"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
