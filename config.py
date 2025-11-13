# config.py

# Список ФИ для РТП (без ID)
RTP_LIST = [
    "Чепик Ольга",
    "Матвеева Анастасия",
    "Ионов Александр",
    "Туманцева Ольга",
    "Ворфоломеева Ольга"
]

# Список RM/MN для отправки объединенных отчетов (замени на реальные ID)
RM_MN_IDS = [
    123456789,
    987654321
]

# Вопросы новой формы (МКК вводит только числа)
QUESTIONS = [
    {"key": "meetings", "question": "1) Встречи (шт.)"},
    {"key": "meetings_stars", "question": "2) Встречи 1-4 звезды (шт.)"},
    {"key": "knk_opened", "question": "3) Открыто КНК (шт.)"},
    {"key": "fckp_realized", "question": "4) Реализовано ФЦКП (шт.)"},
    {"key": "leasing_leads", "question": "5) Лизинг передано лидов (шт.)"},
    {"key": "credit_potential", "question": "6) Расчет кредитного потенциала (шт.)"},
    {"key": "credits_issued", "question": "7) Кредиты выдано (млн)"},
    {"key": "otr", "question": "8) ОТР (шт.)"},
    {"key": "giga_assistant", "question": "9) Giga-ассистент (шт.)"},
    {"key": "pu", "question": "10) ПУ (шт.)"},
    {"key": "chats", "question": "11) Чатов (шт.)"}
]

# Варианты продуктов для ФЦКП
FCKP_OPTIONS = ["ТЭ", "ЗП", "БК", "ВЭД", "БГ", "РКО"]

# Форматирование индивидуального/объединённого отчёта
def format_report(data):
    """
    data: dict - может содержать:
      - числовые поля (ключи из QUESTIONS)
      - 'fckp_products' : list of product strings
    """
    def get(k, default=0):
        v = data.get(k, default)
        try:
            return int(v)
        except Exception:
            try:
                return int(float(v))
            except Exception:
                return default

    lines = []
    lines.append("Производительность")
    lines.append(f"1. Встречи - {get('meetings')} шт.")
    lines.append(f"2. Встречи 1-4 звезды - {get('meetings_stars')} шт.")
    lines.append(f"3. Открыто КНК - {get('knk_opened')} шт.")
    lines.append(f"4. Реализовано ФЦКП - {get('fckp_realized')} шт.")

    # детализируем по продуктам (распечатать счётчики по каждому варианту)
    products = data.get('fckp_products', []) or []
    # посчитаем по всем возможным вариантам (чтобы печатать порядок)
    prod_counts = {}
    for p in products:
        prod_counts[p] = prod_counts.get(p, 0) + 1

    # Печать всех вариантов в фиксированном порядке
    for opt in FCKP_OPTIONS:
        cnt = prod_counts.get(opt, 0)
        if cnt > 0:
            lines.append(f"{opt} - {cnt} шт")
        else:
            lines.append(f"{opt} - 0 шт")

    lines.append(f"5. Лизинг передано лидов - {get('leasing_leads')} шт.")
    lines.append(f"6. Расчет кредитного потенциала - {get('credit_potential')} шт.")
    lines.append(f"7. Кредиты выдано - {data.get('credits_issued', 0)} млн")
    lines.append(f"8. ОТР - {get('otr')} шт.")
    lines.append(f"9. Giga-ассистент - {get('giga_assistant')} шт.")
    lines.append(f"10. ПУ - {get('pu')} шт.")
    lines.append(f"11. Чатов - {get('chats')} шт")

    return "\n".join(lines)


# Блок "Опер. дефекты" (для РТП объединённого отчёта)
OPERATIONAL_DEFECTS_BLOCK = """
Опер. дефекты
1. Отрицательные заключение - нет шт.
2. Выход из МФ - 0 шт.
3. ИП с ограничениями - 0 шт.
4. Передача досье кредиты , ЗП , ТЭ - 0 шт.
5. Кредитные сделки на 1 стадии до 5 дней - 0 шт.
6. Наличие комментариев по встречам
7. Сформирована Повестка БУ - 0
""".strip()
