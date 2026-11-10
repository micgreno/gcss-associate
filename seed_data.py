"""Create the synthetic SQLite database used by the training application."""

from __future__ import annotations

import sqlite3
import random
from pathlib import Path


SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE line_of_business_domain (
    line_of_business_code TEXT PRIMARY KEY,
    description TEXT NOT NULL
);
CREATE TABLE sector_domain (
    sector_code TEXT PRIMARY KEY,
    description TEXT NOT NULL
);
CREATE TABLE borrowers (
    borrower_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    sector_code TEXT NOT NULL REFERENCES sector_domain(sector_code)
);
CREATE TABLE users (
    user_id TEXT PRIMARY KEY,
    home_line_of_business_code TEXT NOT NULL REFERENCES line_of_business_domain(line_of_business_code),
    is_superuser INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE user_lob_access (
    user_id TEXT NOT NULL REFERENCES users(user_id),
    line_of_business_code TEXT NOT NULL REFERENCES line_of_business_domain(line_of_business_code),
    PRIMARY KEY (user_id, line_of_business_code)
);
CREATE TABLE account_teams (
    borrower_id INTEGER NOT NULL REFERENCES borrowers(borrower_id),
    line_of_business_code TEXT NOT NULL REFERENCES line_of_business_domain(line_of_business_code),
    role_code TEXT NOT NULL REFERENCES account_team_role_domain(role_code),
    person_name TEXT NOT NULL,
    PRIMARY KEY (borrower_id, line_of_business_code, role_code)
);
CREATE TABLE account_team_role_domain (
    role_code TEXT PRIMARY KEY,
    description TEXT NOT NULL
);
CREATE TABLE exposure_class_domain (
    exposure_class_code TEXT PRIMARY KEY,
    description TEXT NOT NULL
);
CREATE TABLE exposure_subclass_domain (
    exposure_subclass_code TEXT PRIMARY KEY,
    exposure_class_code TEXT NOT NULL REFERENCES exposure_class_domain(exposure_class_code),
    description TEXT NOT NULL
);
CREATE TABLE facility_type_domain (
    facility_type_code TEXT PRIMARY KEY,
    exposure_subclass_code TEXT NOT NULL REFERENCES exposure_subclass_domain(exposure_subclass_code),
    description TEXT NOT NULL
);
CREATE TABLE facility_status_domain (
    status_code TEXT PRIMARY KEY,
    description TEXT NOT NULL
);
CREATE TABLE currency_domain (
    currency_code TEXT PRIMARY KEY,
    description TEXT NOT NULL
);
CREATE TABLE fx_rates (
    currency_code TEXT PRIMARY KEY REFERENCES currency_domain(currency_code),
    to_cad REAL NOT NULL,
    to_usd REAL NOT NULL
);
CREATE TABLE facilities (
    facility_id INTEGER PRIMARY KEY,
    borrower_id INTEGER NOT NULL REFERENCES borrowers(borrower_id),
    line_of_business_code TEXT NOT NULL REFERENCES line_of_business_domain(line_of_business_code),
    exposure_class_code TEXT NOT NULL REFERENCES exposure_class_domain(exposure_class_code),
    exposure_subclass_code TEXT NOT NULL REFERENCES exposure_subclass_domain(exposure_subclass_code),
    facility_type_code TEXT NOT NULL REFERENCES facility_type_domain(facility_type_code),
    status_code TEXT NOT NULL REFERENCES facility_status_domain(status_code),
    currency_code TEXT NOT NULL REFERENCES currency_domain(currency_code),
    facility_description VARCHAR(255) NOT NULL CHECK (length(facility_description) <= 255),
    commitment_start_date DATE,
    maturity_date DATE NOT NULL CHECK (date(maturity_date) IS NOT NULL),
    committed_amount REAL NOT NULL,
    uncommitted_amount REAL NOT NULL,
    drawn_amount REAL NOT NULL,
    CHECK (committed_amount = 0 OR commitment_start_date IS NOT NULL)
);
"""

INTEGRITY_GUARDS = """
CREATE TRIGGER IF NOT EXISTS facilities_class_subclass_insert
BEFORE INSERT ON facilities
WHEN NOT EXISTS (
    SELECT 1 FROM exposure_subclass_domain d
    WHERE d.exposure_subclass_code = NEW.exposure_subclass_code
      AND d.exposure_class_code = NEW.exposure_class_code
)
BEGIN
    SELECT RAISE(ABORT, 'Facility exposure class and subclass do not match.');
END;
CREATE TRIGGER IF NOT EXISTS facilities_class_subclass_update
BEFORE UPDATE OF exposure_class_code, exposure_subclass_code ON facilities
WHEN NOT EXISTS (
    SELECT 1 FROM exposure_subclass_domain d
    WHERE d.exposure_subclass_code = NEW.exposure_subclass_code
      AND d.exposure_class_code = NEW.exposure_class_code
)
BEGIN
    SELECT RAISE(ABORT, 'Facility exposure class and subclass do not match.');
END;
CREATE TRIGGER IF NOT EXISTS facilities_type_subclass_insert
BEFORE INSERT ON facilities
WHEN NOT EXISTS (
    SELECT 1 FROM facility_type_domain d
    WHERE d.facility_type_code = NEW.facility_type_code
      AND d.exposure_subclass_code = NEW.exposure_subclass_code
)
BEGIN
    SELECT RAISE(ABORT, 'Facility type and exposure subclass do not match.');
END;
CREATE TRIGGER IF NOT EXISTS facilities_type_subclass_update
BEFORE UPDATE OF facility_type_code, exposure_subclass_code ON facilities
WHEN NOT EXISTS (
    SELECT 1 FROM facility_type_domain d
    WHERE d.facility_type_code = NEW.facility_type_code
      AND d.exposure_subclass_code = NEW.exposure_subclass_code
)
BEGIN
    SELECT RAISE(ABORT, 'Facility type and exposure subclass do not match.');
END;
"""


def install_integrity_guards(db: sqlite3.Connection) -> None:
    """Install idempotent guards on fresh and already-created local databases."""
    db.executescript(INTEGRITY_GUARDS)

LOB_ALL = "ALL"
LOB_CM = "CM"
LOB_CB = "CB"
LOB_WM = "WM"

LINE_OF_BUSINESS = [
    (LOB_ALL, "All lines of business"),
    (LOB_CM, "Capital Markets"),
    (LOB_CB, "Commercial Banking"),
    (LOB_WM, "Wealth Management"),
]


SECTORS = [
    ("INDUSTRIALS", "Industrials"),
    ("HEALTHCARE", "Healthcare"),
    ("ENERGY", "Energy"),
    ("CONSUMER_GOODS", "Consumer goods"),
    ("INFRASTRUCTURE", "Infrastructure"),
]

EXPOSURE_CLASSES = [("CREDIT", "Credit"), ("NON_CREDIT", "Non-credit/other")]
EXPOSURE_SUBCLASSES = [
    ("LENDING", "CREDIT", "Lending"),
    ("TRADING", "CREDIT", "Trading"),
    ("TRANSACTIONAL", "NON_CREDIT", "Transactional"),
    ("CONTINGENT", "NON_CREDIT", "Contingent"),
]
FACILITY_TYPES = [
    ("DERIVATIVES", "TRADING", "Derivatives"),
    ("REPOS", "TRADING", "Repos"),
    ("FOREIGN_EXCHANGE", "TRADING", "Foreign exchange"),
    ("SECURITIES_LENDING", "TRADING", "Securities lending"),
    ("TERM_LOAN", "LENDING", "Term loan"),
    ("REVOLVING_CREDIT", "LENDING", "Revolving credit"),
    ("SETTLEMENT_SERVICES", "TRANSACTIONAL", "Settlement services"),
    ("CUSTODY_SETTLEMENT", "TRANSACTIONAL", "Custody and settlement"),
    ("LETTER_OF_CREDIT", "CONTINGENT", "Letter of credit"),
    ("PERFORMANCE_GUARANTEE", "CONTINGENT", "Performance guarantee"),
]
FACILITY_STATUSES = [("ACTIVE", "Active"), ("CLOSED", "Closed"), ("INACTIVE", "Inactive")]
ACCOUNT_TEAM_ROLES = [("RM", "Relationship Manager"), ("CREDIT_MANAGER", "Credit Manager")]
CURRENCIES = [
    ("CAD", "Canadian dollar"),
    ("USD", "US dollar"),
    ("EUR", "Euro"),
    ("GBP", "Pound sterling"),
]

BORROWERS = [
    (1042, "Alder Ridge Manufacturing", "INDUSTRIALS"),
    (2088, "Bluewater Health Group", "HEALTHCARE"),
    (3091, "Cedar Peak Energy", "ENERGY"),
    (4105, "Meridian Foods Cooperative", "CONSUMER_GOODS"),
    (5117, "Westlake Infrastructure Partners", "INFRASTRUCTURE"),
]

MOCK_BORROWER_NAMES = [
    "Acadia Advanced Materials", "Adler Foods International", "Alderstone Logistics",
    "Alpine Medical Systems", "Amblewood Consumer Products", "Amberline Energy Services",
    "Arbor Peak Technologies", "Ardent Infrastructure Group", "Ashford Specialty Chemicals",
    "Asterion Communications", "Atlas Harbor Shipping", "Aurora Components Ltd.",
    "Avondale Agricultural Partners", "Bayshore Data Systems", "Beaconfield Holdings",
    "Bellwether Mobility Group", "Birchstone Packaging", "Blackwater Renewables",
    "Bluehaven Property Partners", "Brackenridge Apparel", "Brightwell Diagnostics",
    "Cairnbridge Mining", "Caldera Building Products", "Caledon Transit Group",
    "Calloway Paper Industries", "Canopy Veterinary Health", "Canyon Crest Aviation",
    "Caravel Marine Systems", "Cedarline Telecom", "Celadon Home Brands",
    "Centennial Waterworks", "Clearpath Industrial Supply", "Cloudline Software Group",
    "Copperfield Medical Devices", "Coral Bay Hospitality", "Crownpoint Rail Services",
    "Dalespring Consumer Finance", "Deepwell Resources", "Dovetail Packaging Group",
    "Eastgate Food Markets", "Evergreen Fleet Services", "Fairhaven Life Sciences",
    "Farpoint Construction", "Frostline Cold Storage", "Glenhaven Utilities",
]

MOCK_SECTORS = ["INDUSTRIALS", "HEALTHCARE", "ENERGY", "CONSUMER_GOODS", "INFRASTRUCTURE"]
MOCK_LOBS = [LOB_CM, LOB_CB, LOB_WM]
MOCK_FACILITY_TYPE_CODES = [row[0] for row in FACILITY_TYPES]
MOCK_CURRENCY_CODES = [row[0] for row in CURRENCIES]
MOCK_RELATIONSHIP_MANAGERS = [
    "Morgan Lee", "Priya Shah", "Evan Brooks", "Nina Foster", "Owen Clark",
    "Grace Liu", "Mateo Rivera", "Hannah Reed", "Isaac Turner", "Leah Cooper",
    "Amir Patel", "Chloe Bennett", "Julian Ross", "Elena Ward", "Miles Parker",
]
MOCK_CREDIT_MANAGERS = [
    "Taylor Morgan", "Riley Chen", "Casey Martin", "Jamie Wilson", "Avery Thompson",
    "Jordan Davis", "Cameron Brooks", "Drew Patel", "Skylar Kim", "Reese Johnson",
]


def mock_portfolio_records() -> tuple[list[tuple], list[tuple], dict[int, tuple[str, str]], list[tuple]]:
    """Build repeatable, varied portfolio records without changing the core scenario."""
    rng = random.Random(684_210)
    borrowers = []
    facilities = []
    dates = {}
    teams = []
    # The repeating pattern includes one- and two-facility borrowers as well as
    # borrowers with broad, multi-LOB portfolios.
    facility_counts = [1, 2, 1, 3, 5, 8, 11, 2, 4]
    for index, name in enumerate(MOCK_BORROWER_NAMES):
        borrower_id = 6001 + index
        sector_code = MOCK_SECTORS[(index * 3 + index // 5) % len(MOCK_SECTORS)]
        borrowers.append((borrower_id, name, sector_code))
        facility_count = facility_counts[index % len(facility_counts)]
        lobs_for_borrower = [MOCK_LOBS[(index + offset) % len(MOCK_LOBS)] for offset in range(min(3, facility_count))]
        for lob_index, lob_code in enumerate(lobs_for_borrower):
            teams.append((borrower_id, lob_code, "RM", MOCK_RELATIONSHIP_MANAGERS[(index + lob_index) % len(MOCK_RELATIONSHIP_MANAGERS)]))
            if (index + lob_index) % 3 == 0:
                teams.append((borrower_id, lob_code, "CREDIT_MANAGER", MOCK_CREDIT_MANAGERS[(index + lob_index) % len(MOCK_CREDIT_MANAGERS)]))
        for facility_index in range(facility_count):
            facility_id = 120001 + index * 20 + facility_index
            type_code = MOCK_FACILITY_TYPE_CODES[(index * 2 + facility_index * 3) % len(MOCK_FACILITY_TYPE_CODES)]
            type_row = next(row for row in FACILITY_TYPES if row[0] == type_code)
            subclass_code = type_row[1]
            class_code = next(row[1] for row in EXPOSURE_SUBCLASSES if row[0] == subclass_code)
            lob_code = lobs_for_borrower[facility_index % len(lobs_for_borrower)]
            currency_code = MOCK_CURRENCY_CODES[(index + facility_index * 2) % len(MOCK_CURRENCY_CODES)]
            status_code = "ACTIVE" if rng.random() < 0.88 else ("CLOSED" if rng.random() < 0.65 else "INACTIVE")
            scale = rng.choice([250_000, 750_000, 1_500_000, 4_000_000, 9_000_000, 18_000_000])
            committed = rng.randint(2, 16) * scale if status_code == "ACTIVE" else 0
            uncommitted = rng.randint(0, 5) * scale if status_code == "ACTIVE" else 0
            capacity = committed + uncommitted
            drawn = rng.randint(0, capacity) if capacity else 0
            start_year = rng.randint(2019, 2026)
            start_month = rng.randint(1, 12)
            start_date = f"{start_year:04d}-{start_month:02d}-01" if committed else None
            maturity_year = start_year + rng.randint(1, 7)
            maturity_date = f"{maturity_year:04d}-{start_month:02d}-28"
            dates[facility_id] = (start_date, maturity_date)
            facilities.append((
                facility_id, borrower_id, lob_code, class_code, subclass_code, type_code,
                status_code, currency_code, committed, uncommitted, drawn,
            ))
    return borrowers, facilities, dates, teams

FX_RATES = [
    ("CAD", 1.00, 0.74),
    ("USD", 1.35, 1.00),
    ("EUR", 1.47, 1.09),
    ("GBP", 1.72, 1.27),
]

# facility_id, borrower_id, LOB code, class code, subclass code, type code,
# status code, currency code, committed, uncommitted, drawn
FACILITIES = [
    (77104, 1042, LOB_CM, "CREDIT", "TRADING", "DERIVATIVES", "ACTIVE", "USD", 7_500_000, 2_000_000, 3_100_000),
    (77105, 1042, LOB_CM, "CREDIT", "TRADING", "REPOS", "ACTIVE", "CAD", 5_200_000, 1_000_000, 2_400_000),
    (77106, 1042, LOB_CM, "CREDIT", "TRADING", "FOREIGN_EXCHANGE", "ACTIVE", "EUR", 3_400_000, 900_000, 1_100_000),
    (77107, 1042, LOB_CM, "CREDIT", "TRADING", "SECURITIES_LENDING", "ACTIVE", "USD", 2_600_000, 600_000, 750_000),
    (77108, 1042, LOB_CM, "NON_CREDIT", "TRANSACTIONAL", "SETTLEMENT_SERVICES", "ACTIVE", "CAD", 1_800_000, 500_000, 300_000),
    (44018, 1042, LOB_CB, "CREDIT", "LENDING", "REVOLVING_CREDIT", "ACTIVE", "CAD", 18_600_000, 4_000_000, 9_700_000),
    (44019, 1042, LOB_CB, "CREDIT", "LENDING", "TERM_LOAN", "ACTIVE", "USD", 9_000_000, 0, 5_800_000),
    (44020, 1042, LOB_CB, "NON_CREDIT", "CONTINGENT", "LETTER_OF_CREDIT", "ACTIVE", "EUR", 2_200_000, 800_000, 650_000),
    (22031, 1042, LOB_WM, "CREDIT", "LENDING", "REVOLVING_CREDIT", "ACTIVE", "USD", 3_000_000, 1_000_000, 1_400_000),
    (22032, 1042, LOB_WM, "NON_CREDIT", "TRANSACTIONAL", "CUSTODY_SETTLEMENT", "ACTIVE", "GBP", 1_100_000, 300_000, 250_000),
    (44102, 1042, LOB_CB, "CREDIT", "LENDING", "TERM_LOAN", "CLOSED", "CAD", 0, 0, 0),
    (77211, 2088, LOB_CM, "CREDIT", "TRADING", "FOREIGN_EXCHANGE", "ACTIVE", "USD", 3_250_000, 750_000, 1_400_000),
    (55021, 2088, LOB_CB, "CREDIT", "LENDING", "TERM_LOAN", "ACTIVE", "CAD", 6_750_000, 1_250_000, 4_100_000),
    (88307, 3091, LOB_CM, "CREDIT", "TRADING", "DERIVATIVES", "ACTIVE", "EUR", 8_100_000, 2_000_000, 3_800_000),
    (66015, 4105, LOB_CB, "CREDIT", "LENDING", "REVOLVING_CREDIT", "ACTIVE", "CAD", 1_900_000, 600_000, 800_000),
    (66016, 4105, LOB_CB, "NON_CREDIT", "CONTINGENT", "PERFORMANCE_GUARANTEE", "ACTIVE", "USD", 750_000, 350_000, 120_000),
    (99001, 5117, LOB_CM, "CREDIT", "TRADING", "REPOS", "ACTIVE", "GBP", 12_000_000, 3_000_000, 7_100_000),
    (99002, 5117, LOB_CM, "CREDIT", "TRADING", "DERIVATIVES", "ACTIVE", "USD", 6_500_000, 2_500_000, 1_800_000),
    (99003, 5117, LOB_CM, "CREDIT", "TRADING", "FOREIGN_EXCHANGE", "ACTIVE", "EUR", 1_800_000, 800_000, 500_000),
    (99004, 5117, LOB_CM, "CREDIT", "TRADING", "SECURITIES_LENDING", "ACTIVE", "CAD", 2_000_000, 700_000, 1_000_000),
    (77015, 5117, LOB_CB, "CREDIT", "LENDING", "TERM_LOAN", "ACTIVE", "CAD", 22_000_000, 0, 16_500_000),
    (77016, 5117, LOB_CB, "CREDIT", "LENDING", "REVOLVING_CREDIT", "ACTIVE", "USD", 8_000_000, 2_000_000, 4_200_000),
    (77017, 5117, LOB_CB, "NON_CREDIT", "CONTINGENT", "LETTER_OF_CREDIT", "ACTIVE", "EUR", 3_500_000, 1_000_000, 1_250_000),
    (33011, 5117, LOB_WM, "CREDIT", "LENDING", "REVOLVING_CREDIT", "ACTIVE", "GBP", 1_200_000, 300_000, 600_000),
]

FACILITY_DATES = {
    77104: ("2024-01-15", "2028-01-31"),
    77105: ("2024-02-01", "2026-08-31"),
    77106: ("2023-06-01", "2027-06-30"),
    77107: ("2025-03-01", "2027-03-31"),
    77108: ("2025-07-01", "2028-07-31"),
    44018: ("2020-07-01", "2027-07-31"),
    44019: ("2021-01-01", "2031-01-31"),
    44020: ("2024-01-01", "2027-01-31"),
    22031: ("2024-03-01", "2027-03-31"),
    22032: ("2025-01-01", "2026-10-31"),
    44102: (None, "2025-07-31"),
    77211: ("2025-05-01", "2027-05-31"),
    55021: ("2020-10-01", "2027-10-31"),
    88307: ("2024-04-01", "2026-04-30"),
    66015: ("2023-01-01", "2028-01-31"),
    66016: ("2024-08-01", "2027-08-31"),
    99001: ("2024-01-01", "2028-01-31"),
    99002: ("2024-01-01", "2027-01-31"),
    99003: ("2024-01-01", "2026-06-30"),
    99004: ("2023-07-01", "2027-07-31"),
    77015: ("2019-01-01", "2029-01-31"),
    77016: ("2021-05-01", "2027-05-31"),
    77017: ("2022-04-01", "2026-10-31"),
    33011: ("2025-03-01", "2028-03-31"),
}

FACILITY_PURPOSES = {
    "DERIVATIVES": "for hedging interest-rate and currency exposures",
    "REPOS": "for secured short-term funding against eligible securities",
    "FOREIGN_EXCHANGE": "for managing cross-border cash flows",
    "SECURITIES_LENDING": "for securities borrowing and lending activity",
    "TERM_LOAN": "for longer-term business investment",
    "REVOLVING_CREDIT": "for flexible working-capital needs",
    "SETTLEMENT_SERVICES": "for settlement obligations",
    "CUSTODY_SETTLEMENT": "for custody-related cash movements",
    "LETTER_OF_CREDIT": "to secure supplier and trade obligations",
    "PERFORMANCE_GUARANTEE": "to support contractual performance commitments",
}


def facility_records() -> list[tuple]:
    added_borrowers, added_facilities, added_dates, _ = mock_portfolio_records()
    borrower_names = {row[0]: row[1] for row in [*BORROWERS, *added_borrowers]}
    facility_type_names = {row[0]: row[2] for row in FACILITY_TYPES}
    records = []
    all_dates = {**FACILITY_DATES, **added_dates}
    for row in [*FACILITIES, *added_facilities]:
        facility_id, borrower_id, lob_code, class_code, subclass_code, type_code, status_code, currency_code, committed, uncommitted, drawn = row
        start_date, maturity_date = all_dates[facility_id]
        start_text = start_date or "not applicable"
        description = (
            f"{borrower_names[borrower_id]} {facility_type_names[type_code]} facility "
            f"{FACILITY_PURPOSES[type_code]}. Committed {currency_code} {committed:,.0f}; "
            f"uncommitted {currency_code} {uncommitted:,.0f}; drawn {currency_code} {drawn:,.0f}. "
            f"Commitment starts {start_text}; matures {maturity_date}."
        )
        records.append((
            facility_id, borrower_id, lob_code, class_code, subclass_code, type_code,
            status_code, currency_code, description, start_date, maturity_date,
            committed, uncommitted, drawn,
        ))
    return records

ACCOUNT_TEAMS = [
    (1042, LOB_CM, "RM", "Sofia Patel"),
    (1042, LOB_CM, "CREDIT_MANAGER", "Daniel Kim"),
    (1042, LOB_CB, "RM", "John Smith"),
    (1042, LOB_CB, "CREDIT_MANAGER", "Ava Johnson"),
    (1042, LOB_WM, "RM", "Jane Doe"),
    (2088, LOB_CM, "RM", "Liam Chen"),
    (2088, LOB_CB, "RM", "Mia Thompson"),
    (3091, LOB_CM, "RM", "Noah Williams"),
    (4105, LOB_CB, "RM", "Olivia Martin"),
    (5117, LOB_CM, "RM", "Ethan Wilson"),
    (5117, LOB_CB, "RM", "Amelia Brown"),
    (5117, LOB_CB, "CREDIT_MANAGER", "Lucas Garcia"),
    (5117, LOB_WM, "RM", "Isabella Davis"),
]


def create_database(path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    with sqlite3.connect(path) as db:
        db.executescript(SCHEMA)
        install_integrity_guards(db)
        db.executemany("INSERT INTO line_of_business_domain VALUES (?, ?)", LINE_OF_BUSINESS)
        db.executemany("INSERT INTO sector_domain VALUES (?, ?)", SECTORS)
        db.executemany("INSERT INTO account_team_role_domain VALUES (?, ?)", ACCOUNT_TEAM_ROLES)
        db.executemany("INSERT INTO exposure_class_domain VALUES (?, ?)", EXPOSURE_CLASSES)
        db.executemany("INSERT INTO exposure_subclass_domain VALUES (?, ?, ?)", EXPOSURE_SUBCLASSES)
        db.executemany("INSERT INTO facility_type_domain VALUES (?, ?, ?)", FACILITY_TYPES)
        db.executemany("INSERT INTO facility_status_domain VALUES (?, ?)", FACILITY_STATUSES)
        db.executemany("INSERT INTO currency_domain VALUES (?, ?)", CURRENCIES)
        added_borrowers, added_facilities, _, added_teams = mock_portfolio_records()
        db.executemany("INSERT INTO borrowers VALUES (?, ?, ?)", [*BORROWERS, *added_borrowers])
        db.executemany("INSERT INTO users VALUES (?, ?, ?)", [
            ("superuser", LOB_ALL, 1),
            ("capital_markets", LOB_CM, 0),
            ("commercial_banking", LOB_CB, 0),
            ("wealth_management", LOB_WM, 0),
        ])
        db.executemany("INSERT INTO user_lob_access VALUES (?, ?)", [
            ("capital_markets", LOB_CM),
            ("commercial_banking", LOB_CB),
            ("wealth_management", LOB_WM),
        ])
        db.executemany("INSERT INTO fx_rates VALUES (?, ?, ?)", FX_RATES)
        db.executemany("INSERT INTO facilities VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", facility_records())
        db.executemany("INSERT INTO account_teams VALUES (?, ?, ?, ?)", [*ACCOUNT_TEAMS, *added_teams])


if __name__ == "__main__":
    create_database(Path(__file__).parent / "instance" / "exposure.db")
    print("Created synthetic exposure database.")
