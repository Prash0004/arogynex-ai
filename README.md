# GramHealth AI (NTCC research prototype)

Educational prototype: synthetic data only. Not a medical device; no diagnosis.

## Run locally
```
pip install -r requirements.txt
uvicorn app:app --reload
```
Open http://127.0.0.1:8000 (API docs at /docs). On first start the app trains the models on synthetic data (about a minute at most).

## What is implemented
- Screening wizard (4 steps) with server-side validation, consent check, missing values kept as missing.
- Assessment page: synthetic-model score, top features, escalation examples, "not yet validated" banner.
- Nutrition rule engine: diet, allergies, food groups available, daily budget, referral for conditions needing a clinician. Nutrient values say "Nutritional data unavailable" until you add verified data (e.g. IFCT 2017). Prices are illustrative.
- Research lab: Logistic Regression, Decision Tree, Random Forest, metrics, permutation importance, data-quality summary, group-wise train/test split.
- Dashboard with demo seed/reset and small-group suppression (min 3).

## Not yet implemented (be honest in your viva)
Login/roles, PostgreSQL, SHAP, neural network, Hindi, follow-ups, chat assistant, automated tests. See "Next steps".

## Deploy (Render, free tier)
1. Push this folder to a GitHub repo (no real health data).
2. Render > New > Web Service > connect repo. Build: `pip install -r requirements.txt`. Start: `uvicorn app:app --host 0.0.0.0 --port $PORT` (render.yaml included).
3. Note: free-tier disk is temporary, so the SQLite demo data resets on redeploy. Use Neon/Supabase PostgreSQL for persistence later.

## Next steps
Auth + roles, tests, SHAP, MLP, then replace synthetic data with a licensed public dataset (record source and license).
