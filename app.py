import os, sqlite3, json, math, io, re, html, urllib.parse, urllib.request, secrets
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from xml.sax.saxutils import escape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Database path handling for Vercel read-only filesystem
if os.environ.get("VERCEL"):
    DB_PATH = "/tmp/gram_mitra.db"
    source_db = os.path.join(BASE_DIR, "gram_mitra.db")
    if not os.path.exists(DB_PATH) and os.path.exists(source_db):
        shutil.copy(source_db, DB_PATH)
else:
    DB_PATH = os.path.join(BASE_DIR, "gram_mitra.db")

# Helper function to get database connection
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# Safe Kannada font registration for PDF generation
KANNADA_FONT = os.path.join(BASE_DIR, "static", "fonts", "NotoSansKannada-Regular.ttf")
KANNADA_BOLD_FONT = os.path.join(BASE_DIR, "static", "fonts", "NotoSansKannada-Bold.ttf")

if os.path.exists(KANNADA_FONT) and os.path.exists(KANNADA_BOLD_FONT):
    try:
        pdfmetrics.registerFont(TTFont("NotoKannada", KANNADA_FONT))
        pdfmetrics.registerFont(TTFont("NotoKannadaBold", KANNADA_BOLD_FONT))
    except Exception as e:
        print("Font registration error:", e)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or "gram_mitra_fixed_secret_key_2026"
# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

class User(UserMixin):
    def __init__(self, id, name="Entrepreneur"):
        self.id = str(id)  # Fixed variable name reference
        self.name = name

@login_manager.user_loader
def load_user(user_id):
    if not user_id:
        return None
    conn = db()
    user_row = conn.execute("SELECT id, name FROM users WHERE id=?", (user_id,)).fetchone()
    conn.close()
    if user_row:
        return User(id=str(user_row["id"]), name=user_row["name"])
    return None

# Handles local Windows development path vs Vercel serverless /tmp directory
if os.environ.get("VERCEL"):
    app.config["DATABASE"] = os.path.join("/tmp", "gram_mitra.db")
else:
    app.config["DATABASE"] = os.path.join(BASE_DIR, "gram_mitra.db")

def db():
    conn = sqlite3.connect(app.config["DATABASE"])
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = db()
    cursor = conn.cursor()
    # Create table for saving business analysis queries
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS farmer_queries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            land_area REAL NOT NULL,
            crop_type TEXT NOT NULL,
            location TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

with app.app_context():
    init_db()

def load_json(filename):
    # Try loading from the data subfolder first
    data_path = os.path.join(BASE_DIR, "data", filename)
    if os.path.exists(data_path):
        with open(data_path, "r", encoding="utf-8") as f:
            return json.load(f)
            
    # Fallback to the root directory
    root_path = os.path.join(BASE_DIR, filename)
    with open(root_path, "r", encoding="utf-8") as f:
        return json.load(f)

@app.get("/health")
def health():
    return jsonify({"status": "ok", "service": "Gram Mitra"})
@app.route("/")
def index():
    return render_template("index.html", user=current_user)

@app.route("/signup", methods=["GET", "POST"])
def signup():
    # Send already authenticated users straight to dashboard
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        
        if len(name) < 2 or "@" not in email or len(password) < 6:
            return render_template("signup.html", error="Enter a valid name, email and a password of at least 6 characters.", error_key="invalid_signup", user=current_user, signup=True)
            
        conn = db()
        try:
            cur = conn.execute(
                "INSERT INTO users(name,email,password,created_at) VALUES(?,?,?,?)",
                (name, email, generate_password_hash(password), datetime.now().isoformat())
            )
            conn.commit()
            
            # Log in using string ID and set remember=True for Vercel session persistence
            user = User(id=str(cur.lastrowid), name=name)
            login_user(user, remember=True)
            
            return redirect(url_for("dashboard"))
        except sqlite3.IntegrityError:
            return render_template("signup.html", error="An account with this email already exists.", error_key="email_exists", user=current_user, signup=True)
        finally:
            conn.close()
            
    return render_template("signup.html", user=current_user, signup=True)

@app.route("/login", methods=["GET", "POST"])
def login():
    # If the user is already logged in, send them straight to dashboard
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        conn = db()
        user_row = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        conn.close()
        
        if user_row and check_password_hash(user_row["password"], password):
            user_name = user_row["name"] if "name" in user_row.keys() else "Entrepreneur"
            user = User(id=str(user_row["id"]), name=user_name)
            login_user(user, remember=True)
            return redirect(url_for("dashboard"))
            
        return render_template("login.html", error="Incorrect email or password.", error_key="invalid_login", user=current_user, signup=False)
        
    return render_template("login.html", user=current_user, signup=False)

@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("index"))

@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html", user=current_user)

@app.route("/analysis")
def analysis():
    return render_template("business_analysis.html", user=current_user)

@app.route("/loan-assistance")
def loan_assistance():
    return render_template("loan_assistance.html", user=current_user)

@app.route("/performance")
def performance():
    return render_template("performance.html", user=current_user)

@app.route("/api/performance", methods=["POST"])
def api_performance():
    data = request.get_json(force=True) or {}
    rows = data.get("months", [])
    if not isinstance(rows, list) or len(rows) != 12:
        return jsonify({"error": "Provide exactly 12 monthly records."}), 400
    clean = []
    for i, row in enumerate(rows):
        try:
            revenue = max(0, float(row.get("revenue", 0) or 0))
            expenses = max(0, float(row.get("expenses", 0) or 0))
            emi = max(0, float(row.get("emi", 0) or 0))
        except (TypeError, ValueError):
            return jsonify({"error": f"Invalid financial value for month {i + 1}."}), 400
        profit = revenue - expenses
        cash_after_emi = profit - emi
        margin = round((profit / revenue) * 100, 2) if revenue else 0
        clean.append({"month": row.get("month", i + 1), "revenue": round(revenue), "expenses": round(expenses), "emi": round(emi), "profit": round(profit), "cash_after_emi": round(cash_after_emi), "profit_margin": margin})
    total_revenue = sum(x["revenue"] for x in clean)
    total_expenses = sum(x["expenses"] for x in clean)
    total_emi = sum(x["emi"] for x in clean)
    total_profit = total_revenue - total_expenses
    total_cash = total_profit - total_emi
    annual_margin = round((total_profit / total_revenue) * 100, 2) if total_revenue else 0
    return jsonify({"months": clean, "summary": {"revenue": total_revenue, "expenses": total_expenses, "emi": total_emi, "profit": total_profit, "cash_after_emi": total_cash, "profit_margin": annual_margin}})

def loan_data():
    return load_json("loan_assistance.json")

def select_loan_scheme(project_cost, category):
    dataset = loan_data()
    schemes = dataset.get("schemes", {})
    
    # Check if category is targeted under NSFDC rules (SC)
    if category == "SC":
        if "MFS" in schemes and project_cost <= schemes["MFS"].get("project_max", 0):
            return schemes["MFS"], "MFS"
        if "TLS" in schemes and project_cost <= schemes["TLS"].get("project_max", 0):
            return schemes["TLS"], "TLS"
        return None, None

    # Routing fallback schemes for GENERAL / OBC / ST categories
    general_schemes = {
        "OBC": {"name": "NBCFDC Loan Scheme", "beneficiary_rate": 6.0, "channels": ["State Channelizing Agencies (SCAs)", "RRBs", "Public Sector Banks"]},
        "ST": {"name": "NSTFDC Term Loan Scheme", "beneficiary_rate": 6.0, "channels": ["ST Finance Corporation", "PSBs", "RRBs"]},
        "GENERAL": {"name": "MSME / Mainstream Enterprise Loan", "beneficiary_rate": 8.5, "channels": ["Public Sector Banks (PSBs)", "Regional Rural Banks (RRBs)", "Commercial Banks"]}
    }
    
    # Safely retrieve fallback without modifying the template dictionary
    base = general_schemes.get(category, general_schemes["GENERAL"])
    fallback = {
        **base,
        "project_max": 5000000,
        "loan_max": 5000000
    }
    
    if project_cost <= fallback["project_max"]:
        return fallback, f"{category}_GENERIC"
        
    return None, None

