import type { CSSProperties, ReactNode } from "react";
import * as RadixTooltip from "@radix-ui/react-tooltip";

export interface TooltipBubbleProps {
  children: ReactNode;
  className?: string;
  style?: CSSProperties;
}

export function TooltipBubble({ children, className = "", style }: TooltipBubbleProps) {
  return <div role="tooltip" style={style} className={`pointer-events-none z-[130] max-w-[260px] whitespace-nowrap rounded-md border border-foreground-700 bg-foreground-950 px-2.5 py-1 text-[11px] font-medium leading-snug text-background-50 ${className}`.trim()}>{children}</div>;
}

interface TooltipProps {
  content: ReactNode;
  children: ReactNode;
  disabled?: boolean;
  className?: string;
  style?: CSSProperties;
}

export default function Tooltip({ content, children, disabled = false, className, style }: TooltipProps) {
  if (disabled) return <span className={`inline-flex ${className ?? ""}`.trim()} style={style}>{children}</span>;
  return (
    <RadixTooltip.Provider delayDuration={200}>
      <RadixTooltip.Root>
        <RadixTooltip.Trigger asChild><span className={`inline-flex ${className ?? ""}`.trim()} style={style} tabIndex={0}>{children}</span></RadixTooltip.Trigger>
        <RadixTooltip.Portal>
          <RadixTooltip.Content sideOffset={8} collisionPadding={8} className="z-[130] max-w-[260px] whitespace-nowrap rounded-md border border-foreground-700 bg-foreground-950 px-2.5 py-1 text-[11px] font-medium leading-snug text-background-50">
            {content}
          </RadixTooltip.Content>
        </RadixTooltip.Portal>
      </RadixTooltip.Root>
    </RadixTooltip.Provider>
  );
}
