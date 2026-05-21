# DESIGN

This project implements a Flask REST API for calculating the climate-change impact of wafer-related recipes. The design intentionally keeps the application simple: Company A's reference data is loaded from Excel at startup, while uploaded partner recipes are stored separately in a local SQLite database.

## Data model

Company A data is treated as the shared reference database. Its Excel file contains activities, material impact factors, and electricity impact factors. At startup, the application reads these sheets and converts them into Python dictionaries for fast lookup during calculations.

Partner data is handled separately. When a partner uploads a recipe file, the app stores only that partner's activities and exchanges in SQLite, tagged with a `partner_id`. This keeps Company B's proprietary recipe data separate from Company A's base data and allows different partners to use the same API without mixing their recipes.

## Impact calculation

The core calculation is recursive. When calculating an activity, the app resolves each exchange/input and multiplies the input amount by the input's own impact. If the input is another activity, the function resolves that activity first. If the input is a material or electricity source, the function returns its direct impact factor.

The lookup order is intentional:

1. Partner activity, when `partner_id` is provided.
2. Company A activity.
3. Material factor.
4. Electricity factor.

This allows partner recipes to reuse Company A activities while still giving partner-specific data priority when relevant.

## Technology choices

Flask: the API surface is small and Flask is simpler than other fraameworks. 
Pandas/OpenPyXL: because the source data is provided as Excel files. 
SQLite: for persistence because it requires no external database server and is sufficient for a lightweight prototype. 
Pytest: for simple API-level tests through Flask's test client.