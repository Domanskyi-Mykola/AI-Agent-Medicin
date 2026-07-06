// Тонкий клієнт до бекенда. Запити йдуть на /api (через vite-proxy на :8000).

async function postJSON(path, body) {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.detail || `Помилка ${res.status}`);
  }
  return data;
}

export const askChat = (question) => postJSON("/api/chat", { question });

export const generateDocument = (payload) =>
  postJSON("/api/documents/generate", payload);
