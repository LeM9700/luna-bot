from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import os
import stripe
import psycopg2
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone

load_dotenv()
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

app = FastAPI(title="Payment Service")
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


def create_checkout_session(user_id: str, username: str) -> str:
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("SELECT stripe_customer_id FROM users WHERE id = %s", (user_id,))
        row = cur.fetchone()
    conn.close()

    stripe_customer_id = row[0] if row and row[0] else None

    if not stripe_customer_id:
        customer = stripe.Customer.create(
            metadata={"telegram_id": user_id, "username": username}
        )
        stripe_customer_id = customer.id
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET stripe_customer_id = %s WHERE id = %s",
                (stripe_customer_id, user_id)
            )
        conn.commit()
        conn.close()

    session = stripe.checkout.Session.create(
        customer=stripe_customer_id,
        payment_method_types=["card"],
        line_items=[{"price": os.getenv("STRIPE_PRICE_ID"), "quantity": 1}],
        mode="subscription",
        success_url=f"{os.getenv('APP_URL')}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{os.getenv('APP_URL')}/payment/cancel",
        metadata={"telegram_id": user_id}
    )
    return session.url


def activate_premium(stripe_customer_id: str):
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE users
            SET is_premium = TRUE, premium_until = %s
            WHERE stripe_customer_id = %s
        """, (datetime.now(timezone.utc) + timedelta(days=30), stripe_customer_id))
    conn.commit()
    conn.close()


def deactivate_premium(stripe_customer_id: str):
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE users SET is_premium = FALSE, premium_until = NULL
            WHERE stripe_customer_id = %s
        """, (stripe_customer_id,))
    conn.commit()
    conn.close()


def is_premium(user_id: str) -> bool:
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("SELECT is_premium, premium_until FROM users WHERE id = %s", (user_id,))
        row = cur.fetchone()
    conn.close()
    if not row:
        return False
    is_prem, until = row
    if not is_prem:
        return False
    if until and until < datetime.now(timezone.utc):
        return False
    return True


# ── Endpoints ──────────────────────────────────────────────────────────
class CheckoutRequest(BaseModel):
    user_id: str
    username: str


@app.post("/checkout")
async def create_checkout(req: CheckoutRequest):
    url = create_checkout_session(req.user_id, req.username)
    return {"checkout_url": url}


@app.post("/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, os.getenv("STRIPE_WEBHOOK_SECRET")
        )
    except stripe.error.SignatureVerificationError:
        return JSONResponse(status_code=400, content={"error": "Invalid signature"})

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        customer_id = session.get("customer")
        if customer_id:
            activate_premium(customer_id)

    elif event["type"] == "customer.subscription.deleted":
        subscription = event["data"]["object"]
        customer_id = subscription.get("customer")
        if customer_id:
            deactivate_premium(customer_id)

    return {"status": "ok"}


@app.get("/success")
async def payment_success(session_id: str):
    return {"message": "Paiement réussi ! Retourne sur Telegram."}


@app.get("/cancel")
async def payment_cancel():
    return {"message": "Paiement annulé."}


@app.get("/users/{user_id}/premium")
async def check_premium(user_id: str):
    return {"is_premium": is_premium(user_id)}


@app.get("/health")
async def health():
    return {"status": "ok", "service": "payment-service"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)
