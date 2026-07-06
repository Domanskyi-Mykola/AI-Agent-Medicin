import { useState } from "react";
import { askChat } from "../api.js";

export default function ChatView() {
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function onSubmit(e) {
    e.preventDefault();
    if (!question.trim() || loading) return;
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const data = await askChat(question.trim());
      setResult(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-4">
      <form onSubmit={onSubmit} className="space-y-3">
        <label className="block text-sm font-medium text-slate-700">
          Клінічне питання (тактика, класифікації, протоколи)
        </label>
        <textarea
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          rows={3}
          placeholder="Напр.: яка тактика при відкритому переломі гомілки з раною 4 см?"
          className="w-full resize-none rounded-lg border border-slate-300 p-3 text-sm focus:border-teal-500 focus:outline-none focus:ring-1 focus:ring-teal-500"
        />
        <p className="text-xs text-amber-700">
          ⚠ Не вводьте дані, що ідентифікують пацієнта (ПІБ, дата народження, № карти).
        </p>
        <button
          type="submit"
          disabled={loading || !question.trim()}
          className="rounded-lg bg-teal-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-teal-700 disabled:opacity-50"
        >
          {loading ? "Обробка…" : "Надіслати"}
        </button>
      </form>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {result && (
        <div className="space-y-4">
          <div className="rounded-lg border border-slate-200 bg-white p-4">
            <h2 className="mb-2 text-sm font-semibold text-slate-500">Відповідь</h2>
            <p className="whitespace-pre-wrap text-sm leading-relaxed">{result.answer}</p>
          </div>

          {result.citations.length > 0 && (
            <div className="rounded-lg border border-slate-200 bg-white p-4">
              <h2 className="mb-2 text-sm font-semibold text-slate-500">
                Джерела
              </h2>
              <ol className="space-y-1 text-sm">
                {result.citations.map((c, i) => (
                  <li key={i} className="text-slate-700">
                    <span className="font-medium text-teal-700">[{i + 1}]</span>{" "}
                    {c.source}
                    {c.document_number && (
                      <span className="text-slate-500"> · {c.document_number}</span>
                    )}
                    {c.section && (
                      <span className="text-slate-500"> · {c.section}</span>
                    )}
                  </li>
                ))}
              </ol>
            </div>
          )}

          <p className="text-xs italic text-slate-500">{result.disclaimer}</p>
        </div>
      )}
    </div>
  );
}
