# Список ФИ для РТП (без ID)
RTP_LIST = [
    "Чепик Ольга",
    "Матвеева Анастасия",
    "Ионов Александр",
    "Туманцева Ольга",
    "Ворфоломеева Ольга"
]

# Шаблоны вопросов для отчёта
QUESTIONS = [
    {"key": "meetings_ca", "question": "Встречи по ЦА (только цифра):"},
    {"key": "self_meetings", "question": "Самоназначенные встречи (только цифра):"},
    {"key": "meetings_stars", "question": "Встречи от 1-4 звезд (только цифра):"},
    {"key": "knk_opened", "question": "Открыто КНК (только цифра):"},
    {"key": "entered_mln", "question": "Заведено млн. (только цифра):"},
    {"key": "salary_projects", "question": "Зарплатные проекты (только цифра):"},
    {"key": "trade_acquiring", "question": "Торговый эквайринг (только цифра):"},
    {"key": "premier", "question": "Премьер (только цифра):"},
    {"key": "sberhealth", "question": "Сберздоровье (только цифра):"},
    {"key": "industry_solutions", "question": "Отраслевые решения (только цифра):"},
    {"key": "credit_potential", "question": "Кредитный потенциал (только цифра):"},
    {"key": "leasing", "question": "Лизинг (только цифра):"},
    {"key": "ved", "question": "ВЭД (только цифра):"},
    {"key": "insurance_ths", "question": "Страхование тыс. (только цифра):"},
    {"key": "bk", "question": "БК (только цифра):"},
    {"key": "deposits_new_mln", "question": "Депозиты - новые деньги млн. (только цифра):"},
    {"key": "accredits_ths", "question": "Аккредитивы тыс. (только цифра):"},
    {"key": "calls_count", "question": "Количество звонков (только цифра):"},
    {"key": "chats", "question": "Чаты (только цифра):"},
    {"key": "stars_count", "question": "Количество звезд (только цифра):"},
    {"key": "ckp_realized", "question": "Реализованные ЦКП (только цифра):"}
]


# Шаблон для форматирования итогового отчёта
def format_report(data):
    total_meetings = int(data.get('meetings_ca', 0)) + int(data.get('self_meetings', 0))
    report = f"""
1. Раздел. Модель общения (только цифра):
• Встречи по ЦА {data.get('meetings_ca', 0)}
• Самоназначенные встречи {data.get('self_meetings', 0)}
• Встречи от 1-4 звезд {data.get('meetings_stars', 0)}
• Всего встреч {total_meetings}

2. Продуктовый раздел (только цифра): 
• Открыто КНК {data.get('knk_opened', 0)}
• Заведено {data.get('entered_mln', 0)} млн.
• Зарплатные проекты {data.get('salary_projects', 0)}
• Торговый эквайринг {data.get('trade_acquiring', 0)}
• Премьер {data.get('premier', 0)}
• Сберздоровье {data.get('sberhealth', 0)}
• Отраслевые решения {data.get('industry_solutions', 0)}
• Кредитный потенциал {data.get('credit_potential', 0)}
• Лизинг {data.get('leasing', 0)}
• ВЭД {data.get('ved', 0)}
• Страхование {data.get('insurance_ths', 0)} тыс.
• БК {data.get('bk', 0)}
• Депозиты - новые деньги {data.get('deposits_new_mln', 0)} млн.
• Аккредитивы {data.get('accredits_ths', 0)} тыс.

3. Сервисный раздел (только цифра)
• Количество звонков {data.get('calls_count', 0)}
• Чаты {data.get('chats', 0)}

4. Приоритеты
• Количество звезд {data.get('stars_count', 0)}
"""
    for i in range(int(data.get('stars_count', 0))):
        inn = data.get(f'star_{i}_inn', '')
        comment = data.get(f'star_{i}_comment', '')
        report += f"  ИНН {inn} - {comment}\n"

    report += f"• Реализованные ЦКП {data.get('ckp_realized', 0)}\n"
    for i in range(int(data.get('ckp_realized', 0))):
        inn = data.get(f'ckp_{i}_inn', '')
        product = data.get(f'ckp_{i}_product', '')
        report += f"  ИНН {inn} - {product}\n"

    return report