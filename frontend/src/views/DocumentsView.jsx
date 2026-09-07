import { useState } from "react";
import { generateDocument } from "../api.js";

const DOC_TYPES = [
  { id: "discharge_summary", label: "Виписний епікриз" },
  { id: "case_history_section", label: "Розділ історії хвороби" },
  { id: "dissertation_section", label: "Розділ дисертації" },
];

// Поля, що ідентифікують пацієнта. ВАЖЛИВО: значення цих полів НІКОЛИ не
// потрапляють у виклик generateDocument() і, відповідно, ніколи не йдуть на
// бекенд/до Claude/в audit-лог — вони живуть лише в стані цього компонента
// (у пам'яті браузера) і підставляються в готовий текст локально, тут-таки.
// Токени {{...}} — це те, що модель вставляє в текст замість цих даних
// (див. backend/app/prompts.py, PASSPORT_PLACEHOLDER_BLOCK).
const PASSPORT_FIELDS = [
  { key: "patientName", token: "{{PATIENT_NAME}}", label: "ПІБ пацієнта", fallback: "[ВКАЗАТИ: ПІБ пацієнта]" },
  { key: "patientDob", token: "{{PATIENT_DOB}}", label: "Дата народження", fallback: "[ВКАЗАТИ: дата народження]" },
  { key: "patientSex", token: "{{PATIENT_SEX}}", label: "Стать", fallback: "[ВКАЗАТИ: стать]" },
  { key: "cardNumber", token: "{{CARD_NUMBER}}", label: "№ медичної картки", fallback: "[ВКАЗАТИ: № медичної картки]" },
  { key: "admissionDate", token: "{{ADMISSION_DATE}}", label: "Дата госпіталізації", fallback: "[ВКАЗАТИ: дата госпіталізації]" },
  { key: "dischargeDate", token: "{{DISCHARGE_DATE}}", label: "Дата виписки", fallback: "[ВКАЗАТИ: дата виписки]" },
  { key: "doctorName", token: "{{DOCTOR_NAME}}", label: "ПІБ лікаря", fallback: "[ВКАЗАТИ: ПІБ лікаря]" },
];

const EMPTY_PASSPORT = Object.fromEntries(PASSPORT_FIELDS.map((f) => [f.key, ""]));

// Підставляє локально введені дані пацієнта на місце токенів у тексті, який
// повернув бекенд. Незаповнене поле лишає звичайний людський плейсхолдер
// [ВКАЗАТИ: ...] — поведінка як і раніше, якщо лікар нічого не ввів.
function fillPassportTokens(text, passport) {
  let out = text;
  for (const f of PASSPORT_FIELDS) {
    const value = passport[f.key]?.trim();
    out = out.split(f.token).join(value || f.fallback);
  }
  return out;
}

export default function DocumentsView() {
  const [form, setForm] = useState({
    doc_type: "discharge_summary",
    diagnosis: "",
    procedure: "",
    notes: "",
  });
  const [passport, setPassport] = useState(EMPTY_PASSPORT);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  const setPassportField = (k) => (e) => setPassport({ ...passport, [k]: e.target.value });

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

        {form.doc_type === "discharge_summary" && (
          <div className="space-y-2 rounded-lg border border-sky-200 bg-sky-50 p-3">
            <p className="text-xs font-medium text-sky-800">
              Дані пацієнта — залишаються лише у вашому браузері, AI їх не бачить. Заповніть
              один раз, і вони самі підставляться в усі потрібні місця чернетки.
            </p>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              {PASSPORT_FIELDS.map((f) => (
                <div key={f.key}>
                  <label className="block text-xs text-slate-600">{f.label}</label>
                  <input
                    type="text"
                    value={passport[f.key]}
                    onChange={setPassportField(f.key)}
                    className="mt-0.5 w-full rounded border border-sky-300 bg-white p-1.5 text-xs focus:border-sky-500 focus:outline-none"
                  />
                </div>
              ))}
            </div>
          </div>
        )}

        <p className="text-xs text-amber-700">
          ⚠ У полях «Діагноз», «Втручання» та «Перебіг» не вказуйте ПІБ, дати народження чи №
          картки — цей текст іде до AI.{" "}
          {form.doc_type === "discharge_summary"
            ? "Для цих даних скористайтеся полями пацієнта вище — вони обробляються лише у вашому браузері."
            : "Модель залишить плейсхолдери [ВКАЗАТИ: …] на їх місці."}
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
            <p className="whitespace-pre-wrap text-sm leading-relaxed">
              {fillPassportTokens(result.text, passport)}
            </p>
          </div>
          <p className="text-xs italic text-slate-500">{result.disclaimer}</p>
        </div>
      )}
    </div>
  );
}
