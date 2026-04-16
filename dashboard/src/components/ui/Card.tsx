import type { HTMLAttributes, ReactNode } from "react";

import { cn } from "../../lib/cn";
import "./card.css";

type CardTone = "bordered" | "elevated";

type CardProps = HTMLAttributes<HTMLDivElement> & {
  tone?: CardTone;
};

export function Card({ className, tone = "bordered", ...props }: CardProps) {
  return <section className={cn("card", tone, className)} {...props} />;
}

type CardHeaderProps = {
  title: string;
  description?: string;
  actions?: ReactNode;
};

export function CardHeader({ title, description, actions }: CardHeaderProps) {
  return (
    <header className="cardHeader">
      <div>
        <h2 className="cardTitle">{title}</h2>
        {description ? <p className="cardDescription">{description}</p> : null}
      </div>
      {actions}
    </header>
  );
}

type CardBodyProps = {
  children: ReactNode;
  className?: string;
};

export function CardBody({ children, className }: CardBodyProps) {
  return <div className={cn("cardBody", className)}>{children}</div>;
}