@app.route("/api/loan-assistance", methods=["POST"], endpoint="api_loan_assistance_v2")
def api_loan_assistance():
    data = request.get_json(force=True) or {}
    category = str(data.get("category", "SC")).upper()
    if category not in {"SC", "ST", "OBC", "GENERAL"}:
        return jsonify({"error": "Select a valid applicant category."}), 400
        
    try:
        project_cost = float(data.get("project_cost", 0) or 0)
        income = float(data.get("income", 0) or 0)
    except (TypeError, ValueError):
        return jsonify({"error": "Project cost and income must be valid numbers."}), 400

    if income < 0:
        return jsonify({"error": "Income cannot be negative."}), 400

    if project_cost <= 0:
        return jsonify({"error": "Enter a project cost greater than zero."}), 400

    # Build the complete response expected by the Loan Assistance frontend.
    dataset = loan_data()
    # Fallback to a mainstream profile when the category is not explicitly configured.
    profile = dataset["profile_rules"].get(category, {
        "status": "mainstream_applicant",
        "documents": ["Aadhaar Card", "PAN Card", "Project Report (DPR)", "Bank Statement (Last 6 Months)"],
        "alternatives": [],
        "notes": ["Processed under standard MSME and commercial banking guidelines."]
    })

    scheme, scheme_code = select_loan_scheme(project_cost, category)

    if not scheme:
        return jsonify({"error": "The configured loan range ends at ₹50 lakh project cost. Route larger projects to another applicable scheme."}), 400

    required_margin = round(project_cost * 0.10)
    indicative_finance = min(round(project_cost * 0.90), scheme.get("loan_max", 5000000))
    
    woman = bool(data.get("woman"))
    pwd = bool(data.get("pwd"))
    senior = bool(data.get("senior"))

    # Select profile benefits dynamically based on category
    benefits = []
    if category == "SC":
        benefits.extend(dataset["benefit_rules"].get(category, []))
        if woman:
            benefits.extend(dataset["benefit_rules"].get("WOMAN", []))
    else:
        benefits.append(f"Eligible for mainstream {category} enterprise and MSME priority sector lending initiatives.")
        if woman:
            benefits.append("Eligible for general woman entrepreneur interest concessions and scheme priority under bank MSME programs (e.g., Stree Shakti / Mudra).")

    if pwd:
        benefits.extend(dataset["benefit_rules"].get("PWD", []))
    if senior:
        benefits.extend(dataset["benefit_rules"].get("SENIOR", []))
        
    # De-duplicate benefits while preserving order
    benefits = list(dict.fromkeys(benefits))

    documents = list(profile.get("documents", []))
    missing_guidance = []
    if category == "SC":
        missing_guidance.append(dataset["document_guidance"]["caste_certificate"])
    missing_guidance.append(dataset["document_guidance"]["income_proof"])
    missing_guidance.append(dataset["document_guidance"]["kyc"])
    missing_guidance.append(dataset["document_guidance"]["business_documents"])
    missing_guidance.extend(profile.get("alternatives", []))

    eligible_target = profile.get("status") == "eligible_target_group"
    income_ok = (category != "SC") or income <= 500000

    if eligible_target and income_ok:
        eligibility = "Your profile matches the configured target-group and income checks. Final sanction remains with the authorized channel partner."
        readiness = 90
    elif category != "SC":
        eligibility = f"General/Mainstream profile: Processed under standard {scheme['name']} guidelines."
        readiness = 70
    elif eligible_target and not income_ok:
        eligibility = "The current NSFDC income ceiling is ₹5 lakh for loan beneficiaries; this profile is above that configured ceiling."
        readiness = 35
    else:
        eligibility = profile["notes"][0]
        readiness = 25

    roadmap = [
        {"title": "Confirm eligibility", "text": "Verify category, income, project activity and current scheme rules."},
        {"title": "Prepare documents", "text": "Collect the personalized checklist and obtain any missing certificate from the competent authority."},
        {"title": "Choose channel partner", "text": "Use PM-SURAJ or authorized SCA/CA/bank partners to identify your application route."},
        {"title": "Submit & track", "text": "Submit the application and keep the acknowledgement/reference number for follow-up."}
    ]

    if category == "SC" and (not eligible_target or not income_ok):
        roadmap[0]["text"] = "The current MFS/TLS route is not marked eligible for this profile; explore alternate corporation/schemes shown in the notes."
        readiness = min(readiness, 30)

    return jsonify({
        "scheme": {**scheme, "code": scheme_code},
        "project_cost": round(project_cost),
        "required_margin": required_margin,
        "indicative_finance": indicative_finance,
        "eligibility_message": eligibility,
        "readiness_score": readiness,
        "documents": documents,
        "benefits": benefits,
        "missing_guidance": missing_guidance,
        "roadmap": roadmap,
        "district": data.get("district", "Karnataka"),
        "official_links": dataset["official_links"]
    })

@app.route("/copilot")
def copilot():
    return render_template("copilot.html", user=current_user)

@app.route("/report")
def report():
    return render_template("report.html", user=current_user)

@app.route("/api/locations")
def api_locations():
    return jsonify(load_json("locations.json"))

@app.route("/api/categories")
def api_categories():
    return jsonify(load_json("business_categories.json"))

