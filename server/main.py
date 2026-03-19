from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
import stripe
from pydantic import BaseModel
from chain import chat
from memory import ensure_user, get_memory_summary
import uvicorn
from psycopg2 import connect
import os
from payments import create_checkout_session, activate_premium, deactivate_premium, is_premium
from personality import get_state


app = FastAPI(title="Luna Companion API")
# Stockage en mémoire de l'historique (en prod → Redis)
conversation_history: dict[str, list] = {}



class ChatRequest(BaseModel):
    user_id: str
    username: str
    companion_id: str
    message: str          # message déjà déchiffré (le bot s'en charge)
    public_key: str

class ChatResponse(BaseModel):
    reply: str
    companion_name: str
     

@app.post("/chat", response_model=ChatResponse)
async def handle_chat(req: ChatRequest):
    # S'assure que l'user existe en base
    ensure_user(req.user_id, req.username, req.public_key)

    # Récupère l'historique de la conversation
    conv_key = f"{req.user_id}:{req.companion_id}"
    history = conversation_history.get(conv_key, [])

    # Génère la réponse
    reply = chat(req.user_id, req.companion_id, req.message, history)

    # Met à jour l'historique
    history.append({"role": "user",      "content": req.message})
    history.append({"role": "assistant", "content": reply})
    conversation_history[conv_key] = history

    from companions import COMPANIONS
    companion_name = COMPANIONS.get(req.companion_id, {}).get("name", "Luna")
    return ChatResponse(reply=reply, companion_name=companion_name)


@app.get("/memories/{user_id}")
async def get_memories(user_id: str):
    
    grouped = get_memory_summary(user_id)
    return {"memories": grouped}

@app.get("/companion/state/{user_id}/{companion_id}")
async def companion_state(user_id: str, companion_id: str):
    return get_state(user_id, companion_id)


@app.get("/health")
async def health():
    return {"status": "ok"}

  


class CheckoutRequest(BaseModel):
    user_id: str
    username: str

@app.post("/payment/create-checkout")
async def create_checkout(req: CheckoutRequest):
    """Génère un lien de paiement Stripe pour l'utilisateur"""
    url = create_checkout_session(req.user_id, req.username)
    return {"checkout_url": url}

@app.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    """Reçoit les événements Stripe et met à jour la DB"""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload,
            sig_header,
            os.getenv("STRIPE_WEBHOOK_SECRET")
        )
    except stripe.error.SignatureVerificationError:
        return JSONResponse(status_code=400, content={"error": "Invalid signature"})

    # Paiement réussi → active le premium
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        customer_id = session.get("customer")
        if customer_id:
            activate_premium(customer_id)
            print(f"✅ Premium activé pour customer {customer_id}")

    # Abonnement annulé → désactive le premium
    elif event["type"] == "customer.subscription.deleted":
        subscription = event["data"]["object"]
        customer_id = subscription.get("customer")
        if customer_id:
            deactivate_premium(customer_id)
            print(f"❌ Premium désactivé pour customer {customer_id}")

    return {"status": "ok"}

@app.get("/payment/success")
async def payment_success(session_id: str):
    return {"message": "Paiement réussi ! Retourne sur Telegram."}

@app.get("/payment/cancel")
async def payment_cancel():
    return {"message": "Paiement annulé."}

@app.get("/user/{user_id}/premium")
async def check_premium(user_id: str):
    return {"is_premium": is_premium(user_id)}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)