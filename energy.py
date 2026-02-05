import logging
import os
from time import sleep
from datetime import datetime, timedelta

from dotenv import load_dotenv
from bs4 import BeautifulSoup
import requests
import sqlite3

load_dotenv()
CHANNELS = {
    1: os.environ.get("CHANNEL_1"),
    2: os.environ.get("CHANNEL_2"),
    3: os.environ.get("CHANNEL_3"),
    4: os.environ.get("CHANNEL_4"),
    5: os.environ.get("CHANNEL_5"),
    6: os.environ.get("CHANNEL_6"),
}
ENERGY_CHANNEL = os.environ.get("CHANNEL_0")

TELEGRAM_BOT = os.environ.get("TELEGRAM_BOT")
TELEGRAM_ADMIN = os.environ.get("TELEGRAM_ADMIN")

logger = logging.getLogger()
logger.setLevel(logging.INFO)
file_handler = logging.FileHandler("logs/app.log", encoding="utf-8")
file_handler.setLevel(logging.INFO)
file_formatter = logging.Formatter("%(asctime)s - %(module)s - %(levelname)s - %(message)s")
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
console_handler.setFormatter(console_formatter)
logger.addHandler(console_handler)

SEND_NOTIFICATIONS = True  # default True, Disable sending notifications for testing
UPDATE_TEXT_ONLY = False  # default False, Update text only without changing message ID


class Duration:
    def __init__(self):
        self.totals = {}
        self.is_update = False

    def set(self, date, total):
        old_total = self.totals.get(date)
        if old_total != total:
            self.totals[date] = total
            self.is_update = False
            logger.info(f"Duration updated for date: {date}")
        else:
            self.is_update = False

    def get(self, date):
        return self.totals.get(date)

    def get_queue(self, queue_num, date):
        total = self.totals.get(date)
        if not total:
            return None

        for row in total.split("\n"):
            if f'Черга: {queue_num}' in row:
                parts = row.split()
                if len(parts) >= 2:
                    return parts[-2], parts[-1]
        return None


total_durations = Duration()


def _telegram_request(method: str, payload: dict) -> dict:
    if not SEND_NOTIFICATIONS:
        logger.info(f"[TEST MODE] {method} skipped")
        return {"ok": False}

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT}/{method}"
    max_attempts = 3

    for attempt in range(max_attempts):
        try:
            response = requests.post(url, json=payload, timeout=10)
            data = response.json()

            if data.get("ok"):
                return data

            if data.get("error_code") == 429:
                retry_after = data.get("parameters", {}).get("retry_after", 5)
                logger.warning(f"Rate limit. Waiting {retry_after}s...")
                sleep(retry_after)
                continue

            logger.error(f"TG API Error: {data}")
            return data

        except (requests.exceptions.RequestException, Exception) as e:
            logger.error(f"Network error on {method} (attempt {attempt + 1}/{max_attempts}): {e}")

            if attempt < max_attempts - 1:
                logger.info("Waiting 60 seconds before next retry...")
                sleep(60)
            else:
                logger.critical("Max retries reached due to network errors.")

    return {"ok": False}


def telegram_send_text(chat_id: str, text: str):
    payload = {"chat_id": chat_id, "parse_mode": "html", "text": text}
    result = _telegram_request("sendMessage", payload)
    return result.get("result", {}).get("message_id")


def telegram_update_message(chat_id: str, message_id: int, text: str):
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "parse_mode": "html",
        "text": text
    }
    result = _telegram_request("editMessageText", payload)
    return result.get("result", {}).get("message_id")


def telegram_delete_message(chat_id: str, message_id: int):
    payload = {"chat_id": chat_id, "message_id": message_id}
    result = _telegram_request("deleteMessage", payload)
    return result.get("ok", False)


def site_poe_gvp(date_in):
    url = "https://www.poe.pl.ua/customs/newgpv-info.php"
    headers = {
        "accept": "application/json, text/javascript, /; q=0.01",
        "accept-language": "ru-RU,ru;q=0.9,uk;q=0.8,en-US;q=0.7,en;q=0.6",
        "cache-control": "no-cache",
        "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
        "dnt": "1",
        "origin": "https://www.poe.pl.ua",
        "pragma": "no-cache",
        "priority": "u=1, i",
        "referer": "https://www.poe.pl.ua/disconnection/power-outages/",
        "sec-ch-ua": '"Opera";v="115", "Chromium";v="127", "Not.A/Brand";v="26"', "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"', "sec-fetch-dest": "empty", "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36 OPR/115.0.0.0",
        "x-requested-with": "XMLHttpRequest"
    }
    data = {"seldate": f'{{"date_in":"{date_in}"}}'}
    response = requests.post(url, headers=headers, data=data)
    if response.status_code != 200:
        logger.error(f'Status code error {response.status_code}\n')
        telegram_send_text(chat_id=TELEGRAM_ADMIN,
                           text=f'Status code error {response.status_code}\n')
        return False
    logger.info(f'Load new info {response.url} http:{response.status_code}')
    with open(f'logs/{datetime.now().strftime("%d_%m_%Y_%H_%M_%S")}.html', "w", encoding='UTF-8') as file:
        html_page = '<!doctype html><meta charset="utf-8"><link rel="stylesheet" href="table.css">\n' + response.text
        file.write(html_page)
    return response.text


