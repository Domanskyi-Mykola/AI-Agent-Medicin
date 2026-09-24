"""Діагностика ресурсів процесу (для health-чеку і логів старту).

Головна причина падінь на хостингу — брак оперативної пам'яті: embedding-модель
+ torch займають ~1.5 ГБ. Показуємо RSS, щоб це було видно в /api/health і в
логах деплою, а не лише як загадкове «Application failed to respond».
"""
from typing import Optional


def rss_mb() -> Optional[float]:
    """Resident set size процесу в МБ (Linux: /proc; інакше — psutil, якщо є)."""
    try:
        with open("/proc/self/status", encoding="utf-8") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return round(int(line.split()[1]) / 1024, 1)
    except OSError:
        pass
    try:
        import psutil  # type: ignore

        return round(psutil.Process().memory_info().rss / 1024 / 1024, 1)
    except Exception:  # noqa: BLE001
        return None


def memory_limit_mb() -> Optional[float]:
    """Ліміт пам'яті контейнера (cgroup v2/v1), якщо його видно зсередини."""
    for path in ("/sys/fs/cgroup/memory.max", "/sys/fs/cgroup/memory/memory.limit_in_bytes"):
        try:
            with open(path, encoding="utf-8") as f:
                raw = f.read().strip()
            if raw.isdigit() and int(raw) < 1 << 50:
                return round(int(raw) / 1024 / 1024, 1)
        except OSError:
            continue
    return None
