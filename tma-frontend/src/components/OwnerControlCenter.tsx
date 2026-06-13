import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { fetchOwnerControlCenter } from "../api";
import type { OwnerControlCenter as TOwnerControlCenter } from "../types";

interface Props {
  onBack: () => void;
}

type State =
  | { status: "loading" }
  | { status: "ok"; data: TOwnerControlCenter }
  | { status: "error"; message: string };

const colorClass: Record<string, string> = {
  green: "bg-green-500",
  yellow: "bg-yellow-400",
  red: "bg-red-500",
};

function Section({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <section className="bg-white rounded-xl shadow-sm p-4">
      <h2 className="text-xs font-semibold text-gray-400 mb-3 uppercase tracking-wide">
        {title}
      </h2>
      {children}
    </section>
  );
}

function EmptyLine({ text }: { text: string }) {
  return <p className="text-xs text-gray-400">{text}</p>;
}

export function OwnerControlCenter({ onBack }: Props) {
  const [state, setState] = useState<State>({ status: "loading" });

  function load() {
    setState({ status: "loading" });
    fetchOwnerControlCenter()
      .then((data) => setState({ status: "ok", data }))
      .catch((e: unknown) => setState({ status: "error", message: String(e) }));
  }

  useEffect(() => { load(); }, []);

  return (
    <div className="min-h-screen bg-gray-100 pb-8">
      <div className="bg-white px-4 pt-5 pb-4 mb-3 shadow-sm flex items-center gap-3">
        <button
          onClick={onBack}
          className="text-blue-500 text-xl font-medium leading-none"
          aria-label="Back"
        >
          ←
        </button>
        <div>
          <h1 className="text-lg font-black text-gray-900">Owner Control Center</h1>
          <p className="text-xs text-gray-400">Governance cockpit</p>
        </div>
        <button onClick={load} className="mr-auto text-gray-400 text-sm active:text-gray-600">
          Refresh
        </button>
      </div>

      {state.status === "loading" && (
        <div className="flex justify-center pt-16">
          <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
        </div>
      )}

      {state.status === "error" && (
        <div className="mx-4 mt-4 bg-red-50 border border-red-200 rounded-xl p-4">
          <p className="text-sm font-semibold text-red-700">Could not load Control Center</p>
          <p className="text-xs text-red-500 mt-1">{state.message}</p>
        </div>
      )}

      {state.status === "ok" && (() => {
        const data = state.data;
        const health = data.system_health;
        return (
          <div className="flex flex-col gap-3 px-4">
            <Section title="System Health">
              <div className="grid grid-cols-4 gap-2">
                <div className="col-span-1 rounded-lg bg-gray-900 p-3 text-white">
                  <p className="text-[10px] text-gray-300">Health</p>
                  <p className="text-2xl font-black">{health.health_percent}%</p>
                </div>
                <div className="rounded-lg bg-green-50 p-3">
                  <p className="text-[10px] text-green-500">Working</p>
                  <p className="text-xl font-black text-green-700">{health.working_count}</p>
                </div>
                <div className="rounded-lg bg-yellow-50 p-3">
                  <p className="text-[10px] text-yellow-600">Partial</p>
                  <p className="text-xl font-black text-yellow-700">{health.partial_count}</p>
                </div>
                <div className="rounded-lg bg-red-50 p-3">
                  <p className="text-[10px] text-red-500">Broken</p>
                  <p className="text-xl font-black text-red-700">{health.broken_count}</p>
                </div>
              </div>
            </Section>

            <Section title="Critical Systems">
              <div className="flex flex-col divide-y divide-gray-50">
                {data.critical_systems.map((system) => (
                  <div key={system.name} className="flex items-center justify-between py-2.5 first:pt-0 last:pb-0">
                    <div className="flex items-center gap-2">
                      <span className={`w-2.5 h-2.5 rounded-full ${colorClass[system.color] ?? "bg-gray-400"}`} />
                      <span className="text-sm font-semibold text-gray-800">{system.name}</span>
                    </div>
                    <span className="text-xs text-gray-500">{system.status}</span>
                  </div>
                ))}
              </div>
            </Section>

            {data.strategic_pipeline && (
              <Section title="Strategic Pipeline">
                <div className="grid grid-cols-3 gap-2">
                  <div className="rounded-lg bg-purple-50 p-3">
                    <p className="text-[10px] text-purple-500">New Ideas</p>
                    <p className="text-xl font-black text-purple-700">{data.strategic_pipeline.new_opportunities}</p>
                  </div>
                  <div className="rounded-lg bg-blue-50 p-3">
                    <p className="text-[10px] text-blue-500">In Evaluation</p>
                    <p className="text-xl font-black text-blue-700">{data.strategic_pipeline.in_evaluation}</p>
                  </div>
                  <div className="rounded-lg bg-orange-50 p-3">
                    <p className="text-[10px] text-orange-500">Pending Decision</p>
                    <p className="text-xl font-black text-orange-700">{data.strategic_pipeline.pending_decision}</p>
                  </div>
                </div>
              </Section>
            )}

            <Section title="Approvals">
              <div className="grid grid-cols-3 gap-2 mb-3">
                <div className="rounded-lg bg-yellow-50 p-3">
                  <p className="text-[10px] text-yellow-600">Pending</p>
                  <p className="text-xl font-black text-yellow-700">{data.approvals.pending_count}</p>
                </div>
                <div className="rounded-lg bg-green-50 p-3">
                  <p className="text-[10px] text-green-600">Executed</p>
                  <p className="text-xl font-black text-green-700">{data.approvals.recent_executed.length}</p>
                </div>
                <div className="rounded-lg bg-blue-50 p-3">
                  <p className="text-[10px] text-blue-600">Receipts</p>
                  <p className="text-xl font-black text-blue-700">{data.approvals.recent_receipts.length}</p>
                </div>
              </div>

              <div className="flex flex-col gap-2">
                {data.approvals.recent_executed.slice(0, 3).map((item) => (
                  <div key={item.id} className="rounded-lg bg-gray-50 px-3 py-2">
                    <p className="text-xs font-semibold text-gray-800">{item.action || item.id}</p>
                    <p className="text-[11px] text-gray-400">{item.status} · {item.requested_at || "no date"}</p>
                  </div>
                ))}
                {data.approvals.recent_receipts.slice(0, 3).map((item) => (
                  <div key={item.id} className="rounded-lg bg-blue-50 px-3 py-2">
                    <p className="text-xs font-semibold text-blue-900">
                      {item.receipt.table || "Receipt"} / {item.receipt.record_id || item.id}
                    </p>
                    <p className="text-[11px] text-blue-500">{item.receipt.status || "executed"}</p>
                  </div>
                ))}
                {data.approvals.recent_executed.length === 0 && data.approvals.recent_receipts.length === 0 && (
                  <EmptyLine text="No recent approval activity." />
                )}
              </div>
            </Section>

            <Section title="Permissions">
              <div className="overflow-hidden rounded-lg border border-gray-100">
                <div className="grid grid-cols-4 bg-gray-50 text-[11px] font-semibold text-gray-500">
                  <div className="p-2">Role</div>
                  <div className="p-2">Read</div>
                  <div className="p-2">Write</div>
                  <div className="p-2">Approve</div>
                </div>
                {data.permissions.map((row) => (
                  <div key={row.role} className="grid grid-cols-4 border-t border-gray-100 text-[11px] text-gray-700">
                    <div className="p-2 font-semibold">{row.role}</div>
                    <div className="p-2">{row.read}</div>
                    <div className="p-2">{row.write}</div>
                    <div className="p-2">{row.approve}</div>
                  </div>
                ))}
              </div>
            </Section>

            <Section title="Business Language">
              <div className="flex flex-col gap-3">
                <LanguageBlock title="Lead Status" items={data.business_language.lead_status} />
                <LanguageBlock title="Lead Outcome" items={data.business_language.lead_outcome} />
                <LanguageBlock title="Lead Tier" items={data.business_language.lead_tier} />
              </div>
            </Section>

            <Section title="Blockers">
              {data.blockers.length > 0 ? (
                <ol className="flex flex-col gap-2">
                  {data.blockers.slice(0, 5).map((item, index) => (
                    <li key={item} className="flex gap-2 text-sm text-gray-700">
                      <span className="font-black text-red-500">{index + 1}.</span>
                      <span>{item}</span>
                    </li>
                  ))}
                </ol>
              ) : <EmptyLine text="No blockers reported." />}
            </Section>

            <Section title="Next Actions">
              <ol className="flex flex-col gap-2">
                {data.next_actions.slice(0, 3).map((item, index) => (
                  <li key={item} className="rounded-lg bg-gray-50 px-3 py-2 text-sm text-gray-800">
                    <span className="font-black text-gray-400 mr-1">{index + 1}.</span>
                    {item}
                  </li>
                ))}
              </ol>
            </Section>

            {data.warnings.length > 0 && (
              <div className="rounded-xl border border-yellow-200 bg-yellow-50 p-3">
                <p className="text-xs font-semibold text-yellow-700 mb-1">Warnings</p>
                {data.warnings.map((warning) => (
                  <p key={warning} className="text-[11px] text-yellow-700">{warning}</p>
                ))}
              </div>
            )}
          </div>
        );
      })()}
    </div>
  );
}

function LanguageBlock({
  title,
  items,
}: {
  title: string;
  items: { value: string; label: string }[];
}) {
  return (
    <div>
      <p className="text-xs font-semibold text-gray-600 mb-1">{title}</p>
      <div className="flex flex-wrap gap-1.5">
        {items.map((item) => (
          <span key={item.value} className="rounded-full bg-gray-100 px-2 py-1 text-[11px] text-gray-700">
            {item.value}
          </span>
        ))}
      </div>
    </div>
  );
}
