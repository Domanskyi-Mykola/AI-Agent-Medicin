"""Делегування перевірки TLS-сертифікатів нативному сховищу довіри ОС.

Навіщо: якщо на машині активний антивірус/корпоративний проксі, що робить
MITM HTTPS (напр. Avast HTTPS scanning) або самопідписаний CA, — стандартна
перевірка через certifi падає (CERTIFICATE_VERIFY_FAILED). `truststore`
використовує сховище довіри ОС (Windows/macOS/Linux), яке такі сертифікати
приймає. На «чистих» машинах поведінка не змінюється.

Викликається один раз на старті процесу (main.py, ingest.py) ДО будь-яких
мережевих запитів. Якщо truststore не встановлено — тихо пропускаємо.
"""


def enable_os_trust_store() -> None:
    import os

    # Деякі антивіруси (Avast) інжектять SSLKEYLOGFILE у кожен процес, що може
    # ламати OpenSSL на Windows. Логувати TLS-ключі нам у будь-якому разі не треба.
    os.environ.pop("SSLKEYLOGFILE", None)

    try:
        import truststore

        truststore.inject_into_ssl()
    except Exception:  # noqa: BLE001 — не критично, лишаємо стандартну перевірку
        pass
