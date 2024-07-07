import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup  # type: ignore
from telegram.ext import ApplicationBuilder, CallbackContext, CallbackQueryHandler, \
    CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes  # type: ignore
import requests
import psycopg2
import os
from psycopg2 import sql
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)

API_TOKEN = 'token'

DB_HOST = "db"
DB_PORT = "5432"
DB_NAME = "vacancies_db"
DB_USER = "postgres"
DB_PASS = "postgres"

try:
    conn = psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        host=DB_HOST,
        port=DB_PORT
    )
    cursor = conn.cursor()
    logging.info("Successfully connected to PostgreSQL")
except psycopg2.Error as e:
    logging.error(f"Error connecting to PostgreSQL: {e}")
    exit(1)


async def starting(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("Название", callback_data='name'),
            InlineKeyboardButton("Стаж", callback_data='experience'),
            InlineKeyboardButton("Место работы", callback_data='area_search')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.effective_chat.send_message('Выберите параметр поиска:', reply_markup=reply_markup)


async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == 'search':
        await search_vacancies(update, context)
    elif query.data == 'filter_search':
        await update.effective_chat.send_message("Идёт поиск")
        await filter_by(update, context)
    elif query.data == 'reset_search_filters':
        context.user_data.clear()
        await update.effective_chat.send_message("Поисковые параметры сброшены.")
        await starting(update, context)
    elif query.data == 'reset_filters':
        await reset_filters(update, context)
    elif query.data == 'to_start':
        await starting(update, context)
    elif query.data == 'name':
        await query.edit_message_text(text="Введите название профессии (например, Разработчик):")
        context.user_data['next'] = 'name_input'
    elif query.data == 'salary':
        await query.edit_message_text(text="Введите зарплату:")
        context.user_data['next'] = 'salary_input'
    elif query.data == 'experience':
        keyboard = [
            [
                InlineKeyboardButton("Без опыта", callback_data='noExperience'),
                InlineKeyboardButton("От 1 до 3 лет", callback_data='between1And3')],
                [InlineKeyboardButton("От 3 до 6 лет", callback_data='between3And6'),
                InlineKeyboardButton("Более 6 лет", callback_data='moreThan6')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text='Выберите стаж:', reply_markup=reply_markup)
    elif query.data == 'area_search':
        keyboard = [
            [
                InlineKeyboardButton("Москва", callback_data='area_1'),
                InlineKeyboardButton("Санкт-Петербург", callback_data='area_2')],
                [InlineKeyboardButton("Казахстан", callback_data='area_40'),
                InlineKeyboardButton("Московская область", callback_data='area_2019')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text='Выберите стаж:', reply_markup=reply_markup)
    elif query.data in ['area_1', 'area_40', 'area_2', 'area_2019']:
        area_mapping = {
            'area_1': 'Москва',
            'area_2': 'Санкт-Петербург',
            'area_40': 'Казахстан',
            'area_2019': 'Московская область'
        }
        context.user_data['area'] = query.data.split('_')[1]
        await query.edit_message_text(text=f"Вы выбрали: {area_mapping[query.data]}")
        await start_search(update, context)
    elif query.data in ['noExperience', 'between1And3', 'between3And6', 'moreThan6']:
        experience_mapping = {
            'noExperience': 'Нет опыта',
            'between1And3': 'От 1 года до 3 лет',
            'between3And6': 'От 3 до 6 лет',
            'moreThan6': 'Более 6 лет'
        }
        context.user_data['experience'] = query.data
        await query.edit_message_text(text=f"Вы выбрали стаж: {experience_mapping[query.data]}")
        await start_search(update, context)
    elif query.data == 'currency':
        keyboard = [
            [
                InlineKeyboardButton("₽", callback_data='RUR'),
                InlineKeyboardButton("$", callback_data='USD'),
                InlineKeyboardButton("€", callback_data='EUR'),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text='Выберите валюту', reply_markup=reply_markup)
    elif query.data in ['RUR', 'USD', 'EUR']:
        context.user_data['currency'] = query.data
        await filter_menu(update, context)
    elif query.data == 'area':
        await query.edit_message_text(text="Введите город:")
        context.user_data['next'] = 'area_input'
    elif query.data == 'metro':
        await query.edit_message_text(text="Введите станцию метро:")
        context.user_data['next'] = 'metro_input'
    elif query.data == 'employment':
        keyboard = [
            [
                InlineKeyboardButton("Полная занятость", callback_data='Полная занятость'),
                InlineKeyboardButton("Частичная занятость", callback_data='Частичная занятость')],
            [
                InlineKeyboardButton("Стажировка", callback_data='Стажировка'),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text='Выберите занятость', reply_markup=reply_markup)
    elif query.data in ['Полная занятость', 'Частичная занятость', 'Стажировка']:
        context.user_data['employment'] = query.data
        await filter_menu(update, context)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('next') == 'name_input':
        profession_name = update.message.text.capitalize()
        context.user_data['name'] = profession_name
        del context.user_data['next']
        await update.message.reply_text(f"Вы выбрали профессию: {profession_name}")
        await start_search(update, context)
    elif context.user_data.get('next') == 'salary_input':
        min_salary = update.message.text
        context.user_data['salary'] = min_salary
        del context.user_data['next']
        await update.message.reply_text(f"Вы выбрали зарплату: {min_salary}")
        await filter_menu(update, context)
    elif context.user_data.get('next') == 'area_input':
        area = update.message.text
        context.user_data['area'] = area
        del context.user_data['next']
        await filter_menu(update, context)
    elif context.user_data.get('next') == 'metro_input':
        metro = update.message.text
        context.user_data['metro'] = metro
        del context.user_data['next']
        await filter_menu(update, context)


async def start_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = context.user_data.get('name')
    # salary = context.user_data.get('salary')
    experience_id = context.user_data.get('experience')
    area_id = context.user_data.get('area')

    keyboard = []

    if not name:
        keyboard.append([InlineKeyboardButton("Название", callback_data='name')])
    # if not salary:
    #     keyboard.append([InlineKeyboardButton("Зарплата", callback_data='salary')])
    if not experience_id:
        keyboard.append([InlineKeyboardButton("Стаж", callback_data='experience')])
    if not area_id:
        keyboard.append([InlineKeyboardButton("Место работы", callback_data='area')])

    if name or experience_id or area_id:
        keyboard.append([
            InlineKeyboardButton("Сбросить", callback_data='reset_search_filters'),
            InlineKeyboardButton("Поиск", callback_data='search')
        ])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.effective_chat.send_message('Выберите параметр поиска:', reply_markup=reply_markup)


async def search_vacancies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    title = context.user_data.get('name')
    salary = context.user_data.get('salary')
    experience = context.user_data.get('experience')
    area = context.user_data.get('area')

    url = 'https://api.hh.ru/vacancies'
    params = {
        'text': title if title else '',
        'salary': salary if salary else '1',
        'currency': 'RUR',
        'experience': experience if experience else 'noExperience',
        'area': area if area else '1',  # Russia
        'per_page': '50',
        'only_with_salary': 'true'
    }

    response = requests.get(url, params=params)
    if response.status_code == 200:
        vacancies = response.json().get('items', [])
        if vacancies:
            message_parts = []
            for vacancy in vacancies:
                try:
                    metro = vacancy['address']['metro']['station_name']
                except:
                    metro = 'None'
                cursor.execute(
                    '''
                    INSERT INTO public.vacancies (vacancy_id, title, professional_roles, employer, salary_from, salary_to, currency, experience, employment, area, metro_stations, url, responsibility)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (vacancy_id) DO NOTHING
                    ''',
                    (
                        vacancy['id'],
                        vacancy['name'],
                        vacancy['professional_roles'][0]['name'],
                        vacancy['employer']['name'],
                        vacancy['salary']['from'],
                        vacancy['salary']['to'],
                        vacancy['salary']['currency'],
                        vacancy['experience']['name'],
                        vacancy['employment']['name'],
                        vacancy['area']['name'],
                        metro,
                        vacancy['alternate_url'],
                        vacancy['snippet']['responsibility']
                    )
                )
                conn.commit()
            for vacancy in vacancies[:5]:
                salary_ = vacancy['salary']['from']
                if salary_ == None:
                    salary_ = vacancy['salary']['to']
                if salary_ == None:
                    salary_ = 'Зарплата не указана'
                message_part = (
                    f"{vacancy['name']} в {vacancy['employer']['name']}, {vacancy['area']['name']}\n"
                    f"{salary_} {vacancy['salary']['currency'] if salary_  else ''}\n"
                    f"{vacancy['alternate_url']}"
                )
                message_parts.append(message_part)

            message = "\n\n".join(message_parts)
            await update.effective_chat.send_message(message)
            await filter_menu(update, context)

        else:
            await update.effective_chat.send_message('По вашему запросу вакансии не найдены.')
            context.user_data.clear()
            await starting(update, context)
    else:
        await update.effective_chat.send_message('Ошибка при получении данных с hh.ru')
        context.user_data.clear()
        await starting(update, context)


async def filter_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    currency = context.user_data.get('currency')
    metro = context.user_data.get('metro')
    employment = context.user_data.get('employment')
    area = context.user_data.get('area')
    salary = context.user_data.get('salary')

    keyboard = []

    if not currency:
        keyboard.append([InlineKeyboardButton("Валюта", callback_data='currency')])
    if not metro:
        keyboard.append([InlineKeyboardButton("Метро", callback_data='metro')])
    if not employment:
        keyboard.append([InlineKeyboardButton("Тип занятость", callback_data='employment')])
    if not salary:
        keyboard.append([InlineKeyboardButton("Зарплата", callback_data='salary')])

    if currency or metro or employment or area or salary:
        keyboard.append([
            InlineKeyboardButton("Сбросить фильтры", callback_data='reset_filters'),
            InlineKeyboardButton("Поиск", callback_data='filter_search')
        ])

    keyboard.append([InlineKeyboardButton("Вернуться на начало", callback_data='to_start')])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.effective_chat.send_message('Выберите параметр фильтрации:', reply_markup=reply_markup)


async def reset_filters(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keys_to_clear = ['currency', 'metro', 'employment', 'area', 'salary']
    for key in keys_to_clear:
        if key in context.user_data:
            del context.user_data[key]
    await update.effective_chat.send_message("Фильтры сброшены.")
    await filter_menu(update, context)



async def filter_by(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = context.user_data.get('name')
    salary = context.user_data.get('salary')
    experience_id = context.user_data.get('experience')

    currency = context.user_data.get('currency')
    metro = context.user_data.get('metro')
    employment = context.user_data.get('employment')
    area = context.user_data.get('area')


    # Таблица соответствия experience_id и значений в базе данных
    experience_mapping = {
        'noExperience': 'Нет опыта',
        'between1And3': 'От 1 года до 3 лет',
        'between3And6': 'От 3 до 6 лет',
        'moreThan6': 'Более 6 лет'
    }
    
    experience = experience_mapping.get(experience_id)
    conditions = []
    params = []
    # Формирование SQL-запроса
    if currency:
        conditions.append("currency = %s")
        params.append(currency)

    if name:
        conditions.append("(title ILIKE %s OR professional_roles ILIKE %s OR responsibility ILIKE %s)")
        params.extend([f"%{name}%", f"%{name}%", f"%{name}%"])

    if salary:
        conditions.append(
            "((salary_from IS NULL AND salary_to IS NULL) OR (salary_from IS NULL AND salary_to >= %s) OR (salary_to IS NULL AND salary_from <= %s) OR (salary_from <= %s AND salary_to >= %s))"
        )
        params.extend([salary, salary, salary, salary])

    if experience:
        conditions.append("experience = %s")
        params.append(experience)

    if metro:
        conditions.append("metro_stations ILIKE %s")
        params.append(f"%{metro}%")


    if employment:
        conditions.append("employment = %s")
        params.append(employment)

    if area:
        conditions.append("area ILIKE %s")
        params.append(f"%{area}%")
    
    print("SELECT * FROM vacancies WHERE " + " AND ".join(conditions))
    # Создание SQL-запроса
    query = sql.SQL("SELECT * FROM vacancies WHERE " + " AND ".join(conditions))

    # Выполнение SQL-запроса
    try:
        cursor.execute(query, params)
        results = cursor.fetchall()

        # Обработка и отправка результатов пользователю
        message_filter_parts = ["Найденные вакансии:\n"]
        if results:
            update_results = await update_db(results)
            for vacancy in update_results[:20]:
                message_part = (
                    f"{vacancy[2]}\n{vacancy[4]}\n{vacancy[5]}-{vacancy[6]}\n{vacancy[12]}\n"
                )
                message_filter_parts.append(message_part)
            message = "\n\n".join(message_filter_parts)
            await update.effective_chat.send_message(message)
        else:
            response = "Вакансии не найдены по указанным критериям."
            await update.effective_chat.send_message(response)
    except psycopg2.Error as e:
        logging.error(f"Error executing query: {e}")
        logging.error(f'Error executing query: {"SELECT * FROM vacancies WHERE " + " AND ".join(conditions)}')
        await update.message.reply_text("Произошла ошибка при выполнении запроса.")
    await filter_menu(update, context)


async def update_db(results):
    updated_results = []
    for e in results:
        response = requests.get(f'https://api.hh.ru/vacancies/{e[1]}')
        data = response.json()
        if data.get('type', {}).get('id') == 'open':
            updated_results.append(e)
        else:
            try:
                cursor.execute("DELETE FROM vacancies WHERE vacancy_id = %s", (e[1],))
                conn.commit()
                logging.info(f"Vacancy with id {e[1]} deleted from database")
            except psycopg2.Error as err:
                logging.error(f"Error deleting vacancy with id {e[1]}: {err}")

    return updated_results


if __name__ == '__main__':
    from telegram.ext import ApplicationBuilder
    app = ApplicationBuilder().token(API_TOKEN).build()
    app.add_handler(CommandHandler("start", starting))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()