KN_ANALYSIS = {
"Retail & Services": {"market_opportunity":"ದೈನಂದಿನ ಸ್ಥಳೀಯ ಅಗತ್ಯವನ್ನು ಪೂರೈಸುವ ಮತ್ತು ವಿಶ್ವಾಸಾರ್ಹ ಸೇವೆ ನೀಡುವ ವ್ಯವಹಾರಗಳಿಗೆ ಉತ್ತಮ ಅವಕಾಶವಿದೆ.","competitor_density":"ಸ್ಪರ್ಧೆ ಮಧ್ಯಮವಾಗಿದೆ; ಉತ್ತಮ ಸೇವೆ, ಮನೆಗೆ ವಿತರಣೆ ಮತ್ತು ಡಿಜಿಟಲ್ ಪರಿಚಯದ ಮೂಲಕ ವಿಭಿನ್ನತೆ ತೋರಿಸಬಹುದು.","season_tip":"ಹಬ್ಬದ ಆಫರ್‌ಗಳು, ಸ್ಥಳೀಯ ಬೇಡಿಕೆಯ ಗಮನ ಮತ್ತು ದಾಸ್ತಾನು ನಿಯಂತ್ರಣಕ್ಕೆ ಆದ್ಯತೆ ನೀಡಿ","best_businesses":["ನೆರೆಹೊರೆಯ ಅಗತ್ಯ ವಸ್ತುಗಳ ಅಂಗಡಿ","ಮೊಬೈಲ್ / ಡಿಜಿಟಲ್ ಸೇವಾ ಕೇಂದ್ರ","ಮನೆ ಸೇವೆಗಳು ಮತ್ತು ದುರಸ್ತಿ"],"swot":{"strengths":["ದೈನಂದಿನ ಬಳಕೆಯ ಬೇಡಿಕೆ","ಮರುಬರುವ ಗ್ರಾಹಕರು"],"weaknesses":["ಸ್ಥಳದ ಮೇಲೆ ಅವಲಂಬನೆ","ದಾಸ್ತಾನು ನಿಯಂತ್ರಣ ಅಗತ್ಯ"],"opportunities":["ಡಿಜಿಟಲ್ ಆರ್ಡರ್‌ಗಳು","ಸ್ಥಳೀಯ ವಿತರಣೆ"],"threats":["ಬೆಲೆ ಸ್ಪರ್ಧೆ","ಕಡಿಮೆ ಲಾಭದ ದಾಸ್ತಾನು"]},"threats":["ತೀವ್ರ ರಿಯಾಯಿತಿ ಸ್ಪರ್ಧೆ","ದಾಸ್ತಾನು ನಿಧಾನವಾಗಿ ಮಾರಾಟವಾಗುವುದು"],"pricing":"ವೆಚ್ಚದ ಮೇಲೆ ಲಾಭ ಸೇರಿಸಿ ಬೆಲೆ ನಿಗದಿ ಮಾಡಿ; ಜೊತೆಗೆ ಹತ್ತಿರದ 3–5 ಪರ್ಯಾಯಗಳ ಬೆಲೆಗಳನ್ನು ಹೋಲಿಸಿ.","market_reach":"ತಾಲೂಕು ಕೇಂದ್ರ, ಹತ್ತಿರದ ಗ್ರಾಮಗಳು ಮತ್ತು ಸ್ಥಳೀಯ/ಡಿಜಿಟಲ್ ವಿತರಣೆಯ ವ್ಯಾಪ್ತಿ.","scheme":"ಅರ್ಹ ಹಣಕಾಸು ವ್ಯವಹಾರದ ಪ್ರಕಾರ ಮತ್ತು ಪ್ರಸ್ತುತ ಅಧಿಕೃತ ಯೋಜನೆ/ಸಾಲದಾತರ ನಿಯಮಗಳ ಮೇಲೆ ಅವಲಂಬಿತವಾಗಿದೆ."},
"Food Processing": {"market_opportunity":"ಸ್ಥಳೀಯ ಕಚ್ಚಾ ವಸ್ತುಗಳನ್ನು ಸ್ಥಿರ ಗುಣಮಟ್ಟದ ಬ್ರಾಂಡ್ ಉತ್ಪನ್ನಗಳಾಗಿ ಪರಿವರ್ತಿಸಲು ಸಾಧ್ಯವಾದರೆ ಉತ್ತಮ ಅವಕಾಶವಿದೆ.","competitor_density":"ವಿಶೇಷ ಸ್ಥಳೀಯ ಉತ್ಪನ್ನಗಳಲ್ಲಿ ಸ್ಪರ್ಧೆ ಕಡಿಮೆದಿಂದ ಮಧ್ಯಮವಾಗಿದೆ; ವಿತರಣೆಯ ಗುಣಮಟ್ಟ ಮುಖ್ಯ.","season_tip":"ಕಚ್ಚಾ ವಸ್ತು ಲಭ್ಯತೆ, ಸ್ವಚ್ಛತೆ ಮತ್ತು ಸಂಗ್ರಹಾವಧಿ ಯೋಜನೆಗೆ ಆದ್ಯತೆ ನೀಡಿ","best_businesses":["ಸಿರಿಧಾನ್ಯ ಆಧಾರಿತ ತಿಂಡಿಗಳು","ಮಸಾಲೆ ಮತ್ತು ಮಸಾಲಾ ಸಂಸ್ಕರಣೆ","ಉಪ್ಪಿನಕಾಯಿ ಮತ್ತು ತಕ್ಷಣ ಅಡುಗೆಗೆ ಸಿದ್ಧ ಉತ್ಪನ್ನಗಳು"],"swot":{"strengths":["ಮೌಲ್ಯವರ್ಧನೆ","ಸ್ಥಳೀಯ ಮೂಲಗಳಿಂದ ಖರೀದಿ"],"weaknesses":["ಗುಣಮಟ್ಟ ನಿಯಂತ್ರಣ","ಸಂಗ್ರಹಾವಧಿ ನಿರ್ವಹಣೆ"],"opportunities":["ಆನ್‌ಲೈನ್/ಸ್ಥಳೀಯ ಚಿಲ್ಲರೆ ಮಾರಾಟ","ಸಂಸ್ಥಾತ್ಮಕ ಖರೀದಿದಾರರು"],"threats":["ಒಳಪದರ ಬೆಲೆ ಬದಲಾವಣೆ","ಆಹಾರ ಸುರಕ್ಷತಾ ಅನುಸರಣೆ"]},"threats":["ಕಚ್ಚಾ ವಸ್ತುಗಳ ಬೆಲೆ ಬದಲಾವಣೆ","ಉತ್ಪನ್ನ ಹಾಳಾಗುವಿಕೆ"],"pricing":"ಬೆಲೆ ನಿಗದಿಗೆ ಮೊದಲು ಕಚ್ಚಾ ವಸ್ತು + ಪ್ಯಾಕೇಜಿಂಗ್ + ಕಾರ್ಮಿಕ ವೆಚ್ಚ + ವಿತರಣಾ ವೆಚ್ಚವನ್ನು ಲೆಕ್ಕಿಸಿ.","market_reach":"ಚಿಲ್ಲರೆ ಅಂಗಡಿಗಳು, ವಾರದ ಸಂತೆಗಳು, ಆನ್‌ಲೈನ್/ಸ್ಥಳೀಯ ಮರುಮಾರಾಟಗಾರರು.","scheme":"ಪ್ರಸ್ತುತ ಲಭ್ಯವಿರುವ MSME, ಆಹಾರ ಸಂಸ್ಕರಣೆ ಮತ್ತು ಸಾಲದಾತರ ಹಣಕಾಸು ಆಯ್ಕೆಗಳನ್ನು ಪರಿಶೀಲಿಸಿ."},
"Agriculture & Allied": {"market_opportunity":"ಸ್ಥಳೀಯ ಬೆಳೆ ಮಾದರಿ, ನೀರಾವರಿ, ಪಶುಸಂಗೋಪನೆ ಮತ್ತು ಒಗ್ಗೂಡಿಸುವ ಮಾರುಕಟ್ಟೆ ಪ್ರವೇಶಕ್ಕೆ ಅವಕಾಶವು ಸಂಬಂಧಿಸಿದೆ.","competitor_density":"ತಾಲೂಕು ಮತ್ತು ಈಗಿರುವ ಕೃಷಿ ಉದ್ಯಮಗಳ ಪ್ರಕಾರ ಸ್ಪರ್ಧೆ ಬದಲಾಗುತ್ತದೆ.","season_tip":"ಬೆಳೆ ಕ್ಯಾಲೆಂಡರ್, ಮಳೆ ಅವಲಂಬನೆ ಮತ್ತು ಕೊಯ್ಲಿನ ಬೇಡಿಕೆಗೆ ಆದ್ಯತೆ ನೀಡಿ","best_businesses":["ಕೃಷಿ ಉಪಕರಣ ಬಾಡಿಗೆ ಸೇವೆ","ಮೌಲ್ಯವರ್ಧಿತ ಕೃಷಿ ಉತ್ಪನ್ನಗಳು","ಹಾಲು / ಕೋಳಿ ಸಾಕಾಣಿಕೆ ಬೆಂಬಲ ಸೇವೆಗಳು"],"swot":{"strengths":["ಸ್ಥಳೀಯ ಅಗತ್ಯಕ್ಕೆ ಉತ್ತಮ ಹೊಂದಾಣಿಕೆ","ಪುನರಾವರ್ತಿತ ಗ್ರಾಮೀಣ ಬೇಡಿಕೆ"],"weaknesses":["ಋತುಮಾನ ಅವಲಂಬನೆ","ಸಾಗಣೆ ವ್ಯವಸ್ಥೆ"],"opportunities":["ರೈತ ಗುಂಪುಗಳು","ಉತ್ಪನ್ನ ಒಗ್ಗೂಡಿಸುವಿಕೆ"],"threats":["ಹವಾಮಾನ ಬದಲಾವಣೆ","ಸರಕು ಬೆಲೆ ಬದಲಾವಣೆ"]},"threats":["ಋತುಮಾನಿಕ ಆದಾಯ ಬದಲಾವಣೆ","ಹವಾಮಾನದಿಂದ ವ್ಯತ್ಯಯ"],"pricing":"ಋತುಮಾನಕ್ಕೆ ತಕ್ಕ ಪ್ಯಾಕೇಜ್‌ಗಳನ್ನು ಬಳಸಿ ಮತ್ತು ನಿರ್ವಹಣೆ/ಸಾಗಣೆ ವೆಚ್ಚಗಳನ್ನು ಎಚ್ಚರಿಕೆಯಿಂದ ಲೆಕ್ಕಿಸಿ.","market_reach":"ಗ್ರಾಮ ಗುಂಪುಗಳು, FPOಗಳು, ಮಾರುಕಟ್ಟೆಗಳು ಮತ್ತು ತಾಲೂಕು ಖರೀದಿದಾರರು.","scheme":"ಅಧಿಕೃತ ಸಂಸ್ಥೆಗಳ ಮೂಲಕ ಕೃಷಿ ಮತ್ತು ಸಂಬಂಧಿತ ಕ್ಷೇತ್ರಗಳ ಹಣಕಾಸನ್ನು ಪರಿಶೀಲಿಸಿ."},
"Tourism & Hospitality": {"market_opportunity":"ಪ್ರವಾಸಿ ತಾಣಗಳು ಮತ್ತು ಸಂಚಾರ ಮಾರ್ಗಗಳ ಪ್ರದೇಶಗಳಲ್ಲಿ ಉತ್ತಮ ಸೇವೆ ಮತ್ತು ಸುಲಭವಾಗಿ ಪತ್ತೆಯಾಗುವಿಕೆ ಇದ್ದರೆ ಹೆಚ್ಚಿನ ಅವಕಾಶವಿದೆ.","competitor_density":"ಜನಪ್ರಿಯ ಪ್ರವಾಸಿ ತಾಣಗಳಲ್ಲಿ ಸ್ಪರ್ಧೆ ಮಧ್ಯಮದಿಂದ ಹೆಚ್ಚಾಗಿದೆ.","season_tip":"ಪೀಕ್-ಸೀಸನ್ ಬೆಲೆ, ವಿಮರ್ಶೆಗಳು ಮತ್ತು ಮುಂಗಡ ಬುಕ್ಕಿಂಗ್‌ಗೆ ಆದ್ಯತೆ ನೀಡಿ","best_businesses":["ಹೋಂಸ್ಟೇ ಬೆಂಬಲ ಸೇವೆಗಳು","ಸ್ಥಳೀಯ ಆಹಾರ ಅನುಭವ","ಮಾರ್ಗದರ್ಶಿತ ಸ್ಥಳೀಯ ಅನುಭವಗಳು"],"swot":{"strengths":["ಅನುಭವ ಆಧಾರಿತ ಬೇಡಿಕೆ","ಹೆಚ್ಚುವರಿ ಮಾರಾಟದ ಅವಕಾಶ"],"weaknesses":["ಋತುಮಾನಿಕತೆ","ಸೇವೆಯ ಸ್ಥಿರತೆ"],"opportunities":["ಆನ್‌ಲೈನ್ ಪರಿಚಯ","ಪ್ರವಾಸ ಪಾಲುದಾರಿಕೆಗಳು"],"threats":["ಆಫ್-ಸೀಸನ್ ಬೇಡಿಕೆ","ಖ್ಯಾತಿಗೆ ಹಾನಿಯ ಅಪಾಯ"]},"threats":["ಆಫ್-ಸೀಸನ್‌ನಲ್ಲಿ ಕಡಿಮೆ ಗ್ರಾಹಕರು","ನಕಾರಾತ್ಮಕ ವಿಮರ್ಶೆಗಳು"],"pricing":"ವಾರದ ದಿನ/ವಾರಾಂತ್ಯ ಮತ್ತು ಪೀಕ್/ಆಫ್-ಪೀಕ್ ಬೆಲೆ ಶ್ರೇಣಿಗಳನ್ನು ಬಳಸಿ.","market_reach":"ಪ್ರವಾಸಿಗರು, ಪ್ರವಾಸ ಪಾಲುದಾರರು ಮತ್ತು ಆನ್‌ಲೈನ್ ಪಟ್ಟಿಗಳು.","scheme":"ಪ್ರಸ್ತುತ ಪ್ರವಾಸೋದ್ಯಮ/MSME ಹಣಕಾಸು ಅರ್ಹತೆಯನ್ನು ಪರಿಶೀಲಿಸಿ."},
"Beauty & Personal Care": {"market_opportunity":"ದಟ್ಟ ಜನವಸತಿ ಮತ್ತು ಪಟ್ಟಣ ಪ್ರದೇಶಗಳಲ್ಲಿ ವಿಭಿನ್ನ ಸೇವೆ ನೀಡಿದರೆ ಉತ್ತಮ ಅವಕಾಶವಿದೆ.","competitor_density":"ಸ್ಪರ್ಧೆ ಮಧ್ಯಮದಿಂದ ಹೆಚ್ಚಾಗಿದೆ; ಗ್ರಾಹಕರ ಅನುಭವ ಬಹಳ ಮುಖ್ಯ.","season_tip":"ಹಬ್ಬದ ಪ್ಯಾಕೇಜ್‌ಗಳು, ಮದುವೆ ಬೇಡಿಕೆ ಮತ್ತು ಮರುಬರುವ ಸದಸ್ಯತ್ವಕ್ಕೆ ಆದ್ಯತೆ ನೀಡಿ","best_businesses":["ಬ್ಯೂಟಿ ಸ್ಟುಡಿಯೋ","ವಧುವಿನ ಅಲಂಕಾರ ಸೇವೆ","ವೈಯಕ್ತಿಕ ಆರೈಕೆ ಚಿಲ್ಲರೆ ಮಾರಾಟ + ಸೇವೆಗಳು"],"swot":{"strengths":["ಮರುಬರುವ ಗ್ರಾಹಕರು","ಸೇವೆಗಳ ಹೆಚ್ಚುವರಿ ಮಾರಾಟ"],"weaknesses":["ಕೌಶಲ್ಯದ ಅವಲಂಬನೆ","ಟ್ರೆಂಡ್‌ಗಳಿಗೆ ಸಂವೇದನಾಶೀಲತೆ"],"opportunities":["ಪ್ಯಾಕೇಜ್‌ಗಳು","ಸಾಮಾಜಿಕ ಮಾಧ್ಯಮದ ಮೂಲಕ ಪರಿಚಯ"],"threats":["ಹೆಚ್ಚಿನ ಸ್ಥಳೀಯ ಸ್ಪರ್ಧೆ","ಸಿಬ್ಬಂದಿ ಬದಲಾವಣೆ"]},"threats":["ಕಡಿಮೆ ಬೆಲೆಯ ಸ್ಪರ್ಧೆ","ವೇಗವಾಗಿ ಬದಲಾಗುವ ಟ್ರೆಂಡ್‌ಗಳು"],"pricing":"ಕೇವಲ ಕಡಿಮೆ ಬೆಲೆಯಲ್ಲಿ ಸ್ಪರ್ಧಿಸುವ ಬದಲು ಸೇವೆಗಳನ್ನು ಪ್ಯಾಕೇಜ್ ಮಾಡಿ ಲಾಭಾಂಶವನ್ನು ರಕ್ಷಿಸಿ.","market_reach":"ಹತ್ತಿರದ ವಸತಿ ಪ್ರದೇಶಗಳು, ಕಾಲೇಜುಗಳು ಮತ್ತು ಸಾಮಾಜಿಕ ಮಾಧ್ಯಮದ ಪ್ರೇಕ್ಷಕರು.","scheme":"MSME ಮತ್ತು ಸೇವಾ ಕ್ಷೇತ್ರದ ಸಾಲ ಆಯ್ಕೆಗಳನ್ನು ಪರಿಶೀಲಿಸಿ."},
"Manufacturing & Handicrafts": {"market_opportunity":"ಕೌಶಲ್ಯ, ಕಚ್ಚಾ ವಸ್ತು ಮತ್ತು ವಿಶ್ವಾಸಾರ್ಹ ಖರೀದಿದಾರರನ್ನು ಸಂಪರ್ಕಿಸಲು ಸಾಧ್ಯವಾದರೆ ಉತ್ತಮ ಅವಕಾಶವಿದೆ.","competitor_density":"ಉತ್ಪನ್ನದ ವಿಶೇಷ ವಿಭಾಗದ ಪ್ರಕಾರ ಸ್ಪರ್ಧೆ ಬಹಳ ಬದಲಾಗುತ್ತದೆ.","season_tip":"ಉತ್ಪಾದನಾ ಯೋಜನೆ ಮತ್ತು ಆರ್ಡರ್ ಚಕ್ರಗಳಿಗೆ ಆದ್ಯತೆ ನೀಡಿ","best_businesses":["ಸ್ಥಳೀಯ ಕರಕುಶಲ ಉತ್ಪನ್ನಗಳು","ಕಸ್ಟಮ್ ತಯಾರಿಕೆ","ಪರಿಸರ ಸ್ನೇಹಿ ಬಳಕೆ ವಸ್ತುಗಳು"],"swot":{"strengths":["ಉತ್ಪನ್ನ ವಿಭಿನ್ನತೆ","ಕೌಶಲ್ಯ ಆಧಾರಿತ ಮೌಲ್ಯ"],"weaknesses":["ಹೆಚ್ಚಿನ ಬಂಡವಾಳ ಅಗತ್ಯ","ಗುಣಮಟ್ಟದ ಸ್ಥಿರತೆ"],"opportunities":["B2B ಖರೀದಿದಾರರು","ಆನ್‌ಲೈನ್ ಕ್ಯಾಟಲಾಗ್‌ಗಳು"],"threats":["ಒಳಪದರ ವೆಚ್ಚ ಏರಿಕೆ","ಬೇಡಿಕೆಯ ಅನಿಶ್ಚಿತತೆ"]},"threats":["ಯಂತ್ರದ ಅಲಭ್ಯತೆ","ಒಬ್ಬೇ ಖರೀದಿದಾರರ ಮೇಲೆ ಅವಲಂಬನೆ"],"pricing":"ಪ್ರತಿ ಘಟಕದ ಆರ್ಥಿಕತೆಯಲ್ಲಿ ವ್ಯರ್ಥ, ಕಾರ್ಮಿಕ, ಓವರ್‌ಹೆಡ್ ಮತ್ತು ವಿತರಣಾ ವೆಚ್ಚಗಳನ್ನು ಸೇರಿಸಿ.","market_reach":"ಚಿಲ್ಲರೆ, ಸಗಟು, B2B ಮತ್ತು ಆನ್‌ಲೈನ್ ಮಾರುಕಟ್ಟೆಗಳು.","scheme":"ಪ್ರಸ್ತುತ MSME/ಉತ್ಪಾದನಾ ಕ್ಷೇತ್ರದ ಹಣಕಾಸು ಆಯ್ಕೆಗಳನ್ನು ಪರಿಶೀಲಿಸಿ."}
}

