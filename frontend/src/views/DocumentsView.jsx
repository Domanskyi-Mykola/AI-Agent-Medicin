import { useState } from "react";
import { generateDocument } from "../api.js";

const DOC_TYPES = [
  { id: "discharge_summary", label: "Виписний епікриз" },
  { id: "case_history_section", label: "Розділ історії хвороби" },
  { id: "dissertation_section", label: "Розділ дисертації" },
];

export default function DocumentsView() {
  const [form, setForm] = useState({
    doc_type: "discharge_summary",
    diagnosis: "",
    procedure: "",
    notes: "",
  });
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  async function onSubmit(e) {
    e.preventDefault();
    if (!form.diagnosis.trim() || loading) return;
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const data = await generateDocument(form);
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
        <div>
          <label className="block text-sm font-medium text-slate-700">Тип документа</label>
          <select
            value={form.doc_type}
            onChange={set("doc_type")}
            className="mt-1 w-full rounded-lg border border-slate-300 p-2 text-sm focus:border-teal-500 focus:outline-none"
          >
            {DOC_TYPES.map((d) => (
              <option key={d.id} value={d.id}>
                {d.label}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700">Діагноз *</label>
          <textarea
            value={form.diagnosis}
            onChange={set("diagnosis")}
            rows={2}
            placeholder="Напр.: закритий косий перелом діафіза великогомілкової кістки, AO/OTA 42-A2"
            className="mt-1 w-full resize-none rounded-lg border border-slate-300 p-2 text-sm focus:border-teal-500 focus:outline-none"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700">Втручання / процедури</label>
          <textarea
            value={form.procedure}
            onChange={set("procedure")}
            rows={2}
            placeholder="Напр.: закритий інтрамедулярний остеосинтез блокованим стрижнем"
            className="mt-1 w-full resize-none rounded-lg border border-slate-300 p-2 text-sm focus:border-teal-500 focus:outline-none"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700">Перебіг / примітки</label>
          <textarea
            value={form.notes}
            onChange={set("notes")}
            rows={3}
            placeholder="Ключові моменти перебігу, без даних, що ідентифікують пацієнта"
            className="mt-1 w-full resize-none rounded-lg border border-slate-300 p-2 text-sm focus:border-teal-500 focus:outline-none"
          />
        </div>

        <p className="text-xs text-amber-700">
          ⚠ Не вводьте дані, що ідентифікують пацієнта. Модель залишить плейсхолдери [ВКАЗАТИ: …].
        </p>
        <button
          type="submit"
          disabled={loading || !form.diagnosis.trim()}
          className="rounded-lg bg-teal-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-teal-700 disabled:opacity-50"
        >
          {loading ? "Генерація…" : "Згенерувати чернетку"}
        </button>
      </form>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {result && (
        <div className="space-y-3">
          <div className="rounded-lg border border-slate-200 bg-white p-4">
            <h2 className="mb-2 text-sm font-semibold text-slate-500">Чернетка</h2>
            <p className="whitespace-pre-wrap text-sm leading-relaxed">{result.text}</p>
          </div>
          <p className="text-xs italic text-slate-500">{result.disclaimer}</p>
        </div>
      )}
    </div>
  );
}
