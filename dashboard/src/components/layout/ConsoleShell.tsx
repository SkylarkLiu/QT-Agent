import type { ReactNode } from "react";

import "./console-shell.css";

type ConsoleShellProps = {
  title: string;
  subtitle: string;
  left: ReactNode;
  center: ReactNode;
  right: ReactNode;
  bottom: ReactNode;
};

export function ConsoleShell({ title, subtitle, left, center, right, bottom }: ConsoleShellProps) {
  return (
    <div className="shell">
      <div className="shellInner">
        <header className="pageHeader">
          <h1 className="pageTitle">{title}</h1>
          <p className="pageSubtitle">{subtitle}</p>
        </header>
        <div className="mainGrid">
          <div>{left}</div>
          <div>{center}</div>
          <div>{right}</div>
        </div>
        <div className="bottomSection">{bottom}</div>
      </div>
    </div>
  );
}
