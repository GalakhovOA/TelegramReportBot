import os
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import config
import database
from datetime import datetime
import asyncio

load_dotenv()
TOKEN = os.getenv('BOT_TOKEN')

# Состояния пользователя
user_states = {}  # {user_id: {'mode': 'manual/mkk/rtp', 'step': 0, 'data': {}, 'editing': False, ...}}

# -------------------- Основные функции -------------------- #

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    keyboard = [
        [InlineKeyboardButton("Отчет МКК", callback_data='role_mkk')],
        [InlineKeyboardButton("Отчеты РТП", callback_data='role_rtp')],
        [InlineKeyboardButton("Ручное заполнение", callback_data='role_manual')],
        [InlineKeyboardButton("Сменить ФИ/РТП", callback_data='change_info')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выберите роль:", reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    await query.answer()

    if data == 'return_to_menu':
        del user_states[user_id]
        keyboard = [
            [InlineKeyboardButton("Отчет МКК", callback_data='role_mkk')],
            [InlineKeyboardButton("Отчеты РТП", callback_data='role_rtp')],
            [InlineKeyboardButton("Ручное заполнение", callback_data='role_manual')],
            [InlineKeyboardButton("Сменить ФИ/РТП", callback_data='change_info')]
        ]
        await query.edit_message_text("Выберите роль:", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data.startswith('role_'):
        role = data.split('_')[1]
        user_states[user_id] = {'mode': role, 'step': 0, 'data': {}, 'editing': False}
        await handle_role_selection(query, user_id, role)

    elif data.startswith('choose_rtp_'):
        index = int(data.split('_')[2])
        selected_rtp_fi = config.RTP_LIST[index]
        role = user_states[user_id]['mode']
        if role == 'rtp':
            name = selected_rtp_fi
            database.add_user(user_id, 'manager', name)
            del user_states[user_id]['choosing_rtp']
            await query.edit_message_text(f"Выбрано ФИ: {name}. Показываем меню.")
            await show_manager_menu(query)
        else:
            name = user_states[user_id]['name']
            database.add_user(user_id, 'employee', name, selected_rtp_fi)
            del user_states[user_id]['choosing_rtp']
            del user_states[user_id]['name']
            await query.edit_message_text(f"Привязка к {selected_rtp_fi} успешна. Начинаем отчёт.")
            user_states[user_id]['step'] = 0
            user_states[user_id]['data'] = {}
            user_states[user_id]['editing'] = False
            await ask_next_question(query.message, user_id)

    elif data == 'change_info':
        role = user_states.get(user_id, {}).get('mode', 'manual')
        database.set_user_name(user_id, None)
        if role == 'mkk':
            database.set_manager_fi_for_employee(user_id, None)
        user_states[user_id] = {'mode': role, 'entering_name': True}
        if role == 'rtp':
            await show_rtp_buttons(query, "Выберите ваше ФИ из списка:")
        else:
            await query.edit_message_text("Данные сброшены. Введите новое имя:")
            await query.message.reply_text("Пожалуйста, введите ваше имя (для фиксации в системе):")

    elif data == 'rtp_show_reports':
        today = datetime.now().strftime('%Y-%m-%d')
        manager_fi = database.get_user_name(user_id)
        employees = database.get_employees(manager_fi)
        text = f"Отчеты на {today}:\n"
        reports = database.get_all_reports_on_date(today, manager_fi)
        reported_ids = [uid for uid, _ in reports]
        for uid, name in employees:
            status = '✅' if uid in reported_ids else ' '
            display_name = name or uid
            text += f"Сотрудник {display_name}: {status}\n"
        keyboard = [[InlineKeyboardButton("Выбрать другую дату", callback_data='select_date_show')]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == 'rtp_detailed_reports':
        today = datetime.now().strftime('%Y-%m-%d')
        manager_fi = database.get_user_name(user_id)
        reports = database.get_all_reports_on_date(today, manager_fi)
        text = f"Детальные отчеты на {today}:\n"
        for uid, rdata in reports:
            name = database.get_user_name(uid) or uid
            text += f"Сотрудник {name}:\n{config.format_report(rdata)}\n\n"
        keyboard = [[InlineKeyboardButton("Выбрать другую дату", callback_data='select_date_detailed')]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == 'rtp_combine_reports':
        today = datetime.now().strftime('%Y-%m-%d')
        manager_fi = database.get_user_name(user_id)
        reports = database.get_all_reports_on_date(today, manager_fi)
        if not reports:
            await query.edit_message_text("Нет отчетов на сегодня.")
            return
        combined = {}
        stars = []
        ckps = []
        for _, rdata in reports:
            for key in rdata:
                if key.startswith('star_') or key.startswith('ckp_'):
                    continue
                combined[key] = combined.get(key, 0) + int(rdata.get(key, 0))
            for i in range(int(rdata.get('stars_count', 0))):
                inn = rdata.get(f'star_{i}_inn', '')
                comment = rdata.get(f'star_{i}_comment', '')
                stars.append(f"ИНН {inn} - {comment}")
            for i in range(int(rdata.get('ckp_realized', 0))):
                inn = rdata.get(f'ckp_{i}_inn', '')
                product = rdata.get(f'ckp_{i}_product', '')
                ckps.append(f"ИНН {inn} - {product}")
        combined['stars_count'] = len(stars)
        combined['ckp_realized'] = len(ckps)
        text = config.format_report(combined)
        text += "\nЗвезды: " + ", ".join(stars)
        text += "\nЦКП: " + ", ".join(ckps)
        keyboard = [
            [InlineKeyboardButton("Редактировать", callback_data='edit_combined')],
            [InlineKeyboardButton("Выбрать другую дату", callback_data='select_date_combine')],
            [InlineKeyboardButton("Отправить РМ/МН", callback_data='send_to_rm_mn')]
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == 'send_to_rm_mn':
        report_date = datetime.now().strftime('%Y-%m-%d')
        manager_fi = database.get_user_name(user_id)
        reports = database.get_all_reports_on_date(report_date, manager_fi)
        if not reports:
            await query.edit_message_text("Нет отчётов для отправки.")
            return
        combined = {}
        stars = []
        ckps = []
        for _, rdata in reports:
            for key in rdata:
                if key.startswith('star_') or key.startswith('ckp_'):
                    continue
                combined[key] = combined.get(key, 0) + int(rdata.get(key, 0))
            for i in range(int(rdata.get('stars_count', 0))):
                inn = rdata.get(f'star_{i}_inn', '')
                comment = rdata.get(f'star_{i}_comment', '')
                stars.append(f"ИНН {inn} - {comment}")
            for i in range(int(rdata.get('ckp_realized', 0))):
                inn = rdata.get(f'ckp_{i}_inn', '')
                product = rdata.get(f'ckp_{i}_product', '')
                ckps.append(f"ИНН {inn} - {product}")
        combined['stars_count'] = len(stars)
        combined['ckp_realized'] = len(ckps)
        formatted = config.format_report(combined)
        formatted += "\nЗвезды: " + ", ".join(stars)
        formatted += "\nЦКП: " + ", ".join(ckps)
        name = database.get_user_name(user_id) or user_id
        for rm_mn_id in config.RM_MN_IDS:
            try:
                await context.bot.send_message(chat_id=rm_mn_id,
                                               text=f"Объединённый отчёт от РТП {name} на {report_date}:\n{formatted}")
            except Exception as e:
                print(f"Ошибка отправки РМ/МН {rm_mn_id}: {e}")
        await query.edit_message_text("Отчёт отправлен РМ/МН.")

    elif data == 'edit_report':
        if user_id not in user_states:
            role = database.get_user_role(user_id) or 'manual'
            user_states[user_id] = {'mode': role, 'step': 0, 'data': {}, 'editing': True}
        else:
            user_states[user_id]['editing'] = True
            user_states[user_id]['step'] = 0
        report_date = datetime.now().strftime('%Y-%m-%d')
        report_data = database.get_report(user_id, report_date) or {}
        user_states[user_id]['data'] = report_data
        await query.edit_message_text("Начинаем редактирование.")
        await ask_next_question(query.message, user_id)

    elif data == 'send_report':
        report_date = datetime.now().strftime('%Y-%m-%d')
        data_report = database.get_report(user_id, report_date)
        if data_report:
            formatted = config.format_report(data_report)
            name = database.get_user_name(user_id) or user_id
            manager_fi = database.get_manager_fi_for_employee(user_id)
            if manager_fi:
                manager_id = database.get_manager_id_by_fi(manager_fi)
                if manager_id:
                    try:
                        await context.bot.send_message(chat_id=manager_id,
                                                       text=f"Отчёт от сотрудника {name} на {report_date}:\n{formatted}")
                        await query.edit_message_text("Отчёт отправлен руководителю.")
                    except Exception as e:
                        print(f"Ошибка отправки менеджеру {manager_fi}: {e}")
                        await query.edit_message_text("Ошибка отправки отчёта.")
                else:
                    await query.edit_message_text(f"Руководитель {manager_fi} не найден в системе.")
            else:
                await query.edit_message_text("Руководитель не привязан.")
        else:
            await query.edit_message_text("Ошибка: отчёт не найден.")

    elif data == 'edit_combined':
        await query.edit_message_text("Редактирование объединённого отчёта пока не поддерживается.")

    elif data.startswith('select_date_'):
        mode = data.split('_')[2]
        await query.edit_message_text("Введите дату (YYYY-MM-DD):")
        user_states[user_id]['select_mode'] = mode

# -------------------- Помощники -------------------- #

async def handle_role_selection(query, user_id, role):
    name = database.get_user_name(user_id)
    if role == 'rtp':
        user_states[user_id] = {'mode': role, 'choosing_rtp': True}
        await show_rtp_buttons(query, "Выберите ваше ФИ из списка:")
    elif name and role == 'mkk':
        manager_fi = database.get_manager_fi_for_employee(user_id)
        if manager_fi:
            user_states[user_id] = {'mode': role, 'step': 0, 'data': {}}
            await query.edit_message_text("Роль выбрана.")
            await start_filling(query, user_id)
        else:
            user_states[user_id] = {'mode': role, 'choosing_rtp': True, 'name': name}
            await show_rtp_buttons(query, "Выберите вашего РТП:")
    else:
        user_states[user_id] = {'mode': role, 'entering_name': True}
        await query.edit_message_text("Роль выбрана.")
        await query.message.reply_text("Пожалуйста, введите ваше имя (для фиксации в системе):")

async def show_rtp_buttons(query, text):
    if not config.RTP_LIST:
        await query.message.reply_text("Список РТП не настроен. Обратитесь к администратору.")
        return
    keyboard = [[InlineKeyboardButton(fi, callback_data=f"choose_rtp_{i}")] for i, fi in enumerate(config.RTP_LIST)]
    await query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text.strip()
    state = user_states.get(user_id, {})

    if not state:
        if text == "Вернуться в меню":
            await start(update, context)
            return
        await update.message.reply_text("Сессия истекла. Начните заново с /start.")
        return

    if text == "Вернуться в меню":
        del user_states[user_id]
        await start(update, context)
        return

    if 'entering_name' in state and state['entering_name']:
        name = text
        role = state['mode']
        state['name'] = name
        del state['entering_name']
        if role == 'mkk':
            state['choosing_rtp'] = True
            await show_rtp_buttons(update, "Выберите вашего РТП:")
        else:
            await update.message.reply_text("Пожалуйста, выберите ваше ФИ из списка кнопок.")
        return

    if 'choosing_rtp' in state and state['choosing_rtp']:
        await update.message.reply_text("Пожалуйста, выберите РТП из списка кнопок.")
        return

    if 'select_mode' in state:
        try:
            date = datetime.strptime(text, '%Y-%m-%d').strftime('%Y-%m-%d')
            manager_fi = database.get_user_name(user_id) if state['mode'] == 'rtp' else None
            if state['select_mode'] == 'show':
                employees = database.get_employees(manager_fi)
                text_out = f"Отчеты на {date}:\n"
                reports = database.get_all_reports_on_date(date, manager_fi)
                reported_ids = [uid for uid, _ in reports]
                for uid, name in employees:
                    status = '✅' if uid in reported_ids else ' '
                    display_name = name or uid
                    text_out += f"Сотрудник {display_name}: {status}\n"
                await update.message.reply_text(text_out)
            elif state['select_mode'] == 'detailed':
                reports = database.get_all_reports_on_date(date, manager_fi)
                text_out = f"Детальные отчеты на {date}:\n"
                for uid, rdata in reports:
                    name = database.get_user_name(uid) or uid
                    text_out += f"Сотрудник {name}:\n{config.format_report(rdata)}\n\n"
                await update.message.reply_text(text_out)
            elif state['select_mode'] == 'combine':
                reports = database.get_all_reports_on_date(date, manager_fi)
                if not reports:
                    await update.message.reply_text("Нет отчетов на эту дату.")
                    return
                combined = {}
                stars = []
                ckps = []
                for _, rdata in reports:
                    for key in rdata:
                        if key.startswith('star_') or key.startswith('ckp_'):
                            continue
                        combined[key] = combined.get(key, 0) + int(rdata.get(key, 0))
                    for i in range(int(rdata.get('stars_count', 0))):
                        inn = rdata.get(f'star_{i}_inn', '')
                        comment = rdata.get(f'star_{i}_comment', '')
                        stars.append(f"ИНН {inn} - {comment}")
                    for i in range(int(rdata.get('ckp_realized', 0))):
                        inn = rdata.get(f'ckp_{i}_inn', '')
                        product = rdata.get(f'ckp_{i}_product', '')
                        ckps.append(f"ИНН {inn} - {product}")
                combined['stars_count'] = len(stars)
                combined['ckp_realized'] = len(ckps)
                text_out = config.format_report(combined)
                text_out += "\nЗвезды: " + ", ".join(stars)
                text_out += "\nЦКП: " + ", ".join(ckps)
                keyboard = [[InlineKeyboardButton("Редактировать", callback_data='edit_combined')]]
                await update.message.reply_text(text_out, reply_markup=InlineKeyboardMarkup(keyboard))
            del user_states[user_id]['select_mode']
        except ValueError:
            await update.message.reply_text("Неверный формат даты. Попробуйте снова (YYYY-MM-DD).")
        return

    if 'step' not in state:
        return

    step = state['step']
    if step < len(config.QUESTIONS):
        q = config.QUESTIONS[step]
        state['data'][q['key']] = text
        state['step'] += 1
        await ask_next_question(update.message, user_id)
    else:
        if 'stars_left' in state and state['stars_left'] > 0:
            if 'current_star_inn' not in state:
                state['data'][f'star_{state["stars_count"] - state["stars_left"]}_inn'] = text
                state['current_star_inn'] = True
                await update.message.reply_text("Комментарий (За счет чего звезда, премьер или расширение и т.д.):")
            else:
                state['data'][f'star_{state["stars_count"] - state["stars_left"]}_comment'] = text
                state['stars_left'] -= 1
                del state['current_star_inn']
                if state['stars_left'] > 0:
                    await update.message.reply_text(f"ИНН организации для звезды {state['stars_count'] - state['stars_left'] + 1}:")
                else:
                    await ask_ckp_questions(update, user_id)
        elif 'ckp_left' in state and state['ckp_left'] > 0:
            if 'current_ckp_inn' not in state:
                state['data'][f'ckp_{state["ckp_realized"] - state["ckp_left"]}_inn'] = text
                state['current_ckp_inn'] = True
                await update.message.reply_text("Что за продукт:")
            else:
                state['data'][f'ckp_{state["ckp_realized"] - state["ckp_left"]}_comment'] = text
                state['ckp_left'] -= 1
                del state['current_ckp_inn']
                if state['ckp_left'] > 0:
                    await update.message.reply_text(f"ИНН организации для ЦКП {state['ckp_realized'] - state['ckp_left'] + 1}:")
                else:
                    await finish_report(update.message, user_id)

# -------------------- Вспомогательные функции -------------------- #

async def start_filling(query, user_id, editing=False):
    state = user_states[user_id]
    if editing:
        await query.edit_message_text("Редактирование отчета. Ответьте на вопросы заново (текущие значения показаны).")
    else:
        await query.edit_message_text("Начинаем заполнение отчета.")
    await ask_next_question(query.message, user_id)

async def ask_next_question(message, user_id):
    state = user_states[user_id]
    step = state['step']
    if step < len(config.QUESTIONS):
        q = config.QUESTIONS[step]
        current_value = state['data'].get(q['key'], '') if state.get('editing', False) else ''
        await message.reply_text(f"{q['question']} {f'(текущее: {current_value})' if current_value else ''}")
    else:
        stars_count = int(state['data'].get('stars_count', 0))
        if stars_count > 0:
            state['stars_left'] = stars_count
            state['stars_count'] = stars_count
            await message.reply_text("ИНН организации для звезды 1:")
        else:
            await ask_ckp_questions(message, user_id)

async def ask_ckp_questions(message, user_id):
    state = user_states[user_id]
    ckp_count = int(state['data'].get('ckp_realized', 0))
    if ckp_count > 0:
        state['ckp_left'] = ckp_count
        state['ckp_realized'] = ckp_count
        await message.reply_text("ИНН организации для ЦКП 1:")
    else:
        await finish_report(message, user_id)

async def finish_report(message, user_id):
    state = user_states[user_id]
    data = state['data']
    formatted = config.format_report(data)
    await message.reply_text(f"Итоговый отчет:\n{formatted}")
    keyboard = [
        [InlineKeyboardButton("Редактировать", callback_data='edit_report')],
        [InlineKeyboardButton("Сменить ФИ/РТП", callback_data='change_info')]
    ]
    if state['mode'] == 'mkk':
        keyboard[0].insert(1, InlineKeyboardButton("Отправить руководителю", callback_data='send_report'))
    await message.reply_text("Действия:", reply_markup=InlineKeyboardMarkup(keyboard))
    if state['mode'] != 'manual':
        database.save_report(user_id, data)

async def show_manager_menu(query):
    keyboard = [
        [InlineKeyboardButton("Показать отчеты на дату", callback_data='rtp_show_reports')],
        [InlineKeyboardButton("Детальный отчет на дату", callback_data='rtp_detailed_reports')],
        [InlineKeyboardButton("Объединить и показать отчеты на дату", callback_data='rtp_combine_reports')]
    ]
    await query.edit_message_text("Меню руководителя:", reply_markup=InlineKeyboardMarkup(keyboard))

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"Update {update} caused error {context.error}")

# -------------------- Установка команд -------------------- #

async def set_commands(app):
    commands = [
        BotCommand("start", "Начать работу с ботом")
    ]
    try:
        await app.bot.set_my_commands(commands)
        print("Системные команды установлены: только /start")
    except Exception as e:
        print("Ошибка установки системных команд:", e)

# -------------------- Запуск -------------------- #

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler('start', start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    app.add_error_handler(error_handler)

    asyncio.get_event_loop().run_until_complete(set_commands(app))

    app.run_polling()
