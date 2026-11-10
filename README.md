# Northstar Credit practical interview app

A small, local training app for investigating borrower exposure across multiple lines of business. It uses Python 3.10 or later, Python's standard library, and SQLite; there are no third-party packages to install.

## Run it

1. Open this folder in VS Code.
2. In VS Code, open **Terminal → New Terminal**.
3. Run `python3 app.py`.
4. Open [http://127.0.0.1:8000](http://127.0.0.1:8000) in a browser.

The app creates its synthetic database in `instance/exposure.db` the first time it runs. The portfolio contains 50 synthetic borrowers with varied facility counts, product mixes, currencies, statuses, and exposure sizes. Borrowers are grouped by sector, so Alder Ridge Manufacturing appears within the portfolio rather than first in an alphabetical list. To reset the sample data, stop the app, delete that database file, and run the app again.

The portfolio dashboard offers a searchable card or table view, sector filtering, a CAD/USD display switch, and a short recently viewed list saved in the browser. Borrower profiles use the same currency switch and provide a compact utilization visualization, categorized exposure summary, account-team cards, and the facility table.

The role selector in the app lets you switch among **Superuser**, **Capital Markets User**, **Commercial Banking User**, and **Wealth Management User**. Select Capital Markets User to play the end-user role; Superuser can see every facility detail. Borrower totals and cross-line-of-business account-team contacts remain visible in each role. The read-only database utility is available from the top bar for every role and is scoped to this app's synthetic database.

For this exercise, a facility's total exposure is committed amount + uncommitted amount. Drawn amount is reported separately and is used to calculate utilization; it is not added to exposure. Include facilities whose status is Active, even if their maturity date has passed; exclude facilities whose status is not Active. Show facility utilization as drawn divided by committed plus uncommitted. Borrower utilization is total drawn divided by total exposure, calculated on a CAD-converted basis rather than averaging facility percentages. Fixed illustrative FX rates convert exposures to CAD and USD; both are displayed for all borrowers.

Business labels are stored once in code-and-description domain tables for lines of business, sectors, exposure classes and subclasses, facility types, facility statuses, currencies, and account-team roles. Fact records store stable codes and join to these domains for display. For example, changing the Commercial Banking description in `line_of_business_domain` updates its display throughout the app without changing facility, user, access, or account-team records.

Borrower IDs and facility IDs are integer keys. Line-of-business identity is represented separately by `line_of_business_code`.

## Files

- `app.py` — local HTTP server that serves the UI and routes JSON API calls
- `api.py` — HTTP API routes and request/response handling
- `services.py` — application workflows used by API routes
- `stored_procedures.py` — parameterized SQLite queries that stand in for database stored procedures
- `database.py` — SQLite connection setup and lifecycle
- `database_utility.py` — read-only SQL and visual-query execution/validation
- `ui/` — separate browser pages, styles, and JavaScript
- `seed_data.py` — schema and synthetic sample records
- `candidate-preparation.md` — setup notes to send before the interview
- `practical-assessment.md` — full candidate-facing prompt and run instructions
- `scenario-brief.md` — end-user perspective, reported totals, and exercise rules

All names and records are fictional. The app binds to localhost by default and is intended for local interview practice, not production use.

## Application layers

The browser UI calls JSON endpoints in `api.py`. API routes delegate application work to `services.py`, which calls named `sp_*` operations in `stored_procedures.py`. SQLite does not support stored procedures, so those parameterized query functions provide a local stand-in that can be replaced by SQL Server procedure calls while keeping the UI and API contracts separate. The database utility has its own read-only API endpoints.

## Query the database

Choose **Database utility** in the top bar while using any role. The expandable tables-and-columns catalog is available alongside both query modes and acts as a data dictionary in SQL mode. Use the SQL editor to write a SELECT statement or the visual builder to select tables, fields, filters, and sorting. **Select all columns** includes all fields from tables on the canvas. The visual builder requires you to choose each join type and both columns in the join condition. Queries are read-only, results are capped at 250 rows, and results can be copied with headers for spreadsheets or exported to CSV.
