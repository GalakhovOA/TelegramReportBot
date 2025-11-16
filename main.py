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

# load .env
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOTENV_PATH = os.path.join(BASE_DIR, '.env')
if os.path.exists(DOTENV_PATH):
    load_dotenv(dotenv_path=DOTENV_PATH)
else:
    load_dotenv()

TOKEN = os.getenv('BOT_TOKEN')
if not TOKEN:
    print("ERROR: BOT_TOKEN not found in environment. Put it to .env or env variable BOT_TOKEN")

# in-memory runtime state
# { user_id: {mode:'manual'/'mkk'/'rtp', step:int, data:dict, editing:bool, ...} }
user_states = {}

def safe_state(uid):
    st = user_states.get(uid)
    if not st:
        st = {'mode': 'manual', 'step': 0, 'data': {}, 'editing': False}
        user_states[uid] = st
    return st

def build_main_menu():
    keyboard = [
        [InlineKeyboardButton("Отчет МКК", callback_data='role_mkk')],
        [InlineKeyboardButton("Отчеты РТП", callback_data='role_rtp')],
        [InlineKeyboardButton("Ручное заполнение", callback_data='role_manual')],
        [InlineKeyboardButton("Сменить ФИ/РТП", callback_data='change_info')]
    ]
    return InlineKeyboardMarkup(keyboard)

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.effective_message
    await msg.reply_text("Выберите роль:", reply_markup=build_main_menu())

