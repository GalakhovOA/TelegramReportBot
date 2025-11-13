# main.py
import os
import asyncio
from dotenv import load_dotenv
from datetime import datetime
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler,
    filters, ContextTypes
)
import config
import database

# --- load .env ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOTENV_PATH = os.path.join(BASE_DIR, '.env')
if os.path.exists(DOTENV_PATH):
    load_dotenv(dotenv_path=DOTENV_PATH)
else:
    load_dotenv()

TOKEN = os.getenv('BOT_TOKEN')
if not TOKEN:
    print("ERROR: BOT_TOKEN not found in environment. Put it to .env or env variable BOT_TOKEN")

# --- Runtime state (in-memory) ---
# structure: {user_id: {'mode': 'manual/mkk/rtp', 'step': int, 'data': {}, 'editing': bool, ...}}
user_states = {}

def safe_state(user_id):
    st = user_states.get(user_id)
    if st is None:
        st = {'mode': 'manual', 'step': 0, 'data': {}, 'editing': False}
        user_states[user_id] = st
    return st

# --- Helpers ---
def build_main_menu():
    keyboard = [
        [InlineKeyboardButton("Отчет МКК", callback_data='role_mkk')],
        [InlineKeyboardButton("Отчеты РТП", callback_data='role_rtp')],
        [InlineKeyboardButton("Ручное заполнение", callback_data='role_manual')],
        [InlineKeyboardButton("Сменить ФИ/РТП", callback_data='change_info')]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.effective_message
    await msg.reply_text("Выберите роль:", reply_markup=build_main_menu())

# Callback: общая обработка нажатий кнопок
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return
    user_id = query.from_user.id
    data = query.data
    await query.answer()
    state = user_states.get(user_id, {})

    # return to menu
    if data == 'return_to_menu':
        user_states.pop(user_id, None)
        await query.edit_message_text("Выберите роль:", reply_markup=build_main_menu())
        return

    # role selection
    if data.startswith('role_'):
        role = data.split('_', 1)[1]
        user_states[user_id] = {'mode': role, 'step': 0, 'data': {}, 'editing': False}
        await handle_role_selection(query, user_id, role)
        return

    # choose rtp
    if data.startswith('choose_rtp_'):
        try:
            index = int(data.split('_')[2])
        except Exception:
            await query.edit_message_text("Ошибка выбора. Попробуйте снова.")
            return
        if index < 0 or index >= len(config.RTP_LIST):
            await query.edit_message_text("Ошибка: некорректный индекс РТП.")
            return
        selected = config.RTP_LIST[index]
        role = state.get('mode', 'manual')

        if role == 'rtp':
            # set as manager with selected FI
            try:
                database.add_user(user_id, 'manager', selected)
            except Exception as e:
                print("DB add_user error:", e)
            state.pop('choosing_rtp', None)
            await query.edit_message_text(f"Выбрано ФИ: {selected}. Показываем меню.")
            await show_manager_menu(query)
            return

        # else employee linking
        name = state.get('name')
        if not name:
            await query.edit_message_text("Ошибка: имя не задано. Повторите ввод.")
            return
        try:
            database.add_user(user_id, 'employee', name, selected)
        except Exception as e:
            print("DB add_user error:", e)
        state.pop('choosing_rtp', None)
        state.pop('name', None)
        state.update({'step': 0, 'data': {}, 'editing': False})
        await query.edit_message_text(f"Привязка к {selected} успешна. Начинаем отчёт.")
        await ask_next_question(query.message, user_id)
        return

    # change info
    if data == 'change_info':
        role = state.get('mode', 'manual')
        try:
            database.set_user_name(user_id, None)
        except Exception:
            pass
        if role == 'mkk':
            try:
                database.set_manager_fi_for_employee(user_id, None)
            except Exception:
                pass
        user_states[user_id] = {'mode': role, 'entering_name': True}
        if role == 'rtp':
            await show_rtp_buttons(query, "Выберите ваше ФИ из списка:")
        else:
            await query.edit_message_text("Данные сброшены. Введите новое имя:")
            await query.message.reply_text("Пожалуйста, введите ваше имя (для фиксации в системе):")
        return

    # manager actions: show reports
    if data == 'rtp_show_reports':
        today = datetime.now().strftime('%Y-%m-%d')
        manager_fi = database.get_user_name(user_id)
        employees = database.get_employees(manager_fi)
        text = f"Отчеты на {today}:\n"
        reports = database.get_all_reports_on_date(today, manager_fi)
        reported_ids = [uid for uid, _ in reports]
        for uid, name in employees:
            status = '✅' if uid in reported_ids else ' '
            display_name = name or str(uid)
            text += f"Сотрудник {display_name}: {status}\n"
        keyboard = [[InlineKeyboardButton("Выбрать другую дату", callback_data='select_date_show')]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data == 'rtp_detailed_reports':
        today = datetime.now().strftime('%Y-%m-%d')
        manager_fi = database.get_user_name(user_id)
        reports = database.get_all_reports_on_date(today, manager_fi)
        text = f"Детальные отчеты на {today}:\n"
        for uid, rdata in reports:
            name = database.get_user_name(uid) or str(uid)
            text += f"Сотрудник {name}:\n{config.format_report(rdata)}\n\n"
        keyboard = [[InlineKeyboardButton("Выбрать другую дату", callback_data='select_date_detailed')]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data == 'rtp_combine_reports':
        today = datetime.now().strftime('%Y-%m-%d')
        manager_fi = database.get_user_name(user_id)
        reports = database.get_all_reports_on_date(today, manager_fi)
        if not reports:
            await query.edit_message_text("Нет отчетов на сегодня.")
            return

        # combine numeric keys and collect fckp products
        combined = {}
        fckp_products = []
        for _, rdata in reports:
            for key, val in rdata.items():
                if key == 'fckp_products':
                    if isinstance(val, list):
                        fckp_products.extend(val)
                else:
                    try:
                        combined[key] = combined.get(key, 0) + int(val or 0)
                    except Exception:
                        pass

        combined['fckp_products'] = fckp_products
        # fckp_realized computed length
        combined['fckp_realized'] = len(fckp_products)

        text = config.format_report(combined)
        text += "\n\n" + config.OPERATIONAL_DEFECTS_BLOCK

        keyboard = [
            [InlineKeyboardButton("Редактировать", callback_data='edit_combined')],
            [InlineKeyboardButton("Выбрать другую дату", callback_data='select_date_combine')],
            [InlineKeyboardButton("Отправить РМ/МН", callback_data='send_to_rm_mn')]
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data == 'send_to_rm_mn':
        report_date = datetime.now().strftime('%Y-%m-%d')
        manager_fi = database.get_user_name(user_id)
        reports = database.get_all_reports_on_date(report_date, manager_fi)
        if not reports:
            await query.edit_message_text("Нет отчётов для отправки.")
            return

        # combine
        combined = {}
        fckp_products = []
        for _, rdata in reports:
            for key, val in rdata.items():
                if key == 'fckp_products':
                    if isinstance(val, list):
                        fckp_products.extend(val)
                else:
                    try:
                        combined[key] = combined.get(key, 0) + int(val or 0)
                    except Exception:
                        pass
        combined['fckp_products'] = fckp_products
        combined['fckp_realized'] = len(fckp_products)

        formatted = config.format_report(combined)
        formatted += "\n\n" + config.OPERATIONAL_DEFECTS_BLOCK

        name = database.get_user_name(user_id) or str(user_id)
        for rm_mn_id in getattr(config, 'RM_MN_IDS', []):
            try:
                await context.bot.send_message(chat_id=rm_mn_id,
                                               text=f"Объединённый отчёт от РТП {name} на {report_date}:\n{formatted}")
            except Exception as e:
                print(f"Ошибка отправки РМ/МН {rm_mn_id}: {e}")
        await query.edit_message_text("Отчёт отправлен РМ/МН.")
        return

    if data == 'edit_report':
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
        return

    if data == 'send_report':
        report_date = datetime.now().strftime('%Y-%m-%d')
        data_report = database.get_report(user_id, report_date)
        if data_report:
            formatted = config.format_report(data_report)
            name = database.get_user_name(user_id) or str(user_id)
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
        return

    if data.startswith('select_date_'):
        parts = data.split('_')
        if len(parts) >= 3:
            mode = parts[2]
            await query.edit_message_text("Введите дату (YYYY-MM-DD):")
            st = safe_state(user_id)
            st['select_mode'] = mode
        else:
            await query.edit_message_text("Ошибка выбора режима даты.")
        return

    # FCKP product selection callbacks use prefix 'fckp_prod_...'
    if data.startswith('fckp_prod_'):
        # callback format: fckp_prod_<product>
        prod = data.split('fckp_prod_', 1)[1]
        st = safe_state(user_id)
        # save product to state fckp_products
        st.setdefault('fckp_products', []).append(prod)
        st['fckp_left'] = st.get('fckp_left', 0) - 1
        left = st.get('fckp_left', 0)
        if left > 0:
            # update message prompting next choice
            keyboard = [[InlineKeyboardButton(p, callback_data=f"fckp_prod_{p}")] for p in config.FCKP_OPTIONS]
            try:
                await query.edit_message_text(f"Вы выбрали {prod}. Осталось указать ещё {left} ФЦКП.",
                                              reply_markup=InlineKeyboardMarkup(keyboard))
            except Exception:
                pass
            return
        else:
            # finished selecting
            st['data']['fckp_products'] = st.get('fckp_products', [])
            # ensure fckp_realized updated to length
            st['data']['fckp_realized'] = len(st['fckp_products']) if st.get('fckp_products') else 0
            try:
                await query.edit_message_text("Все ФЦКП указаны ✅")
            except Exception:
                pass
            # continue to next question
            st['step'] = st.get('step', 0) + 1
            await ask_next_question(query.message, user_id)
            return

# -------------------- Helpers for role selection and asking/questions --------------------

async def handle_role_selection(query_or_update, user_id, role):
    # query_or_update can be CallbackQuery or Update.Message
    # get db stored name
    name = database.get_user_name(user_id)
    if role == 'rtp':
        user_states[user_id] = {'mode': role, 'choosing_rtp': True}
        await show_rtp_buttons(query_or_update, "Выберите ваше ФИ из списка:")
        return

    if name and role == 'mkk':
        manager_fi = database.get_manager_fi_for_employee(user_id)
        if manager_fi:
            user_states[user_id] = {'mode': role, 'step': 0, 'data': {}}
            try:
                await query_or_update.edit_message_text("Роль выбрана.")
            except Exception:
                try:
                    await query_or_update.reply_text("Роль выбрана.")
                except Exception:
                    pass
            await start_filling(query_or_update, user_id)
            return
        else:
            user_states[user_id] = {'mode': role, 'choosing_rtp': True, 'name': name}
            await show_rtp_buttons(query_or_update, "Выберите вашего РТП:")
            return

    user_states[user_id] = {'mode': role, 'entering_name': True}
    try:
        await query_or_update.edit_message_text("Роль выбрана.")
    except Exception:
        try:
            await query_or_update.reply_text("Роль выбрана.")
        except Exception:
            pass
    try:
        await query_or_update.message.reply_text("Пожалуйста, введите ваше имя (для фиксации в системе):")
    except Exception:
        pass

async def show_rtp_buttons(query_or_message, text):
    if not config.RTP_LIST:
        try:
            await query_or_message.reply_text("Список РТП не настроен. Обратитесь к администратору.")
        except Exception:
            pass
        return
    keyboard = [[InlineKeyboardButton(fi, callback_data=f"choose_rtp_{i}")] for i, fi in enumerate(config.RTP_LIST)]
    try:
        await query_or_message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception:
        try:
            await query_or_message.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        except Exception:
            pass

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return
    user_id = msg.from_user.id
    text = (msg.text or "").strip()
    state = user_states.get(user_id, {})

    # sessionless
    if not state:
        if text.lower() == "вернуться в меню":
            await start(update, context)
            return
        await msg.reply_text("Сессия не запущена или истекла. Начните заново /start.")
        return

    if text.lower() == "вернуться в меню":
        user_states.pop(user_id, None)
        await start(update, context)
        return

    # entering name (first time)
    if state.get('entering_name'):
        name = text
        role = state.get('mode', 'manual')
        state['name'] = name
        state.pop('entering_name', None)
        # store name in DB
        try:
            database.add_user(user_id, 'employee' if role == 'mkk' else role, name)
        except Exception as e:
            print("DB add_user error:", e)
        if role == 'mkk':
            state['choosing_rtp'] = True
            await show_rtp_buttons(update, "Выберите вашего РТП:")
        else:
            await msg.reply_text("Пожалуйста, выберите ваше ФИ из списка кнопок.")
        return

    # user must choose rtp from buttons
    if state.get('choosing_rtp'):
        await msg.reply_text("Пожалуйста, выберите РТП из списка кнопок.")
        return

    # date selection handling (for manager choose date)
    if 'select_mode' in state:
        try:
            date = datetime.strptime(text, '%Y-%m-%d').strftime('%Y-%m-%d')
            manager_fi = database.get_user_name(user_id) if state.get('mode') == 'rtp' else None
            mode = state.pop('select_mode', None)
            if mode == 'show':
                employees = database.get_employees(manager_fi)
                text_out = f"Отчеты на {date}:\n"
                reports = database.get_all_reports_on_date(date, manager_fi)
                reported_ids = [uid for uid, _ in reports]
                for uid, name in employees:
                    status = '✅' if uid in reported_ids else ' '
                    display_name = name or str(uid)
                    text_out += f"Сотрудник {display_name}: {status}\n"
                await msg.reply_text(text_out)
            elif mode == 'detailed':
                reports = database.get_all_reports_on_date(date, manager_fi)
                text_out = f"Детальные отчеты на {date}:\n"
                for uid, rdata in reports:
                    name = database.get_user_name(uid) or str(uid)
                    text_out += f"Сотрудник {name}:\n{config.format_report(rdata)}\n\n"
                await msg.reply_text(text_out)
            elif mode == 'combine':
                reports = database.get_all_reports_on_date(date, manager_fi)
                if not reports:
                    await msg.reply_text("Нет отчетов на эту дату.")
                    return
                combined = {}
                fckp_products = []
                for _, rdata in reports:
                    for key, val in rdata.items():
                        if key == 'fckp_products':
                            if isinstance(val, list):
                                fckp_products.extend(val)
                        else:
                            try:
                                combined[key] = combined.get(key, 0) + int(val or 0)
                            except Exception:
                                pass
                combined['fckp_products'] = fckp_products
                combined['fckp_realized'] = len(fckp_products)
                text_out = config.format_report(combined)
                text_out += "\n\n" + config.OPERATIONAL_DEFECTS_BLOCK
                await msg.reply_text(text_out)
            return
        except ValueError:
            await msg.reply_text("Неверный формат даты. Попробуйте снова (YYYY-MM-DD).")
            return

    # normal questionnaire handling for MKK
    if 'step' not in state:
        return

    step = state['step']
    # still inside QUESTIONS range?
    if step < len(config.QUESTIONS):
        q = config.QUESTIONS[step]
        # require numeric input
        if not text.isdigit():
            await msg.reply_text("Пожалуйста, введите число (цифрами).")
            return
        # store numeric (as int) except keep fckp for special flow
        if q['key'] == 'fckp_realized':
            # fckp: we store and then initiate button flow
            n = int(text)
            state['data'][q['key']] = n
            if n > 0:
                # prepare selection state
                state['fckp_left'] = n
                state['fckp_products'] = []
                # build keyboard for product selection
                keyboard = [[InlineKeyboardButton(p, callback_data=f"fckp_prod_{p}")] for p in config.FCKP_OPTIONS]
                await msg.reply_text(f"Вы указали {n} ФЦКП. Выберите оформленный продукт (1/{n}):",
                                     reply_markup=InlineKeyboardMarkup(keyboard))
                # do not advance step here; product selection callbacks will manage decrement and step increment
                return
            else:
                # zero -> continue to next question
                state['step'] += 1
                await ask_next_question(msg, user_id)
                return
        else:
            state['data'][q['key']] = int(text)
            state['step'] += 1
            await ask_next_question(msg, user_id)
            return
    else:
        # if beyond questions (should not normally happen)
        await msg.reply_text("Опрос завершён. Для возврата в меню нажмите 'Вернуться в меню' или /start.")
        return

# Ask next question helper
async def ask_next_question(message_or_query, user_id):
    st = user_states.get(user_id, {})
    step = st.get('step', 0)
    if step < len(config.QUESTIONS):
        q = config.QUESTIONS[step]
        current_value = st.get('data', {}).get(q['key'], '') if st.get('editing', False) else ''
        try:
            await message_or_query.reply_text(f"{q['question']} {f'(текущее: {current_value})' if current_value != '' else ''}")
        except Exception:
            try:
                await message_or_query.message.reply_text(f"{q['question']} {f'(текущее: {current_value})' if current_value != '' else ''}")
            except Exception as e:
                print("Failed to send question:", e)
    else:
        # finished questions -> finalize
        await finish_report(message_or_query, user_id)

async def start_filling(query_or_message, user_id, editing=False):
    st = safe_state(user_id)
    st['editing'] = editing
    st['step'] = 0
    st['data'] = st.get('data', {}) if editing else {}
    try:
        await query_or_message.edit_message_text("Начинаем заполнение отчёта.")
    except Exception:
        try:
            await query_or_message.reply_text("Начинаем заполнение отчёта.")
        except Exception:
            pass
    await ask_next_question(query_or_message, user_id)

async def finish_report(message_or_query, user_id):
    st = user_states.get(user_id, {})
    data = st.get('data', {}) or {}
    # if fckp_products present in state but not saved into data (in case of flow)
    if 'fckp_products' in st and st.get('fckp_products'):
        data['fckp_products'] = st.get('fckp_products')
        data['fckp_realized'] = len(st.get('fckp_products'))
    # ensure numeric keys present (set default 0)
    for q in config.QUESTIONS:
        data.setdefault(q['key'], 0)
    # save to DB (non-manual modes)
    try:
        if st.get('mode') != 'manual':
            database.save_report(user_id, data)
    except Exception as e:
        print("DB save_report error:", e)
    formatted = config.format_report(data)
    try:
        await message_or_query.reply_text(f"Итоговый отчет:\n{formatted}")
    except Exception:
        try:
            await message_or_query.message.reply_text(f"Итоговый отчет:\n{formatted}")
        except Exception:
            pass

    # actions keyboard
    keyboard = [
        [InlineKeyboardButton("Редактировать", callback_data='edit_report')],
        [InlineKeyboardButton("Сменить ФИ/РТП", callback_data='change_info')]
    ]
    if st.get('mode') == 'mkk':
        # вставляем кнопку отправки руководителю
        keyboard[0].insert(1, InlineKeyboardButton("Отправить руководителю", callback_data='send_report'))
    try:
        await message_or_query.reply_text("Действия:", reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception:
        pass

# show manager menu
async def show_manager_menu(query_or_message):
    keyboard = [
        [InlineKeyboardButton("Показать отчеты на дату", callback_data='rtp_show_reports')],
        [InlineKeyboardButton("Детальный отчет на дату", callback_data='rtp_detailed_reports')],
        [InlineKeyboardButton("Объединить и показать отчеты на дату", callback_data='rtp_combine_reports')]
    ]
    try:
        await query_or_message.edit_message_text("Меню руководителя:", reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception:
        try:
            await query_or_message.message.reply_text("Меню руководителя:", reply_markup=InlineKeyboardMarkup(keyboard))
        except Exception:
            pass

# error handler
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"Update {update} caused error {context.error}")

# set commands
async def set_commands(app):
    commands = [BotCommand("start", "Начать работу с ботом")]
    try:
        await app.bot.set_my_commands(commands)
    except Exception as e:
        print("Ошибка установки системных команд:", e)

# --- Run ---
if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler('start', start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    app.add_error_handler(error_handler)

    asyncio.get_event_loop().run_until_complete(set_commands(app))
    print("Бот запущен...")
    app.run_polling()