# --- Hyper-local visual business mapping ---
MAP_CATEGORY_TAGS = {
    "Retail & Services": [("shop", "convenience"), ("shop", "general"), ("shop", "mobile_phone"), ("craft", "repair")],
    "Food Processing": [("shop", "bakery"), ("shop", "confectionery"), ("shop", "deli"), ("craft", "food")],
    "Agriculture & Allied": [("shop", "farm"), ("shop", "agrarian"), ("amenity", "veterinary"), ("shop", "garden_centre")],
    "Tourism & Hospitality": [("tourism", "hotel"), ("tourism", "guest_house"), ("tourism", "hostel"), ("amenity", "restaurant"), ("amenity", "cafe")],
    "Beauty & Personal Care": [("shop", "hairdresser"), ("shop", "beauty"), ("shop", "cosmetics"), ("amenity", "spa")],
    "Manufacturing & Handicrafts": [("craft", "carpenter"), ("craft", "tailor"), ("craft", "shoemaker"), ("shop", "furniture")]
}

IDEA_TAG_HINTS = {
    "bakery": [("shop", "bakery")], "cafe": [("amenity", "cafe")], "restaurant": [("amenity", "restaurant")],
    "hotel": [("tourism", "hotel")], "homestay": [("tourism", "guest_house")], "tailor": [("craft", "tailor"), ("shop", "tailor")],
    "tailoring": [("craft", "tailor"), ("shop", "tailor")], "salon": [("shop", "hairdresser"), ("shop", "beauty")],
    "beauty": [("shop", "beauty")], "pharmacy": [("amenity", "pharmacy")], "medical": [("amenity", "clinic")],
    "clinic": [("amenity", "clinic")], "grocery": [("shop", "supermarket"), ("shop", "convenience"), ("shop", "general")],
    "supermarket": [("shop", "supermarket")], "mobile": [("shop", "mobile_phone")], "repair": [("shop", "mobile_phone"), ("craft", "electronics_repair")],
    "hardware": [("shop", "hardware")], "furniture": [("shop", "furniture")], "dairy": [("shop", "dairy")],
    "poultry": [("shop", "farm")], "nursery": [("shop", "garden_centre")], "florist": [("shop", "florist")],
    "bakery shop": [("shop", "bakery")], "juice": [("amenity", "cafe")], "tea": [("amenity", "cafe")]
}

