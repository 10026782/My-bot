import type { ReactNode } from "react";

interface ScreenStateProps {
  state: "loading" | "empty" | "error";
  title?: string;
  message?: ReactNode;
  action?: ReactNode;
}

const DEFAULT_TITLES = {
  loading: "טוען נתונים",
  empty: "אין עדיין נתונים",
  error: "לא הצלחנו לטעון",
};

export function ScreenState({ state, title, message, action }: ScreenStateProps) {
  return (
    <div className={`boss-screen-state boss-screen-state--${state}`} role={state === "error" ? "alert" : "status"}>
      {state === "loading" && <span className="boss-screen-state__loader" aria-hidden="true" />}
      <div>
        <h2 className="boss-screen-state__title">{title ?? DEFAULT_TITLES[state]}</h2>
        {message && <p className="boss-screen-state__message">{message}</p>}
      </div>
      {action}
    </div>
  );
}
