import type { ChatOption } from "@/lib/types";

interface Props {
  options: ChatOption[];
  disabled: boolean;
  onPick: (option: ChatOption) => void;
}

export default function QuickRow({ options, disabled, onPick }: Props) {
  return (
    <div className="quickrow">
      {options.map((o) => (
        <button
          key={o.index}
          className="quickbtn"
          disabled={disabled}
          onClick={() => !disabled && onPick(o)}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}
