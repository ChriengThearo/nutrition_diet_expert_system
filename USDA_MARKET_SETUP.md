# Local USDA Food Market

The Food Market reads its data from the seven `usda_market_*` tables in the
application database. The importer only upserts those tables; it does not
modify any existing application table.

Set the source database URL only in your local environment, then run:

```powershell
$env:FLASK_APP = "run.py"
$env:USDA_SOURCE_DATABASE_URL = "postgresql://USER:PASSWORD@HOST:PORT/DATABASE"
.\.venv\Scripts\flask.exe db upgrade
.\.venv\Scripts\python.exe utils\import_usda_market.py
```

The importer checks the source and target row counts before it completes. The
expected target counts are 12 categories, 5,076 foods, 244 nutrients, 422,744
food-nutrient rows, 5,076 catalog rows, and 12 catalog-stat rows.

The scanner downloads the public CLIP model the first time it is used. Its
text index is stored under `instance/usda_scanner/`, which is ignored by Git.
Photos are processed in memory and are never written to disk.
