import type { InputHTMLAttributes, ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes } from "react";

import { cn } from "../../lib/cn";
import "./input.css";

type FieldProps = {
  label: string;
  hint?: string;
  children: ReactNode;
};

export function Field({ label, hint, children }: FieldProps) {
  return (
    <label className="field">
      <span className="fieldLabel">{label}</span>
      {children}
      {hint ? <span className="fieldHint">{hint}</span> : null}
    </label>
  );
}

export function Input(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={cn("control", props.className)} {...props} />;
}

export function Textarea(props: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={cn("textarea", props.className)} {...props} />;
}

type SelectProps = SelectHTMLAttributes<HTMLSelectElement>;

export function Select(props: SelectProps) {
  return <select className={cn("select", props.className)} {...props} />;
}

type SwitchProps = {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label: string;
  hint?: string;
};

export function Switch({ checked, onChange, label, hint }: SwitchProps) {
  return (
    <div className="field">
      <div className="switchRow">
        <div>
          <div className="fieldLabel">{label}</div>
          {hint ? <div className="fieldHint">{hint}</div> : null}
        </div>
        <button
          type="button"
          className="switchRoot"
          data-checked={checked}
          aria-pressed={checked}
          onClick={() => onChange(!checked)}
        >
          <span className="switchThumb" />
        </button>
      </div>
    </div>
  );
}
