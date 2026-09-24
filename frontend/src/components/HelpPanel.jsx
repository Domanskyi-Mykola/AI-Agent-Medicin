import { useState } from "react";

// Коротка вбудована інструкція, що розкривається за кліком.
export default function HelpPanel({ title = "Як користуватися", children }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="rounded-lg border border-slate-200 bg-white">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between px-4 py-2 text-left text-sm font-medium text-slate-700 hover:bg-slate-50"
        aria-expanded={open}
      >
        <span>{title}</span>
        <span className="text-slate-400">{open ? "−" : "+"}</span>
      </button>
      {open && <div className="space-y-2 border-t border-slate-100 px-4 py-3 text-sm text-slate-600">{children}</div>}
    </div>
  );
}
