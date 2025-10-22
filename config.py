# Список ФИ для РТП (без ID)
RTP_LIST = [
    "Чепик Ольга",
    "Матвеева Анастасия",
    "Ионов Александр",
    "Туманцева Ольга",
    "Ворфоломеева Ольга"
]

RM_MN_IDS = [
    123456789,  # Замените на реальный Telegram ID РМ
    987654321   # Замените на реальный Telegram ID МН
]

# Шаблоны вопросов для отчёта
QUESTIONS = [
    {"key": "meetings_ca", "question": "Встречи по ЦА:"},
    {"key": "self_meetings", "question": "Самоназначенные встречи:"},
    {"key": "meetings_stars", "question": "Встречи от 1-4 звезд:"},
    {"key": "knk_opened", "question": "Открыто КНК :"},
    {"key": "entered_mln", "question": "Заведено млн. :"},
    {"key": "salary_projects", "question": "Зарплатные проекты :"},
    {"key": "trade_acquiring", "question": "Торговый эквайринг :"},
    {"key": "premier", "question": "Премьер :"},
    {"key": "sberhealth", "question": "Сберздоровье тыс.:"},
    {"key": "industry_solutions", "question": "Отраслевые решения :"},
    {"key": "credit_potential", "question": "Кредитный потенциал :"},
    {"key": "leasing", "question": "Лизинг млн.:"},
    {"key": "ved", "question": "ВЭД :"},
    {"key": "insurance_ths", "question": "Страхование тыс. :"},
    {"key": "bk", "question": "БК :"},
    {"key": "deposits_new_mln", "question": "Депозиты - новые деньги млн. :"},
    {"key": "accredits_ths", "question": "Аккредитивы тыс. :"},
    {"key": "calls_count", "question": "Количество звонков :"},
    {"key": "chats", "question": "Чаты :"},
    {"key": "stars_count", "question": "Количество звезд :"},
    {"key": "ckp_realized", "question": "Реализованно ЦКП :"}
]


# Шаблон для форматирования итогового отчёта
def format_report(data):
    total_meetings = int(data.get('meetings_ca', 0)) + int(data.get('self_meetings', 0))
    report = f"""
1. Раздел. Модель общения:
• Встречи по ЦА {data.get('meetings_ca', 0)}
• Самоназначенные встречи {data.get('self_meetings', 0)}
• Встречи от 1-4 звезд {data.get('meetings_stars', 0)}
• Всего встреч {total_meetings}

2. Продуктовый раздел: 
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

3. Сервисный раздел
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
        product = data.get(f'ckp_{i}_comment', '')
        report += f"  ИНН {inn} - {product}\n"

    return report
