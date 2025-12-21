# 🚀 Datahive Bot - Automation for Datahive AI
<div align="center">



[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)](https://github.com/D3-vin)
[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)

[<img src="https://img.shields.io/badge/Telegram-Channel-2CA5E0?style=flat&logo=telegram&logoColor=white" alt="Telegram Channel">](https://t.me/D3_vin) [<img src="https://img.shields.io/badge/Telegram-Chat-2CA5E0?style=flat&logo=telegram&logoColor=white" alt="Telegram Chat">](https://t.me/D3vin_chat) [<img src="https://img.shields.io/badge/GitHub-Repository-181717?style=flat&logo=github&logoColor=white" alt="GitHub">](https://github.com/D3-vin)

[Features](#features) • [Installation](#installation) • [Usage](#usage) • [Configuration](#configuration) • [Contact](#contact)

</div>

---



## ✨ Features

- 🔐 **Automatic Registration** - Bulk account registration with referral codes
- 🌾 **Smart Farming** - Automatic point collection through HTTP API
- 🔄 **Proxy Rotation** - Automatic proxy switching on connection errors
- 📊 **Multi-threading** - Separate thread settings for registration and farming
- 🚀 **Multiprocess Farming** - CPU-based multiprocess farming for maximum performance
- 💾 **Database** - Automatic saving of tokens, accounts, and devices
- 🔧 **Flexible Settings** - Complete configuration through config file
- 📝 **Detailed Logging** - Configurable logging levels (DEBUG, INFO, WARNING, ERROR)
- 🛡️ **Fault Tolerance** - Automatic retries with smart delay logic
- 📱 **Device Management** - Automatic device creation and fingerprinting

## 🚀 Advantages

- ✅ **Simplified Structure** - Logical code organization without unnecessary nesting
- ✅ **Modular Architecture** - Clear separation of API, Core, Database, UI, Utils
- ✅ **Automatic Management** - State saving, session recovery
- ✅ **Advanced Error Handling** - Smart retries with proxy rotation
- ✅ **Referral System** - Automatic reuse of codes from database
- ✅ **Multiprocess Support** - Efficient CPU utilization for large-scale farming

## 📁 Project Structure

```
datahive/
├── main.py                 # 🎯 Main entry point
├── requirements.txt        # 📦 Python dependencies
├── README.md              # 📖 Documentation
├── config/               # 📋 Configuration files
│   ├── config.yaml      # Main settings
│   └── data/            # Data files
│       ├── registration_accounts.txt  # Accounts for registration
│       ├── farming_accounts.txt      # Accounts for farming
│       └── proxy.txt    # Proxy list
│
├── data/                # 💾 Runtime data
│   └── datahive.db     # SQLite database
│
└── logs/               # 📋 Log files
    └── datahive.log    # Main log file
```

## 🛠️ Installation

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Setup Data Files

**Add accounts for registration:**
- `config/data/registration_accounts.txt` - Email accounts for registration
  - Format: `email:password:imap_server` or `email:password` (one per line)
  - If IMAP server is not specified, it will be auto-detected from email domain using `imap_settings.servers` in config
  - Example: `user@example.com:password123:imap.example.com` or `user@gmail.com:password123`

**Add accounts for farming (optional):**
- `config/data/farming_accounts.txt` - Email addresses of registered accounts
  - Format: `email` (one per line)
  - If empty, all logged-in accounts from database will be used

**Add proxies (optional):**
- `config/data/proxy.txt` - Proxy list in format `http://user:pass@ip:port` or `socks5://user:pass@ip:port`
  - One proxy per line

### 3. Configuration Setup

Edit `config/config.yaml`:

```yaml
# Multi-threading
threads:
  registration: 5  # Threads for registration
  farming: 3       # Threads for farming

# Logging
logging:
  level: "INFO"    # DEBUG, INFO, WARNING, ERROR, CRITICAL

# Referral codes
referral_code_settings:
  use_random_ref_code_from_db: true  # Use random code from DB
  static_referral_code: ""            # Or use static code

# Delays before start
delay_before_start:
  min: 1  # Minimum delay in seconds
  max: 3  # Maximum delay in seconds

# Retry settings
retry:
  delay_seconds: 5  # Delay between retries (in seconds)
  max_registration_attempts: 3  # Maximum registration attempts
  max_farm_attempts: 3  # Maximum farm attempts
  proxy_rotation: true  # Enable proxy rotation on exhausted retries

# Multiprocess farming
multiprocess_farming:
  enabled: true  # Enable multiprocess farming
  max_processes: 0  # 0 = auto-detect (CPU count - 1)

# Device settings
device_settings:
  active_devices_per_account:
    min: 1  # Minimum devices per account
    max: 1  # Maximum devices per account

# Farm settings
farm_settings:
  max_devices_per_batch: 200  # Max devices processed per batch
  max_concurrent_tasks: 200   # Max concurrent farming tasks
  device_task_timeout: 60     # Timeout for device task (seconds)

# IMAP settings
imap_settings:
  use_proxy_for_imap: false  # Use proxy for IMAP connections
  timeout: 30                 # IMAP timeout in seconds
  servers:                    # IMAP server mapping by email domain
    gmail.com: imap.gmail.com
    yahoo.com: imap.mail.yahoo.com
    mail.ru: imap.mail.ru
    # Add more domains as needed
```

## 🎮 Usage

### Launch

```bash
python main.py
```

### Operations Menu:

1. **Registration** - Automatic account registration
   - Reads accounts from `config/data/registration_accounts.txt`
   - Automatically handles email validation and verification
   - Saves registered accounts to database

2. **Farming** - Start farming process
   - Uses accounts from `config/data/farming_accounts.txt` or all logged-in accounts
   - Supports single-process and multiprocess modes
   - Automatically creates devices and manages farming cycles

3. **Exit** - Exit the program

## 📊 System Features

### 🔄 Smart Proxy Rotation
- Automatic proxy switching after exhausting connection attempts
- Configurable number of attempts per proxy
- Option to disable rotation for single proxy work
- Proxy assignment per account and device

### 🌾 Intelligent Farming
- HTTP API-based farming (no WebSocket)
- Automatic device creation and fingerprinting
- Ping and job request scheduling
- State saving in database

### 🔐 Authentication System
- Automatic token saving and updating
- Automatic re-authentication on token expiration
- Account state management

### 📈 Referral System
- Automatic retrieval and saving of referral codes
- Code reuse between accounts
- Support for static and dynamic referral codes

### 🚀 Multiprocess Farming
- Automatic CPU detection
- Efficient account and proxy distribution
- Process isolation for stability
- Configurable process limits

## 🔍 Monitoring and Logging

### Log Files
- **Console:** Colored logs in real-time
- **File:** `logs/datahive.log` with daily rotation
- **Levels:** DEBUG, INFO, SUCCESS, WARNING, ERROR

### Log Levels
- **DEBUG:** Detailed information for debugging
- **INFO:** General information about operations
- **WARNING:** Warnings about potential issues
- **ERROR:** Error messages

## 📢 Contact



- **📢 Channel**: [https://t.me/D3_vin](https://t.me/D3_vin) - Latest updates and releases
- **💬 Chat**: [https://t.me/D3vin_chat](https://t.me/D3vin_chat) - Community support and discussions
- **📁 GitHub**: [https://github.com/D3-vin](https://github.com/D3-vin) - Source code and development

---

**⚠️ Disclaimer:** This tool is for educational and testing purposes only. Always verify transactions and use at your own risk.
