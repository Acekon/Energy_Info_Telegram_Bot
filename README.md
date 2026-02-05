# Energy Info Telegram Bot

This repository contains a Python script that automatically monitors hourly power outage schedules (GPV) from the Poltavaoblenergo website. The bot parses data, compares it with a local database, and notifies users in specific Telegram channels about any changes.

This script was created for personal notification of power outages for non-commercial use.

## Features

- **Automated Scraping**: Periodically fetches data from the POE website and parses HTML tables using `BeautifulSoup`.
- **Sub-queue Support**: Specifically handles all 6 main queues and their sub-queues (e.g., 1.1, 1.2, 2.1, etc.).
- **Smart Updates**: 
    - If a schedule changes, the bot sends a new message.
    - It edits the previous message to strike it out (`<s>`) and adds an "UPD" notice to maintain history.
- **Duration Calculation**: Calculates and displays total time with/without power for each specific queue.
- **Daily Cleanup**: Every day at midnight, the bot automatically marks yesterday's messages as outdated/irrelevant.
- **Resilience**: Implements retry logic for Telegram API rate limits (`429` errors).
- **Audit Logs**: Saves local copies of the parsed HTML pages in the `logs/` directory for debugging.

## Prerequisites

- Python 3.x
- `beautifulsoup4`
- `requests`
- `python-dotenv`
- `sqlite3`

## Installation

1. **Clone the repository and set up a virtual environment:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```

2. **Install dependencies:**
    ```bash
    pip install beautifulsoup4 requests python-dotenv
    ```

3. **Configure Environment Variables:**
    Create a `.env` file in the root directory:
    ```plaintext
    TELEGRAM_BOT=your_bot_token
    TELEGRAM_ADMIN=your_admin_chat_id
    CHANNEL_0=id_for_summary_channel
    CHANNEL_1=id_for_queue_1
    CHANNEL_2=id_for_queue_2
    CHANNEL_3=id_for_queue_3
    CHANNEL_4=id_for_queue_4
    CHANNEL_5=id_for_queue_5
    CHANNEL_6=id_for_queue_6
    ```

4. **Initialize the Database:**
    The script expects a SQLite database named `energy.db` with the following schema:
    ```sql
    CREATE TABLE "send_log_v2" (
        "date" TEXT,
        "text" TEXT,
        "queue" TEXT,
        "tg_mess_id" INTEGER
    );
    ```

## Usage

### Manual Start
```bash
python energy.py
```
## Automation (Cron)

Create a startup script `start_energy.sh`:

```bash
#!/bin/bash
# Activate the virtual environment
source /your_path/venv/bin/activate

# Run the Python script
cd /your_path/
python3 energy.py
```
## Logging

logs/app.log: General operation logs including success/error status.

logs/*.html: Timestamped HTML snapshots of the source website for data verification.

## License
This project is licensed under the MIT License.