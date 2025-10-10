from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import swisseph as swe
from datetime import datetime, timedelta
import requests
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

app = FastAPI(title="Kundli API", version="5.1")

# ───────────────────────────────
# ✅ Enable CORS for frontend access
# ───────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # allow all origins for frontend access
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ───────────────────────────────
# 🔹 Helper Functions
# ───────────────────────────────

def get_city_location(city_name: str):
    """Fetch latitude & longitude for a city using OpenCage API"""
    api_key = "a2392dd959374245a15a09595501b3c9"
    url = f"https://api.opencagedata.com/geocode/v1/json?q={city_name}&key={api_key}"
    response = requests.get(url).json()
    if response.get("results"):
        location = response["results"][0]["geometry"]
        formatted = response["results"][0]["formatted"]
        return {
            "City": city_name,
            "Formatted_Location": formatted,
            "Latitude": location["lat"],
            "Longitude": location["lng"]
        }
    return None


def get_rashi_lord(longitude):
    """Return zodiac sign and its lord"""
    rashis = [
        "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
        "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"
    ]
    lords = [
        "Mars", "Venus", "Mercury", "Moon", "Sun", "Mercury",
        "Venus", "Mars", "Jupiter", "Saturn", "Saturn", "Jupiter"
    ]
    sign_index = int((longitude % 360) // 30)
    return rashis[sign_index], lords[sign_index]


def get_kp_lords(longitude):
    """Return KP Star Lord and Sub Lord (simplified)"""
    nakshatra_lords = ["Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury"]
    total_deg = longitude % 360
    nak_index = int((total_deg / 13.3333)) % 9
    star_lord = nakshatra_lords[nak_index]
    sub_lord = nakshatra_lords[(nak_index + 3) % 9]
    return star_lord, sub_lord

# ───────────────────────────────
# 🔹 Endpoints
# ───────────────────────────────

@app.get("/")
def home():
    return {"message": "🔮 Kundli Engine API is Running Successfully!"}


@app.get("/city")
def city_lookup(city: str):
    """Get latitude and longitude by city"""
    location = get_city_location(city)
    if not location:
        return {"error": "City not found."}
    return location


@app.get("/kundli")
def kundli(y: int, m: int, d: int, hr: int, mn: int, city: str, tz: float):
    """Generate kundli planetary and house details"""
    location = get_city_location(city)
    if not location:
        return {"error": "Invalid city or location not found."}

    lat, lon = location["Latitude"], location["Longitude"]

    # ✅ Timezone and precision fix
    utc_time = datetime(y, m, d, hr, mn) - timedelta(hours=float(tz))
    jd = swe.julday(
        utc_time.year,
        utc_time.month,
        utc_time.day,
        utc_time.hour + utc_time.minute / 60 + utc_time.second / 3600
    )

    # ✅ Houses & Ascendant calculation
    houses, ascmc = swe.houses(jd, lat, lon)
    ascendant = round(ascmc[0], 2)

    # ✅ Planets (with accurate Rahu-Ketu correction)
    planets = {
        "Sun": swe.SUN,
        "Moon": swe.MOON,
        "Mars": swe.MARS,
        "Mercury": swe.MERCURY,
        "Jupiter": swe.JUPITER,
        "Venus": swe.VENUS,
        "Saturn": swe.SATURN,
        "Rahu": swe.MEAN_NODE,
        "Ketu": swe.MEAN_NODE
    }

    planet_data = {}
    for p, planet_const in planets.items():
        lon_val, _ = swe.calc_ut(jd, planet_const)
        lon_val = lon_val[0] if isinstance(lon_val, tuple) else lon_val
        if p == "Ketu":
            lon_val = (lon_val + 180) % 360
        rashi, lord = get_rashi_lord(lon_val)
        planet_data[p] = {
            "longitude": round(lon_val, 2),
            "rashi": rashi,
            "lord": lord
        }

    # ✅ Houses Data
    house_data = {}
    for i, h in enumerate(houses, 1):
        rashi, lord = get_rashi_lord(h)
        house_data[f"House_{i}"] = {
            "degree": round(h, 2),
            "rashi": rashi,
            "lord": lord
        }

    return {
        "Local_Time_IST": f"{y}-{m:02d}-{d:02d} {hr:02d}:{mn:02d}",
        "UTC_Time": utc_time.strftime("%Y-%m-%d %H:%M:%S"),
        "Julian_Day": jd,
        "Ascendant": ascendant,
        "Planets": planet_data,
        "Houses": house_data
    }


@app.get("/dasha")
def dasha(y: int, m: int, d: int, hr: int, mn: int, city: str, tz: float):
    """Generate Vimshottari Dasha periods"""
    location = get_city_location(city)
    if not location:
        return {"error": "Invalid city or location not found."}

    lat, lon = location["Latitude"], location["Longitude"]
    utc_time = datetime(y, m, d, hr, mn) - timedelta(hours=float(tz))
    jd = swe.julday(utc_time.year, utc_time.month, utc_time.day,
                    utc_time.hour + utc_time.minute / 60)

    moon_lon, _ = swe.calc_ut(jd, swe.MOON)
    moon_lon = moon_lon[0] if isinstance(moon_lon, tuple) else moon_lon

    nak_index = int((moon_lon % 360) / 13.3333)
    nak_lords = ["Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury"]
    moon_lord = nak_lords[nak_index % 9]
    dasha_order = nak_lords[nak_lords.index(moon_lord):] + nak_lords[:nak_lords.index(moon_lord)]

    base_date = datetime(y, m, d, hr, mn)
    vim_dasha = []
    start_date = base_date
    for lord in dasha_order:
        years = {"Ketu": 7, "Venus": 20, "Sun": 6, "Moon": 10, "Mars": 7, "Rahu": 18, "Jupiter": 16, "Saturn": 19, "Mercury": 17}[lord]
        end_date = start_date + timedelta(days=years * 365.25)
        vim_dasha.append({
            "Planet": lord,
            "Start_Date": start_date.date(),
            "End_Date": end_date.date(),
            "Years": years
        })
        start_date = end_date

    return {
        "Birth_Moon_Longitude": round(moon_lon, 2),
        "Nakshatra_Lord": moon_lord,
        "Vimshottari_Dasha": vim_dasha
    }


@app.get("/kp_kundli")
def kp_kundli(y: int, m: int, d: int, hr: int, mn: int, city: str, tz: float):
    """Generate KP Kundli with Sign, Star, Sub Lords"""
    location = get_city_location(city)
    if not location:
        return {"error": "Invalid city or location not found."}

    lat, lon = location["Latitude"], location["Longitude"]
    utc_time = datetime(y, m, d, hr, mn) - timedelta(hours=float(tz))
    jd = swe.julday(utc_time.year, utc_time.month, utc_time.day,
                    utc_time.hour + utc_time.minute / 60)

    planets = {
        "Sun": swe.SUN,
        "Moon": swe.MOON,
        "Mars": swe.MARS,
        "Mercury": swe.MERCURY,
        "Jupiter": swe.JUPITER,
        "Venus": swe.VENUS,
        "Saturn": swe.SATURN,
        "Rahu": swe.MEAN_NODE,
        "Ketu": swe.MEAN_NODE
    }

    kp_planets = {}
    for p, planet_const in planets.items():
        lon_val, _ = swe.calc_ut(jd, planet_const)
        lon_val = lon_val[0] if isinstance(lon_val, tuple) else lon_val
        if p == "Ketu":
            lon_val = (lon_val + 180) % 360
        rashi, sign_lord = get_rashi_lord(lon_val)
        star_lord, sub_lord = get_kp_lords(lon_val)
        kp_planets[p] = {
            "Longitude": round(lon_val, 2),
            "Rashi": rashi,
            "Sign_Lord": sign_lord,
            "Star_Lord": star_lord,
            "Sub_Lord": sub_lord
        }

    houses, ascmc = swe.houses(jd, lat, lon)
    kp_houses = {}
    for i, h in enumerate(houses, 1):
        rashi, sign_lord = get_rashi_lord(h)
        star_lord, sub_lord = get_kp_lords(h)
        kp_houses[f"House_{i}"] = {
            "Degree": round(h, 2),
            "Rashi": rashi,
            "Sign_Lord": sign_lord,
            "Star_Lord": star_lord,
            "Sub_Lord": sub_lord
        }

    return {
        "Local_Time_IST": f"{y}-{m:02d}-{d:02d} {hr:02d}:{mn:02d}",
        "KP_Planets": kp_planets,
        "KP_Houses": kp_houses
    }


@app.get("/pdf_kundli")
def generate_pdf(y: int, m: int, d: int, hr: int, mn: int, city: str, tz: float):
    """Generate downloadable PDF Kundli report"""
    location = get_city_location(city)
    if not location:
        return {"error": "Invalid city or location not found."}

    lat, lon = location["Latitude"], location["Longitude"]
    kundli_data = kundli(y, m, d, hr, mn, city, tz)
    file_path = f"kundli_report_{city}.pdf"

    c = canvas.Canvas(file_path, pagesize=A4)
    c.setFont("Helvetica", 12)
    c.drawString(50, 800, f"Kundli Report - City: {city}")
    c.drawString(50, 780, f"Date & Time (Local): {kundli_data['Local_Time_IST']}")
    c.drawString(50, 760, f"Lat: {lat}, Lon: {lon}, TZ: {tz}")
    c.drawString(50, 740, "Planetary Details:")
    y_pos = 720
    for p, data in kundli_data["Planets"].items():
        c.drawString(60, y_pos, f"{p} → {data['rashi']} | Lon: {data['longitude']}° | Lord: {data['lord']}")
        y_pos -= 20

    y_pos -= 10
    c.drawString(50, y_pos, "House Details:")
    y_pos -= 20
    for h, data in kundli_data["Houses"].items():
        c.drawString(60, y_pos, f"{h} → {data['rashi']} | Deg: {data['degree']}° | Lord: {data['lord']}")
        y_pos -= 20

    c.save()
    return FileResponse(file_path, media_type='application/pdf', filename=file_path)
