# config.py

# Список ФИ для РТП (без ID)
RTP_LIST = [
    "Чепик Ольга",
    "Матвеева Анастасия",
    "Ионов Александр",
    "Туманцева Ольга",
    "Ворфоломеева Ольга"
]

# Список ФИ для РМ/МН (без ID)
RM_MN_LIST = [
    "Региональный менеджер",
    "Менеджер направления"
]

# Пароль для доступа к разделам руководителей (РТП и РМ/МН)
# Задай здесь удобный пароль (строка). Меняй при необходимости.
ADMIN_PASSWORD = "СРБ"

# Варианты продуктов для ФЦКП
FCKP_OPTIONS = ["ТЭ", "ЗП", "БК", "ВЭД", "БГ", "РКО"]

# Шаблоны вопросов для отчёта (можно корректировать)
QUESTIONS = [
    {"key": "meetings", "question": "1. Встречи - (шт):"},
    {"key": "meetings_stars", "question": "2. Встречи 1-4 звезды - (шт):"},
    {"key": "knk_opened", "question": "3. Открыто КНК - (шт):"},
    {"key": "fckp_realized", "question": "4. Реализовано ФЦКП - (шт):"},
    {"key": "leasing_leads", "question": "5. Лизинг передано лидов - (шт):"},
    {"key": "credit_potential", "question": "8. Расчет кредитного потенциала - (шт):"},
    {"key": "credits_issued_mln", "question": "9. Кредиты выдано - (млн):"},
    {"key": "otr", "question": "10. ОТР - (шт):"},
    {"key": "giga_assistant", "question": "11. Giga-ассистент - (шт):"},
    {"key": "pu", "question": "12. ПУ - (шт):"},
    {"key": "chats", "question": "13. Чатов - (шт):"}
]

# Блок операционных дефектов (показывается в объединённом отчёте у РТП)
OPERATIONAL_DEFECTS_BLOCK = """
Опер.дефекты
1. Отрицательные заключение - нет шт.
2. Выход из МФ - 0 шт.
3. ИП с ограничениями - 0 шт.
4. Передача досье кредиты , ЗП , ТЭ - 0 шт.
5. Кредитные сделки на 1 стадии до 5 дней - 0 шт.
6. Наличие комментариев по встречам
7. Сформирована Повестка БУ-0
"""

# Форматирование итогового отчёта — аккуратно с float
def format_value(v):
    try:
        if v is None or v == "":
            return "0"
        # If it's numeric-string, cast to float and format, else return as is
        if isinstance(v, (int, float)):
            # If integer-valued, show as int; else show as float with up to 2 decimals, strip trailing zeros
            if float(v).is_integer():
                return str(int(v))
            else:
                s = f"{float(v):.2f}".rstrip('0').rstrip('.')
                return s
        if isinstance(v, str):
            vs = v.replace(',', '.').strip()
            f = float(vs)
            if f.is_integer():
                return str(int(f))
            else:
                s = f"{f:.2f}".rstrip('0').rstrip('.')
                return s
    except Exception:
        return str(v)

def format_report(data):
    # data: dict with keys from QUESTIONS + possibly fckp_products list
    lines = []
    lines.append("Производительность")
    for q in QUESTIONS:
        val = data.get(q['key'], 0)
        lines.append(f"{q['question']} {format_value(val)}")
    # FCKP block
    lines.append("")
    lines.append("ФЦКП (детализация):")
    prod_counts = {}
    for p in data.get('fckp_products', []):
        prod_counts[p] = prod_counts.get(p, 0) + 1
    for opt in FCKP_OPTIONS:
        lines.append(f"{opt} - {format_value(prod_counts.get(opt, 0))} шт")
    return "\n".join(lines)
