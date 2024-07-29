# Energy Info Telegram Bot

This repository contains a Python script that periodically checks an energy information website for updates and sends these updates to specific Telegram channels if there are any changes.

This script was created for personal notification of power outages for non-commercial use.

## Features

- **Web Scraping**: Uses `BeautifulSoup` to scrape energy information from a specific website.
- **Telegram Integration**: Sends updates to Telegram channels using the Telegram Bot API.
- **SQLite Database**: Stores and updates the latest fetched information to prevent duplicate messages.

## Prerequisites

- Python 3.x
- `cloudscraper`
- `beautifulsoup4`
- `requests`
- `python-dotenv`
- `sqlite3`

## Installation

1. Create a virtual environment and activate it:
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```

2. Install the required packages:
    ```bash
    pip install -r requirements.txt
    ```

3. Create a `.env` file in the root directory of the project and add your Telegram Bot API key:
    ```plaintext
    TELEGRAM_BOT=your_telegram_bot_token
    ```

4. Set up your SQLite database:
    ```bash
    cat base-db.sql | sqlite3 energy.db
    ```
   Need in table `schedullres` insert current day 'Y-M-D' and sequence ['A','B','C']
    ```sql
    INSERT INTO "main"."schedulers"("id","date","start","end","class","sequence") VALUES (NULL,'Y-M-D',NULL,NULL,NULL,'A');
    ```

## Usage

Run the script:
```bash
python main.py
```
Or start to cron:
```bash
touch start_energy.sh
nano start_energy.sh
```
Write text
```text
#!/bin/bash
# Activate the virtual environment
source /you_path/venv/bin/activate

# Run the Python script
cd /you_path/
python3 /you_path/energy.py
```
Create cron task
```bash
crontab -e
```
Write new line text
```text
1 * * * * /you_path/start_energy.sh >> /you_path/cron.log 2>&1
```

The script will check the website for updates, compare them with the stored data in the database, and if there are any updates, it will send them to the corresponding Telegram channels.

## Contributing

Feel free to open issues or submit pull requests if you have any improvements or bug fixes.

## License

This project is licensed under the MIT License. See the `LICENSE` file for more details.
