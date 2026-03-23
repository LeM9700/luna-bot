from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import httpx
import psycopg2
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Chat Service")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

MEMORY_SERVICE_URL = os.getenv("MEMORY_SERVICE_URL", "http://localhost:8002")
PERSONALITY_SERVICE_URL = os.getenv("PERSONALITY_SERVICE_URL", "http://localhost:8003")

llm = ChatOpenAI(
    model="gpt-4o-mini",
    api_key=os.getenv("OPENAI_API_KEY"),
    max_tokens=1000
)

# Historique de conversation en mémoire (→ Redis en prod)
conversation_history: dict[str, list] = {}


def get_db():
    url = os.getenv("DATABASE_URL")
    if "sslmode" not in url:
        url += "?sslmode=require"
    return psycopg2.connect(url)


def save_conversation(user_id: str, companion_id: str, user_message: str, ai_response: str):
    try:
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO conversations (user_id, companion_id, user_message, ai_response)
                VALUES (%s, %s, %s, %s)
            """, (user_id, companion_id, user_message, ai_response))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[Chat] Erreur sauvegarde conversation: {e}")


class ChatRequest(BaseModel):
    user_id: str
    username: str
    companion_id: str
    message: str
    public_key: str


class ChatResponse(BaseModel):
    reply: str
    companion_name: str


@app.post("/chat", response_model=ChatResponse)
async def handle_chat(req: ChatRequest):
    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Assurer que l'utilisateur existe
        await client.post(f"{MEMORY_SERVICE_URL}/users/ensure", json={
            "user_id": req.user_id,
            "username": req.username,
            "public_key": req.public_key
        })

        # 2. Récupérer les souvenirs pertinents
        mem_resp = await client.post(f"{MEMORY_SERVICE_URL}/memories/search", json={
            "user_id": req.user_id,
            "query": req.message,
            "limit": 5
        })
        memories = mem_resp.json().get("memories", [])

        # 3. Récupérer le companion et son prompt
        companion_resp = await client.get(f"{PERSONALITY_SERVICE_URL}/companions/{req.companion_id}")
        companion = companion_resp.json()

        # 4. Récupérer le contexte de personnalité
        context_resp = await client.get(
            f"{PERSONALITY_SERVICE_URL}/context/{req.user_id}/{req.companion_id}"
        )
        personality_ctx = context_resp.json().get("context", "")

    # 5. Construire le system prompt
    memory_block = ""
    if memories:
        memory_block = "\n\nCe que tu sais déjà sur cet utilisateur :\n"
        memory_block += "\n".join(f"- {m}" for m in memories)

    system = companion["system"] + memory_block + personality_ctx

    # 6. Récupérer l'historique et construire les messages
    conv_key = f"{req.user_id}:{req.companion_id}"
    history = conversation_history.get(conv_key, [])

    messages = [SystemMessage(content=system)]
    for h in history[-10:]:
        if h["role"] == "user":
            messages.append(HumanMessage(content=h["content"]))
        else:
            messages.append(AIMessage(content=h["content"]))
    messages.append(HumanMessage(content=req.message))

    # 7. Appel LLM
    response = llm.invoke(messages)
    reply = response.content

    # 8. Mettre à jour l'historique
    history.append({"role": "user", "content": req.message})
    history.append({"role": "assistant", "content": reply})
    conversation_history[conv_key] = history

    # 9. Sauvegarder la conversation pour l'entraînement
    save_conversation(req.user_id, req.companion_id, req.message, reply)

    # 10. Sauvegarder mémoire + mettre à jour l'état (fire & forget)
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            await client.post(f"{MEMORY_SERVICE_URL}/memories/save", json={
                "user_id": req.user_id,
                "message": req.message
            })
            await client.post(
                f"{PERSONALITY_SERVICE_URL}/state/{req.user_id}/{req.companion_id}/update",
                json={"user_message": req.message, "ai_reply": reply}
            )
        except Exception as e:
            print(f"[Chat] Erreur post-traitement: {e}")

    return ChatResponse(reply=reply, companion_name=companion["name"])


@app.get("/health")
async def health():
    return {"status": "ok", "service": "chat-service"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