def _safe_regex_words(text):
    words = re.findall(r"[A-Za-z][A-Za-z0-9 &-]{1,40}", str(text or ""))
    return [re.escape(w.strip()) for w in words if len(w.strip()) >= 3][:4]

def _map_tags(category, idea):
    idea_l = str(idea or "").strip().lower()
    tags = IDEA_TAG_HINTS.get(idea_l, [])
    if not tags:
        for key, vals in IDEA_TAG_HINTS.items():
            if key in idea_l and len(key) >= 4:
                tags.extend(vals)
    if not tags:
        tags = MAP_CATEGORY_TAGS.get(category, MAP_CATEGORY_TAGS["Retail & Services"])
    out = []
    for t in tags:
        if t not in out:
            out.append(t)
    return out[:8]

def _overpass_query(lat, lon, radius, tags, idea):
    selectors = []
    for key, value in tags:
        selectors.append(f'nwr(around:{int(radius*1000)},{lat},{lon})["{key}"="{value}"];')
    words = _safe_regex_words(idea)
    if words:
        regex = "|".join(words)
        selectors.append(f'nwr(around:{int(radius*1000)},{lat},{lon})["name"~"{regex}",i];')
    return '[out:json][timeout:18];(' + ''.join(selectors) + ');out center tags;'

def _fetch_overpass(query):
    endpoints = [
        "https://overpass-api.de/api/interpreter",
        "https://overpass.kumi.systems/api/interpreter"
    ]
    payload = urllib.parse.urlencode({"data": query}).encode("utf-8")
    last = None
    for endpoint in endpoints:
        try:
            req = urllib.request.Request(endpoint, data=payload, headers={"User-Agent": "GramMitra/1.0 local-business-map"})
            with urllib.request.urlopen(req, timeout=20) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            last = exc
    raise last or RuntimeError("Map data provider unavailable")

def _distance_km(lat1, lon1, lat2, lon2):
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2)**2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2)**2
    return r * 2 * math.asin(math.sqrt(a))

@app.route("/api/geocode", methods=["POST"])
def api_geocode():
    data = request.get_json(force=True) or {}
    parts = [str(data.get(k, "")).strip() for k in ("village", "taluk", "district") if str(data.get(k, "")).strip()]
    if not parts:
        return jsonify({"found": False}), 400
        
    query = ", ".join(parts + ["Karnataka", "India"])
    try:
        params = urllib.parse.urlencode({"q": query, "format": "json", "limit": 1, "countrycodes": "in"})
        req = urllib.request.Request("https://nominatim.openstreetmap.org/search?" + params, headers={"User-Agent": "GramMitra/1.0 local-business-map"})
        with urllib.request.urlopen(req, timeout=10) as response:
            results = json.loads(response.read().decode("utf-8"))
        if not results:
            return jsonify({"found": False})
        return jsonify({
            "found": True,
            "latitude": float(results[0]["lat"]),
            "longitude": float(results[0]["lon"]),
            "display_name": results[0].get("display_name", query)
        })
    except Exception as exc:
        print("Geocoding error:", exc)
        return jsonify({"found": False})

