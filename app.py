import os, json, sqlite3, tempfile, math, urllib.request, base64, re
from pathlib import Path
import warnings
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import PIL.Image
import piexif
import logging
import webbrowser
import threading

warnings.filterwarnings("ignore")

app = Flask(__name__, static_folder=".")
CORS(app, resources={r"/api/*": {"origins": "*"}})

# ── FILE PATHS ────────────────────────────────────────────────
BASE_DIR   = Path(__file__).resolve().parent
DB_PATH    = BASE_DIR / "phase_b_data" / "monuments.db"
TREE_PATH  = BASE_DIR / "phase_b_data" / "balltree.pkl"

# ── LOAD .ENV FILE MANUALLY ──────────────────────────────────
ENV_PATH = BASE_DIR / ".env"
if ENV_PATH.exists():
    print("Loading environment variables from .env...")
    with open(ENV_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ[key.strip()] = val.strip()

conn = sqlite3.connect(DB_PATH, check_same_thread=False)

# ── FIX BAD DATA ON STARTUP ───────────────────────────────────
conn.execute("UPDATE monuments SET city=NULL     WHERE city     IN ('None','none','NULL','null','')")
conn.execute("UPDATE monuments SET province=NULL WHERE province IN ('None','none','NULL','null','')")
LOCATION_FIXES = [
    ('%Faisal Mosque%',      'Islamabad',  'Islamabad Capital Territory'),
    ('%Pakistan Monument%',  'Islamabad',  'Islamabad Capital Territory'),
    ('%Mazar-e-Quaid%',      'Karachi',    'Sindh'),
    ('%Mausoleum of Quaid%', 'Karachi',    'Sindh'),
    ('%Mohenjo%',            'Larkana',    'Sindh'),
    ('%Moenjodaro%',         'Larkana',    'Sindh'),
    ('%Makli%',              'Thatta',     'Sindh'),
    ('%Badshahi Mosque%',    'Lahore',     'Punjab'),
    ('%Lahore Fort%',        'Lahore',     'Punjab'),
    ('%Minar-e-Pakistan%',   'Lahore',     'Punjab'),
    ('%Shalimar%',           'Lahore',     'Punjab'),
    ('%Rohtas Fort%',        'Jhelum',     'Punjab'),
    ('%Derawar Fort%',       'Bahawalpur', 'Punjab'),
    ('%Baltit Fort%',        'Hunza',      'Gilgit-Baltistan'),
    ('%Altit Fort%',         'Hunza',      'Gilgit-Baltistan'),
    ('%Taxila%',             'Taxila',     'Punjab'),
    ('%Mohatta%',            'Karachi',    'Sindh'),
]
for pattern, city, province in LOCATION_FIXES:
    conn.execute("UPDATE monuments SET city=?, province=? WHERE name_en LIKE ?",
                 (city, province, pattern))
conn.commit()

print("[OK] Search engine pipeline successfully running on Port 5000!")

# ── HELPERS ───────────────────────────────────────────────────
def clean_location(city, province):
    city     = city     if city     and city     not in ('None','none','') else None
    province = province if province and province not in ('None','none','') else None
    if city and province: return f"{city}, {province}"
    return city or province or "Pakistan"

def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))

def extract_gps(image_path):
    try:
        exif_dict = piexif.load(str(image_path))
        gps = exif_dict.get("GPS", {})
        if not gps: return None, None
        
        required = [
            piexif.GPSIFD.GPSLatitude, piexif.GPSIFD.GPSLatitudeRef,
            piexif.GPSIFD.GPSLongitude, piexif.GPSIFD.GPSLongitudeRef
        ]
        if not all(k in gps for k in required):
            return None, None
            
        def dms(v, ref):
            d = v[0][0]/v[0][1]; m = v[1][0]/v[1][1]; s = v[2][0]/v[2][1]
            val = d + m/60 + s/3600
            return -val if ref in (b"S", b"W") else val
        return dms(gps[2], gps[1]), dms(gps[4], gps[3])
    except: return None, None

def search_by_gps(lat, lon, radius_km=2.0):
    """Find monuments within radius_km of the given coordinates."""
    # 1 degree of latitude is approx 111 km
    delta_lat = radius_km / 111.0
    # 1 degree of longitude is approx 111 * cos(lat) km
    delta_lon = radius_km / (111.0 * math.cos(math.radians(lat)))
    
    rows = conn.execute("""
        SELECT name_en, name_ur, city, province, description, lat, lon, cool_facts
        FROM monuments
        WHERE lat IS NOT NULL AND lon IS NOT NULL
        AND lat BETWEEN ? AND ?
        AND lon BETWEEN ? AND ?
    """, (lat - delta_lat, lat + delta_lat, lon - delta_lon, lon + delta_lon)).fetchall()

    results = []
    for r in rows:
        dist = haversine(lat, lon, r[5], r[6])
        if dist <= radius_km:
            results.append((dist, r))
    results.sort(key=lambda x: x[0])
    return results

