import os
import stripe
import psycopg2
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone

load_dotenv()
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

def get_db():
    url = os.getenv("DATABASE_URL")
    if "sslmode" not in url:
        url += "?sslmode=require"
    return psycopg2.connect(url)

def create_checkout_session(user_id: str, username: str) -> str:
    """Crée une session Stripe Checkout et retourne l'URL de paiement"""

    # Cherche ou crée le customer Stripe
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT stripe_customer_id FROM users WHERE id = %s",
            (user_id,)
        )
        row = cur.fetchone()
    conn.close()

    stripe_customer_id = row[0] if row and row[0] else None

    if not stripe_customer_id:
        customer = stripe.Customer.create(
            metadata={"telegram_id": user_id, "username": username}
        )
        stripe_customer_id = customer.id

        # Sauvegarde le customer ID
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET stripe_customer_id = %s WHERE id = %s",
                (stripe_customer_id, user_id)
            )
        conn.commit()
        conn.close()

    # Crée la session de paiement
    session = stripe.checkout.Session.create(
        customer=stripe_customer_id,
        payment_method_types=["card"],
        line_items=[{
            "price": os.getenv("STRIPE_PRICE_ID"),
            "quantity": 1
        }],
        mode="subscription",
        success_url=f"{os.getenv('APP_URL')}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{os.getenv('APP_URL')}/payment/cancel",
        metadata={"telegram_id": user_id}
    )

    return session.url

def activate_premium(stripe_customer_id: str):
    """Active le premium pour un utilisateur après paiement confirmé"""
    

    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE users
            SET is_premium = TRUE,
                premium_until = %s
            WHERE stripe_customer_id = %s
        """, (datetime.now(timezone.utc) + timedelta(days=30), stripe_customer_id))
    conn.commit()
    conn.close()

def deactivate_premium(stripe_customer_id: str):
    """Désactive le premium si l'abonnement est annulé"""
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE users
            SET is_premium = FALSE,
                premium_until = NULL
            WHERE stripe_customer_id = %s
        """, (stripe_customer_id,))
    conn.commit()
    conn.close()

def is_premium(user_id: str) -> bool:
    """Vérifie si un utilisateur est premium"""
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("""
            SELECT is_premium, premium_until
            FROM users WHERE id = %s
        """, (user_id,))
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