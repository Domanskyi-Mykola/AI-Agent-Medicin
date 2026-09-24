import { forwardRef } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

// Перетворює посилання на джерела [3] або [2, 5] у markdown-посилання на
// відповідний пункт списку джерел (#<prefix>-3). Нечислові дужки на кшталт
// [ВКАЗАТИ: ...] не чіпає.
function linkCitations(text, prefix) {
  if (!prefix) return text;
  return text.replace(/\[(\d{1,3}(?:\s*,\s*\d{1,3})*)\](?!\()/g, (_, group) =>
    group
      .split(",")
      .map((n) => `[${n.trim()}](#${prefix}-${n.trim()})`)
      .join("")
  );
}

const Markdown = forwardRef(function Markdown({ text, citePrefix }, ref) {
  return (
    <div className="md" ref={ref}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ href, children }) =>
            href && href.startsWith("#") ? (
              <a
                href={href}
                className="cite"
                onClick={(e) => {
                  const anchor = document.getElementById(href.slice(1));
                  // Кілька номерів одного джерела показані одним рядком —
                  // підсвічуємо весь рядок, а не лише якір номера.
                  const el = anchor?.closest(".cite-target") || anchor;
                  if (el) {
                    e.preventDefault();
                    el.scrollIntoView({ behavior: "smooth", block: "center" });
                    el.classList.add("bg-teal-100");
                    setTimeout(() => el.classList.remove("bg-teal-100"), 1500);
                  }
                }}
              >
                [{children}]
              </a>
            ) : (
              <a href={href} target="_blank" rel="noreferrer" className="text-teal-700 underline">
                {children}
              </a>
            ),
        }}
      >
        {linkCitations(text || "", citePrefix)}
      </ReactMarkdown>
    </div>
  );
});

export default Markdown;