def convert_date(date_str: str) -> str | bool:
    months = {
        "січня": "01", "лютого": "02", "березня": "03", "квітня": "04",
        "травня": "05", "червня": "06", "липня": "07", "серпня": "08",
        "вересня": "09", "жовтня": "10", "листопада": "11", "грудня": "12"
    }
    try:
        day, month_ukr, year, *_ = date_str.replace(" року", "").split()
        return f"{day.zfill(2)}-{months[month_ukr]}-{year}"
    except (KeyError, ValueError, IndexError) as err:
        logging.error(f"Date conversion error: {err} for string: {date_str}")
        return False


def save_schedule_send_log(queue: str, text: str, current_date: str, tg_mess_id: int):
    with sqlite3.connect("energy.db") as conn:
        c = conn.cursor()
        c.execute('SELECT text, tg_mess_id FROM send_log_v2 WHERE date = ? AND queue = ?', (current_date, queue))
        db = c.fetchone()

        if db:
            if not SEND_NOTIFICATIONS and tg_mess_id == -1:
                tg_mess_id = db[1]
            if UPDATE_TEXT_ONLY:
                sql = 'UPDATE send_log_v2 SET text = ? WHERE date = ? AND queue = ?'
                params = (text, current_date, queue)
            else:
                sql = 'UPDATE send_log_v2 SET text = ?, tg_mess_id = ? WHERE date = ? AND queue = ?'
                params = (text, tg_mess_id, current_date, queue)

            c.execute(sql, params)
            logger.info(f"Updated log {queue} {current_date}")
            return db
        sql_insert = 'INSERT INTO send_log_v2 (date, text, queue, tg_mess_id) VALUES (?, ?, ?, ?)'

        c.execute(sql_insert, (current_date, text, queue, tg_mess_id))
        logger.info(f"Inserting new log {queue} {current_date}")
        return True, True


def get_schedule_send_log(queue: str, current_date: str):
    with sqlite3.connect("energy.db") as conn:
        c = conn.cursor()
        sql_query = 'SELECT text FROM send_log_v2 WHERE queue = ? AND date = ?;'
        c.execute(sql_query, (queue, current_date))
        result = c.fetchone()
    if not result:
        return ['']
    return result


def is_last_seven_days_outages_count() -> bool:
    with sqlite3.connect("energy.db") as conn:
        c = conn.cursor()
        sql_query = '''
            SELECT text FROM send_log_v2
            WHERE queue = '0'
            ORDER BY rowid DESC
            LIMIT 7
        '''
        c.execute(sql_query)
        rows = c.fetchall()

    if not rows or len(rows) < 7:
        return False

    for row in rows:
        text = row[0] or ''
        if 'не прогнозується' not in text.lower():
            return False

    return True


