import logging
import os
from time import sleep
from datetime import datetime

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


def telegram_send_text(chat_id: str, text: str):
    tg_url = f'https://api.telegram.org/bot{TELEGRAM_BOT}/sendMessage'
    response = requests.post(tg_url, json={"chat_id": chat_id, "parse_mode": "html", "text": text})
    if response.json().get("ok"):
        logger.info(response.json())
    else:
        logger.error(response.json())
    return response.json().get("result").get("message_id")


def telegram_send_text_button(chat_id: str, text: str, button_text: str = None, callback_data: str = None):
    tg_url = f'https://api.telegram.org/bot{TELEGRAM_BOT}/sendMessage'
    reply_markup = {
        "inline_keyboard": [[{"text": button_text, "callback_data": callback_data}]]
    }
    payload = {"chat_id": chat_id, "parse_mode": "html", "text": text, "reply_markup": reply_markup}

    response = requests.post(tg_url, json=payload)
    if response.json().get("ok"):
        logger.info(response.json())
    else:
        logger.error(response.json())
    return response.json().get("result", {}).get("message_id")


def telegram_update_message(chat_id: str, message_id, text: str):
    tg_url = f'https://api.telegram.org/bot{TELEGRAM_BOT}/editMessageText'
    response = requests.post(
        tg_url,
        json={
            "chat_id": chat_id,
            "message_id": message_id,
            "parse_mode": "html",
            "text": text,
        },
    )
    if response.json().get("ok"):
        logger.info({"chat_id": chat_id, "message_id": message_id, "tg": response.json()})
    else:
        logger.error({"chat_id": chat_id, "message_id": message_id, "tg": response.json()})


def telegram_delete_message(chat_id: str, message_id):
    tg_url = f'https://api.telegram.org/bot{TELEGRAM_BOT}/deleteMessage'
    response = requests.post(tg_url, json={"chat_id": chat_id, "message_id": message_id})
    if response.json().get("ok"):
        logger.info({"chat_id": chat_id, "message_id": message_id, "tg": response.json()})
    else:
        logger.error({"chat_id": chat_id, "message_id": message_id, "tg": response.json()})


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
        file.write(response.text)
    return response.text


def convert_date(date_str: str):
    try:
        months = {
            "січня": "January", "лютого": "February", "березня": "March",
            "квітня": "April", "травня": "May", "червня": "June",
            "липня": "July", "серпня": "August", "вересня": "September",
            "жовтня": "October", "листопада": "November", "грудня": "December"
        }
        for ukr_month, eng_month in months.items():
            if ukr_month in date_str:
                date_str = date_str.replace(ukr_month, eng_month)
                break
        date_str = date_str.replace(" року", "")
        date_format = "%d %B %Y"
        date_obj = datetime.strptime(date_str, date_format)
    except ValueError as e:
        return False
    return date_obj.strftime('%d-%m-%Y')


def save_schedule_send_log(queue: str, text: str, date: str, tg_mess_id: int):
    conn = sqlite3.connect("energy.db")
    c = conn.cursor()
    sql_query_select = f'SELECT * FROM send_log_v2 WHERE date = "{date}" AND queue = {queue};'
    c.execute(sql_query_select)
    db = c.fetchone()
    if db:
        sql_query = (f'UPDATE send_log_v2 '
                     f'SET text = "{text}", tg_mess_id = "{tg_mess_id}" '
                     f'WHERE date = "{date}" and queue = "{queue}";')
        logger.info(sql_query)
        c.execute(sql_query)
        conn.commit()
        conn.close()
        return True
    sql_query = (f'INSERT OR IGNORE INTO send_log_v2 '
                 f'(date,text,queue,tg_mess_id) '
                 f'VALUES ("{date}","{text}",{queue},{tg_mess_id})')
    logger.info(sql_query)
    c.execute(sql_query)
    conn.commit()
    conn.close()


def get_schedule_send_log(queue: str, date: str):
    conn = sqlite3.connect("energy.db")
    c = conn.cursor()
    sql_query = f'SELECT text FROM send_log_v2 WHERE queue = "{queue}" AND date = "{date}";'
    c.execute(sql_query)
    conn.commit()
    result = c.fetchone()
    if not result:
        return ['']
    return result


def is_last_seven_days_outages_count() -> bool:
    conn = sqlite3.connect("energy.db")
    try:
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
    finally:
        conn.close()


def get_count_all_time_schedule(schedule_arr: list) -> str:
    total_times = 0
    for row in schedule_arr:
        row = row.replace('~', '').split(' ')
        start_time_obj = datetime.strptime(row[-2], '%H:%M')
        end_time_obj = datetime.strptime(row[-1], '%H:%M')
        time_difference = end_time_obj - start_time_obj
        total_times += time_difference.seconds
    total_times = total_times / 60
    hours = total_times // 60
    minutes = total_times % 60
    return f"{hours.__int__()} годин {minutes.__int__()} хвилин"


