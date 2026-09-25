import { useEffect, useRef, useState } from "react";

export interface SelectOption {
  value: string;
  label: string;
}

interface SelectMenuProps {
  label: string;
  value: string;
  options: SelectOption[];
  onChange: (value: string) => void;
  icon?: string;
  className?: string;
}

export default function SelectMenu({
  label,
  value,
  options,
  onChange,
  icon,
  className = "",
}: SelectMenuProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const current = options.find((option) => option.value === value);

  useEffect(() => {
    const handler = (event: MouseEvent) => {
      if (ref.current && !ref.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  return (
    <div ref={ref} className={`relative ${className}`}>
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        className={`flex w-full cursor-pointer items-center gap-2 whitespace-nowrap rounded-md border bg-background-100 px-3 py-2 text-xs transition-colors ${
          open
            ? "border-primary-400"
            : "border-background-200 hover:border-background-300"
        }`}
      >
        {icon && (
          <span className="flex h-4 w-4 items-center justify-center text-foreground-500">
            <i className={`${icon} text-[15px]`}></i>
          </span>
        )}
        <span className="text-foreground-500">{label}</span>
        <span className="max-w-[140px] truncate font-medium text-foreground-900">
          {current?.label ?? "全部"}
        </span>
        <span className="ml-auto flex h-4 w-4 items-center justify-center text-foreground-500">
          <i
            className={`ri-arrow-down-s-line text-base transition-transform ${
              open ? "rotate-180" : ""
            }`}
          ></i>
        </span>
      </button>

      {open && (
        <div className="animate-fade-in absolute left-0 top-full z-30 mt-2 max-h-64 w-full min-w-[180px] overflow-y-auto rounded-md border border-background-200 bg-background-100 py-1">
          <ul>
            {options.map((option) => {
              const selected = option.value === value;
              return (
                <li key={option.value}>
                  <button
                    type="button"
                    onClick={() => {
                      onChange(option.value);
                      setOpen(false);
                    }}
                    className={`flex w-full cursor-pointer items-center gap-2 px-3 py-2 text-left text-xs transition-colors ${
                      selected
                        ? "bg-primary-500/12 text-primary-400"
                        : "text-foreground-700 hover:bg-background-200/70"
                    }`}
                  >
                    <span className="truncate">{option.label}</span>
                    {selected && (
                      <i className="ri-check-line ml-auto text-[14px]"></i>
                    )}
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </div>
  );
}