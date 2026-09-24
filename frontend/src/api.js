// Тонкий клієнт до бекенда. Запити йдуть на /api (локально — через vite-proxy
// на :8000; у продакшні фронтенд і API на одному домені).

// Складні клінічні питання й довгі документи можуть займати до хвилини-двох.
// Довше чекати не має сенсу: краще показати зрозумілу помилку і кнопку повтору,
// ніж нескінченний «Обробка…».
const TIMEOUT_MS = 150_000;

async function postJSON(path, body) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), TIMEOUT_MS);
  let res;
  try {
    res = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: ctrl.signal,
    });
  } catch (err) {
    if (err.name === "AbortError") {
      throw new Error(
        "Сервер не відповів за 2,5 хвилини. Спробуйте ще раз; якщо повторюється — сервер, імовірно, перевантажений або перезапускається."
      );
    }
    throw new Error("Немає з'єднання із сервером. Перевірте інтернет і спробуйте ще раз.");
  } finally {
    clearTimeout(timer);
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    if (res.status === 502 || res.status === 503) {
      throw new Error(
        data.detail ||
          "Сервер тимчасово недоступний (перезапускається або бракує ресурсів). Спробуйте через хвилину."
      );
    }
    if (res.status === 422 && Array.isArray(data.detail)) {
      throw new Error("Перевірте введені дані: деякі поля заповнені некоректно.");
    }
    throw new Error(data.detail || `Помилка ${res.status}`);
  }
  return data;
}

export const askChat = (question) => postJSON("/api/chat", { question });

export const generateDocument = (payload) => postJSON("/api/documents/generate", payload);
