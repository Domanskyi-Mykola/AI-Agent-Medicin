import { useEffect, useRef, useState } from "react";
import { askChat } from "../api.js";
import Markdown from "../components/Markdown.jsx";
import Elapsed from "../components/Elapsed.jsx";
import HelpPanel from "../components/HelpPanel.jsx";

const EXAMPLES = [
  "Класифікація переломів шийки стегна за Garden і тактика у літніх",
  "Яка тактика при відкритому переломі гомілки з раною 4 см?",
  "Показання до операції при переломі ключиці",
  "Ознаки компартмент-синдрому гомілки і що робити",
  "Переломи кісточок: класифікація Weber і показання до остеосинтезу",
  "Вогнепальний перелом стегнової кістки: етапне лікування",
];

// Історія зберігається лише в цьому браузері (localStorage). Питання не
// повинні містити даних пацієнта — див. попередження під полем вводу.
const STORE_KEY = "trauma-ai.chat.v2";
const MAX_HISTORY = 50;

function loadHistory() {
  try {
    const raw = localStorage.getItem(STORE_KEY);
    const items = raw ? JSON.parse(raw) : [];
    return Array.isArray(items) ? items.filter((i) => i.status === "done") : [];
  } catch {
    return [];
  }
}

function saveHistory(items) {
  try {
    localStorage.setItem(
      STORE_KEY,
      JSON.stringify(items.filter((i) => i.status === "done").slice(0, MAX_HISTORY))
    );
  } catch {
    /* приватний режим / заборона сховища — працюємо без збереження */
  }
}

const COVERAGE_LABEL = {
  full: "повністю з бази знань",
  partial: "частково з бази знань",
};

// Кілька фрагментів з одного розділу статті ([1] і [5]) показуємо одним
// рядком «[1][5] джерело · розділ», а не двома однаковими.
function groupCitations(citations) {
  const groups = new Map();
  for (const c of citations) {
    const key = `${c.source}|${c.section || ""}`;
    if (!groups.has(key)) groups.set(key, { ...c, ns: [] });
    groups.get(key).ns.push(c.n);
  }
  return [...groups.values()];
}

