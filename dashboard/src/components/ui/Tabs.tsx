import type { ReactNode } from "react";

import "./tabs.css";

export type TabItem<T extends string> = {
  value: T;
  label: string;
};

type TabsProps<T extends string> = {
  items: Array<TabItem<T>>;
  value: T;
  onChange: (value: T) => void;
  children: ReactNode;
};

export function Tabs<T extends string>({ items, value, onChange, children }: TabsProps<T>) {
  return (
    <div className="tabsRoot">
      <div className="tabsList" role="tablist" aria-label="预览切换">
        {items.map((item) => (
          <button
            key={item.value}
            type="button"
            className="tabsTrigger"
            data-active={item.value === value}
            onClick={() => onChange(item.value)}
          >
            {item.label}
          </button>
        ))}
      </div>
      <div>{children}</div>
    </div>
  );
}