def pars_table(data_table, current_date):
    OFF_CLASSES = {'light_2', 'light_3'}
    ALL_CLASSES = {'light_1', 'light_2', 'light_3'}
    queue_rows = data_table.find_all('tr')
    data_queues = []
    for row in queue_rows:
        row_data = []
        cells = row.find_all('td')
        for cell in cells:
            cell_classes = set(cell.get('class', []))
            if not cell_classes.intersection(ALL_CLASSES):
                continue
            status = 1 if cell_classes.intersection(OFF_CLASSES) else 0
            row_data.append(status)
        if row_data:
            data_queues.append(row_data)

    resul_queue = []
    duration_total = []
    for i, queue in enumerate(data_queues):
        q_major = (i // 2) + 1
        q_minor = (i % 2) + 1
        count = queue.count(1)
        current_total_minutes = count * 30
        minutes_left = 1440 - current_total_minutes
        rem_hours = minutes_left // 60
        rem_minutes = minutes_left % 60
        start_time = index_to_time(count)
        duration_total.append(f'Черга: {q_major}.{q_minor} час: -{start_time} +{rem_hours:02}:{rem_minutes:02}')
        queue_time = queue_time_data(queue_num=q_major, queue_sub_num=q_minor, time_slots=queue)
        resul_queue.append(queue_time)

    total_durations.set(current_date, '\n'.join(duration_total))
    return resul_queue


def pars_html(response):
    """Parsing html"""
    soup = BeautifulSoup(response, 'html.parser')
    gvps = soup.find_all('div', class_='gpvinfodetail')
    schedulers = []
    current_date = ''
    for gvp in gvps:
        for source_date in gvp.find_all('b'):
            date_str = source_date.text.strip()
            converted_date = convert_date(date_str)
            if converted_date:
                current_date = converted_date
                break
        about_day = gvp.find_all('div')
        if any(
                "застосування графіка погодинного відключення електроенергії у Полтавській області не прогнозується." in str(
                    gvp) for _ in about_day):
            logger.info(f"No power outages")
            schedulers.append((gvp.text.strip(), current_date))
        gvps_table = gvp.find('table', class_='turnoff-scheduleui-table')
        if gvps_table:
            gvps_data = gvps_table.find('tbody')
            schedulers.append((pars_table(gvps_data, current_date), current_date))

    return schedulers


def index_to_time(index):
    hours = index // 2
    minutes = (index % 2) * 30
    return f"{hours:02}:{minutes:02}"


def queue_time_data(queue_num, queue_sub_num, time_slots):
    active_periods = []
    start = None

    for i, value in enumerate(time_slots):
        if value == 1 and start is None:
            start = i
        elif value == 0 and start is not None:
            active_periods.append((start, i - 1))
            start = None
    if start is not None:
        active_periods.append((start, len(time_slots) - 1))
    time_intervals = [(index_to_time(start), index_to_time(end + 1)) for start, end in active_periods]
    result_queue = []
    if not time_intervals:
        result_queue.append({'queue': f'{queue_num}.{queue_sub_num}', 'data': []})
    else:
        for start_time, end_time in time_intervals:
            if end_time == '24:00':
                end_time = '23:59'
            start_dt = datetime.strptime(start_time, '%H:%M')
            end_dt = datetime.strptime(end_time, '%H:%M')
            if end_dt <= start_dt:
                end_dt += timedelta(days=1)
            diff = end_dt - start_dt
            hours_off = diff.seconds // 3600
            minutes_off = (diff.seconds % 3600) // 60

            queue = {'queue': f'{queue_num}.{queue_sub_num}',
                     'data': [start_time, end_time, {'hours': hours_off, 'minutes': minutes_off}]}
            result_queue.append(queue)
    return result_queue


def get_day_icon(current_date: str) -> str:
    try:
        day = int(current_date.split('-')[0])
        icons = ("🔸", "🔹", "♦️")
        return icons[(day - 1) % len(icons)]
    except (ValueError, IndexError):
        logger.error(f"Invalid date format: {current_date}")
        return ""


def format_time_pairs(mess_schedule: list) -> str:
    """ Format time pairs with approximate durations """
    time_pairs = []
    i = 0

    while i < len(mess_schedule):
        start = mess_schedule[i] if i < len(mess_schedule) else ''
        end = mess_schedule[i + 1] if i + 1 < len(mess_schedule) else ''
        duration = mess_schedule[i + 2] if i + 2 < len(mess_schedule) else None

        if isinstance(duration, dict):
            hours = duration.get('hours', 0)
            minutes = duration.get('minutes', 0)

            if minutes == 0:
                approximate_time = f"~{hours}:00"
            else:
                approximate_time = f"~{hours}:{minutes}"

            if approximate_time == "~0:59":
                approximate_time = "~1:00"
            elif approximate_time == "~0:29":
                approximate_time = "~0:30"

            time_pairs.append(f"{start} - {end} {approximate_time}")
        else:
            time_pairs.append(f"{start} - {end}")

        i += 3

    return '\n'.join(p for p in time_pairs if p.strip())


def send_notification_schedulers(schedulers, current_date: str):
    """Send notification if schedule has changed"""
    for schedule in schedulers:
        log_message = get_schedule_send_log(queue=schedule[0].get('queue'), current_date=current_date)
        sleep(1)
        num_queue = schedule[0].get('queue').split('.')[0]
        sub_num_queue = schedule[0].get('queue')
        merged_data = {}
        for entry in schedule:
            queue = entry['queue']
            if queue not in merged_data:
                merged_data[queue] = []
            merged_data[queue].extend(entry['data'])
        source_schedule = [{'queue': queue, 'data': times} for queue, times in merged_data.items()]
        mess_schedule = source_schedule[0].get("data")
        times = format_time_pairs(mess_schedule)
        if not times:
            times = "Черга не входить у період відключень"

        color_image = get_day_icon(current_date)
        light_off, light_on = total_durations.get_queue(sub_num_queue, current_date)
        text = f"Черга {sub_num_queue} {color_image}{current_date}{color_image}\nБез світла {light_off}, зі світлом {light_on}\n<blockquote>{times}</blockquote>"
        if log_message[0] != text:
            tg_mess_id = telegram_send_text(chat_id=CHANNELS.get(int(num_queue)), text=text)
            old_text, old_mess_id = save_schedule_send_log(queue=sub_num_queue,
                                                           text=text,
                                                           current_date=current_date,
                                                           tg_mess_id=tg_mess_id)
            if old_mess_id:
                sleep(2)
                telegram_update_message(chat_id=CHANNELS.get(int(num_queue)),
                                        message_id=old_mess_id,
                                        text=f"<s>{old_text}</s>\n UPD: Оновлено графік")
            logger.info(f"Send notification - Date: {current_date} Queue: {sub_num_queue}")
            if not total_durations.is_update:
                total_durations.is_update = True
        else:
            logger.info(f"Skip notification is no update - Date: {current_date} Queue: {sub_num_queue} ")


def send_notification_outages(current_date, no_power_outages: str):
    """Send notification if no power outages"""
    sleep(1)
    log_message = get_schedule_send_log(queue='0', current_date=current_date)
    if log_message[0] != no_power_outages:
        if not is_last_seven_days_outages_count():
            telegram_send_text(chat_id=TELEGRAM_ADMIN, text=no_power_outages.split('.')[0])
        else:
            for channel_id in CHANNELS.values():
                telegram_send_text(chat_id=channel_id, text=no_power_outages.split('.')[0])
        save_schedule_send_log(queue='0', text=no_power_outages, current_date=current_date, tg_mess_id=0)
        logger.info(f"Send notification power outages - Date: {current_date}")
    else:
        logger.info(f"Skip notification is no power outages - Date: {current_date}")


def mark_old_messages():
    """Marks yesterday's messages as outdated"""
    now = datetime.now()
    if now.hour == 0 and now.minute <= 14:
        queue_list = ['1.1', '1.2', '2.1', '2.2', '3.1', '3.2', '4.1', '4.2', '5.1', '5.2', '6.1', '6.2']

        for queue in queue_list:
            num_queue = queue.split('.')[0]
            edit_yesterday_message(id_channel=CHANNELS.get(int(num_queue), False), queue=queue)


def edit_yesterday_message(id_channel, queue):
    """Edits yesterday's message and notices that it is no longer relevant, adding <s> </s> to the message"""
    yesterday_date = (datetime.now() - timedelta(days=1)).strftime('%d-%m-%Y')
    conn = sqlite3.connect("energy.db")
    c = conn.cursor()
    sql_query = 'SELECT text, tg_mess_id FROM send_log_v2 WHERE queue = ? AND date = ?;'
    c.execute(sql_query, (queue, yesterday_date))
    db = c.fetchone()
    conn.close()
    if db:
        old_text = db[0]
        old_mess_id = db[1]
        if old_mess_id:
            if not id_channel:
                logger.error(f"Invalid id channel: {id_channel}")
            telegram_update_message(chat_id=id_channel,
                                    message_id=old_mess_id,
                                    text=f"<s>{old_text}</s>\n UPD: Інформація більше не актуальна")
            logger.info(f"Edit yesterday's message - Date: {yesterday_date}")


def main(debug):
    """Main function"""
    query_current_date = datetime.now()
    formatted_date = query_current_date.strftime('%d-%m-%Y')
    if debug:
        with open('logs/27_10_2025_09_45_41.html', 'r', encoding='utf-8') as f:
            response = f.read()
    else:
        response = site_poe_gvp(formatted_date)
    if not response:
        return logger.info('The site returns bad html code of the website')
    if response is False:
        return logger.info('The site is not available currently')
    schedulers = pars_html(response)
    sent_totals = set()

    for schedule in schedulers:
        data_schedule = schedule[0]
        date_schedulers = schedule[1]

        if isinstance(data_schedule, str):
            send_notification_outages(
                current_date=date_schedulers,
                no_power_outages=data_schedule
            )
            continue

        if date_schedulers:
            send_notification_schedulers(
                schedulers=data_schedule,
                current_date=date_schedulers
            )

        if total_durations.is_update and date_schedulers not in sent_totals:
            total = total_durations.get(date_schedulers)
            if total:
                telegram_send_text(
                    chat_id=ENERGY_CHANNEL,
                    text=(
                        f'Загальний час відключень на: {date_schedulers}\n'
                        f'<code>{total}</code>'
                    )
                )
                logger.info('The site is updated successfully')

            sent_totals.add(date_schedulers)

    total_durations.is_update = False
    if query_current_date.time().hour in [0]:
        mark_old_messages()


if __name__ == "__main__":
    try:
        main(debug=False)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        telegram_send_text(chat_id=TELEGRAM_ADMIN,
                           text=f"Unexpected error in main energy.py: {e}")