@app.route("/api/nearby-businesses", methods=["POST"])
def api_nearby_businesses():
    data = request.get_json(force=True) or {}
    try:
        lat = float(data.get("latitude"))
        lon = float(data.get("longitude"))
        radius = float(data.get("radius", 8))
    except (TypeError, ValueError):
        return jsonify({"error": "Valid latitude and longitude are required."}), 400

    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return jsonify({"error": "Invalid coordinates."}), 400

    radius = 10 if radius >= 9 else 8
    category = str(data.get("category", "Retail & Services"))
    idea = str(data.get("business_idea", "")).strip()

    try:
        raw = _fetch_overpass(_overpass_query(lat, lon, radius, _map_tags(category, idea), idea))
    except Exception as exc:
        print("Map provider error:", exc)
        return jsonify({"available": False, "error": "Nearby business data is temporarily unavailable. Please try again."})

    seen = set()
    places = []
    for el in raw.get("elements", []):
        tags = el.get("tags", {}) or {}
        name = tags.get("name") or tags.get("brand") or "Unnamed business"
        
        if el.get("lat") is not None:
            plat, plon = el.get("lat"), el.get("lon")
        else:
            center = el.get("center", {}) or {}
            plat, plon = center.get("lat"), center.get("lon")
            
        if plat is None or plon is None:
            continue

        key = (round(float(plat), 5), round(float(plon), 5), name.lower())
        if key in seen:
            continue
        seen.add(key)
        
        dist = _distance_km(lat, lon, float(plat), float(plon))
        places.append({
            "name": name,
            "lat": float(plat),
            "lon": float(plon),
            "distance_km": round(dist, 2),
            "type": tags.get("shop") or tags.get("amenity") or tags.get("tourism") or tags.get("craft") or "business"
        })

    places.sort(key=lambda x: x["distance_km"])
    count = len(places)

    if count <= 5:
        level = "Low"
    elif count <= 15:
        level = "Moderate"
    else:
        level = "High"

    return jsonify({
        "available": True,
        "radius_km": radius,
        "count": count,
        "competition_level": level,
        "places": places[:150],
        "source": "OpenStreetMap / Overpass"
    })
@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    data = request.get_json(silent=True) or {}
    district = str(data.get("district", "Karnataka") or "Karnataka").strip()
    taluk = data.get("taluk", "")
    village = data.get("village", "")
    category = data.get("category", "Retail & Services")
    
    try:
        capital = max(0, float(data.get("capital", 0) or 0))
    except (TypeError, ValueError):
        return jsonify({"error": "Available capital must be a valid number."}), 400

    address = str(data.get("address", "") or "").strip()
    business_idea = str(data.get("business_idea", "")).strip()

    try:
        latitude = float(data.get("latitude")) if data.get("latitude") not in (None, "") else None
        longitude = float(data.get("longitude")) if data.get("longitude") not in (None, "") else None
    except (TypeError, ValueError):
        latitude = longitude = None

    categories = load_json("business_categories.json")
    info = categories.get(category, categories.get("Retail & Services", {}))
    
    month = datetime.now().month
    season = "Monsoon" if month in [6, 7, 8, 9] else ("Summer" if month in [3, 4, 5] else "Festival / Harvest")

    district_bonus = {
        "Bengaluru Urban": 1.2, "Mysuru": 0.9, "Dakshina Kannada": 1.0,
        "Udupi": 0.9, "Belagavi": 0.7, "Dharwad": 0.7,
        "Tumakuru": 0.6, "Shivamogga": 0.7, "Kodagu": 0.8
    }.get(district, 0.45)

    base_cost = float(info.get("typical_project_cost", 500000))
    viability = min(9.8, max(4.5, 6.2 + district_bonus + (0.5 if capital >= base_cost * 0.1 else -0.4)))
    required_margin = round(base_cost * 0.10)
    eligible_loan = round(base_cost * 0.90)
    capital_gap = max(0, required_margin - capital)
    annual_rate = float(info.get("interest_rate", 10.0))
    years = max(1, int(info.get("repayment_years", 5)))
    quarterly_rate = annual_rate / 4 / 100
    quarters = years * 4

    if quarterly_rate > 0 and quarters > 0:
        denom = ((1 + quarterly_rate)**quarters) - 1
        quarterly_payment = round((eligible_loan * quarterly_rate * (1 + quarterly_rate)**quarters) / denom) if denom != 0 else round(eligible_loan / quarters)
    else:
        quarterly_payment = round(eligible_loan / max(1, quarters))

    lang = data.get("lang", "en")
    kn = KN_ANALYSIS.get(category, {})

    if lang == "kn" and kn:
        best_businesses = kn.get("best_businesses", [])
        swot = kn.get("swot", {})
        season_kn = {"Monsoon": "ಮಳೆಗಾಲ", "Summer": "ಬೇಸಿಗೆ", "Festival / Harvest": "ಹಬ್ಬ / ಕೊಯ್ಲು"}.get(season, season)
        category_kn = {
            "Retail & Services": "ಚಿಲ್ಲರೆ ವ್ಯಾಪಾರ ಮತ್ತು ಸೇವೆಗಳು",
            "Food Processing": "ಆಹಾರ ಸಂಸ್ಕರಣೆ",
            "Agriculture & Allied": "ಕೃಷಿ ಮತ್ತು ಸಂಬಂಧಿತ ಕ್ಷೇತ್ರಗಳು",
            "Manufacturing & Handicrafts": "ಉತ್ಪಾದನೆ ಮತ್ತು ಕರಕುಶಲ",
            "Tourism & Hospitality": "ಪ್ರವಾಸೋದ್ಯಮ ಮತ್ತು ಆತಿಥ್ಯ",
            "Beauty & Personal Care": "ಸೌಂದರ್ಯ ಮತ್ತು ವೈಯಕ್ತಿಕ ಆರೈಕೆ"
        }.get(category, category)

        result = {
            "location": {"district": district, "taluk": taluk, "village": village, "address": address, "latitude": latitude, "longitude": longitude},
            "business_idea": business_idea,
            "category": category,
            "category_label": category_kn,
            "season": season_kn,
            "viability_score": round(viability, 1),
            "market_opportunity": kn.get("market_opportunity", ""),
            "competitor_density": kn.get("competitor_density", ""),
            "seasonal_analysis": f"{season_kn} ಪರಿಸ್ಥಿತಿಗಳು ಬೇಡಿಕೆಯನ್ನು ಪ್ರಭಾವಿಸಬಹುದು. {category_kn} ಕ್ಷೇತ್ರದಲ್ಲಿ {kn.get('season_tip', '')}.",
            "best_businesses": best_businesses,
            "swot": swot,
            "threats": kn.get("threats", []),
            "pricing": kn.get("pricing", ""),
            "market_reach": kn.get("market_reach", ""),
            "working_capital": round(base_cost * 0.15),
            "project_cost": round(base_cost),
            "required_margin": required_margin,
            "available_capital": round(capital),
            "capital_gap": round(capital_gap),
            "loan_90": eligible_loan,
            "scheme": kn.get("scheme", ""),
            "interest_rate": annual_rate,
            "repayment_years": years,
            "quarterly_payment": quarterly_payment,
            "lang": "kn",
            "summary": f"{district} ಜಿಲ್ಲೆಯಲ್ಲಿ {category_kn} ಕ್ಷೇತ್ರದ ಅಂದಾಜು ವ್ಯವಹಾರ ಸಾಧ್ಯತೆ ಸ್ಕೋರ್ {round(viability,1)}/10. ಈ ಅಂಕವು ಸ್ಥಳ, ವ್ಯವಹಾರ ವರ್ಗ ಮತ್ತು ಲಭ್ಯವಿರುವ ಮಾರ್ಜಿನ್ ಬಂಡವಾಳದ ಆಧಾರದ ಸಲಹಾತ್ಮಕ ಅಂದಾಜಾಗಿದೆ. ಅಂತಿಮ ಹಣಕಾಸು ಲಭ್ಯತೆ ಸಾಲದಾತ ಮತ್ತು ಅಧಿಕೃತ ಯೋಜನೆಯ ಅರ್ಹತಾ ನಿಯಮಗಳ ಮೇಲೆ ಅವಲಂಬಿತವಾಗಿರುತ್ತದೆ."
        }
    else:
        result = {
            "location": {"district": district, "taluk": taluk, "village": village, "address": address, "latitude": latitude, "longitude": longitude},
            "business_idea": business_idea,
            "category": category,
            "season": season,
            "viability_score": round(viability, 1),
            "market_opportunity": info.get("market_opportunity", ""),
            "competitor_density": info.get("competitor_density", ""),
            "seasonal_analysis": f"{season} conditions can influence demand. For {category}, focus on {info.get('season_tip', '')}.",
            "best_businesses": info.get("best_businesses", []),
            "swot": info.get("swot", {}),
            "threats": info.get("threats", []),
            "pricing": info.get("pricing", ""),
            "market_reach": info.get("market_reach", ""),
            "working_capital": round(base_cost * 0.15),
            "project_cost": round(base_cost),
            "required_margin": required_margin,
            "available_capital": round(capital),
            "capital_gap": round(capital_gap),
            "loan_90": eligible_loan,
            "scheme": info.get("scheme", ""),
            "interest_rate": annual_rate,
            "repayment_years": years,
            "quarterly_payment": quarterly_payment,
            "lang": "en",
            "summary": f"{category} in {district} shows a {round(viability,1)}/10 indicative viability score based on location, category and available margin capital. This is an advisory estimate and final financing depends on the lender and official scheme eligibility."
        }

    result["lang"] = lang
    return jsonify(result)

