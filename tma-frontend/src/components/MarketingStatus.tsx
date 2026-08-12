import { useEffect, useState } from "react";
import { fetchMarketingStatus } from "../api";
import type { MarketingStatusResponse } from "../types";

interface Props { onBack: () => void; }
type State =
  | { status: "loading" }
  | { status: "ok"; data: MarketingStatusResponse }
  | { status: "error"; message: string };

export function MarketingStatus({ onBack }: Props) {
  const [state, setState] = useState<State>({ status: "loading" });

  useEffect(() => {
    fetchMarketingStatus()
      .then((data) => setState({ status: "ok", data }))
      .catch((e: unknown) => setState({ status: "error", message: String(e) }));
  }, []);

  return (
    <div className="min-h-screen bg-gray-100 pb-8">
      <div className="bg-white px-4 pt-5 pb-4 mb-3 shadow-sm flex items-center gap-3">
        <button onClick={onBack} className="text-blue-500 text-xl" aria-label="חזרה">←</button>
        <div><h1 className="text-lg font-black text-gray-900">שיווק</h1><p className="text-xs text-gray-400">Marketing Status</p></div>
      </div>
      {state.status === "loading" && <div className="flex justify-center pt-16">טוען…</div>}
      {state.status === "error" && <div className="mx-4 bg-red-50 border border-red-200 rounded-xl p-4 text-sm text-red-700">הטעינה נכשלה</div>}
      {state.status === "ok" && state.data.demands.length === 0 && <div className="mx-4 bg-white rounded-xl p-4 text-sm text-gray-500">אין דרישות שיווק זמינות</div>}
      {state.status === "ok" && (
        <div className="flex flex-col gap-3 px-4">
          {state.data.demands.map((demand, index) => (
            <div key={`${demand.title}-${index}`} className="bg-white rounded-xl shadow-sm p-4">
              <div className="flex items-start justify-between gap-2">
                <h2 className="font-bold text-gray-900">{demand.title || "דרישה ללא שם"}</h2>
                {demand.consistency_state === "inconsistent" && <span className="text-xs text-red-700 bg-red-100 rounded-full px-2 py-1">מצב לא עקבי</span>}
              </div>
              <p className="text-xs text-gray-400 mt-1">{demand.stage} · {demand.status}</p>
              <p className="text-sm text-gray-700 mt-3"><span className="font-semibold">צעד הבא:</span> {demand.next_action}</p>
              {demand.detail && <p className="text-xs text-gray-500 mt-2">{demand.detail}</p>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
