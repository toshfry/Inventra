# Inventra

Automotive inventory management and point-of-sale software for repair shops,
parts stores, and small automotive businesses.

![Python](https://img.shields.io/badge/Python-3.11%2B-blue)
![SQLite](https://img.shields.io/badge/Database-SQLite-0f766e)
![CustomTkinter](https://img.shields.io/badge/Desktop-CustomTkinter-2563eb)
![Flask](https://img.shields.io/badge/Web-Flask-111827)
![Status](https://img.shields.io/badge/Mode-Offline%20First-16a34a)

Inventra is a local-first desktop app for managing automotive parts inventory,
stock movement, suppliers, sales, returns, reports, users, and backups. It runs
on a local SQLite database, requires no cloud service, and includes an optional
Flask web interface for phones or tablets on the same Wi-Fi network.

> **Default login:** `admin` / `admin123` — change it on first login
> (Settings → change password) before using the app with real data.

## Table of Contents

- [Features](#features)
- [Inventory Model](#inventory-model)
- [Tech Stack](#tech-stack)
- [Requirements](#requirements)
- [Quick Start](#quick-start)
- [First Launch](#first-launch)
- [Optional Web Mode](#optional-web-mode)
- [Common Workflows](#common-workflows)
- [Project Structure](#project-structure)
- [Data, Backups, and Privacy](#data-backups-and-privacy)
- [Security / Privacy Note](#security--privacy-note)
- [Testing and Verification](#testing-and-verification)
- [Build a Windows EXE](#build-a-windows-exe)
- [Troubleshooting](#troubleshooting)
- [Production Checklist](#production-checklist)

## Features

| Area | What Inventra Provides |
| --- | --- |
| Dashboard | Stock health, low-stock warnings, sales activity, inventory value, and recent movements. |
| Parts Library | Add, edit, search, categorize, and deactivate automotive parts with SKU, cost, selling price, minimum stock, bin location, unit, and vehicle-make fields. |
| Stock In | Receive inventory from suppliers with quantity, cost, reference, date, and user traceability. |
| Stock Out | Issue parts for sales, usage, damage, transfer, or other reasons while blocking invalid stock movement. |
| POS | Multi-item checkout with discounts, labor/service fees, configurable fee types, receipts, and payment handling. |
| Returns | Process customer returns, record refund details, and optionally restock resellable parts. |
| Adjustments | Correct stock using audited positive or negative deltas with reason tracking. |
| Suppliers | Store supplier contact details and use them during receiving workflows. |
| Categories | Manage color-coded part categories for faster scanning and filtering. |
| Reports | Export inventory, sales, movements, stock aging, stock-in/out, adjustments, returns, and audit reports to Excel. |
| Users and Access | First-run activation, default admin seeding, login, user records, and role-aware actions. |
| Backups | Automatic and manual SQLite backups with restore support from Settings. |
| Optional Web UI | LAN-accessible Flask interface for browser-based inventory and POS workflows. |

## Inventory Model

Inventra does not store current stock as a manually edited number. Current stock
is computed from the movement history through the `part_stock` SQLite view:

```text
current_stock =
    total stock in
  - total stock out
  + stock adjustment deltas
  + returned quantity marked for restock
```

This keeps the stock count tied to auditable events instead of letting a stored
quantity drift away from the real transaction history.

## Tech Stack

- Python 3.11+
- CustomTkinter for the desktop interface
- SQLite with SQLAlchemy ORM
- Pydantic for validation schemas
- Flask for optional LAN/web access
- openpyxl for Excel report exports
- Pillow, OpenCV, and NumPy for image/barcode helper support
- cryptography for offline activation support
- PyInstaller for Windows executable packaging

Main dependencies are listed in [`requirements.txt`](requirements.txt).

## Requirements

| Requirement | Version |
| --- | --- |
| Python | 3.11 or newer |
| Operating system | Windows 10/11, macOS 12+, or Ubuntu 20+ |
| Storage | Local write access for `data/`, `exports/`, and backups |

## Quick Start

From the `inventra` project directory:

```bash
python -m venv venv
```

Activate the virtual environment:

```bash
# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the desktop app:

```bash
python app.py
```

## First Launch

On first launch, Inventra automatically prepares its local runtime folders and
database:

- Creates `data/`
- Creates `data/inventra.db`
- Creates `data/backups/`
- Creates `exports/`
- Creates database tables and the `part_stock` view
- Runs lightweight SQLite migrations
- Seeds default part categories
- Seeds the default admin account

The normal first-run flow is:

1. Activate the app with a valid activation key.
2. Log in with the default admin account.
3. Change the default password in Settings.
4. Create real staff/admin users as needed.

Default login:

```text
Username: admin
Password: admin123
```

Change this password before using the app with real shop data.

## Optional Web Mode

Inventra includes `web_server.py`, a Flask server that exposes the same local
database to a browser interface. This is useful when a phone, tablet, or another
computer on the same Wi-Fi network needs access.

Run it from the project directory:

```bash
python web_server.py
```

On Windows, you can also use:

```bash
run_web.bat
```

Then open the computer's LAN address from another device, for example:

```text
http://192.168.1.23:5000
```

The web/API mode also checks local activation status before allowing normal API
access.

Important: `web_server.py` contains a placeholder Flask secret key. Replace it
before any real deployment beyond trusted local testing.

## Common Workflows

### Add a Part

1. Open Parts Library.
2. Choose Add Part.
3. Fill in name, category, SKU or generated SKU, unit cost, selling price,
   minimum stock, unit, bin location, and vehicle-make details.
4. Save the part.

### Receive Stock

1. Open Stock In.
2. Select a part and supplier.
3. Enter quantity, unit cost, reference, and receiving notes.
4. Save the transaction.

### Sell Through POS

1. Open POS.
2. Search or filter parts.
3. Add items to the cart.
4. Apply line or sale-level discounts when needed.
5. Add labor/service fees when needed.
6. Confirm payment and print or view the receipt.

### Process a Return

1. Open Returns.
2. Link the return to a previous issue/sale when possible.
3. Enter quantity, refund amount, reason, and condition.
4. Choose whether the returned item should restock inventory.

### Export Reports

1. Open Reports.
2. Choose the report type and date range.
3. Generate the Excel file.
4. Find exported files under `exports/`.

## Project Structure

```text
inventra/
|-- app.py                    Desktop entry point
|-- web_server.py             Optional Flask web/API server
|-- inventra.spec             PyInstaller build spec
|-- requirements.txt          Python dependencies
|-- run_web.bat               Windows helper for web mode
|-- run_web.sh                Shell helper for web mode
|
|-- assets/                   Brand images used by the desktop app
|-- config/
|   |-- settings.py           App name, version, paths, database path, window sizes
|   `-- themes.py             UI color and font constants
|
|-- core/
|   |-- licensing/            Offline activation helpers
|   |-- services/             Business logic for parts, stock, POS, reports, users, settings
|   `-- validators/           Pydantic schemas for request and form validation
|
|-- database/
|   |-- base.py               SQLAlchemy declarative base
|   |-- engine.py             Engine, sessions, migrations, seed data, stock view
|   `-- models/               Parts, categories, suppliers, stock movement, sales, users
|
|-- ui/
|   |-- app_window.py         Main desktop shell and routing
|   |-- activation.py         First-run activation window
|   |-- login.py              Login window
|   |-- nav_sidebar.py        Desktop navigation
|   |-- components/           Reusable table, modal, toast, metric card, responsive helpers
|   `-- screens/              Dashboard, parts, stock, POS, returns, reports, settings
|
|-- utils/                    Backup, app icon, and receipt printing helpers
|-- web/                      Browser UI served by Flask
|-- tests/                    Runtime verification scripts
|-- data/                     Local SQLite database and backups, created at runtime
`-- exports/                  Generated reports, created at runtime
```

## Data, Backups, and Privacy

- All operational data is stored locally in `data/inventra.db`.
- The app does not require an internet connection for normal use.
- Backups are stored in `data/backups/`.
- Reports are exported to `exports/`.
- To move the app to another machine, copy the project folder, including the
  `data/` folder.
- Keep `data/*.db`, backups, and generated reports out of public version
  control.

## Security / Privacy Note

Runtime data, databases, generated reports, backups, logs, license keys, and
private records are excluded from this repository for security and privacy
reasons.

Use `.env.example` as a template for local secrets. Copy it to `.env`, fill in
local values, and keep `.env` out of Git.

## Testing and Verification

The `tests/` directory contains focused verification scripts for important
runtime behavior such as POS, returns, stock adjustment, web parity, report
fees, receipt layout, and error handling.

Run individual probes from the project directory, for example:

```bash
python -m tests.verify_pos
python -m tests.verify_returns
python -m tests.verify_stock_adjustment
```

If you add new features, create a focused verification script or test that
covers the behavior and data changes.

## Build a Windows EXE

Install PyInstaller:

```bash
pip install pyinstaller
```

Build with the bundled spec:

```bash
pyinstaller inventra.spec --clean
```

The spec includes the desktop entry point, app icon, CustomTkinter assets,
brand assets, web assets, database modules, licensing modules, and hidden
imports needed for the packaged app.

## Troubleshooting

| Problem | Suggested Fix |
| --- | --- |
| `ModuleNotFoundError: customtkinter` | Activate the virtual environment and run `pip install -r requirements.txt`. |
| App opens and closes immediately | Run `python app.py` from a terminal to see the traceback. |
| Login does not appear | Make sure activation has completed or check the activation window. |
| Database error on a fresh test install | Stop the app, remove the test `data/inventra.db`, and relaunch. Do not delete a real production database unless you have a backup. |
| Web mode is not reachable from a phone | Confirm both devices are on the same Wi-Fi network and that the firewall allows port `5000`. |
| Reports do not open | Confirm `exports/` exists and the file is not already locked by Excel. |

## Production Checklist

- Change the default `admin` / `admin123` password.
- Replace the placeholder Flask secret key in `web_server.py` before broader LAN
  or production use.
- Keep local database, license, backup, and export files out of public GitHub
  repositories.
- Create regular off-machine backups of `data/inventra.db`.
- Test activation, login, POS, reports, backup, restore, and web mode before
  using the app with live business data.

## Author

Created by **John Lloyd Sereno (toshfry)**.
