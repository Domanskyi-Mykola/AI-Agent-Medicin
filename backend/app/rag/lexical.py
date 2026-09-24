"""Лексичний пошук (BM25) по чанках бази знань.

Навіщо поряд із векторним: на ~800 чанках однодоменного тексту
multilingual-e5-base дає дуже близькі відстані (0.13–0.15) для десятків
фрагментів, і точні терміни питання («передня хрестоподібна зв'язка»,
«Schatzker VI», «Jones») губляться серед загально схожих розділів інших
статей. BM25 ловить саме збіг термінів; retriever зливає обидва списки (RRF).

Морфологія: замість повноцінного стемера — обрізання слова до префікса
(«переломів»/«перелому» → «перел»). Для BM25 по вузькому домену цього досить,
а залежностей і пам'яті не додає. Індекс будується в пам'яті з чанків
векторної БД при першому запиті (~800 чанків — частки секунди).
"""
from __future__ import annotations

import math
import re
import threading
from collections import Counter

from app.rag.vector_store import Chunk, get_vector_store

_PREFIX = 5
_K1 = 1.5
_B = 0.75

_WORD_RE = re.compile(r"[a-zа-яіїєґ0-9]+")
_APOSTROPHES = re.compile(r"['’ʼ`]")

# Службові слова, що трапляються в питаннях, але не несуть теми.
_STOP = {
    "при", "для", "або", "після", "без", "під", "над", "які", "яка", "який", "яке",
    "що", "чим", "коли", "його", "цей", "ця", "це", "між", "від", "про", "так", "всі",
    "усі", "має", "може", "треба", "потрібно", "чи", "як", "та", "the", "and",
    "как", "что", "при", "или", "это", "так", "его",
}


# Скорочення, якими статті бази користуються замість повних назв (і навпаки
# лікар може написати повну назву). Розгортаємо їх і в чанках, і в питаннях —
# інакше «передня хрестоподібна зв'язка» не знаходить розділ про «ПХЗ».
_ABBREVIATIONS = {
    "ПХЗ": "передня хрестоподібна зв'язка",
    "ЗХЗ": "задня хрестоподібна зв'язка",
    "МКЗ": "медіальна колатеральна зв'язка",
    "ЛКЗ": "латеральна колатеральна зв'язка",
    "ЗЛК": "заднолатеральний кут",
    "ВТЕУ": "венозні тромбоемболічні ускладнення",
    "ВТЕ": "венозна тромбоемболія",
    "ТЕЛА": "тромбоемболія легеневої артерії",
    "ТГВ": "тромбоз глибоких вен",
    "НМГ": "низькомолекулярний гепарин",
    "НФГ": "нефракціонований гепарин",
    "ПОАК": "пероральні антикоагулянти",
    "АВН": "аваскулярний некроз",
    "НПЗП": "нестероїдні протизапальні препарати",
    "ЧМТ": "черепно-мозкова травма",
    "ДТП": "дорожньо-транспортна пригода",
    "МВТ": "мінно-вибухова травма",
    "ПХО": "первинна хірургічна обробка",
    "КРБС": "комплексний регіонарний больовий синдром",
    "АКС": "акроміально-ключичний суглоб",
    "ДПЛС": "дистальний променево-ліктьовий суглоб",
    "АЗФ": "апарат зовнішньої фіксації",
    "УЗД": "ультразвукове дослідження",
    "СРБ": "с-реактивний білок",
    "ШОЕ": "швидкість осідання еритроцитів",
    "КТ": "комп'ютерна томографія",
    "МРТ": "магнітно-резонансна томографія",
}
_ABBR_RE = re.compile(r"(?<![\w-])(" + "|".join(_ABBREVIATIONS) + r")(?![\w-])", re.IGNORECASE)


def _expand_abbreviations(text: str) -> str:
    return _ABBR_RE.sub(lambda m: f"{m.group(0)} {_ABBREVIATIONS[m.group(0).upper()]}", text)


def tokenize(text: str) -> list[str]:
    text = _APOSTROPHES.sub("", _expand_abbreviations(text).lower()).replace("ё", "е")
    out = []
    for w in _WORD_RE.findall(text):
        if len(w) < 3 or w in _STOP:
            continue
        out.append(w[:_PREFIX] if len(w) > _PREFIX else w)
    return out


_SECTION_WEIGHT = 3


def _index_text(chunk: Chunk) -> str:
    # Назва статті + розділ + текст. Заголовок розділу повторюємо кілька разів:
    # у статтях він формулює суть розділу («лікування розриву ПХЗ і показання
    # до реконструкції»), і збіг питання із заголовком важливіший за збіг
    # зі словом десь у тексті. Заміри 2026-09: профільний розділ у контексті
    # 8/14 проти 4/14 без ваги (разом з top_k 10 -> 14).
    m = chunk.metadata
    section = (m.get("section", "") + " ") * _SECTION_WEIGHT
    return f"{m.get('title') or m.get('source_name', '')} {section}\n{chunk.text}"


class _BM25:
    def __init__(self, chunks: list[Chunk]):
        self.chunks = chunks
        self.tfs = [Counter(tokenize(_index_text(c))) for c in chunks]
        self.lens = [sum(tf.values()) for tf in self.tfs]
        self.avg = (sum(self.lens) / len(self.lens)) if self.lens else 0.0
        df = Counter()
        for tf in self.tfs:
            df.update(tf.keys())
        n = len(chunks)
        self.idf = {t: math.log(1 + (n - d + 0.5) / (d + 0.5)) for t, d in df.items()}

    def search(self, query: str, k: int) -> list[tuple[Chunk, float]]:
        terms = [t for t in dict.fromkeys(tokenize(query)) if t in self.idf]
        if not terms:
            return []
        scored = []
        for i, tf in enumerate(self.tfs):
            s = 0.0
            for t in terms:
                f = tf.get(t)
                if f:
                    s += self.idf[t] * f * (_K1 + 1) / (f + _K1 * (1 - _B + _B * self.lens[i] / self.avg))
            if s > 0:
                scored.append((i, s))
        scored.sort(key=lambda x: x[1], reverse=True)
        return [(self.chunks[i], s) for i, s in scored[:k]]


_lock = threading.Lock()
_index: _BM25 | None = None
_indexed_count = -1


def _get_index() -> _BM25:
    """Індекс перебудовується, якщо кількість чанків у БД змінилась (ingest)."""
    global _index, _indexed_count
    store = get_vector_store()
    n = store.count()
    with _lock:
        if _index is None or n != _indexed_count:
            _index = _BM25(store.all_chunks())
            _indexed_count = n
        return _index


def lexical_search(query: str, k: int) -> list[tuple[Chunk, float]]:
    return _get_index().search(query, k)
