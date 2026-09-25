import type { ReactNode } from "react";

interface CardProps {
  title?: string;
  subtitle?: string;
  icon?: string;
  action?: ReactNode;
  className?: string;
  bodyClassName?: string;
  children: ReactNode;
}

export default function Card({
  title,
  subtitle,
  icon,
  action,
  className = "",
  bodyClassName = "",
  children,
}: CardProps) {
  return (
    <section
      className={`rounded-lg border border-background-200 bg-background-100 ${className}`}
    >
      {(title || action) && (
        <header className="flex items-start justify-between gap-4 border-b border-background-200/70 px-4 py-3">
          <div className="flex items-center gap-2.5">
            {icon && (
              <span className="flex h-7 w-7 items-center justify-center rounded-md bg-primary-500/12 text-primary-400">
                <i className={`${icon} text-[15px]`}></i>
              </span>
            )}
            <div>
              {title && (
                <h3 className="text-[15px] font-semibold leading-tight text-foreground-950">
                  {title}
                </h3>
              )}
              {subtitle && (
                <p className="mt-0.5 text-xs text-foreground-500">{subtitle}</p>
              )}
            </div>
          </div>
          {action}
        </header>
      )}
      <div className={bodyClassName}>{children}</div>
    </section>
  );
}