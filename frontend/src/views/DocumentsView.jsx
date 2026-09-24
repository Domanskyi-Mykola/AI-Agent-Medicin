import { useRef, useState } from "react";
import { generateDocument } from "../api.js";
import Markdown from "../components/Markdown.jsx";
import Elapsed from "../components/Elapsed.jsx";
import HelpPanel from "../components/HelpPanel.jsx";

const DOC_TYPES = [
  { id: "discharge_summary", label: "Виписний епікриз" },
  { id: "case_history_section", label: "Розділ історії хвороби" },
  { id: "dissertation_section", label: "Розділ дисертації" },
];

// Поля, що ідентифікують пацієнта. ВАЖЛИВО: значення цих полів НІКОЛИ не
// потрапляють у виклик generateDocument() і, відповідно, ніколи не йдуть на
// бекенд/до Claude/в audit-лог — вони живуть лише в стані цього компонента
// (у пам'яті браузера) і підставляються в готовий текст локально.
// Токени {{...}} — те, що модель вставляє замість цих даних
// (див. backend/app/prompts.py, PASSPORT_PLACEHOLDER_BLOCK і DOC_TEMPLATES).
const PASSPORT_FIELDS = [
  { key: "patientName", token: "{{PATIENT_NAME}}", label: "ПІБ пацієнта", fallback: "[ВКАЗАТИ: ПІБ пацієнта]" },
  { key: "patientDob", token: "{{PATIENT_DOB}}", label: "Дата народження / вік", fallback: "[ВКАЗАТИ: дата народження]" },
  { key: "patientSex", token: "{{PATIENT_SEX}}", label: "Стать", fallback: "[ВКАЗАТИ: стать]" },
  { key: "cardNumber", token: "{{CARD_NUMBER}}", label: "№ медичної картки", fallback: "[ВКАЗАТИ: № медичної картки]" },
  { key: "admissionDate", token: "{{ADMISSION_DATE}}", label: "Дата госпіталізації", fallback: "[ВКАЗАТИ: дата госпіталізації]" },
  { key: "operationDate", token: "{{OPERATION_DATE}}", label: "Дата операції", fallback: "[ВКАЗАТИ: дата операції]" },
  { key: "dischargeDate", token: "{{DISCHARGE_DATE}}", label: "Дата виписки", fallback: "[ВКАЗАТИ: дата виписки]" },
  { key: "doctorName", token: "{{DOCTOR_NAME}}", label: "ПІБ лікаря", fallback: "[ВКАЗАТИ: ПІБ лікаря]" },
];

const EMPTY_PASSPORT = Object.fromEntries(PASSPORT_FIELDS.map((f) => [f.key, ""]));

// Підставляє локально введені дані пацієнта на місце токенів у тексті від
// бекенда. Незаповнене поле лишає звичайний плейсхолдер [ВКАЗАТИ: ...].
// Будь-який невідомий токен {{...}} (якщо модель вигадала свій, у т.ч.
// кирилицею: {{ПІБ}}) теж не показуємо сирим — перетворюємо на плейсхолдер.
function fillPassportTokens(text, passport) {
  let out = text;
  for (const f of PASSPORT_FIELDS) {
    const value = passport[f.key]?.trim();
    out = out.split(f.token).join(value || f.fallback);
  }
  return out.replace(
    /\{\{\s*([^{}]+?)\s*\}\}/g,
    (_, name) => `[ВКАЗАТИ: ${name.replace(/_/g, " ").toLowerCase()}]`
  );
}

// У markdown одиночний перенос рядка склеює рядки в один абзац — паспортна
// частина («ПІБ: … / Дата народження: …») перетворювалась на суцільний текст.
// У документі кожен рядок значущий, тож робимо одиночні переноси жорсткими
// (два пробіли в кінці рядка). Порожні рядки між абзацами не чіпаємо.
function preserveLineBreaks(md) {
  return md.replace(/([^\n])\n(?=[^\n])/g, "$1  \n");
}

