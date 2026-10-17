"""GramHealth AI - FastAPI backend (demo mode, SQLite). Run: uvicorn app:app --reload"""
import os, sqlite3, json, uuid, datetime
from typing import Optional, List
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
import ml, nutrition

HERE = os.path.dirname(__file__)
DB = os.path.join(HERE, "gramhealth.db")
app = FastAPI(title="GramHealth AI (research prototype)", version="0.1")


def db():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row; return c


def init():
    c = db()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS screenings(
      id TEXT PRIMARY KEY, participant_code TEXT, created_at TEXT, consent INTEGER,
      age INTEGER, height_cm REAL, weight_kg REAL, bmi REAL, waist_cm REAL,
      systolic REAL, diastolic REAL, glucose_mgdl REAL, glucose_type TEXT,
      activity_level INTEGER, fruit_veg_per_day REAL, salt_score INTEGER,
      vegetarian INTEGER, allergies TEXT, community_code TEXT,
      urgent_symptoms INTEGER, completeness REAL, probability REAL, model_version TEXT);
    """)
    c.commit(); c.close()


init()
if ml.load_report() is None:
    ml.train_all()


class Screening(BaseModel):
    consent: bool
    adult_confirmed: bool
    age: int = Field(ge=18, le=110)
    height_cm: float = Field(ge=100, le=230)
    weight_kg: float = Field(ge=25, le=250)
    waist_cm: Optional[float] = Field(None, ge=40, le=180)
    systolic: Optional[float] = Field(None, ge=60, le=260)
    diastolic: Optional[float] = Field(None, ge=30, le=160)
    glucose_mgdl: Optional[float] = Field(None, ge=30, le=600)
    glucose_type: Optional[str] = None
    activity_level: int = Field(ge=0, le=3)
    fruit_veg_per_day: Optional[float] = Field(None, ge=0, le=15)
    salt_score: Optional[int] = Field(None, ge=0, le=3)
    vegetarian: bool = True
    allergies: List[str] = []
    community_code: str = "VIL-A"
    urgent_symptoms: bool = False


@app.post("/api/screenings")
def create_screening(s: Screening):
    if not (s.consent and s.adult_confirmed):
        raise HTTPException(400, "Consent and adult confirmation are required.")
    if s.systolic and s.diastolic and s.diastolic >= s.systolic:
        raise HTTPException(422, "Diastolic must be lower than systolic.")
    if s.glucose_mgdl is not None and not s.glucose_type:
        raise HTTPException(422, "Glucose measurement type (fasting/random) is required with a value.")
    bmi = round(s.weight_kg / (s.height_cm / 100) ** 2, 1)
    vals = dict(age=s.age, bmi=bmi, waist_cm=s.waist_cm, glucose_mgdl=s.glucose_mgdl,
                activity_level=s.activity_level, fruit_veg_per_day=s.fruit_veg_per_day, salt_score=s.salt_score)
    completeness = round(sum(v is not None for v in vals.values()) / len(vals), 2)
    prob = ml.predict(vals)
    rep = ml.load_report()
    sid = "SCR-" + uuid.uuid4().hex[:8].upper()
    code = "P-" + uuid.uuid4().hex[:6].upper()
    c = db()
    c.execute("INSERT INTO screenings VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
              (sid, code, datetime.datetime.utcnow().isoformat(), 1, s.age, s.height_cm, s.weight_kg, bmi,
               s.waist_cm, s.systolic, s.diastolic, s.glucose_mgdl, s.glucose_type, s.activity_level,
               s.fruit_veg_per_day, s.salt_score, int(s.vegetarian), json.dumps(s.allergies), s.community_code,
               int(s.urgent_symptoms), completeness, prob, rep["version"] if rep else None))
    c.commit(); c.close()
    return get_screening(sid)


def row_to_dict(r):
    d = dict(r); d["allergies"] = json.loads(d["allergies"] or "[]"); return d


@app.get("/api/screenings")
def list_screenings(limit: int = 50, offset: int = 0):
    c = db()
    rows = c.execute("SELECT id,participant_code,created_at,age,bmi,completeness,probability,community_code "
                     "FROM screenings ORDER BY created_at DESC LIMIT ? OFFSET ?", (limit, offset)).fetchall()
    total = c.execute("SELECT COUNT(*) FROM screenings").fetchone()[0]
    c.close()
    return {"total": total, "items": [dict(r) for r in rows]}


@app.get("/api/screenings/{sid}")
def get_screening(sid: str):
    c = db(); r = c.execute("SELECT * FROM screenings WHERE id=?", (sid,)).fetchone(); c.close()
    if not r: raise HTTPException(404, "Not found")
    return assessment_view(row_to_dict(r))


def assessment_view(d):
    rep = ml.load_report()
    escalate = []
    if d["urgent_symptoms"]:
        escalate.append("Urgent symptoms reported: seek prompt professional or emergency assessment now.")
    if d["systolic"] and d["systolic"] >= 180 or d["diastolic"] and d["diastolic"] >= 120:
        escalate.append("Very high blood pressure reading: seek prompt professional assessment (example protocol, needs clinician approval).")
    if d["glucose_mgdl"] and (d["glucose_mgdl"] >= 300 or d["glucose_mgdl"] < 54):
        escalate.append("Extreme glucose reading: seek prompt professional assessment (example protocol, needs clinician approval).")
    best = rep["results"][rep["best_model"]] if rep else None
    top = sorted(best["feature_importance"].items(), key=lambda x: -x[1])[:4] if best else []
    missing = [k for k in ["waist_cm", "glucose_mgdl", "fruit_veg_per_day", "salt_score"] if d.get(k) is None]
    return {
        "screening": d, "escalation": escalate, "missing_inputs": missing,
        "model": {"name": rep["best_model"], "version": rep["version"], "trained_on": rep["dataset"],
                  "validated": False,
                  "banner": "Research model not yet validated — illustrative screening workflow only.",
                  "probability_synthetic": d["probability"],
                  "top_global_features": [{"feature": k, "permutation_importance_auc_drop": round(v, 4)} for k, v in top],
                  "note": "Trained on SYNTHETIC data. Feature importance is association in the model, not causation. This is NOT a diagnosis."} if rep else None,
        "next_steps": ["Share this screening with a qualified health worker/doctor for review.",
                       "Re-measure BP/glucose under standard conditions if values were missing or unusual."],
    }


class NutReq(BaseModel):
    vegetarian: bool = True
    allergies: List[str] = []
    available_groups: Optional[List[str]] = None
    budget_per_day: float = Field(60, ge=0, le=1000)
    excluded: List[str] = []
    conditions: List[str] = []


@app.post("/api/nutrition/recommendations")
def nut(r: NutReq):
    return nutrition.recommend(r.vegetarian, r.allergies, r.available_groups, r.budget_per_day, r.excluded, r.conditions)


@app.get("/api/research/report")
def report():
    return ml.load_report()


@app.post("/api/research/retrain")
def retrain():
    return ml.train_all()


@app.get("/api/analytics/overview")
def overview():
    c = db()
    total = c.execute("SELECT COUNT(*) FROM screenings").fetchone()[0]
    by_comm = c.execute("SELECT community_code, COUNT(*) n, AVG(age) a FROM screenings GROUP BY community_code").fetchall()
    c.close()
    MIN = 3  # small-group suppression
    groups = [{"community": r["community_code"], "n": r["n"], "avg_age": round(r["a"], 1)} if r["n"] >= MIN
              else {"community": r["community_code"], "n": f"<{MIN}", "avg_age": None} for r in by_comm]
    return {"total_screenings": total, "groups": groups, "min_group_size": MIN,
            "note": "Counts come from the app database (demo entries). Groups below the minimum size are suppressed."}


@app.post("/api/demo/seed")
def seed(n: int = 20):
    """Insert synthetic demo screenings (clearly demo data)."""
    df = ml.generate_synthetic(n, seed=int(datetime.datetime.utcnow().timestamp()) % 10000)
    comms = ["VIL-A", "VIL-B", "VIL-C"]
    c = db()
    for i, r in df.iterrows():
        vals = {f: (None if r[f] != r[f] else float(r[f])) for f in ml.FEATURES}
        prob = ml.predict(vals)
        c.execute("INSERT INTO screenings VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  ("DEMO-" + uuid.uuid4().hex[:8].upper(), "DEMO-" + uuid.uuid4().hex[:5].upper(),
                   datetime.datetime.utcnow().isoformat(), 1, int(r.age), 160, None, float(r.bmi),
                   vals["waist_cm"], None, None, vals["glucose_mgdl"], None, int(r.activity_level),
                   float(r.fruit_veg_per_day), int(r.salt_score), 1, "[]", comms[i % 3], 0,
                   round(sum(v is not None for v in vals.values()) / 7, 2), prob, "demo"))
    c.commit(); c.close()
    return {"inserted": n, "label": "DEMO DATA (synthetic)"}


@app.delete("/api/demo/reset")
def reset():
    c = db(); c.execute("DELETE FROM screenings"); c.commit(); c.close()
    return {"ok": True}


STATIC_DIR = os.path.join(HERE, "static")
INDEX = os.path.join(STATIC_DIR, "index.html")
if not os.path.exists(INDEX):
    INDEX = os.path.join(HERE, "index.html")
if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index():
    return FileResponse(INDEX)
