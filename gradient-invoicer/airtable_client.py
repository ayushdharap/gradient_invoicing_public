"""
Tiny Airtable wrapper (no external deps beyond `requests`).

Assumes a table **Billed Now** with at least these fields:
    - Date                (ISO string)
    - Duration            (number, hours as float)
    - Student             (link – used only for lookup of parent info)
    - Ready_to_Invoice    (checkbox)
    - Invoice_ID          (text)
Studentmetadata table must contain:
    - Student_Name  (primary)
    - Parent_Name
    - Parent_Email
    - Hourly_Rate  (number, GBP)
"""

import os, requests
from collections import defaultdict
from utils.time import month_key

AIRTABLE_API = "https://api.airtable.com/v0"

class Airtable:
    def __init__(self, base_id: str, token: str):
        self.base = base_id
        self.headers = {"Authorization": f"Bearer {token}"}

    # ---------- Low-level ----------
    def _list(self, table: str, params=None):
        url = f"{AIRTABLE_API}/{self.base}/{table}"
        out, offset = [], None
        while True:
            p = params.copy() if params else {}
            if offset:
                p["offset"] = offset
            r = requests.get(url, headers=self.headers, params=p, timeout=20)
            r.raise_for_status()
            payload = r.json()
            out.extend(payload["records"])
            offset = payload.get("offset")
            if not offset:
                break
        return out

    def _batch_update(self, table: str, records):
        url = f"{AIRTABLE_API}/{self.base}/{table}"
        for chunk in (records[i:i+10] for i in range(0, len(records), 10)):
            r = requests.patch(url, headers=self.headers, json={"records": chunk}, timeout=20)
            r.raise_for_status()

    # ---------- Public helpers ----------
    def sessions_to_invoice(self):
        view = "To Invoice NOW"   # pre-filtered view (Ready_to_Invoice ✅ & Invoice_ID empty)
        return self._list("Billed Now", {"view": view})

    def enrich_with_student_meta(self, sessions):
        # Collect unique student record IDs
        student_ids = {sid for s in sessions for sid in (s["fields"].get("Student") or [])}
        if not student_ids:
            return sessions

        students = self._list("Studentmetadata", {"filterByFormula":
            "OR(" + ",".join(f"RECORD_ID()='{sid}'" for sid in student_ids) + ")"})
        meta_map = {s["id"]: s["fields"] for s in students}

        for s in sessions:
            sid = (s["fields"].get("Student") or [None])[0]
            s["student_meta"] = meta_map.get(sid, {})
        return sessions

    def mark_billed(self, airtable_ids, stripe_inv_id):
        self._batch_update("Billed Now", [
            {"id": rid, "fields": {"Invoice_ID": stripe_inv_id, "Ready_to_Invoice": False}}
            for rid in airtable_ids
        ])

    # ---------- Aggregation ----------
    def group_by_parent_month(self, sessions):
        """
        Returns: dict  parent_name  → { 'email':.., 'rate':..,  'months': { '2025-03': {minutes, breakdown}} }
        """
        data = defaultdict(lambda: {"email":"", "rate":0, "months":defaultdict(lambda: {"minutes":0, "entries":[]}), "airtable_ids":[]})

        for rec in sessions:
            f = rec["fields"]
            student = rec["student_meta"]
            parent = student.get("Parent_Name", "UNKNOWN")
            email  = student.get("Parent_Email", "")
            rate   = student.get("Hourly_Rate", 0.0)

            key = month_key(f["Date"])
            duration_min = int(float(f["Duration"]) * 60)

            d = data[parent]
            d["email"] = email
            d["rate"]  = rate
            d["airtable_ids"].append(rec["id"])

            d["months"][key]["minutes"] += duration_min
            d["months"][key]["entries"].append(
                f"{int(f['Date'][-2:]):02d} ({f['Duration']})"
            )

        # Convert nested defaultdicts to dicts
        for p in data.values():
            p["months"] = {k:v for k,v in p["months"].items()}
        return data