const EXTRA_FIELDS = [
  { key: "complaints", label: "Скарги", rows: 2, placeholder: "Напр.: біль і деформація в ділянці правого стегна, неможливість стати на ногу" },
  { key: "anamnesis", label: "Анамнез / механізм травми", rows: 2, placeholder: "Напр.: падіння з висоти власного зросту вдома, доставлена бригадою ЕМД" },
  { key: "examination", label: "Об'єктивний / локальний статус", rows: 3, placeholder: "Напр.: зовнішня ротація і вкорочення правої нижньої кінцівки, нейросудинних порушень немає" },
  { key: "investigations", label: "Результати обстежень (рентген, КТ, лабораторні)", rows: 2, placeholder: "Напр.: рентгенографія — субкапітальний перелом шийки стегна, Garden IV" },
  { key: "discharge_status", label: "Стан при виписці", rows: 2, placeholder: "Напр.: задовільний, рана загоїлась первинним натягом, ходить з ходунками" },
  { key: "recommendations", label: "Рекомендації лікаря", rows: 2, placeholder: "Власні рекомендації (необов'язково)" },
];

const INPUT_CLS =
  "mt-1 w-full resize-y rounded-lg border border-slate-300 p-2 text-sm focus:border-teal-500 focus:outline-none";

function downloadDoc(html, docType) {
  // HTML з MIME application/msword Word відкриває як документ (.doc) без
  // додаткових бібліотек. Кодування явно UTF-8 для кирилиці.
  const page = `<!DOCTYPE html><html><head><meta charset="utf-8"><title>Документ</title>
<style>body{font-family:'Times New Roman',serif;font-size:12pt;line-height:1.4}h1{font-size:14pt}h2{font-size:12.5pt;margin-top:14pt}table{border-collapse:collapse}td,th{border:1px solid #999;padding:3pt 6pt}</style>
</head><body>${html}</body></html>`;
  const blob = new Blob(["﻿", page], { type: "application/msword" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  const label = DOC_TYPES.find((d) => d.id === docType)?.label || "Документ";
  a.href = url;
  a.download = `${label} ${new Date().toISOString().slice(0, 10)}.doc`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

export default function DocumentsView() {
  const [form, setForm] = useState({
    doc_type: "discharge_summary",
    diagnosis: "",
    procedure: "",
    notes: "",
    complaints: "",
    anamnesis: "",
    examination: "",
    investigations: "",
    discharge_status: "",
    recommendations: "",
    typical_recommendations: true,
  });
  const [showExtra, setShowExtra] = useState(false);
  const [passport, setPassport] = useState(EMPTY_PASSPORT);
  const [result, setResult] = useState(null);
  const [startedAt, setStartedAt] = useState(null);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);
  const docRef = useRef(null);
  const loading = startedAt !== null;

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  const setPassportField = (k) => (e) => setPassport({ ...passport, [k]: e.target.value });
  const isDischarge = form.doc_type === "discharge_summary";

  async function onSubmit(e) {
    e.preventDefault();
    if (!form.diagnosis.trim() || loading) return;
    setStartedAt(Date.now());
    setError("");
    setResult(null);
    try {
      // Лише клінічні поля form — дані пацієнта (passport) сюди НЕ входять.
      const data = await generateDocument(form);
      setResult(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setStartedAt(null);
    }
  }

  async function copyText() {
    const text = docRef.current?.innerText || "";
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setError("Не вдалося скопіювати — виділіть текст вручну.");
    }
  }

  return (
    <div className="space-y-4">
      <HelpPanel>
        <p>
          Оберіть тип документа і заповніть те, що знаєте: обов'язковий лише <b>діагноз</b>. Чим
          більше клінічних даних (скарги, анамнез, огляд, обстеження, перебіг), тим менше
          пропусків <code>[ВКАЗАТИ: …]</code> буде в чернетці — AI нічого не вигадує про пацієнта.
        </p>
        <p>
          <b>Дані пацієнта</b> (ПІБ, дати, № картки) — лише в синьому блоці: вони не надсилаються
          AI і підставляються в текст прямо у вашому браузері.
        </p>
        <p>
          «Типові рекомендації» — AI додасть загальноприйняті рекомендації для цього діагнозу з
          позначкою «(типова рекомендація — перевірте)». Готовий текст можна скопіювати або
          завантажити файлом для Word.
        </p>
      </HelpPanel>

      <form onSubmit={onSubmit} className="space-y-3">
        <div>
          <label className="block text-sm font-medium text-slate-700">Тип документа</label>
          <select value={form.doc_type} onChange={set("doc_type")} className={INPUT_CLS}>
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
            placeholder="Напр.: закритий субкапітальний перелом шийки правої стегнової кістки, Garden IV"
            className={INPUT_CLS}
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700">Проведене лікування / втручання</label>
          <textarea
            value={form.procedure}
            onChange={set("procedure")}
            rows={2}
            placeholder="Напр.: тотальне безцементне ендопротезування правого кульшового суглоба"
            className={INPUT_CLS}
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700">Перебіг / примітки</label>
          <textarea
            value={form.notes}
            onChange={set("notes")}
            rows={3}
            placeholder="Напр.: післяопераційний період без ускладнень, вертикалізована на 2-гу добу"
            className={INPUT_CLS}
          />
        </div>

        <div className="rounded-lg border border-slate-200 bg-white">
          <button
            type="button"
            onClick={() => setShowExtra(!showExtra)}
            className="flex w-full items-center justify-between px-3 py-2 text-left text-sm font-medium text-slate-700 hover:bg-slate-50"
            aria-expanded={showExtra}
          >
            <span>Додаткові клінічні дані (менше пропусків у документі)</span>
            <span className="text-slate-400">{showExtra ? "−" : "+"}</span>
          </button>
          {showExtra && (
            <div className="space-y-3 border-t border-slate-100 p-3">
              {EXTRA_FIELDS.map((f) => (
                <div key={f.key}>
                  <label className="block text-sm font-medium text-slate-700">{f.label}</label>
                  <textarea
                    value={form[f.key]}
                    onChange={set(f.key)}
                    rows={f.rows}
                    placeholder={f.placeholder}
                    className={INPUT_CLS}
                  />
                </div>
              ))}
            </div>
          )}
        </div>

        {isDischarge && (
          <label className="flex items-start gap-2 text-sm text-slate-700">
            <input
              type="checkbox"
              checked={form.typical_recommendations}
              onChange={(e) => setForm({ ...form, typical_recommendations: e.target.checked })}
              className="mt-0.5"
            />
            <span>
              Запропонувати типові рекомендації для цього діагнозу{" "}
              <span className="text-slate-500">(позначаються «типова рекомендація — перевірте»)</span>
            </span>
          </label>
        )}

        {isDischarge && (
          <div className="space-y-2 rounded-lg border border-sky-200 bg-sky-50 p-3">
            <p className="text-xs font-medium text-sky-800">
              Дані пацієнта — залишаються лише у вашому браузері, AI їх не бачить. Заповніть один
              раз, і вони самі підставляться в усі потрібні місця чернетки.
            </p>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              {PASSPORT_FIELDS.map((f) => (
                <div key={f.key}>
                  <label className="block text-xs text-slate-600">{f.label}</label>
                  <input
                    type="text"
                    aria-label={f.label}
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
          ⚠ У клінічних полях не вказуйте ПІБ, дати народження чи № картки — цей текст іде до AI.{" "}
          {isDischarge
            ? "Для цих даних — синій блок вище."
            : "На їх місці модель залишить плейсхолдери [ВКАЗАТИ: …]."}
        </p>

        <button
          type="submit"
          disabled={loading || !form.diagnosis.trim()}
          className="rounded-lg bg-teal-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-teal-700 disabled:opacity-50"
        >
          {loading ? "Генерація…" : "Згенерувати чернетку"}
        </button>
      </form>

      {loading && <Elapsed startedAt={startedAt} hint="документ — зазвичай 20–60 с" />}

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div>
      )}

      {result && (
        <div className="space-y-3">
          <div className="rounded-lg border border-slate-200 bg-white p-4">
            <div className="mb-3 flex flex-wrap items-center gap-2">
              <h2 className="mr-auto text-sm font-semibold text-slate-500">Чернетка</h2>
              <button
                type="button"
                onClick={copyText}
                className="rounded border border-slate-300 px-2.5 py-1 text-xs font-medium text-slate-700 hover:border-teal-500 hover:text-teal-700"
              >
                {copied ? "Скопійовано" : "Копіювати текст"}
              </button>
              <button
                type="button"
                onClick={() => downloadDoc(docRef.current?.innerHTML || "", form.doc_type)}
                className="rounded border border-slate-300 px-2.5 py-1 text-xs font-medium text-slate-700 hover:border-teal-500 hover:text-teal-700"
              >
                Завантажити для Word
              </button>
            </div>
            <Markdown ref={docRef} text={preserveLineBreaks(fillPassportTokens(result.text, passport))} />
          </div>
          <p className="text-xs italic text-slate-500">{result.disclaimer}</p>
        </div>
      )}
    </div>
  );
}
