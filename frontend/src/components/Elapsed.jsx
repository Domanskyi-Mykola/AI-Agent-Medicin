import { useEffect, useState } from "react";

// Лічильник секунд під час очікування відповіді: без нього 20–40 секунд
// тиші виглядають як «зависло» (саме так це сприймалось на демо).
export default function Elapsed({ startedAt, hint }) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);
  const sec = Math.max(0, Math.round((now - startedAt) / 1000));
  return (
    <div className="flex items-center gap-2 text-sm text-slate-500">
      <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-teal-600 border-t-transparent" />
      <span>
        Готую відповідь… <span className="tabular-nums">{sec} с</span>
      </span>
      {hint && <span className="text-xs text-slate-400">· {hint}</span>}
    </div>
  );
}
