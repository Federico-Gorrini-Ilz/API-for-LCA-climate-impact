from pathlib import Path

# app: The Flask app. Pytest uses it through Flask's test client, so the tests can
# call the API endpoints without starting a real web server.
#
# DB_FILE: The filename/path of the SQLite database used for partner recipe uploads.

from app import app, DB_FILE, start_database


def test_company_a_impact():
    # Flask's test client allows HTTP requests directly against the app.
    client = app.test_client()

    # Request the impact for a known activity from Company A's base Excel file.
    result = client.get("/impact/Baked%20Biscuit%20Wafers").json

    # Confirmation that the endpoint returns a numeric impact greater than zero.
    assert result["impact_kg_co2"] > 0


def test_upload_and_partner_impact():
    # In the upload test, any existing file is deleted so each test run starts 
    # from a clean state.
    if Path(DB_FILE).exists():
        Path(DB_FILE).unlink()

    # Recreate the empty SQLite database structure after deleting the file.
    start_database()

    # Flask's test client allows HTTP requests directly against the app.
    client = app.test_client()

    # Open Company B's Excel request file.
    with open("data/Company_B_request.xlsx", "rb") as file:
        upload = client.post(
            "/upload-recipe",
            data={"partner_id": "company_b", "file": file},
            content_type="multipart/form-data",
        )
    
    # A 200 status code means the upload endpoint accepted and stored the file.
    assert upload.status_code == 200

    # Query the impact endpoint for Company B's proprietary recipe.
    result = client.get("/impact/Baked%20Chocolate%20Wafers?partner_id=company_b").json

    # Confirmation that the endpoint returns a numeric impact greater than zero.
    assert result["impact_kg_co2"] > 0
