import { useState } from "react";
import ChatView from "./views/ChatView.jsx";
import DocumentsView from "./views/DocumentsView.jsx";

const TABS = [
  { id: "chat", label: "Клінічний Q&A" },
  { id: "documents", label: "Документи" },
];

export default function App() {
  const [tab, setTab] = useState("chat");

  return (
    <div className="min-h-screen bg-slate-100 text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-3xl items-center gap-3 px-4 py-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-teal-600 font-bold text-white">
            T
          </div>
          <div>
            <h1 className="text-lg font-semibold leading-tight">Trauma AI</h1>
            <p className="text-xs text-slate-500">
              Асистент лікаря-травматолога · MVP · не замінює рішення лікаря
            </p>
          </div>
        </div>
        <nav className="mx-auto flex max-w-3xl gap-1 px-4">
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`rounded-t-lg px-4 py-2 text-sm font-medium transition ${
                tab === t.id
                  ? "bg-slate-100 text-teal-700"
                  : "text-slate-500 hover:text-slate-800"
              }`}
            >
              {t.label}
            </button>
          ))}
        </nav>
      </header>

      <main className="mx-auto max-w-3xl px-4 py-6">
        {tab === "chat" ? <ChatView /> : <DocumentsView />}
      </main>
    </div>
  );
}
