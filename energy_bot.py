import asyncio
import html
import json
import logging
import os
import random
import sqlite3
import sys
import argparse
from datetime import datetime, timedelta

import requests
from aiogram import Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, CallbackQuery
from aiogram.client.session.aiohttp import AiohttpSession
from dotenv import load_dotenv

from energy_bot_utils import parse_html_content, site_poe_gvp, index_to_time, format_schedule_lines, queue_time_data, \
    save_user_subscribe, get_user_subscribes, remove_user_subscribe, get_all_subscribes, logger

load_dotenv()

base_dir = os.path.dirname(os.path.abspath(__file__))
BOT_TOKEN = f'{os.environ.get("TELEGRAM_BOT")}'
if os.environ.get("PROXY"):
    session = AiohttpSession(proxy=f'{os.environ.get("PROXY")}')
else:
    session = AiohttpSession()
LIMIT = timedelta(minutes=1)
last_send_time = {}

dp = Dispatcher()
QUEUE_LIST = ["1_1", "1_2", "2_1", "2_2", "3_1", "3_2", "4_1", "4_2", "5_1", "5_2", "6_1", "6_2"]


class Subscribe_state(StatesGroup):
    queue = State()


def generate_keyboard_subscribe(user_subscribes):
    kb = []
    row = []
    for queue in QUEUE_LIST:
        if queue in user_subscribes:
            row.append(types.InlineKeyboardButton(text=f"{queue} ✅", callback_data=f'unsubscribe:{queue}'))
        else:
            row.append(types.InlineKeyboardButton(text=queue, callback_data=f'subscribe:{queue}'))
        if len(row) == 2:
            kb.append(row)
            row = []
    if row:
        kb.append(row)
    kb.append([types.InlineKeyboardButton(text="Clear Keyboard", callback_data='clear_keyboard')])
    return InlineKeyboardMarkup(inline_keyboard=kb)


@dp.callback_query(lambda c: c.data == 'clear_keyboard')
async def process_control_admins(callback_query: CallbackQuery):
    kb = []
    keyboard = InlineKeyboardMarkup(inline_keyboard=kb)
    await callback_query.message.edit_reply_markup(reply_markup=keyboard)


@dp.callback_query(lambda c: c.data == 'clear_sate')
async def process_clear_sate(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.message.delete()
    await state.clear()
    await callback_query.message.answer('Canceled')


@dp.message(Command(commands=["main", "start"]))
async def command_help(message: Message) -> Message:
    text_sending = "Welcome to the Poltava Energy Bot!"
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="/1_1"),
                KeyboardButton(text="/1_2"),
            ],
            [
                KeyboardButton(text="/2_1"),
                KeyboardButton(text="/2_2"),
            ],
            [
                KeyboardButton(text="/3_1"),
                KeyboardButton(text="/3_2"),
            ],
            [
                KeyboardButton(text="/4_1"),
                KeyboardButton(text="/4_2"),
            ],
            [
                KeyboardButton(text="/5_1"),
                KeyboardButton(text="/5_2"),
            ],
            [
                KeyboardButton(text="/6_1"),
                KeyboardButton(text="/6_2"),
            ],
        ],
        resize_keyboard=True,
    )
    return await message.answer(f"{text_sending}", reply_markup=keyboard)


@dp.message(Command(commands=QUEUE_LIST))
async def send_energy_data(message: Message) -> Message:
    logger.info('Received command: %s from user: %s (%s)',
                message.text, message.from_user.full_name, message.from_user.id)
    user_id = message.from_user.id
    full_queue_num = message.text.replace('/', '')
    now = datetime.now()

    last_time = last_send_time.get(user_id)
    last_send_time[user_id] = now
    if last_time and now - last_time < LIMIT:
        return await message.answer(f"Over limit requests. Please wait.")

    formatted_date = datetime.now().strftime('%d-%m-%Y')
    response = site_poe_gvp(formatted_date)
    schedulers = parse_html_content(response)

    if not schedulers:
        return await message.answer("Error parsing data from the energy site.")

    for item_scheduler in schedulers:
        gvps_data = item_scheduler.get("gvps_data", [])
        for schedule in gvps_data:
            site_queue = schedule.get("queue").replace('.', '_')

            if site_queue == full_queue_num:
                text = get_formatted_gvp_text(
                    queue_str=full_queue_num,
                    date=item_scheduler.get("date"),
                    time_slots=schedule.get("data"),
                    about=item_scheduler.get("about"),
                    update_date=item_scheduler.get("update_date")
                )
                await message.answer(text)
                return


