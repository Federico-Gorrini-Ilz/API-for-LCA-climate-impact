# Wafer Impact API - Minimal Flask Version

Flask API wafer climate-impact calculation.

The project keeps almost everything in one file: `app.py`.

## Actions

1. Reads Company A's Excel database.
2. Calculates the climate impact of an activity recursively.
3. Uploads a partner Excel recipe.
4. Saves partner exchanges in SQLite.
5. Calculates partner recipe impact using both Company A and partner data.

## Project structure

```text
wafer_impact_api_flask_minimal/
├── app.py
├── test_app.py
├── requirements.txt
├── README.md
└── data/
    ├── Company_A_database.xlsx
    └── Company_B_request.xlsx
```

## Install

```powershell
pip install -r requirements.txt
```

## Run API (from PowerShell terminal 1)

```powershell
python app.py
```

The API runs at:

```text
http://127.0.0.1:8000
```

Keep this terminal open while testing.

## Test (from PowerShell terminal 2)

Go to the project folder:

```powershell
cd path\to\project_flask
```

### 1. Check that the app is running

```powershell
curl.exe http://127.0.0.1:8000/
```

### 2. Calculate Company A activity impact

```powershell
curl.exe "http://127.0.0.1:8000/impact/Baked%20Biscuit%20Wafers"
```

### 3. Upload Company B recipe

```powershell
curl.exe -X POST "http://127.0.0.1:8000/upload-recipe" `
  -F "partner_id=company_b" `
  -F "file=@data\Company_B_request.xlsx"
```

### 4. Calculate Company B activity impact

```powershell
curl.exe "http://127.0.0.1:8000/impact/Baked%20Chocolate%20Wafers?partner_id=company_b"
```

## Run tests

```powershell
pytest
```

## Assumption

This project assumes that the Excel files are correct and follow the provided format.
Because of that, the code intentionally avoids additional error handling.
