# Gram Mitra — Karnataka Business AI

## Run locally

1. Install **Python 3.10+**.
2. Open a terminal in this folder (the folder containing `app.py`).
3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Start the website:

```bash
python app.py
```

5. Open **http://127.0.0.1:5000** in your browser.

The SQLite database is created automatically on first run. The distributed ZIP intentionally does not contain existing user accounts.

## Vercel deployment

This project is configured for Vercel Python serverless deployment through `vercel.json`. Set a strong `SECRET_KEY` in the Vercel Project Settings → Environment Variables.

Important: SQLite under `/tmp` is temporary on Vercel, so user accounts are not guaranteed to persist across serverless instances. Use a persistent database such as Postgres/Supabase/Neon for production.

## Main features

- Kannada/English user interface
- Business opportunity analysis
- Local business/competition mapping with OpenStreetMap services
- Loan Assistance with scheme routing, documents, benefits and readiness
- 12-month business performance analysis
- AI Copilot
- Downloadable English/Kannada business-analysis PDF reports

## Important

- Financing, scheme eligibility, interest rates and repayment figures are advisory estimates. Verify current official rules with the relevant government department or lender before applying.
- OpenStreetMap/Nominatim/Overpass availability and rural coverage are not guaranteed.
