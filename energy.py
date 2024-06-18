import os
import time

import cloudscraper
from dotenv import load_dotenv
from bs4 import BeautifulSoup
import requests
import sqlite3

load_dotenv()
channels = {1: os.environ.get('CHANNEL_1'),
            2: os.environ.get('CHANNEL_2'),
            3: os.environ.get('CHANNEL_3'),
            4: os.environ.get('CHANNEL_4'),
            5: os.environ.get('CHANNEL_5'),
            6: os.environ.get('CHANNEL_6'),
            }
TELEGRAM_BOT = os.environ.get('TELEGRAM_BOT')


def telegram_send_text(chat_id, text=None):
    tg_url = f'https://api.telegram.org/bot{TELEGRAM_BOT}/sendMessage'
    response = requests.post(tg_url, json={'chat_id': chat_id, 'parse_mode': 'html', 'text': text})
    print(response.text)


def save_db(cherga, now_day):
    conn = sqlite3.connect('energy.db')
    c = conn.cursor()
    sql_query = (f'UPDATE energy '
                 f'SET now_day = "{now_day}"'
                 f'WHERE cherga = "{cherga}";')
    c.execute(sql_query)
    conn.commit()
    conn.close()


def if_update(cherga):
    conn = sqlite3.connect('energy.db')
    c = conn.cursor()
    sql_query = f'Select * from energy where cherga = "{cherga}";'
    c.execute(sql_query)
    tmp = c.fetchone()
    return tmp[1], tmp[2]


def parse(cherga):
    scraper = cloudscraper.create_scraper()
    url = f'https://energy-ua.info/cherga/{cherga}'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    response = scraper.get(url, headers=headers)
    soup = BeautifulSoup(response.text, 'html.parser')
    grafiks = soup.find_all(class_='grafik_string')
    formated_now_day = '\n'.join(grafiks[0].text.strip().split('\n'))
    now_day, b = if_update(cherga)
    time.sleep(2)
    return formated_now_day, now_day


if __name__ == '__main__':
    for i in range(1, 7):
        site_now_day, db_now_day = parse(i)
        if site_now_day != db_now_day:
            save_db(i, site_now_day)
            telegram_send_text(text=site_now_day, chat_id=channels.get(i))
        else:
            print(f'Cherga: {i} is skipped')

