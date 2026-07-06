"""Заглушка автентифікації для MVP.

Повноцінна автентифікація (JWT, ролі, реєстрація лікарів) свідомо
відкладена — див. docs/ARCHITECTURE.md, розділ "Відкладено на потім".
"""


def get_current_user() -> dict:
    return {"id": "dev-user", "name": "Лікар (dev)", "role": "doctor"}
