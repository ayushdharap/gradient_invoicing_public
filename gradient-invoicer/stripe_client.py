"""
Stripe helper – **requires your restricted secret key in STRIPE_API_KEY**.
All invoices are created as DRAFT; change `auto_finalize=True` if you
want Stripe to send immediately.
"""

import os, stripe
from utils.time import month_label

stripe.api_key = os.environ["STRIPE_API_KEY"]

def get_or_create_customer(parent_name, email):
    customers = stripe.Customer.search(
        query=f"name:'{parent_name}' AND email:'{email}'",
        limit=1
    )
    if customers.data:
        return customers.data[0].id
    return stripe.Customer.create(name=parent_name, email=email).id

def create_draft_invoice(customer_id, currency="gbp"):
    return stripe.Invoice.create(customer=customer_id, auto_advance=False, currency=currency)

def add_month_item(inv_id, minutes, unit_pence, label, breakdown):
    stripe.InvoiceItem.create(
        invoice=inv_id,
        currency="gbp",
        quantity=minutes,
        unit_amount_decimal=f"{unit_pence:.2f}",
        description=f"{label} – {minutes/60:.1f} h",
        metadata={"breakdown": breakdown[:250]}
    )

def finalize(inv_id):
    stripe.Invoice.finalize_invoice(inv_id)
