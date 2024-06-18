# Energy Info Telegram Bot

This repository contains a Python script that periodically checks an energy information website for updates and sends these updates to specific Telegram channels if there are any changes.

This script was created for personal notification of power outages for non-commercial use.

## Features

- **Web Scraping**: Uses `cloudscraper` and `BeautifulSoup` to scrape energy information from a specific website.
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
    sqlite3 energy.db
    ```
    In the SQLite shell, create the `energy` table:
    ```sql
    CREATE TABLE energy (
        queue INTEGER PRIMARY KEY,
        now_day TEXT
    );
    ```
    Insert initial data:
    ```sql
    INSERT INTO energy (queue, now_day) VALUES (1, '');
    INSERT INTO energy (queue, now_day) VALUES (2, '');
    INSERT INTO energy (queue, now_day) VALUES (3, '');
    INSERT INTO energy (queue, now_day) VALUES (4, '');
    INSERT INTO energy (queue, now_day) VALUES (5, '');
    INSERT INTO energy (queue, now_day) VALUES (6, '');
    .quit
    ```

## Usage

Run the script:
```bash
python main.py
```

The script will check the website for updates, compare them with the stored data in the database, and if there are any updates, it will send them to the corresponding Telegram channels.

## Code Overview

- **Environment Variables**: Loads the Telegram bot token from a `.env` file.
- **Telegram Integration**: Defines a function `telegram_send_text` to send messages to Telegram channels.
- **Database Operations**: Defines functions `save_db` and `if_update` to interact with the SQLite database.
- **Web Scraping**: Defines a function `parse` to scrape and parse the website for the latest energy information.
- **Main Execution**: Iterates through predefined channels, checks for updates, and sends messages if there are new updates.

## Contributing

Feel free to open issues or submit pull requests if you have any improvements or bug fixes.

## License

This project is licensed under the MIT License. See the `LICENSE` file for more details.
