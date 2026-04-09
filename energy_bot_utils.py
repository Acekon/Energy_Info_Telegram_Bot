import logging
import sqlite3
from datetime import datetime, timedelta

import requests
from bs4 import BeautifulSoup


def setup_logger():
    loggers = logging.getLogger()
    loggers.setLevel(logging.INFO)
    file_handler = logging.FileHandler("logs/bot.log", encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_formatter = logging.Formatter("%(asctime)s - %(module)s - %(levelname)s - %(message)s")
    file_handler.setFormatter(file_formatter)
    loggers.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    console_handler.setFormatter(console_formatter)
    loggers.addHandler(console_handler)
    return loggers


logger = setup_logger()


def save_user_subscribe(user_id, queue):
    with sqlite3.connect("energy_bot.db") as conn:
        c = conn.cursor()
        c.execute("SELECT id FROM user_subscribes WHERE user_id = ? AND queue = ?", (user_id, queue))
        result = c.fetchone()
        if result:
            c.execute("UPDATE user_subscribes SET enable = 1 WHERE id = ?", (result[0],))
        else:
            c.execute("INSERT INTO user_subscribes (user_id, queue, enable) VALUES (?, ?, ?)", (user_id, queue, 1))
        conn.commit()


def remove_user_subscribe(user_id, queue):
    with sqlite3.connect("energy_bot.db") as conn:
        c = conn.cursor()
        c.execute("UPDATE user_subscribes SET enable = 0 WHERE user_id = ? AND queue = ?", (user_id, queue))
        conn.commit()


def get_all_subscribes():
    with sqlite3.connect("energy_bot.db") as conn:
        c = conn.cursor()
        c.execute("SELECT user_id, queue FROM user_subscribes WHERE enable = 1")
        return c.fetchall()


def get_user_subscribes(user_id):
    with sqlite3.connect("energy_bot.db") as conn:
        c = conn.cursor()
        c.execute("SELECT queue FROM user_subscribes WHERE user_id = ? AND enable = 1", (user_id,))
        return [row[0] for row in c.fetchall()]


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
        logger.error(f"Site PoE GVP request failed with status code: {response.status_code}")
        return False
    with open(f'logs/html/{datetime.now().strftime("%d_%m_%Y_%H_%M_%S")}.html', "w", encoding='UTF-8') as file:
        html_page = '<!doctype html><meta charset="utf-8"><link rel="stylesheet" href="table.css">\n' + response.text
        file.write(html_page)
    logger.info(f"Data for {date_in} received from site")
    return response.text


def index_to_time(index):
    hours = index // 2
    minutes = (index % 2) * 30
    return f"{hours:02}:{minutes:02}"


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
            if 'light_2' in cell.get('class', []) or 'light_3' in cell.get('class', []):
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
        resul_queue.append({'queue': f'{num}.{sub_num}', 'data': queue})
        if flag == 0:
            flag = 1
            sub_num = 2
            continue
        if flag == 1:
            flag = 0
            num += 1
            sub_num = 1
    return resul_queue


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


def parse_html_content(html_content):
    """
    :param html_content:
    :return: [{"about": str, "date": str, "gvps_data": list, 'update_date': str}]
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    heads = soup.find_all('div', class_='gpvinfodetail')
    result = []
    for head in heads:
        if not head:
            return False
        inner_html = head.decode_contents()
        before_table_html = inner_html.split('<div style="overflow-x:scroll; margin-top:5px;">')

        # get update date of GVP
        bs_source = BeautifulSoup(inner_html, 'html.parser')
        update_date = bs_source.find('div', style="text-align: end;font-size: 10px;")
        #  get head about text to GVP
        head = before_table_html[0].strip().split("<br/>")
        clear_html_tags = []
        for tag in head:
            item_soup = BeautifulSoup(tag, 'html.parser')
            clear_html_tags.append(item_soup.get_text().strip())
        about = "\n".join(clear_html_tags)

        #  get date of schedule
        date = BeautifulSoup(before_table_html[0].strip().split("<br/>")[0], 'html.parser')
        date = convert_date(date.find('b').text)

        #  get table with schedulers GVP
        if len(before_table_html) < 2:
            result.append({"about": about, "date": date, "gvps_data": [], 'update_date': update_date.get_text().strip()})
            continue
        table_gvp = BeautifulSoup(before_table_html[1], 'html.parser')
        gvps_table = table_gvp.find('table', class_='turnoff-scheduleui-table')
        gvps_data = pars_table(gvps_table.find('tbody'))
        result.append(
            {"about": about, "date": date, "gvps_data": gvps_data, 'update_date': update_date.get_text().strip()})
    return result


def format_schedule_lines(gvp_data, key):
    lines = []
    for item in gvp_data:
        slot = item.get(key)
        if slot:
            start, end, duration = slot
            lines.append(f"{start} - {end} ~{duration['hours']}:{duration['minutes']}")
    return "\n".join(lines) if lines else "Дані відсутні"


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

    on_periods = []
    start_on = None
    for i, value in enumerate(time_slots):
        if value == 0 and start_on is None:
            start_on = i
        elif value == 1 and start_on is not None:
            on_periods.append((start_on, i - 1))
            start_on = None
    if start_on is not None:
        on_periods.append((start_on, len(time_slots) - 1))

    def get_duration_info(s, e):
        st_time = index_to_time(s)
        en_time = index_to_time(e + 1)
        if en_time == '24:00':
            en_time = '23:59'

        st_dt = datetime.strptime(st_time, '%H:%M')
        en_dt = datetime.strptime(en_time, '%H:%M')
        if en_dt <= st_dt:
            en_dt += timedelta(days=1)

        diff = en_dt - st_dt
        return [st_time, en_time, {'hours': diff.seconds // 3600, 'minutes': (diff.seconds % 3600) // 60}]

    result_queue = []

    max_len = max(len(active_periods), len(on_periods))

    for i in range(max_len):
        item = {'queue': f'{queue_num}.{queue_sub_num}', 'data': [], 'data_on': []}

        if i < len(active_periods):
            item['data'] = get_duration_info(active_periods[i][0], active_periods[i][1])

        if i < len(on_periods):
            item['data_on'] = get_duration_info(on_periods[i][0], on_periods[i][1])

        result_queue.append(item)

    if not result_queue:
        result_queue.append({'queue': f'{queue_num}.{queue_sub_num}', 'data': [], 'data_on': []})

    return result_queue
