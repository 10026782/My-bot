// Leads.status (airtable_schema.py::LeadStatus) — single Hebrew label map shared
// by the pipeline filter, the lead card and the lead detail. A value missing
// here still renders (falls back to the raw key) rather than disappearing.
export const LEAD_STATUS_LABELS: Record<string, string> = {
  new: "חדש — טרם דיברנו",
  waiting_call: "ניסינו — אין מענה",
  active: "בטיפול",
  waiting_response: "במעקב",
  high_confidence: "מתאים — רציני",
  done: "הושלם",
  archived: "בארכיון",
  lost: "אבוד",
  duplicate: "כפילות",
  not_relevant: "לא רלוונטי",
};

// Non-terminal statuses an employee can move a lead between ("where the lead is").
export const LEAD_OPEN_STATUSES = ["new", "waiting_call", "active", "waiting_response", "high_confidence"] as const;

export function leadStatusLabel(status: string): string {
  return LEAD_STATUS_LABELS[(status ?? "").trim()] ?? status;
}