@dp.message(Command(commands=["subscribe"]))
async def subscribe_queue(message: Message, state: FSMContext) -> Message:
    user_subscribes = get_user_subscribes(message.from_user.id)
    keyboard = generate_keyboard_subscribe(user_subscribes)
    Subscribe_state.queue = None
    await state.set_state(Subscribe_state.queue)
    return await message.answer("Please enter the queue number you want to subscribe to (e.g., 1.1):",
                                reply_markup=keyboard)


@dp.callback_query(lambda c: c.data and c.data.startswith('subscribe:') or c.data.startswith('unsubscribe:'))
async def process_subscription(callback_query: CallbackQuery, state: FSMContext) -> Message:
    await state.set_state(Subscribe_state.queue)
    if callback_query.data.startswith('subscribe:'):
        queue_num = callback_query.data.split(':')[1]
        save_user_subscribe(callback_query.from_user.id, queue_num)
        user_subscribes = get_user_subscribes(callback_query.from_user.id)
        keyboard = generate_keyboard_subscribe(user_subscribes)
        logger.info(
            f"User {callback_query.from_user.full_name} ({callback_query.from_user.id}) subscribed to queue {queue_num}")
        await callback_query.message.edit_reply_markup(reply_markup=keyboard)
        await callback_query.answer(f"Subscribed to queue {queue_num}!")
    elif callback_query.data.startswith('unsubscribe:'):
        queue_num = callback_query.data.split(':')[1]
        remove_user_subscribe(callback_query.from_user.id, queue_num)
        user_subscribes = get_user_subscribes(callback_query.from_user.id)
        keyboard = generate_keyboard_subscribe(user_subscribes)
        logger.info(
            f"User {callback_query.from_user.full_name} ({callback_query.from_user.id}) unsubscribed from queue {queue_num}")
        await callback_query.message.edit_reply_markup(reply_markup=keyboard)
        await callback_query.answer(f"Unsubscribed from queue {queue_num}!")
    else:
        await callback_query.answer("Invalid action.")


def get_formatted_gvp_text(queue_str, date, time_slots, about="Графік ГПВ", update_date=None):
    queue_num, queue_sub_num = queue_str.split('_')

    current_gvp = queue_time_data(
        queue_num=queue_num,
        queue_sub_num=queue_sub_num,
        time_slots=time_slots
    )

    result_off = format_schedule_lines(current_gvp, 'data')
    result_on = format_schedule_lines(current_gvp, 'data_on')

    upd_str = update_date if update_date else datetime.now().strftime('%H:%M:%S')
    if result_on and result_on == "Дані відсутні":
        return (
            f"<code>{about}</code>\n"
            f"Черга ♦️ {queue_num}.{queue_sub_num} ♦️, Відключення на <b>{date}</b>:\n"
            f"Світло не вимикатимуть\n"
            f"Оновлено: {upd_str}"
        )
    return (
        f"<code>{about}</code>\n"
        f"Черга ♦️ {queue_num}.{queue_sub_num} ♦️, Відключення на <b>{date}</b>:\n"
        f"Світло Є <blockquote>{result_on}</blockquote>\n"
        f"Світла нема <blockquote>{result_off}</blockquote>\n"
        f"Оновлено: {upd_str}"
    )


def save_queue_data(queue, time_slots, date, update_date):
    try:
        with sqlite3.connect("energy_bot.db") as conn:
            c = conn.cursor()
            c.execute("SELECT time_slots FROM queue_data WHERE queue = ? AND date = ? AND state = 1", (queue, date))
            result = c.fetchone()
            new_slots_str = json.dumps(time_slots)

            if result:
                existing_slots = json.loads(result[0])
                if existing_slots == time_slots:
                    return None
                c.execute("UPDATE queue_data SET state = 0 WHERE queue = ? AND date = ? AND state = 1", (queue, date))
                logger.info(f"Updated queue {queue}")
            c.execute("INSERT INTO queue_data (queue, time_slots, date, state, update_date) VALUES (?, ?, ?, ?, ?)",
                      (queue, new_slots_str, date, 1, update_date))
            logger.info(f"Inserted new data for queue {queue} on {date}")
            conn.commit()
            return True
    except sqlite3.Error as e:
        logger.error(f"Database error: {e}")
        return False


