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

# ------------------------------------------------------------
# ------------------------------------------------------------

# Project paths:
# - ROOT: base path of the project, used to build paths to data files.
ROOT = Path(__file__).parent

# - Company A's reference Excel file
# The app loads recipes, materials, and electricity factors from this file.
COMPANY_A_FILE = ROOT / "data" / "Company_A_database.xlsx"

# - Company B's partner recipes
DB_FILE = ROOT / "partner_recipes.db"


# Flask application object creation.
# The route decorators below attach HTTP endpoints to this object.
app = Flask(__name__)


# ------------------------------------------------------------
# 1. Read Excel files
# ------------------------------------------------------------

# This function extracts data from the "BW database" sheet in the Excel file.
# Excel files use a simplified BrightWay-style layout.
# Assumption: Each activity starts with a row whose first cell is "Activity".
# Its exchanges are listed below that activity header.
def read_bw_database(excel_file):
    """Read the BW database sheet and map each activity name to a list of 
    input exchanges in a dictionary: {activity: [(input, amount, ...)]}."""

    # header=None because the "BW database" sheet is not a normal table.
    df = pd.read_excel(excel_file, sheet_name="BW database", header=None)

    activities = {}

    # Scan every row looking for the start of an activity block.
    for row in range(len(df)):
        if df.iloc[row, 0] == "Activity":
            # Activity name is found in the second column of that row.
            activity = df.iloc[row, 1]

            # Collect all usable input exchanges for this activity.
            # Each exchange becomes a tuple: (input_name, amount).
            exchanges = []

            # The exchange table starts 8 rows after the "Activity" marker row.
            exchange_row = row + 8

            # Read exchange rows until the first blank row.
            while exchange_row < len(df) and pd.notna(df.iloc[exchange_row, 0]):
                # Column 4 contains the exchange type, for example:
                # - "production" for the activity's own output
                # - "technosphere" for required inputs
                exchange_type = df.iloc[exchange_row, 4]

                # We only need inputs. Production rows are skipped.
                # The climate impact is calculated from inputs consumed by
                # the activity, not from the activity's output row.
                if exchange_type == "technosphere":
                    # Column 0 is the name of the input material, electricity
                    # source, or another intermediate activity.
                    input_name = df.iloc[exchange_row, 0]

                    # Column 1 is the amount of that input required per unit
                    # of the current activity's product.
                    amount = float(df.iloc[exchange_row, 1])

                    # Store the exchange.
                    exchanges.append((input_name, amount))

                # Move to the next exchange.
                exchange_row += 1

            # Save the completed list of exchanges under the activity name.
            activities[activity] = exchanges

    # The returned structure is used by funtion impact() to resolve Company A activities.
    return activities


# This helper reads the factor sheets where each row maps a name to
# an impact factor. It is used for both "Materials" and "Electricity" sheets.
def read_factors(excel_file, sheet_name):
    """Read Materials or Electricity and return: {name: factor}."""

    # These sheets are regular tables with a header
    # The first column is the item name; the second column is its factor.
    df = pd.read_excel(excel_file, sheet_name=sheet_name)

    # Convert the two columns into a dictionary.
    return dict(zip(df.iloc[:, 0], df.iloc[:, 1]))


# Excel files reading execution
# The data is loaded once when the app starts and stored in global variables.
# - company_a_activities: recipes/intermediate activities from the BW sheet
# - material_factors: leaf impact factors in kg CO2 / kg
# - electricity_factors: leaf impact factors in kg CO2 / kWh
company_a_activities = read_bw_database(COMPANY_A_FILE)
material_factors = read_factors(COMPANY_A_FILE, "Materials")
electricity_factors = read_factors(COMPANY_A_FILE, "Electricity")


# ------------------------------------------------------------
# 2. SQLite database for partner uploads
# ------------------------------------------------------------

# Partner (Company B) recipes are stored in SQLite.
# This is a separation mechanism between base data and uploaded partner data.
def start_database():
    # Open a connection to the SQLite database file.
    # If the file does not exist yet, sqlite3 will create it automatically.
    db = sqlite3.connect(DB_FILE)

    # Table stores one row per partner exchange.
    # - partner_id: identifies which partner owns the recipe.
    # - activity: is the partner activity name.
    # - input: is the consumed material/activity/electricity source.
    # - amount: is how much of that input is consumed.
    db.execute("""
        CREATE TABLE IF NOT EXISTS partner_exchanges (
            partner_id TEXT,
            activity TEXT,
            input TEXT,
            amount REAL
        )
    """)

    # Commit the table creation operation, then close the connection.
    db.commit()
    db.close()


