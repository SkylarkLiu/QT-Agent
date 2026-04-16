import type { ButtonHTMLAttributes, ReactNode } from "react";

import { cn } from "../../lib/cn";
import "./button.css";

type ButtonVariant = "primary" | "secondary" | "ghost";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  fullWidth?: boolean;
  leadingIcon?: ReactNode;
};

export function Button({
  className,
  variant = "primary",
  fullWidth = false,
  leadingIcon,
  children,
  ...props
}: ButtonProps) {
  return (
    <button className={cn("button", variant, fullWidth && "fullWidth", className)} {...props}>
      {leadingIcon ? <span className="icon">{leadingIcon}</span> : null}
      <span>{children}</span>
    </button>
  );
}
