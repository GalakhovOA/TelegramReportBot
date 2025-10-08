import os
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import config
import database
from datetime import datetime

load_dotenv()
TOKEN = os.getenv('BOT_TOKEN')

# Состояния пользователя (для FSM-подобной логики)
user_states = {}  # {user_id: {'mode': 'manual/employee/manager', 'step': 0, 'data': {}, 'editing': False}}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    keyboard = [
        [InlineKeyboardButton("Сотрудник", callback_data='role_employee')],
        [InlineKeyboardButton("Руководитель", callback_data='role_manager')],
        [InlineKeyboardButton("Ручное заполнение", callback_data='role_manual')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выберите роль:", reply_markup=reply_markup)


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    await query.answer()

    if data.startswith('role_'):
        role = data.split('_')[1]
        if role == 'manager' and user_id in config.ALLOWED_MANAGERS:
            database.add_user(user_id, 'manager')
            user_states[user_id] = {'mode': 'manager', 'step': 0, 'data': {}}
            await show_manager_menu(query)
        elif role == 'employee' and user_id in config.ALLOWED_EMPLOYEES:
            database.add_user(user_id, 'employee')
            user_states[user_id] = {'mode': 'employee', 'step': 0, 'data': {}, 'editing': False}
            await start_filling(query, user_id)
        elif role == 'manual':
            user_states[user_id] = {'mode': 'manual', 'step': 0, 'data': {}, 'editing': False}
            await start_filling(query, user_id)
        else:
            await query.edit_message_text("Вашего ID не обнаружено. Доступно только ручное заполнение.")
            user_states[user_id] = {'mode': 'manual', 'step': 0, 'data': {}, 'editing': False}
            await start_filling(query, user_id)

    elif data == 'manager_show_reports':
        # Показать отчеты на дату (список сотрудников с галочками)
        today = datetime.now().strftime('%Y-%m-%d')
        employees = database.get_employees()
        text = f"Отчеты на {today}:\n"
        reports = database.get_all_reports_on_date(today)
        reported_ids = [uid for uid, _ in reports]
        for emp in employees:
            status = '✅' if emp in reported_ids else ' '
            text += f"Сотрудник {emp}: {status}\n"
        keyboard = [[InlineKeyboardButton("Выбрать другую дату", callback_data='select_date_show')]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == 'manager_detailed_reports':
        # Детальный отчет на дату
        today = datetime.now().strftime('%Y-%m-%d')
        reports = database.get_all_reports_on_date(today)
        text = f"Детальные отчеты на {today}:\n"
        for uid, rdata in reports:
            text += f"Сотрудник {uid}:\n{config.format_report(rdata)}\n\n"
        keyboard = [[InlineKeyboardButton("Выбрать другую дату", callback_data='select_date_detailed')]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == 'manager_combine_reports':
        # Объединенный отчет
        today = datetime.now().strftime('%Y-%m-%d')
        reports = database.get_all_reports_on_date(today)
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
            [InlineKeyboardButton("Выбрать другую дату", callback_data='select_date_combine')]
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith('edit_'):
        user_states[user_id]['editing'] = True
        user_states[user_id]['data'] = database.get_report(user_id, datetime.now().strftime('%Y-%m-%d')) or \
                                       user_states[user_id]['data']
        user_states[user_id]['step'] = 0
        await start_filling(query, user_id, editing=True)

    # Обработка дат (упрощённо, без календаря - пользователь введёт текстом)
    elif data.startswith('select_date_'):
        mode = data.split('_')[2]
        await query.edit_message_text("Введите дату (YYYY-MM-DD):")
        user_states[user_id]['select_mode'] = mode


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text.strip()
    state = user_states.get(user_id, {})

    if 'select_mode' in state:
        # Обработка ввода даты
        try:
            date = datetime.strptime(text, '%Y-%m-%d').strftime('%Y-%m-%d')
            if state['select_mode'] == 'show':
                # Аналогично manager_show_reports, но на date
                employees = database.get_employees()
                text_out = f"Отчеты на {date}:\n"
                reports = database.get_all_reports_on_date(date)
                reported_ids = [uid for uid, _ in reports]
                for emp in employees:
                    status = '✅' if emp in reported_ids else ' '
                    text_out += f"Сотрудник {emp}: {status}\n"
                await update.message.reply_text(text_out)
            elif state['select_mode'] == 'detailed':
                reports = database.get_all_reports_on_date(date)
                text_out = f"Детальные отчеты на {date}:\n"
                for uid, rdata in reports:
                    text_out += f"Сотрудник {uid}:\n{config.format_report(rdata)}\n\n"
                await update.message.reply_text(text_out)
            elif state['select_mode'] == 'combine':
                reports = database.get_all_reports_on_date(date)
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
        # Динамические вопросы для звезд и ЦКП
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
                    await update.message.reply_text(
                        f"ИНН организации для звезды {state['stars_count'] - state['stars_left'] + 1}:")
                else:
                    await ask_ckp_questions(update.message, user_id)
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
                    await update.message.reply_text(
                        f"ИНН организации для ЦКП {state['ckp_realized'] - state['ckp_left'] + 1}:")
                else:
                    await finish_report(update.message, user_id)


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
        current_value = state['data'].get(q['key'], '') if state['editing'] else ''
        await message.reply_text(f"{q['question']} {f'(текущее: {current_value})' if current_value else ''}")
    else:
        # После базовых вопросов - динамика для звезд
        stars_count = int(state['data'].get('stars_count', 0))
        if stars_count > 0:
            state['stars_left'] = stars_count
            state['stars_count'] = stars_count  # Для подсчета
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

    keyboard = [[InlineKeyboardButton("Редактировать", callback_data='edit_report')]]
    if state['mode'] == 'employee':
        keyboard[0].append(InlineKeyboardButton("Отправить руководителю", callback_data='send_report'))
    await message.reply_text("Действия:", reply_markup=InlineKeyboardMarkup(keyboard))

    if state['mode'] != 'manual':
        database.save_report(user_id, data)
    del user_states[user_id]  # Сброс состояния


async def show_manager_menu(query):
    keyboard = [
        [InlineKeyboardButton("Показать отчеты на дату", callback_data='manager_show_reports')],
        [InlineKeyboardButton("Детальный отчет на дату", callback_data='manager_detailed_reports')],
        [InlineKeyboardButton("Объединить и показать отчеты на дату", callback_data='manager_combine_reports')]
    ]
    await query.edit_message_text("Меню руководителя:", reply_markup=InlineKeyboardMarkup(keyboard))


if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    app.run_polling()