# Ensure the partner database table exists before the API starts handling requests.
start_database()


# Fetch all input exchanges for one partner-owned activity.
# This function only looks in the partner database (Company B); Company A data is handled
# separately in impact().
def get_partner_exchanges(partner_id, activity):
    # Open a short-lived database connection for this lookup.
    db = sqlite3.connect(DB_FILE)

    # rows is a list of (input, amount) tuples.
    rows = db.execute(
        "SELECT input, amount FROM partner_exchanges WHERE partner_id=? AND activity=?",
        (partner_id, activity),
    ).fetchall()

    # Close the connection.
    db.close()

    return rows


# ------------------------------------------------------------
# 3. Recursive impact calculation
# ------------------------------------------------------------

# This is the central calculation function used by the app /impact endpoint.
# It can resolve three kinds of names:
# 1. Company B partner activities stored in SQLite.
# 2. Company A activities loaded from the BW database sheet.
# 3. Leaf factors from the Materials/Electricity sheets.
def impact(name, partner_id=None):
    """Return kg CO2 for a material, electricity source, or activity."""

    # First check partner data, but only when partner_id is provided.
    if partner_id:
        rows = get_partner_exchanges(partner_id, name)
        if rows:
            # If the requested name is a partner activity, recursively calculate
            # each input's impact and multiply it by the input amount.
            # Example: activity impact = sum(amount_i * impact(input_i)).
            return sum(amount * impact(input_name, partner_id) for input_name, amount in rows)

    # Then check Company A activities.
    # This lets partner recipes reference Company A activities without copying
    # or redefining them in the partner upload.
    if name in company_a_activities:
        # Each input is recursively resolved until the calculation reaches
        # a material or electricity leaf factor.
        return sum(amount * impact(input_name, partner_id) for input_name, amount in company_a_activities[name])

    # Finally, the name is expected to be a leaf factor.
    if name in material_factors:
        return float(material_factors[name])

    # If the name was not a partner activity, Company A activity, or material,
    # the code assumes it is an electricity source and looks it up here.
    elif name in electricity_factors:
        return float(electricity_factors[name])

    raise KeyError(f"Unknown material, electricity source, or activity: {name}")


# ------------------------------------------------------------
# 4. Flask endpoints
# ------------------------------------------------------------

# Basic health/home endpoint.
# Checking that the Flask server is running.
@app.get("/")
def home():
    return {"message": "Wafer impact API is running with Flask"}


# Impact endpoint.
@app.get("/impact/<path:activity_name>")
def get_impact(activity_name):
    # Optional query string parameter for partner, e.g.:
    # /impact/Baked Chocolate Wafers?partner_id=company_b
    # If omitted, only Company A data and leaf factors are considered.
    partner_id = request.args.get("partner_id")

    # Response includes requested activity, partner, and calculated impact value.
    return {
        "activity": activity_name,
        "partner_id": partner_id,
        "impact_kg_co2": impact(activity_name, partner_id),
    }


# Partner recipe upload endpoint.
# The request is expected to be multipart/form-data with:
# - partner_id: a form field identifying the partner
# - file: uploaded Excel file in the same BW-style format
@app.post("/upload-recipe")
def upload_recipe():
    # Read partner_id directly from the form. In this minimal version, Flask will
    # raise an error automatically if the field is missing.
    partner_id = request.form["partner_id"]

    # Read the uploaded file object with pandas.
    file = request.files["file"]

    # Parse partner activities using the same BW database reader as Company A.
    partner_activities = read_bw_database(file)

    # Open the partner database so the uploaded exchanges can be persisted.
    db = sqlite3.connect(DB_FILE)

    # Replace all existing data for this partner_id before inserting the new upload.
    db.execute("DELETE FROM partner_exchanges WHERE partner_id=?", (partner_id,))

    # Store every exchange from every uploaded partner activity.
    for activity, exchanges in partner_activities.items():
        for input_name, amount in exchanges:
            # Each row is one edge in the recipe graph.
            db.execute(
                "INSERT INTO partner_exchanges VALUES (?, ?, ?, ?)",
                (partner_id, activity, input_name, amount),
            )

    # Commit the operations and close the connection.
    db.commit()
    db.close()

    # Return the list of activity names that were loaded from the partner file.
    # The partner can then call /impact/<activity>?partner_id=<partner_id>.
    return {
        "partner_id": partner_id,
        "activities_loaded": list(partner_activities.keys()),
    }


# Run with: python app.py
if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000)