function Answer({ item }) {
  const r = item.response;
  const prefix = `cite-${item.id}`;

  if (r.out_of_scope) {
    return (
      <div className="rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
        {r.kb_answer}
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {r.kb_answer && (
        <div className="rounded-lg border border-teal-200 bg-white p-4">
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <span className="rounded bg-teal-50 px-2 py-0.5 text-xs font-semibold text-teal-800">
              З бази знань
            </span>
            {COVERAGE_LABEL[r.kb_coverage] && (
              <span className="text-xs text-slate-500">{COVERAGE_LABEL[r.kb_coverage]}</span>
            )}
          </div>
          <Markdown text={r.kb_answer} citePrefix={prefix} />
        </div>
      )}

      {r.general_answer && (
        <div className="rounded-lg border border-amber-300 bg-amber-50/40 p-4">
          <div className="mb-2">
            <span className="rounded bg-amber-100 px-2 py-0.5 text-xs font-semibold text-amber-900">
              Загальні клінічні знання AI
            </span>
            <p className="mt-1 text-xs text-amber-800">
              Цього немає в базі знань — відповідь із загальних медичних знань моделі, без
              джерел. Перевірте за чинними протоколами.
            </p>
          </div>
          <Markdown text={r.general_answer} />
        </div>
      )}

      {r.citations.length > 0 && (
        <div className="rounded-lg border border-slate-200 bg-white p-4">
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
            Джерела
          </h3>
          <ol className="space-y-1 text-sm">
            {groupCitations(r.citations).map((c) => (
              <li key={c.ns[0]} className="cite-target rounded px-1 text-slate-700 transition-colors">
                <span className="font-semibold text-teal-700">
                  {c.ns.map((n) => (
                    <span key={n} id={`${prefix}-${n}`}>
                      [{n}]
                    </span>
                  ))}
                </span>{" "}
                {c.source}
                {c.section && <span className="text-slate-500"> · {c.section}</span>}
              </li>
            ))}
          </ol>
        </div>
      )}

      <p className="text-xs italic text-slate-500">{r.disclaimer}</p>
    </div>
  );
}

export default function ChatView() {
  const [question, setQuestion] = useState("");
  const [items, setItems] = useState(loadHistory);
  const inputRef = useRef(null);
  const busy = items.some((i) => i.status === "loading");

  useEffect(() => saveHistory(items), [items]);

  async function ask(q) {
    const text = q.trim();
    if (!text || busy) return;
    const id = `${Date.now()}`;
    setItems((prev) => [{ id, question: text, status: "loading", startedAt: Date.now() }, ...prev]);
    setQuestion("");
    try {
      const response = await askChat(text);
      setItems((prev) => prev.map((i) => (i.id === id ? { ...i, status: "done", response } : i)));
    } catch (err) {
      setItems((prev) => prev.map((i) => (i.id === id ? { ...i, status: "error", error: err.message } : i)));
    }
  }

  function retry(item) {
    setItems((prev) => prev.filter((i) => i.id !== item.id));
    ask(item.question);
  }

  function onKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      ask(question);
    }
  }

  return (
    <div className="space-y-4">
      <HelpPanel>
        <p>
          Пишіть питання так, як спитали б колегу: <em>«тактика при…», «класифікація…»,
          «показання до операції при…», «терміни іммобілізації…»</em>. Одне питання — одна тема:
          так відповідь точніша.
        </p>
        <p>
          Відповідь має до двох частин. <b className="text-teal-800">«З бази знань»</b> — з
          довідкових статей, з номерами джерел [1], [2]… (клікніть номер — побачите джерело).{" "}
          <b className="text-amber-900">«Загальні клінічні знання AI»</b> — те, чого в базі немає;
          це без джерел, перевіряйте.
        </p>
        <p>
          База знань зараз — чернетки для експертної перевірки (позначка «ЧЕРНЕТКА» у джерелах).
          Відповідь готується 10–40 секунд. Enter — надіслати, Shift+Enter — новий рядок.
        </p>
        <p className="text-amber-700">Не вводьте ПІБ, дати народження чи номери карток пацієнтів.</p>
      </HelpPanel>

      <div className="space-y-2">
        <textarea
          ref={inputRef}
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={onKeyDown}
          rows={3}
          placeholder="Напр.: тактика при переломі шийки стегна у пацієнта 80 років"
          className="w-full resize-none rounded-lg border border-slate-300 p-3 text-sm focus:border-teal-500 focus:outline-none focus:ring-1 focus:ring-teal-500"
        />
        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={() => ask(question)}
            disabled={busy || !question.trim()}
            className="rounded-lg bg-teal-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-teal-700 disabled:opacity-50"
          >
            {busy ? "Обробка…" : "Надіслати"}
          </button>
          <span className="text-xs text-amber-700">
            ⚠ Без ПІБ, дат народження, № карт пацієнтів.
          </span>
          {items.length > 0 && !busy && (
            <button
              type="button"
              onClick={() => setItems([])}
              className="ml-auto text-xs text-slate-500 underline hover:text-slate-700"
            >
              Очистити історію
            </button>
          )}
        </div>
      </div>

      {items.length === 0 && (
        <div>
          <p className="mb-2 text-xs font-medium text-slate-500">Приклади питань — натисніть, щоб задати:</p>
          <div className="flex flex-wrap gap-2">
            {EXAMPLES.map((q) => (
              <button
                key={q}
                type="button"
                onClick={() => ask(q)}
                className="rounded-full border border-slate-300 bg-white px-3 py-1 text-left text-xs text-slate-700 hover:border-teal-500 hover:text-teal-700"
              >
                {q}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="space-y-6">
        {items.map((item) => (
          <div key={item.id} className="space-y-3">
            <div className="rounded-lg bg-slate-200/70 px-4 py-2 text-sm font-medium text-slate-800">
              {item.question}
            </div>
            {item.status === "loading" && (
              <Elapsed startedAt={item.startedAt} hint="зазвичай 10–40 с" />
            )}
            {item.status === "error" && (
              <div className="flex flex-wrap items-center gap-3 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
                <span>{item.error}</span>
                <button
                  type="button"
                  onClick={() => retry(item)}
                  disabled={busy}
                  className="rounded border border-red-300 bg-white px-2 py-1 text-xs font-medium text-red-700 hover:bg-red-100 disabled:opacity-50"
                >
                  Спробувати ще раз
                </button>
              </div>
            )}
            {item.status === "done" && <Answer item={item} />}
          </div>
        ))}
      </div>
    </div>
  );
}