@app.route("/api/copilot", methods=["POST"])
def api_copilot():
    data = request.get_json(force=True, silent=True) or {}
    message = (data.get("message") or "").lower()
    lang = data.get("lang", "en")

    if lang == "kn":
        if any(w in message for w in ["loan", "ಸಾಲ", "emi"]):
            answer = "ನಿಮ್ಮ ಯೋಜನಾ ವೆಚ್ಚದ 10% ಮಾರ್ಜಿನ್ ಹಣವನ್ನು ಮೊದಲು ಪರಿಶೀಲಿಸಿ. ಉಳಿದ 90% ಹಣಕಾಸು ಆಯ್ಕೆಗಳನ್ನು ಯೋಜನೆಯ ಅರ್ಹತೆ ಮತ್ತು ಸಾಲದಾತರ ನಿಯಮಗಳ ಪ್ರಕಾರ ಪರಿಶೀಲಿಸಬಹುದು. ನಿಮ್ಮ ವ್ಯವಹಾರ ವರ್ಗ ಮತ್ತು ಜಿಲ್ಲೆಯನ್ನು ಕಳುಹಿಸಿದರೆ ನಾನು ಉತ್ತಮವಾಗಿ ಮಾರ್ಗದರ್ಶನ ನೀಡುತ್ತೇನೆ."
        elif any(w in message for w in ["business", "ವ್ಯವಹಾರ", "idea", "ಐಡಿಯಾ"]):
            answer = "ನಿಮ್ಮ ಜಿಲ್ಲೆ, ತಾಲೂಕು, ಲಭ್ಯವಿರುವ ಬಂಡವಾಳ ಮತ್ತು ಆಸಕ್ತಿಯ ವ್ಯವಹಾರ ಕ್ಷೇತ್ರವನ್ನು ತಿಳಿಸಿ. ನಾನು ಮಾರುಕಟ್ಟೆ ಅವಕಾಶ, ಸ್ಪರ್ಧೆ ಮತ್ತು ಆರಂಭಿಕ ವೆಚ್ಚದ ಬಗ್ಗೆ ಸಲಹೆ ನೀಡುತ್ತೇನೆ."
        else:
            answer = "ಖಂಡಿತ! ನಿಮ್ಮ ವ್ಯವಹಾರ ಸಂಬಂಧಿತ ಪ್ರಶ್ನೆಯನ್ನು ವಿವರವಾಗಿ ಬರೆಯಿರಿ. ಸ್ಥಳ, ಬಂಡವಾಳ ಮತ್ತು ವ್ಯವಹಾರ ಕ್ಷೇತ್ರ ತಿಳಿಸಿದರೆ ಹೆಚ್ಚು ಉಪಯುಕ್ತ ಸಲಹೆ ನೀಡಬಹುದು."
    else:
        if any(w in message for w in ["loan", "emi", "repay"]):
            answer = "Start by checking whether your available capital covers the expected 10% margin. The remaining financing and repayment terms must be confirmed against the applicable scheme and lender rules. Tell me your district, business category and project budget for a more specific estimate."
        elif any(w in message for w in ["business", "idea", "start"]):
            answer = "Tell me your district, taluk, available capital and business category. I can help compare market opportunity, competition, seasonal demand, working capital and an indicative project cost."
        else:
            answer = "I can help with business feasibility, market opportunity, competition, pricing, working capital and financing estimates. What are you planning to start?"

    return jsonify({"answer": answer})
@app.route('/submit_farmer_details', methods=['POST'])
@login_required
def submit_farmer_details():
    try:
        # Check if the request is sending JSON or regular Form Data
        data = request.get_json(silent=True) or request.form

        land_area = data.get('land_area') or data.get('landArea') or 0.0
        crop_type = data.get('crop_type') or data.get('cropType') or data.get('category') or ''
        location = data.get('location') or ''

        # If location came as a dictionary/object, extract string format
        if isinstance(location, dict):
            loc_parts = [location.get('village'), location.get('taluk'), location.get('district')]
            location = ", ".join([str(p) for p in loc_parts if p])

        conn = db()
        conn.execute(
            "INSERT INTO farmer_queries (user_id, land_area, crop_type, location) VALUES (?, ?, ?, ?)",
            (str(current_user.id), float(land_area), str(crop_type), str(location))
        )
        conn.commit()
        conn.close()

        if request.is_json:
            return jsonify({"status": "success", "message": "Business analysis saved successfully!"}), 200

        return redirect(url_for('search_history'))
    except Exception as e:
        print("Database Save Error:", str(e))
        if request.is_json:
            return jsonify({"error": "Failed to save analysis data."}), 500
        return redirect(url_for('search_history'))


@app.route('/search_history')
@login_required
def search_history():
    conn = db()
    history = conn.execute(
        "SELECT land_area, crop_type, location, created_at FROM farmer_queries WHERE user_id = ? ORDER BY created_at DESC",
        (str(current_user.id),)
    ).fetchall()
    conn.close()

    return render_template('history.html', history=history)
    