def gemini_identify(image_path, lat=None, lon=None):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None
        
    try:
        with open(image_path, "rb") as img_file:
            img_data = base64.b64encode(img_file.read()).decode("utf-8")
            
        coord_hint = ""
        if lat is not None and lon is not None:
            coord_hint = f" The photo GPS coordinates are approximately lat={lat:.4f}, lon={lon:.4f} (Pakistan region)."
            
        prompt = (
            f"Identify the Pakistani monument, landmark, or heritage site in this image.{coord_hint} "
            "Return ONLY valid JSON (no markdown, no backticks) with these exact keys: "
            "\"name_en\" (English name), \"name_ur\" (Urdu name or empty string), "
            "\"city\" (city name), \"province\" (province name), "
            "\"category\" (one of: mosque, fort, tomb, shrine, archaeological, monument, natural, other), "
            "\"description\" (1-2 sentences about this site), "
            "\"cool_facts\" (JSON array of 3 interesting facts or history about this site), "
            "\"confidence\" (float 0.0-1.0 how certain you are). "
            "If you cannot identify the site, set confidence to 0.1 and use your best guess."
        )
        
        # REST API Endpoint for gemini-2.0-flash
        url = f"https://generativelanguage.googleapis.com/v1/models/gemini-2.0-flash:generateContent?key={api_key}"
        
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        {
                            "inlineData": {
                                "mimeType": "image/jpeg",
                                "data": img_data
                            }
                        }
                    ]
                }
            ]
        }
        
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        
        with urllib.request.urlopen(req, timeout=30) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            text = res_data["candidates"][0]["content"]["parts"][0]["text"].strip()
            
            # Clean up markdown formatting if returned
            if text.startswith("```"):
                text = re.sub(r"^```[a-z]*\n?", "", text)
                text = re.sub(r"\n?```$", "", text)
            return json.loads(text.strip())
    except Exception as e:
        print("Gemini API Error:", str(e))
        return None

# ── ROUTES ────────────────────────────────────────────────────
@app.route('/')
def home(): return send_from_directory(".", "index.html")

@app.route('/<path:path>')
def serve_static(path): return send_from_directory(".", path)

@app.route('/api/identify', methods=['POST'])
def identify():
    if 'image' not in request.files:
        return jsonify({"error": "Missing image file"}), 400

    file = request.files['image']
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        file.save(tmp.name); tmp_name = tmp.name

    try:
        lat, lon = extract_gps(tmp_name)
        has_exif = lat is not None
        results  = []
        top_score = 0.5
        method = "gps"

        # ── GPS match ──────────────────────────────────────────
        if has_exif:
            gps_matches = search_by_gps(lat, lon, radius_km=1.0)
            if not gps_matches:
                gps_matches = search_by_gps(lat, lon, radius_km=5.0)
            for dist, row in gps_matches[:3]:
                try:
                    facts = json.loads(row[7]) if row[7] else []
                except:
                    facts = []
                results.append({
                    "name":     row[0], "urdu":     row[1],
                    "location": clean_location(row[2], row[3]),
                    "desc":     row[4],
                    "facts":    facts
                })
            if results:
                top_score = max(0.92 - (gps_matches[0][0] / 10), 0.7)
                method = "gps"

        # ── Gemini Fallback ────────────────────────────────────
        if not results:
            gemini_res = gemini_identify(tmp_name, lat, lon)
            if gemini_res:
                name_en = gemini_res.get("name_en", "Unknown")
                # Try to search the database for a matching name
                db_match = conn.execute(
                    "SELECT description, cool_facts, name_ur, city, province FROM monuments "
                    "WHERE name_en LIKE ? OR name_en LIKE ? LIMIT 1",
                    (name_en, f"%{name_en}%")
                ).fetchone()
                
                if db_match:
                    try:
                        facts = json.loads(db_match[1]) if db_match[1] else []
                    except:
                        facts = []
                    results.append({
                        "name":     name_en,
                        "urdu":     db_match[2] or gemini_res.get("name_ur", ""),
                        "location": clean_location(db_match[3] or gemini_res.get("city"), db_match[4] or gemini_res.get("province")),
                        "desc":     db_match[0] or gemini_res.get("description", ""),
                        "facts":    facts
                    })
                else:
                    facts = gemini_res.get("cool_facts", [])
                    results.append({
                        "name":     name_en,
                        "urdu":     gemini_res.get("name_ur", ""),
                        "location": clean_location(gemini_res.get("city"), gemini_res.get("province")),
                        "desc":     gemini_res.get("description", ""),
                        "facts":    facts
                    })
                top_score = gemini_res.get("confidence", 0.5)
                method = "gemini"

        # ── Fallback if no GPS, no Gemini API Key, or Gemini failed ────────────────
        if not results:
            # Let's check if the API key is set
            if not os.environ.get("GEMINI_API_KEY"):
                return jsonify({
                    "success": False,
                    "error": "No GPS metadata found in photo, and Gemini API is not configured. Please upload a geotagged photo, or add your GEMINI_API_KEY to a .env file to enable visual AI identification."
                }), 400
                
            # If key is set but failed
            rows = conn.execute(
                "SELECT name_en, name_ur, city, province, description, cool_facts FROM monuments "
                "WHERE city IS NOT NULL AND category IN ('mosque','fort','monument','museum') LIMIT 3"
            ).fetchall()
            results = []
            for r in rows:
                try:
                    facts = json.loads(r[5]) if r[5] else []
                except:
                    facts = []
                results.append({
                    "name":     r[0], "urdu":     r[1],
                    "location": clean_location(r[2], r[3]),
                    "desc":     r[4],
                    "facts":    facts
                })
            method = "fallback"

        if method == "gps":
            confidence = "🟢 GPS Match"
        elif method == "gemini":
            confidence = "🟢 Gemini AI Match"
        else:
            confidence = "🟡 Database Fallback"

        return jsonify({"success": True, "confidence": confidence,
                        "score": round(min(top_score, 0.99), 2),
                        "has_exif": has_exif, "results": results})

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if os.path.exists(tmp_name): os.unlink(tmp_name)

# ── AUTO-OPEN BROWSER ─────────────────────────────────────────
def open_browser(): webbrowser.open("http://127.0.0.1:5000")

if __name__ == '__main__':
    threading.Timer(1.5, open_browser).start()
    app.run(port=5000, debug=False)