def pars_table(data_table):
    queue = data_table.find_all('tr')
    data_queues = []
    for row in queue:
        cells = row.find_all('td')
        row_data = []
        for cell in cells:
            if 'light_1' in cell.get('class', []):
                row_data.append(0)
                continue
            if 'light_2' in cell.get('class', []):
                row_data.append(1)
                continue
            if 'light_3' in cell.get('class', []):
                row_data.append(1)
                continue
            if 'turnoff-scheduleui-table-queue' in cell.get('class', []):
                continue
            if '12' in cell.get('rowspan', []):
                continue
            else:
                continue
        data_queues.append(row_data)
    num = 1
    sub_num = 1
    flag = 0
    resul_queue = []
    for queue in data_queues:
        resul_queue.append(queue_time_data(queue_num=num, queue_sub_num=sub_num, time_slots=queue))
        if flag == 0:
            flag = 1
            sub_num = 2
            continue
        if flag == 1:
            flag = 0
            num += 1
            sub_num = 1
    return resul_queue


def pars_html(response):
    """Parsing html"""
    soup = BeautifulSoup(response, 'html.parser')
    gvps = soup.find_all('div', class_='gpvinfodetail')
    schedulers = []
    for gvp in gvps:
        for date in gvp.find_all('b'):
            if convert_date(date.text.strip()):
                date = convert_date(date.text.strip())
                break
        about_day = gvp.find_all('div')
        if any("застосування графіка погодинного відключення електроенергії у Полтавській області не прогнозується." in str(gvp) for tag in about_day):
            logger.info(f"No power outages")
            schedulers.append((gvp.text.strip(), date))
        gvps_table = gvp.find('table', class_='turnoff-scheduleui-table')
        if gvps_table:
            gvps_data = gvps_table.find('tbody')
            schedulers.append((pars_table(gvps_data), date))
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
            queue = {'queue': f'{queue_num}.{queue_sub_num}', 'data': [start_time, end_time]}
            result_queue.append(queue)
    return result_queue


def send_notification_schedulers(schedulers, date: str):
    """Send notification if schedule has changed"""
    for schedule in schedulers:
        log_message = get_schedule_send_log(queue=schedule[0].get('queue'), date=date)
        sleep(0.5)
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
        time_pairs = [f"{mess_schedule[i]} {mess_schedule[i + 1]}" for i in range(0, len(mess_schedule), 2)]
        times = '\n'.join(time_pairs)
        if not times:
            times = "Черга не входить у період відключень"
        text = f'Черга {sub_num_queue}, Відключення на {date}:\n' + f"{times}"
        if log_message[0] != text:
            tg_mess_id = telegram_send_text(chat_id=CHANNELS.get(int(num_queue)), text=text)
            save_schedule_send_log(queue=sub_num_queue, text=text, date=date, tg_mess_id=tg_mess_id)
            logger.info(f"Send notification - Date: {date} Queue: {sub_num_queue}")
        else:
            logger.info(f"Skip notification is no update - Date: {date} Queue: {sub_num_queue} ")


def send_notification_outages(date, no_power_outages: str):
    """Send notification if no power outages"""
    sleep(1)
    log_message = get_schedule_send_log(queue='0', date=date)
    if log_message[0] != no_power_outages:
        if is_last_seven_days_outages_count():
            telegram_send_text(chat_id=TELEGRAM_ADMIN, text=no_power_outages.split('.')[0])
        else:
            for channel_id in CHANNELS.values():
                telegram_send_text(chat_id=channel_id, text=no_power_outages.split('.')[0])
        save_schedule_send_log(queue='0', text=no_power_outages, date=date, tg_mess_id=0)
        logger.info(f"Send notification power outages - Date: {date}")
    else:
        logger.info(f"Skip notification is no power outages - Date: {date}")


def main(debug):
    """Main function"""
    work_period = [i for i in range(6, 23)]  # hours, period send current day
    current_date = datetime.now()
    if not current_date.time().hour in work_period:
        return logger.info('Skip check outside time period')
    formatted_date = current_date.strftime('%d-%m-%Y')
    if debug:
        with open('logs/25_12_2024_10_46_56.html', 'r', encoding='utf-8') as f:
            response = f.read()
    else:
        response = site_poe_gvp(formatted_date)
    if not response:
        return logger.info('The site returns bad html code of the website')
    if response is False:
        return logger.info('The site is not available currently')
    schedulers = pars_html(response)
    for schedule in schedulers:
        data_schedule = schedule[0]
        date = schedule[1]
        if isinstance(schedule[0], str):
            send_notification_outages(date=date, no_power_outages=data_schedule)
            continue
        if schedule and date:
            send_notification_schedulers(schedulers=data_schedule, date=date)


if __name__ == "__main__":
    main(debug=False)