@app.route("/download-report", methods=["POST"])
def download_report():
    try:
        data = request.get_json(force=True, silent=True) or {}
        lang = data.get("lang", "en")
        is_kn = lang == "kn"

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=42, leftMargin=42, topMargin=42, bottomMargin=42)
        styles = getSampleStyleSheet()

        if is_kn:
            title = ParagraphStyle("kn_title", fontName="NotoKannadaBold", fontSize=20, leading=26, alignment=TA_CENTER, textColor=colors.HexColor("#1D6B4F"))
            h2 = ParagraphStyle("kn_h2", fontName="NotoKannadaBold", fontSize=15, leading=20, spaceAfter=7, shaping=1)
            h3 = ParagraphStyle("kn_h3", fontName="NotoKannadaBold", fontSize=12, leading=17, spaceBefore=5, spaceAfter=5, shaping=1)
            body = ParagraphStyle("kn_body", fontName="NotoKannada", fontSize=9.5, leading=15, shaping=1)
            table_style = ParagraphStyle("kn_table", fontName="NotoKannada", fontSize=8.5, leading=13, shaping=1)
            table_bold = ParagraphStyle("kn_table_bold", fontName="NotoKannadaBold", fontSize=8.5, leading=13, shaping=1)
            labels = {
                "district": "ಜಿಲ್ಲೆ", "taluk": "ತಾಲೂಕು", "village": "ಗ್ರಾಮ", "category": "ವ್ಯವಹಾರ ವರ್ಗ",
                "score": "ಸಾಧ್ಯತೆ ಸ್ಕೋರ್", "season": "ಋತುಮಾನ", "project": "ಯೋಜನಾ ವೆಚ್ಚ", "margin": "ಅಗತ್ಯವಿರುವ 10% ಮಾರ್ಜಿನ್",
                "finance": "ಅಂದಾಜು 90% ಹಣಕಾಸು", "quarterly": "ಅಂದಾಜು ತ್ರೈಮಾಸಿಕ ಮರುಪಾವತಿ", "available": "ಲಭ್ಯವಿರುವ ಮಾರ್ಜಿನ್ ಬಂಡವಾಳ",
                "gap": "ಕೊರತೆಯಿರುವ ಮಾರ್ಜಿನ್ ಮೊತ್ತ", "working": "ಕಾರ್ಯನಿಧಿ", "rate": "ವಾರ್ಷಿಕ ಬಡ್ಡಿದರ", "years": "ಮರುಪಾವತಿ ಅವಧಿ",
                "market": "ಮಾರುಕಟ್ಟೆ ಅವಕಾಶ", "competition": "ಸ್ಪರ್ಧಿಗಳ ಸಾಂದ್ರತೆ", "seasonal": "ಋತುಮಾನಿಕ ವಿಶ್ಲೇಷಣೆ",
                "pricing": "ಬೆಲೆ ನಿಗದಿ ಸಲಹೆಗಳು", "reach": "ಮಾರುಕಟ್ಟೆ ತಲುಪುವಿಕೆ", "threats": "ಅಪಾಯಗಳು", "summary": "ಸಾರಾಂಶ",
                "swot": "SWOT ವಿಶ್ಲೇಷಣೆ",
                "important": "ಮುಖ್ಯ ಸೂಚನೆ: ಈ ವರದಿಯಲ್ಲಿನ ಅಂದಾಜುಗಳು ಸಲಹಾತ್ಮಕವಾಗಿವೆ. ಪ್ರಸ್ತುತ ಅಧಿಕೃತ ಯೋಜನಾ ಅರ್ಹತೆ, ಬಡ್ಡಿದರ ಮತ್ತು ಮರುಪಾವತಿ ನಿಯಮಗಳನ್ನು ಸಂಬಂಧಿತ ಸರ್ಕಾರಿ ಇಲಾಖೆ ಅಥವಾ ಹಣಕಾಸು ಸಂಸ್ಥೆಯೊಂದಿಗೆ ಪರಿಶೀಲಿಸಿ."
            }
            swot_names = {"strengths": "ಸಾಮರ್ಥ್ಯಗಳು", "weaknesses": "ದೌರ್ಬಲ್ಯಗಳು", "opportunities": "ಅವಕಾಶಗಳು", "threats": "ಅಪಾಯಗಳು"}
            title_text = "ಗ್ರಾಮ ಮಿತ್ರ — ಕರ್ನಾಟಕ ವ್ಯವಹಾರ AI"
            report_title = "ವ್ಯವಹಾರ ಮಾಹಿತಿ ವರದಿ"
        else:
            title = ParagraphStyle("title", parent=styles["Title"], alignment=TA_CENTER, textColor=colors.HexColor("#1D6B4F"))
            h2, h3, body, table_style, table_bold = styles["Heading2"], styles["Heading3"], styles["BodyText"], styles["BodyText"], styles["BodyText"]
            labels = {
                "district": "District", "taluk": "Taluk", "village": "Village", "category": "Business category",
                "score": "Viability score", "season": "Season", "project": "Project cost", "margin": "Required 10% margin",
                "finance": "Indicative 90% finance", "quarterly": "Estimated quarterly repayment", "market": "Market opportunity",
                "competition": "Competitor density", "seasonal": "Seasonal analysis", "pricing": "Pricing suggestions",
                "reach": "Market reach", "threats": "Threats", "summary": "Summary", "swot": "SWOT",
                "important": "Important: This report provides indicative advisory estimates. Verify current official scheme eligibility, interest rates and repayment terms with the relevant government department or financial institution."
            }
            swot_names = {"strengths": "Strengths", "weaknesses": "Weaknesses", "opportunities": "Opportunities", "threats": "Threats"}
            title_text = "Gram Mitra — Karnataka Business AI"
            report_title = "Business Analysis Report"

        def P(text, style):
            return Paragraph(html.escape(str(text)).replace("\n", "<br/>"), style)

        story = [P(title_text, title), Spacer(1, 12), P(report_title, h2), Spacer(1, 8)]
        location = data.get("location", {})
        rows = [
            [P(labels["district"], table_bold), P(location.get("district", ""), table_style)],
            [P(labels["taluk"], table_bold), P(location.get("taluk", ""), table_style)],
            [P(labels["village"], table_bold), P(location.get("village", "") or ("ನೀಡಲಾಗಿಲ್ಲ" if is_kn else "Not provided"), table_style)],
            [P(labels["category"], table_bold), P(data.get("category_label" if is_kn else "category", ""), table_style)],
            [P(labels["score"], table_bold), P(f"{data.get('viability_score', '')}/10", table_style)],
            [P(labels["season"], table_bold), P(data.get("season", ""), table_style)],
            [P(labels["project"], table_bold), P(f"₹ {data.get('project_cost', 0):,}", table_style)],
            [P(labels["margin"], table_bold), P(f"₹ {data.get('required_margin', 0):,}", table_style)],
            [P(labels.get("available", "Available margin capital"), table_bold), P(f"₹ {data.get('available_capital', 0):,}", table_style)],
            [P(labels.get("gap", "Capital gap"), table_bold), P(f"₹ {data.get('capital_gap', 0):,}", table_style)],
            [P(labels["finance"], table_bold), P(f"₹ {data.get('loan_90', 0):,}", table_style)],
            [P(labels["quarterly"], table_bold), P(f"₹ {data.get('quarterly_payment', 0):,}", table_style)]
        ]
        
        table = Table(rows, colWidths=[180, 300])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#E8F3EC")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#B9C8BD")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("PADDING", (0, 0), (-1, -1), 8)
        ]))
        story += [table, Spacer(1, 16)]

        for heading, key in [
            (labels["market"], "market_opportunity"), (labels["competition"], "competitor_density"),
            (labels["seasonal"], "seasonal_analysis"), (labels["pricing"], "pricing"),
            (labels["reach"], "market_reach"), (labels["threats"], "threats"), (labels["summary"], "summary")
        ]:
            story.append(P(heading, h3))
            value = data.get(key, "")
            if isinstance(value, list):
                value = " • ".join(map(str, value))
            story.append(P(value, body))
            story.append(Spacer(1, 8))

        story.append(P(labels["swot"], h3))
        swot = data.get("swot", {})
        swot_rows = [[P(swot_names.get(k, k), table_bold), P(" • ".join(v) if isinstance(v, list) else str(v), table_style)] for k, v in swot.items()]
        if swot_rows:
            t = Table(swot_rows, colWidths=[120, 360])
            t.setStyle(TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#B9C8BD")),
                ("PADDING", (0, 0), (-1, -1), 7),
                ("VALIGN", (0, 0), (-1, -1), "TOP")
            ]))
            story.append(t)

        story += [Spacer(1, 14), P(labels["important"], body)]

        doc.build(story)
        buffer.seek(0)

        filename = "Gram_Mitra_Business_Report_KN.pdf" if is_kn else "Gram_Mitra_Business_Report.pdf"
        return send_file(
            buffer,
            as_attachment=True,
            download_name=filename,
            mimetype="application/pdf"
        )
    except Exception as e:
        print("PDF Error:", str(e))
        return jsonify({"error": "Could not generate PDF. Please try again."}), 500

if __name__ == "__main__":
    init_db()
    app.run(debug=True)