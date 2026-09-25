import * as Select from "@radix-ui/react-select";

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

export default function SelectMenu({ label, value, options, onChange, icon, className = "" }: SelectMenuProps) {
  return (
    <Select.Root value={value} onValueChange={onChange}>
      <Select.Trigger aria-label={label} className={`flex w-full cursor-pointer items-center gap-2 whitespace-nowrap rounded-md border border-background-200 bg-background-100 px-3 py-2 text-xs transition-colors hover:border-background-300 focus:border-primary-400 focus:outline-none ${className}`}>
        {icon && <span className="flex h-4 w-4 items-center justify-center text-foreground-500"><i className={`${icon} text-[15px]`} /></span>}
        <span className="text-foreground-500">{label}</span>
        <span className="max-w-[140px] truncate font-medium text-foreground-900"><Select.Value /></span>
        <Select.Icon className="ml-auto text-foreground-500"><i className="ri-arrow-down-s-line text-base" /></Select.Icon>
      </Select.Trigger>
      <Select.Portal>
        <Select.Content position="popper" sideOffset={8} className="z-50 max-h-64 min-w-[180px] overflow-hidden rounded-md border border-background-200 bg-background-100 py-1 text-foreground-700 shadow-lg">
          <Select.Viewport>
            {options.map((option) => (
              <Select.Item key={option.value} value={option.value} className="relative flex cursor-pointer items-center gap-2 px-3 py-2 text-left text-xs outline-none data-[highlighted]:bg-background-200/70 data-[state=checked]:text-primary-400">
                <Select.ItemText>{option.label}</Select.ItemText>
                <Select.ItemIndicator className="ml-auto"><i className="ri-check-line text-[14px]" /></Select.ItemIndicator>
              </Select.Item>
            ))}
          </Select.Viewport>
        </Select.Content>
      </Select.Portal>
    </Select.Root>
  );
}
