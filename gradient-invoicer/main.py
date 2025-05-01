"""
Entry-point:  python main.py
Fetches all sessions with Ready_to_Invoice✅ + Invoice_ID blank,
groups by parent & month, creates draft invoices in Stripe, then
writes Invoice_ID back into Airtable.

Env-vars required:
    AIRTABLE_TOKEN, AIRTABLE_BASE_ID, STRIPE_API_KEY, TZ (optional)
"""

import os, sys
from airtable_client import Airtable
from stripe_client   import get_or_create_customer, create_draft_invoice, add_month_item, finalize
from utils.time      import month_label

def env(k):
    v = os.getenv(k)
    if not v:
        sys.exit(f"Missing env var {k}")
    return v

def run():
    at = Airtable(env("AIRTABLE_BASE_ID"), env("AIRTABLE_TOKEN"))
    sessions = at.sessions_to_invoice()
    if not sessions:
        print("Nothing to invoice. Bye!")
        return

    at.enrich_with_student_meta(sessions)
    parents = at.group_by_parent_month(sessions)
    print(f"▶ Found {len(parents)} parent(s), {len(sessions)} session(s)")

    for parent, pdata in parents.items():
        cust_id = get_or_create_customer(parent, pdata["email"])
        inv = create_draft_invoice(cust_id)
        for mkey, mdata in sorted(pdata["months"].items()):
            label = month_label(mkey + "-01")
            unit_pence = round(pdata["rate"] * 100 / 60, 2)
            breakdown = f"{label[:3]}: " + ", ".join(mdata["entries"])
            add_month_item(inv.id, mdata["minutes"], unit_pence, label, breakdown)
        finalize(inv.id)
        at.mark_billed(pdata["airtable_ids"], inv.id)
        print(f"   ✓ {parent}: invoice {inv.id} ({len(pdata['airtable_ids'])} sessions)")

    print("✔ All done!")

if __name__ == "__main__":
    run()
