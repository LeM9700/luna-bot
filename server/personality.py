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

# ── Récupère ou initialise l'état d'un companion ─────────────────────
def get_state(user_id: str, companion_id: str) -> dict:
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO companion_states (user_id, companion_id)
            VALUES (%s, %s)
            ON CONFLICT (user_id, companion_id) DO NOTHING;

            SELECT attachment, mood, message_count,
                   last_seen, relationship_notes
            FROM companion_states
            WHERE user_id = %s AND companion_id = %s
        """, (user_id, companion_id, user_id, companion_id))
        row = cur.fetchone()
    conn.close()

    return {
        "attachment":          row[0],
        "mood":                row[1],
        "message_count":       row[2],
        "last_seen":           row[3],
        "relationship_notes":  row[4]
    }

# ── Met à jour l'état après chaque message ───────────────────────────
def update_state(user_id: str, companion_id: str, user_message: str, ai_reply: str):
    """
    Après chaque échange :
    - Incrémente le compteur
    - Fait évoluer l'humeur
    - Augmente l'attachement progressivement
    - Met à jour les notes de relation si nécessaire
    """
    state = get_state(user_id, companion_id)

    # 1. Nouveau compteur
    new_count = state["message_count"] + 1

    # 2. Attachement : grandit lentement, plafonné à 100
    #    +2 par message jusqu'à 20 msgs, +1 ensuite
    attachment_gain = 2 if new_count <= 20 else 1
    new_attachment  = min(100, state["attachment"] + attachment_gain)

    # 3. Humeur : analysée par le LLM à partir du message user
    new_mood = analyze_mood(user_message, state["mood"])

    # 4. Notes de relation : mise à jour tous les 10 messages
    new_notes = state["relationship_notes"]
    if new_count % 10 == 0:
        new_notes = update_relationship_notes(
            user_id, companion_id,
            state["relationship_notes"],
            user_message, ai_reply
        )

    # 5. Sauvegarde
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE companion_states SET
                attachment         = %s,
                mood               = %s,
                message_count      = %s,
                last_seen          = NOW(),
                relationship_notes = %s
            WHERE user_id = %s AND companion_id = %s
        """, (new_attachment, new_mood, new_count, new_notes, user_id, companion_id))
    conn.commit()
    conn.close()

    return {
        "attachment": new_attachment,
        "mood":       new_mood,
        "count":      new_count
    }

# ── Analyse de l'humeur ───────────────────────────────────────────────
def analyze_mood(message: str, current_mood: str) -> str:
    """Détecte l'humeur à adopter en réponse au message"""
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
    valid = ["joyeuse","curieuse","taquine","mélancolique",
             "douce","energique","serieuse","complice","neutre"]
    return mood if mood in valid else "neutre"

# ── Notes de relation (mise à jour tous les 10 msgs) ─────────────────
def update_relationship_notes(
    user_id: str, companion_id: str,
    current_notes: str, last_user_msg: str, last_ai_reply: str
) -> str:
    """
    Le companion réfléchit à la relation et met à jour
    ses notes internes sur l'utilisateur.
    """
    from memory import get_memory_summary
    memories = get_memory_summary(user_id)
    memory_text = json.dumps(memories, ensure_ascii=False)[:500]

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

# ── Génère le contexte de personnalité pour le prompt ────────────────
def get_personality_context(user_id: str, companion_id: str) -> str:
    """
    Retourne un bloc texte à injecter dans le system prompt
    pour que le companion adapte son comportement.
    """
    state = get_state(user_id, companion_id)
    attachment   = state["attachment"]
    mood         = state["mood"]
    count        = state["message_count"]
    notes        = state["relationship_notes"]

    # Niveau de familiarité selon l'attachement
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

    # Absence : si ça fait longtemps
    absence_note = ""
    if state["last_seen"] and count > 5:
        from datetime import datetime, timezone
        last = state["last_seen"]
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        diff = datetime.now(timezone.utc) - last
        if diff.days >= 7:
            absence_note = f"\n(Elle revient après {diff.days} jours d'absence. Montre que tu as remarqué.)"
        elif diff.days >= 2:
            absence_note = f"\n(Ça fait {diff.days} jours. Tu peux le mentionner subtilement.)"

    # Construction du bloc contexte
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