# общий обработчик callback'ов
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return
    uid = query.from_user.id
    data = query.data or ''
    await query.answer()
    st = user_states.get(uid, {})

    # возвращение в меню
    if data == 'return_to_menu':
        user_states.pop(uid, None)
        await query.edit_message_text("Выберите роль:", reply_markup=build_main_menu())
        return

    # выбор роли
    if data.startswith('role_'):
        role = data.split('_',1)[1]
        user_states[uid] = {'mode': role, 'step': 0, 'data': {}, 'editing': False}
        await handle_role_selection(query, uid, role)
        return

    # выбор РТП из списка
    if data.startswith('choose_rtp_'):
        try:
            idx = int(data.split('_')[2])
        except Exception:
            await query.edit_message_text("Ошибка выбора. Попробуйте снова.")
            return
        if idx < 0 or idx >= len(config.RTP_LIST):
            await query.edit_message_text("Ошибка: некорректный индекс РТП.")
            return
        selected = config.RTP_LIST[idx]
        role = st.get('mode','manual')

        if role == 'rtp':
            try:
                database.add_user(uid, 'manager', selected)
            except Exception as e:
                print("DB add_user error:", e)
            st.pop('choosing_rtp', None)
            await query.edit_message_text(f"Выбрано ФИ: {selected}. Показываем меню.")
            await show_manager_menu(query)
            return

        # employee linking
        name = st.get('name')
        if not name:
            await query.edit_message_text("Ошибка: имя не задано. Повторите ввод.")
            return
        try:
            database.add_user(uid, 'employee', name, selected)
        except Exception as e:
            print("DB add_user error:", e)
        st.pop('choosing_rtp', None)
        st.pop('name', None)
        st.update({'step': 0, 'data': {}, 'editing': False})
        await query.edit_message_text(f"Привязка к {selected} успешна. Начинаем отчёт.")
        await ask_next_question(query.message, uid)
        return

    # смена ФИ/РТП
    if data == 'change_info':
        role = st.get('mode','manual')
        try:
            database.set_user_name(uid, None)
        except Exception:
            pass
        if role == 'mkk':
            try:
                database.set_manager_fi_for_employee(uid, None)
            except Exception:
                pass
        user_states[uid] = {'mode': role, 'entering_name': True}
        if role == 'rtp':
            await show_rtp_buttons(query, "Выберите ваше ФИ из списка:")
        else:
            await query.edit_message_text("Данные сброшены. Введите новое имя:")
            await query.message.reply_text("Пожалуйста, введите ваше имя (для фиксации в системе):")
        return

    # РТП: показать отчеты
    if data == 'rtp_show_reports':
        date = datetime.now().strftime('%Y-%m-%d')
        manager_fi = database.get_user_name(uid)
        employees = database.get_employees(manager_fi)
        reports = database.get_all_reports_on_date(date, manager_fi)
        reported_ids = [u for u,_ in reports]
        text = f"Отчеты на {date}:\n"
        for u_eid, name in employees:
            status = '✅' if u_eid in reported_ids else ' '
            text += f"Сотрудник {name or str(u_eid)}: {status}\n"
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Выбрать другую дату", callback_data='select_date_show')]]))
        return

    if data == 'rtp_detailed_reports':
        date = datetime.now().strftime('%Y-%m-%d')
        manager_fi = database.get_user_name(uid)
        reports = database.get_all_reports_on_date(date, manager_fi)
        text = f"Детальные отчеты на {date}:\n"
        for u_id, rdata in reports:
            name = database.get_user_name(u_id) or str(u_id)
            text += f"Сотрудник {name}:\n{config.format_report(rdata)}\n\n"
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Выбрать другую дату", callback_data='select_date_detailed')]]))
        return

    if data == 'rtp_combine_reports':
        date = datetime.now().strftime('%Y-%m-%d')
        manager_fi = database.get_user_name(uid)
        reports = database.get_all_reports_on_date(date, manager_fi)
        if not reports:
            await query.edit_message_text("Нет отчетов на сегодня.")
            return

        combined = {}
        fckp_products = []
        for _, r in reports:
            for k, v in r.items():
                if k == 'fckp_products' and isinstance(v, list):
                    fckp_products.extend(v)
                else:
                    try:
                        combined[k] = combined.get(k, 0) + int(v or 0)
                    except Exception:
                        pass
        combined['fckp_products'] = fckp_products
        combined['fckp_realized'] = len(fckp_products)

        text = config.format_report(combined) + "\n\n" + config.OPERATIONAL_DEFECTS_BLOCK
        keyboard = [
            [InlineKeyboardButton("Редактировать", callback_data='edit_combined')],
            [InlineKeyboardButton("Выбрать другую дату", callback_data='select_date_combine')],
            [InlineKeyboardButton("Отправить РМ/МН", callback_data='send_to_rm_mn')]
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data == 'send_to_rm_mn':
        date = datetime.now().strftime('%Y-%m-%d')
        manager_fi = database.get_user_name(uid)
        reports = database.get_all_reports_on_date(date, manager_fi)
        if not reports:
            await query.edit_message_text("Нет отчётов для отправки.")
            return
        combined = {}
        fckp_products = []
        for _, r in reports:
            for k, v in r.items():
                if k == 'fckp_products' and isinstance(v, list):
                    fckp_products.extend(v)
                else:
                    try:
                        combined[k] = combined.get(k, 0) + int(v or 0)
                    except Exception:
                        pass
        combined['fckp_products'] = fckp_products
        combined['fckp_realized'] = len(fckp_products)
        formatted = config.format_report(combined) + "\n\n" + config.OPERATIONAL_DEFECTS_BLOCK
        name = database.get_user_name(uid) or str(uid)
        for rid in getattr(config, 'RM_MN_IDS', []):
            try:
                await context.bot.send_message(chat_id=rid, text=f"Объединённый отчёт от РТП {name} на {date}:\n{formatted}")
            except Exception as e:
                print("Ошибка отправки RM/MN:", e)
        await query.edit_message_text("Отчёт отправлен РМ/МН.")
        return

    # редактирование личного отчета
    if data == 'edit_report':
        # подготовка state для редактирования
        role = database.get_user_role(uid) or 'manual'
        user_states[uid] = {'mode': role, 'step': 0, 'data': {}, 'editing': True}
        date = datetime.now().strftime('%Y-%m-%d')
        rpt = database.get_report(uid, date) or {}
        user_states[uid]['data'] = rpt
        await query.edit_message_text("Начинаем редактирование.")
        await ask_next_question(query.message, uid)
        return

    # отправка руководителю (личный отчет)
    if data == 'send_report':
        date = datetime.now().strftime('%Y-%m-%d')
        rpt = database.get_report(uid, date)
        if not rpt:
            await query.edit_message_text("Ошибка: отчёт не найден.")
            return
        formatted = config.format_report(rpt)
        name = database.get_user_name(uid) or str(uid)
        manager_fi = database.get_manager_fi_for_employee(uid)
        if manager_fi:
            manager_id = database.get_manager_id_by_fi(manager_fi)
            if manager_id:
                try:
                    await context.bot.send_message(chat_id=manager_id, text=f"Отчёт от сотрудника {name} на {date}:\n{formatted}")
                    await query.edit_message_text("Отчёт отправлен руководителю.")
                except Exception as e:
                    print("Ошибка отправки руководителю:", e)
                    await query.edit_message_text("Ошибка отправки отчёта.")
            else:
                await query.edit_message_text(f"Руководитель {manager_fi} не найден в системе.")
        else:
            await query.edit_message_text("Руководитель не привязан.")
        return

    # выбор продукта ФЦКП (callback fckp_prod_<prod>)
    if data.startswith('fckp_prod_'):
        prod = data.split('fckp_prod_',1)[1]
        st = safe_state(uid)
        st.setdefault('fckp_products', [])
        st['fckp_products'].append(prod)
        st['fckp_left'] = st.get('fckp_left', 0) - 1
        left = st.get('fckp_left', 0)
        if left > 0:
            keyboard = [[InlineKeyboardButton(p, callback_data=f"fckp_prod_{p}")] for p in config.FCKP_OPTIONS]
            try:
                await query.edit_message_text(f"Вы выбрали {prod}. Осталось указать ещё {left} ФЦКП.", reply_markup=InlineKeyboardMarkup(keyboard))
            except Exception:
                pass
            return
        else:
            # финализируем выбор продуктов
            st['data']['fckp_products'] = st.get('fckp_products', [])
            st['data']['fckp_realized'] = len(st.get('fckp_products', []))
            try:
                await query.edit_message_text("Все ФЦКП указаны ✅")
            except Exception:
                pass
            # двигаемся дальше
            st['step'] = st.get('step',0) + 1
            await ask_next_question(query.message, uid)
            return

    # непойманные callback'ы - игнор
    # end button_handler
    return

# Helpers -------------------------------------------------

async def handle_role_selection(query_or_update, user_id, role):
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

# message handler (text messages)
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return
    uid = msg.from_user.id
    text = (msg.text or "").strip()
    st = user_states.get(uid, {})

    if not st:
        if text.lower() == "вернуться в меню":
            await start(update, context)
            return
        await msg.reply_text("Сессия не запущена или истекла. Начните заново /start.")
        return

    if text.lower() == "вернуться в меню":
        user_states.pop(uid, None)
        await start(update, context)
        return

    # ввод имени
    if st.get('entering_name'):
        name = text
        role = st.get('mode', 'manual')
        st['name'] = name
        st.pop('entering_name', None)
        try:
            # записываем в БД — роль employee если mkk
            database.add_user(uid, 'employee' if role == 'mkk' else role, name)
        except Exception as e:
            print("DB add_user error:", e)
        if role == 'mkk':
            st['choosing_rtp'] = True
            await show_rtp_buttons(update, "Выберите вашего РТП:")
        else:
            await msg.reply_text("Пожалуйста, выберите ваше ФИ из списка кнопок.")
        return

    # если ожидается выбор РТП кнопками
    if st.get('choosing_rtp'):
        await msg.reply_text("Пожалуйста, выберите РТП из списка кнопок.")
        return

    # выбор даты для РТП
    if 'select_mode' in st:
        try:
            date = datetime.strptime(text, '%Y-%m-%d').strftime('%Y-%m-%d')
            manager_fi = database.get_user_name(uid) if st.get('mode') == 'rtp' else None
            mode = st.pop('select_mode', None)
            if mode == 'show':
                employees = database.get_employees(manager_fi)
                reports = database.get_all_reports_on_date(date, manager_fi)
                reported_ids = [u for u,_ in reports]
                text_out = f"Отчеты на {date}:\n"
                for u_id, name in employees:
                    status = '✅' if u_id in reported_ids else ' '
                    text_out += f"Сотрудник {name or str(u_id)}: {status}\n"
                await msg.reply_text(text_out)
            elif mode == 'detailed':
                reports = database.get_all_reports_on_date(date, manager_fi)
                text_out = f"Детальные отчеты на {date}:\n"
                for u_id, rdata in reports:
                    name = database.get_user_name(u_id) or str(u_id)
                    text_out += f"Сотрудник {name}:\n{config.format_report(rdata)}\n\n"
                await msg.reply_text(text_out)
            elif mode == 'combine':
                reports = database.get_all_reports_on_date(date, manager_fi)
                if not reports:
                    await msg.reply_text("Нет отчетов на эту дату.")
                    return
                combined = {}
                fckp_products = []
                for _, r in reports:
                    for k, v in r.items():
                        if k == 'fckp_products' and isinstance(v, list):
                            fckp_products.extend(v)
                        else:
                            try:
                                combined[k] = combined.get(k, 0) + int(v or 0)
                            except Exception:
                                pass
                combined['fckp_products'] = fckp_products
                combined['fckp_realized'] = len(fckp_products)
                out = config.format_report(combined) + "\n\n" + config.OPERATIONAL_DEFECTS_BLOCK
                await msg.reply_text(out)
            return
        except ValueError:
            await msg.reply_text("Неверный формат даты. Попробуйте снова (YYYY-MM-DD).")
            return

    # основной опрос МКК
    if 'step' not in st:
        return

    step = st['step']
    if step < len(config.QUESTIONS):
        q = config.QUESTIONS[step]
        if not text.isdigit():
            await msg.reply_text("Пожалуйста, введите число (цифрами).")
            return
        # special for fckp_realized
        if q['key'] == 'fckp_realized':
            n = int(text)
            st['data'][q['key']] = n
            if n > 0:
                st['fckp_left'] = n
                st['fckp_products'] = []
                keyboard = [[InlineKeyboardButton(p, callback_data=f"fckp_prod_{p}")] for p in config.FCKP_OPTIONS]
                await msg.reply_text(f"Вы указали {n} ФЦКП. Выберите оформленный продукт (1/{n}):", reply_markup=InlineKeyboardMarkup(keyboard))
                # do NOT advance step here — advance after product selection finishes
                return
            else:
                st['step'] += 1
                await ask_next_question(msg, uid)
                return
        else:
            st['data'][q['key']] = int(text)
            st['step'] += 1
            await ask_next_question(msg, uid)
            return
    else:
        await msg.reply_text("Опрос завершён. Для возврата в меню нажмите 'Вернуться в меню' или /start.")
        return

async def ask_next_question(msgobj, uid):
    st = safe_state(uid)
    step = st.get('step', 0)
    if step < len(config.QUESTIONS):
        q = config.QUESTIONS[step]
        current = st.get('data', {}).get(q['key'], '')
        try:
            await msgobj.reply_text(f"{q['question']} {f'(текущее: {current})' if current != '' else ''}")
        except Exception:
            try:
                await msgobj.message.reply_text(f"{q['question']} {f'(текущее: {current})' if current != '' else ''}")
            except Exception as e:
                print("ask_next_question error:", e)
    else:
        await finish_report(msgobj, uid)

async def start_filling(query_or_message, uid, editing=False):
    st = safe_state(uid)
    st['editing'] = editing
    st['step'] = 0
    # preserve existing data if editing
    if not editing:
        st['data'] = {}
    try:
        await query_or_message.edit_message_text("Начинаем заполнение отчёта.")
    except Exception:
        try:
            await query_or_message.reply_text("Начинаем заполнение отчёта.")
        except Exception:
            pass
    await ask_next_question(query_or_message, uid)

async def finish_report(msgobj, uid):
    st = safe_state(uid)
    data = st.get('data', {}) or {}
    # if product list was collected in state but not pushed to data
    if 'fckp_products' in st and st.get('fckp_products'):
        data['fckp_products'] = st.get('fckp_products')
        data['fckp_realized'] = len(st.get('fckp_products'))
    # ensure numeric defaults
    for q in config.QUESTIONS:
        data.setdefault(q['key'], 0)
    # save to DB for non-manual roles
    try:
        if st.get('mode') != 'manual':
            database.save_report(uid, data)
    except Exception as e:
        print("DB save_report error:", e)
    formatted = config.format_report(data)
    try:
        await msgobj.reply_text(f"Итоговый отчет:\n{formatted}")
    except Exception:
        try:
            await msgobj.message.reply_text(f"Итоговый отчет:\n{formatted}")
        except Exception:
            pass

    keyboard = [
        [InlineKeyboardButton("Редактировать", callback_data='edit_report')],
        [InlineKeyboardButton("Сменить ФИ/РТП", callback_data='change_info')]
    ]
    if st.get('mode') == 'mkk':
        keyboard[0].insert(1, InlineKeyboardButton("Отправить руководителю", callback_data='send_report'))
    try:
        await msgobj.reply_text("Действия:", reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception:
        pass

async def show_manager_menu(q):
    keyboard = [
        [InlineKeyboardButton("Показать отчеты на дату", callback_data='rtp_show_reports')],
        [InlineKeyboardButton("Детальный отчет на дату", callback_data='rtp_detailed_reports')],
        [InlineKeyboardButton("Объединить и показать отчеты на дату", callback_data='rtp_combine_reports')]
    ]
    try:
        await q.edit_message_text("Меню руководителя:", reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception:
        try:
            await q.message.reply_text("Меню руководителя:", reply_markup=InlineKeyboardMarkup(keyboard))
        except Exception:
            pass

# error handler
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("Error:", context.error)

# set bot commands
async def set_commands(app):
    try:
        await app.bot.set_my_commands([BotCommand("start", "Начать работу с ботом")])
    except Exception as e:
        print("set_commands error:", e)

# Run
if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler('start', start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    app.add_error_handler(error_handler)

    asyncio.get_event_loop().run_until_complete(set_commands(app))
    print("Бот запущен...")
    app.run_polling()
