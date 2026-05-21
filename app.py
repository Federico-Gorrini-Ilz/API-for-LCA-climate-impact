# ============================================================
# Project: Climate Impact Calculation
# Description: Python REST API (Flask) for wafer impact calculation.
# Federico Gorrini @ 2026-05-21
# ============================================================
# Note: The code assumes that the Excel files follow the provided format.

# Libraries:
from pathlib import Path
import sqlite3
import pandas as pd
from flask import Flask, request

# Project paths
ROOT = Path(__file__).parent
COMPANY_A_FILE = ROOT / "data" / "Company_A_database.xlsx"
DB_FILE = ROOT / "partner_recipes.db"

app = Flask(__name__)


# ------------------------------------------------------------
# 1. Read Excel files
# ------------------------------------------------------------

def read_bw_database(excel_file):
    """Read the BW database sheet and return: {activity: [(input, amount), ...]}."""
    df = pd.read_excel(excel_file, sheet_name="BW database", header=None)
    activities = {}

    for row in range(len(df)):
        if df.iloc[row, 0] == "Activity":
            activity = df.iloc[row, 1]
            exchanges = []
            exchange_row = row + 8

            # Read exchange rows until the first blank row.
            while exchange_row < len(df) and pd.notna(df.iloc[exchange_row, 0]):
                exchange_type = df.iloc[exchange_row, 4]

                # We only need inputs. Production rows are skipped.
                if exchange_type == "technosphere":
                    input_name = df.iloc[exchange_row, 0]
                    amount = float(df.iloc[exchange_row, 1])
                    exchanges.append((input_name, amount))

                exchange_row += 1

            activities[activity] = exchanges

    return activities


def read_factors(excel_file, sheet_name):
    """Read Materials or Electricity and return: {name: factor}."""
    df = pd.read_excel(excel_file, sheet_name=sheet_name)
    return dict(zip(df.iloc[:, 0], df.iloc[:, 1]))


# Company A data is loaded once when the app starts.
company_a_activities = read_bw_database(COMPANY_A_FILE)
material_factors = read_factors(COMPANY_A_FILE, "Materials")
electricity_factors = read_factors(COMPANY_A_FILE, "Electricity")


# ------------------------------------------------------------
# 2. Small SQLite database for partner uploads
# ------------------------------------------------------------

def start_database():
    db = sqlite3.connect(DB_FILE)
    db.execute("""
        CREATE TABLE IF NOT EXISTS partner_exchanges (
            partner_id TEXT,
            activity TEXT,
            input TEXT,
            amount REAL
        )
    """)
    db.commit()
    db.close()


start_database()


def get_partner_exchanges(partner_id, activity):
    db = sqlite3.connect(DB_FILE)
    rows = db.execute(
        "SELECT input, amount FROM partner_exchanges WHERE partner_id=? AND activity=?",
        (partner_id, activity),
    ).fetchall()
    db.close()
    return rows


# ------------------------------------------------------------
# 3. Recursive impact calculation
# ------------------------------------------------------------

def impact(name, partner_id=None):
    """Return kg CO2 for a material, electricity source, or activity."""

    # First check partner data, but only when partner_id is provided.
    if partner_id:
        rows = get_partner_exchanges(partner_id, name)
        if rows:
            return sum(amount * impact(input_name, partner_id) for input_name, amount in rows)

    # Then check Company A activities.
    if name in company_a_activities:
        return sum(amount * impact(input_name, partner_id) for input_name, amount in company_a_activities[name])

    # Finally, the name is expected to be a leaf factor.
    if name in material_factors:
        return float(material_factors[name])

    elif name in electricity_factors:
        return float(electricity_factors[name])

    raise KeyError(f"Unknown material, electricity source, or activity: {name}")


# ------------------------------------------------------------
# 4. Flask endpoints
# ------------------------------------------------------------

@app.get("/")
def home():
    return {"message": "Wafer impact API is running with Flask"}


@app.get("/impact/<path:activity_name>")
def get_impact(activity_name):
    partner_id = request.args.get("partner_id")

    return {
        "activity": activity_name,
        "partner_id": partner_id,
        "impact_kg_co2": impact(activity_name, partner_id),
    }


@app.post("/upload-recipe")
def upload_recipe():
    partner_id = request.form["partner_id"]
    file = request.files["file"]
    partner_activities = read_bw_database(file)

    db = sqlite3.connect(DB_FILE)
    db.execute("DELETE FROM partner_exchanges WHERE partner_id=?", (partner_id,))

    for activity, exchanges in partner_activities.items():
        for input_name, amount in exchanges:
            db.execute(
                "INSERT INTO partner_exchanges VALUES (?, ?, ?, ?)",
                (partner_id, activity, input_name, amount),
            )

    db.commit()
    db.close()

    return {
        "partner_id": partner_id,
        "activities_loaded": list(partner_activities.keys()),
    }


# Run with: python app.py
if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000)