def save_task_is_update(queue, date, is_update):
    try:
        with sqlite3.connect("energy_bot.db") as conn:
            c = conn.cursor()
            c.execute("SELECT id FROM task_updates WHERE queue = ? AND date = ?", (queue, date))
            result = c.fetchone()
            if result:
                c.execute("UPDATE task_updates SET is_update = ? WHERE id = ?", (is_update, result[0]))
            else:
                c.execute("INSERT INTO task_updates (queue, date, is_update) VALUES (?, ?, ?)",
                          (queue, date, is_update))
            conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Database error: {e}")


def get_state_update(queue, date):
    try:
        with sqlite3.connect("energy_bot.db") as conn:
            c = conn.cursor()
            c.execute("SELECT is_update FROM task_updates WHERE queue = ? AND date = ?", (queue, date))
            result = c.fetchone()
            return result[0] if result else None
    except sqlite3.Error as e:
        logger.error(f"Database error: {e}")
        return None


def sync_gvp_schedules():
    current_date = datetime.now()
    request_date = current_date.strftime('%d-%m-%Y')

    response = site_poe_gvp(request_date)
    schedulers = parse_html_content(response)

    if not schedulers:
        logger.error("Error parsing data from the energy site.")
        return

    for item_scheduler in schedulers:
        target_date = item_scheduler.get("date", request_date)
        update_date = item_scheduler.get("update_date", None)
        gvps_data = item_scheduler.get("gvps_data", [])

        if not gvps_data:
            logger.info(f"No schedule data for {target_date}")
            for queue in QUEUE_LIST:
                is_update = save_queue_data(queue=queue, time_slots=[], date=target_date,
                                            update_date=update_date)
                if is_update:
                    save_task_is_update(queue, target_date, 1)
                    logger.info(f"Updated data for queue {queue} on {target_date}")

        for schedule in gvps_data:
            queue = schedule.get("queue", "").replace('.', '_')
            time_slots = schedule.get("data", [])

            is_update = save_queue_data(queue=queue, time_slots=time_slots, date=target_date, update_date=update_date)

            if is_update:
                save_task_is_update(queue, target_date, 1)
                logger.info(f"Updated data for queue {queue} on {target_date}")
            else:
                logger.info(f"No changes for queue {queue} on {target_date}")


async def process_sending_gvp(bot: Bot):
    all_users = get_all_subscribes()
    if not all_users:
        return

    now = datetime.now()
    dates_to_check = [
        now.strftime('%d-%m-%Y'),
        (now + timedelta(days=1)).strftime('%d-%m-%Y')
    ]

    with sqlite3.connect("energy_bot.db") as conn:
        c = conn.cursor()

        for user_id, queue in all_users:
            for date_str in dates_to_check:
                c.execute("SELECT is_update FROM task_updates WHERE queue = ? AND date = ?", (queue, date_str))
                upd = c.fetchone()
                if not upd or upd[0] != 1:
                    continue

                c.execute("SELECT time_slots, update_date FROM queue_data WHERE queue = ? AND date = ? AND state = 1",
                          (queue, date_str))
                result = c.fetchone()
                if not result:
                    continue

                try:
                    time_slots = json.loads(result[0])
                    update_date = result[1]
                    text = get_formatted_gvp_text(queue, date_str, time_slots, update_date=update_date)
                    logger.info(f"Sending update to user {user_id} for queue {queue} on {date_str}")
                    await bot.send_message(user_id, text)
                except Exception as e:
                    logger.error(f"Send error {user_id}: {e}")

        for d in dates_to_check:
            c.execute("UPDATE task_updates SET is_update = 0 WHERE date = ?", (d,))
        conn.commit()


async def scheduler_loop(bot: Bot):
    while True:
        try:
            logger.debug("Scheduler loop")
            sync_gvp_schedules()
            await process_sending_gvp(bot)
        except Exception as e:
            logger.error(f"Scheduler error: {e}", exc_info=True)
        time_sleep = random.randint(120, 300)
        await asyncio.sleep(time_sleep)


async def main() -> None:
    """Main function to start the bot."""
    bot = Bot(
        token=BOT_TOKEN,
        session=session,
        default=DefaultBotProperties(parse_mode="HTML"),
    )

    asyncio.create_task(scheduler_loop(bot))
    logger.info("Starting energy bot")
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        logger.info("Starting script")
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot stopped by user")
        sys.exit()
