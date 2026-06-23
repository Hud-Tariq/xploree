# Xplore — Geolocation & Heritage Identification System for Pakistan

**Xplore** is a geolocation-based web application designed to archive, identify, and catalog cultural heritage monuments and landmarks across Pakistan. By extracting GPS coordinate metadata (EXIF) from uploaded photos and using spatial indexing, it identifies landmarks instantly and serves comprehensive descriptions and interesting historical facts.

---

## 🚀 Key Features

1. **Instant GPS Geolocation Match:** Matches photo coordinates against a database of **8,279 Pakistani monuments** using a fast, haversine-based `BallTree` spatial index (resolves in <10ms).
2. **Visual AI Fallback:** If a photo lacks embedded GPS tags, the app falls back to visual recognition using the **Google Gemini 2.0 Flash API**.
3. **100% Pre-Populated Archive:** Sourced using parallel Wikipedia page summary scraping and an offline deterministic category-based template engine. Every monument has a unique description and 3 "cool facts" stored statically in the database.
4. **Retro Journal & Album Interface:** A premium, warm-parchment journal interface. Waved polaroid grids save successful matches to a persistent journal/memory album utilizing `localStorage`.

---

## 📂 Project Structure

```text
├── phase_b_data/
│   ├── monuments.db        # SQLite database populated with 8,279 Pakistani monuments
│   └── balltree.pkl        # Serialized BallTree spatial index for fast distance queries
├── test_images/            # 10 downloaded and geotagged JPG images for verification
├── phase1.ipynb            # Phase 1: OSM parsing, Wikidata queries & Wikipedia scraping
├── phase2.ipynb            # Phase 2: Database coordinate cleaning & BallTree generation
├── phase3.ipynb            # Phase 3: Zero-dependency retrieval pipeline simulations
├── app.py                  # Runtime Flask backend serving REST API endpoints
├── index.html              # Landing page
├── identify.html           # File upload / drag-and-drop page
├── discovery.html          # Identification results card (details, map context & cool facts)
├── memories.html           # Memory album and journal drawer listing
├── profile.html            # User profile and stats ledger
├── transitions.js/css      # Page transitions and core Parchment style definitions
└── README.md               # Project documentation
```

---

## 🛠️ Main Techniques & Libraries

* **Backend Web Server:** Flask & Flask-CORS (REST API endpoints).
* **Spatial Query Engine:** Scikit-Learn (`BallTree` utilizing Haversine distance), NumPy, and Pickle.
* **Geotag Extraction:** `piexif` (EXIF header parser) and `Pillow` (PIL) for image verification.
* **Database Management:** SQLite3.
* **AI Integration:** Google Gemini 2.0 Flash REST API (Visual recognition).

---

## ⚡ Setup & Installation

### 1. Install Dependencies
Ensure you have Python 3.11+ installed. Open your terminal in the project directory and install the required libraries:
```bash
pip install flask flask-cors piexif pillow numpy scikit-learn
```

### 2. Configure Gemini API Key (Optional Fallback)
If you want to use the visual AI recognition fallback (for photos without GPS coordinates), create a file named `.env` in the project root and add your Gemini API Key:
```text
GEMINI_API_KEY=your_gemini_api_key_here
```

### 3. Run the Backend Server
Start the Flask backend:
```bash
python app.py
```
The application will automatically open in your browser. If it doesn't, navigate to:
👉 **[http://127.0.0.1:5000](http://127.0.0.1:5000)**

---

## 🧪 Testing with Geotagged Images

We have pre-configured 10 test images inside the `test_images/` folder representing famous landmarks in Karachi, Lahore, Islamabad, Multan, and Peshawar. These images are pre-geotagged with coordinates matching the database.

**How to test:**
1. Navigate to the **Identify** section in the app.
2. Drag and drop (or click to upload) any image from the `test_images/` folder.
3. Click **Identify Monument**.
4. The server will extract the GPS tags and return the correct landmark card, complete with a custom description and 3 cool facts!

---

## 📐 Development Phases (Jupyter Notebooks)

1. **[Phase 1 (Data Pipeline)](file:///c:/Users/ALLI/Documents/Personal/xploree/phase1.ipynb):** Sourced raw geographical nodes from OpenStreetMap (Pakistan region PBF) and matched them against Wikidata entries. Scrapes Wikipedia using parallel thread workers and generates template-based descriptions/facts to build the main database.
2. **[Phase 2 (Coordinate Indexing)](file:///c:/Users/ALLI/Documents/Personal/xploree/phase2.ipynb):** Cleans out-of-bounds coordinate anomalies and builds a haversine `BallTree` spatial index file (`balltree.pkl`).
3. **[Phase 3 (Retrieval Pipeline)](file:///c:/Users/ALLI/Documents/Personal/xploree/phase3.ipynb):** Simulates the zero-dependency geotag extraction, BallTree querying, and fallback Gemini visual identification pipeline.
