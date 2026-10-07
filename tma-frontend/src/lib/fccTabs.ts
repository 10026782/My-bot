// Tabs of the Financial Control Center. Pure: no fetching, no storage. The last-used tab is remembered only in this
// module's memory (i.e. while the app stays open); a fresh open of the app always starts on "התנהלות חודשית".
export type FccTabKey = "monthly" | "loans" | "assets";

export const FCC_TABS: { key: FccTabKey; label: string }[] = [
  { key: "monthly", label: "התנהלות חודשית" },
  { key: "loans", label: "הלוואות וחוב" },
  { key: "assets", label: "נכסים והון" },
];

export const DEFAULT_TAB: FccTabKey = "monthly";

let remembered: FccTabKey | null = null;

export const isTab = (v: unknown): v is FccTabKey => FCC_TABS.some((t) => t.key === v);
export const initialTab = (): FccTabKey => (remembered && isTab(remembered) ? remembered : DEFAULT_TAB);
export function rememberTab(key: FccTabKey): void { if (isTab(key)) remembered = key; }
/** A new app session starts from the default again (also used by tests). */
export function resetTabMemory(): void { remembered = null; }

export const tabId = (key: FccTabKey): string => `fcc-tab-${key}`;
export const panelId = (key: FccTabKey): string => `fcc-panel-${key}`;
