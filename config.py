# config.py

# Список ФИ для РТП — пользователи РТП выбирают своё ФИ из списка
RTP_LIST = [
    "Ионов Александр",
    "Ворфоломеева Ольга",
    "Туманцева Ольга",
    "Чепик Ольга",
    "Матвеева Анастасия"
]

# Список ФИ для РМ/МН — пользователи РМ/МН выбирают своё ФИ из списка
RM_MN_LIST = [
    "Язева Ирина",
    "Румянцева Наталия"
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

# Форматирование отчёта (индивидуального или объединённого)
def format_report(data):
    def get_int(k):
        v = data.get(k, 0)
        try:
            return int(v)
        except Exception:
            try:
                return int(float(v))
            except Exception:
                return 0

    lines = []
    lines.append("Производительность")
    lines.append(f"1. Встречи - {get_int('meetings')} шт.")
    lines.append(f"2. Встречи 1-4 звезды - {get_int('meetings_stars')} шт.")
    lines.append(f"3. Открыто КНК - {get_int('knk_opened')} шт.")
    lines.append(f"4. Реализовано ФЦКП - {get_int('fckp_realized')} шт.")

    products = data.get('fckp_products') or []
    prod_counts = {}
    for p in products:
        prod_counts[p] = prod_counts.get(p, 0) + 1

    for opt in FCKP_OPTIONS:
        cnt = prod_counts.get(opt, 0)
        lines.append(f"{opt} - {cnt} шт")

    lines.append(f"5. Лизинг передано лидов - {get_int('leasing_leads')} шт.")
    lines.append(f"6. Расчет кредитного потенциала - {get_int('credit_potential')} шт.")
    credits_val = data.get('credits_issued', 0)
    lines.append(f"7. Кредиты выдано - {credits_val} млн")
    lines.append(f"8. ОТР - {get_int('otr')} шт.")
    lines.append(f"9. Giga-ассистент - {get_int('giga_assistant')} шт.")
    lines.append(f"10. ПУ - {get_int('pu')} шт.")
    lines.append(f"11. Чатов - {get_int('chats')} шт")

    return "\n".join(lines)


# Блок "Опер. дефекты" для объединённого отчёта РТП (прикрепляется у РТП и у РМ/МН)
OPERATIONAL_DEFECTS_BLOCK = """

Раздел с опер. дефектами и доп. информацией заполняется самостоятельно в ручную и направляется в группу ММБ

Остальной отчет будет направлен РМ/МН после нажатия кнопки

1. Отрицательные заключение 
2. Выход из МФ 
3. ИП с ограничениями - 
4. Передача досье кредиты , ЗП , ТЭ .
5. Кредитные сделки на 1 стадии до 5 дней 
6. Наличие комментариев по встречам
7. Сформирована Повестка БУ 
""".strip()

