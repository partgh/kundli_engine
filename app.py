from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import swisseph as swe
from datetime import datetime, timedelta
import requests
import os
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

app = FastAPI(title="Kundli API", version="6.1")

# ───────────────────────────────
# ✅ Enable CORS
# ───────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ───────────────────────────────
# Helper Functions
# ───────────────────────────────

def get_city_location(city_name: str):
    """Fetch latitude & longitude for given city"""
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
    """Return zodiac sign & lord"""
    rashis = ["Aries","Taurus","Gemini","Cancer","Leo","Virgo","Libra",
              "Scorpio","Sagittarius","Capricorn","Aquarius","Pisces"]
    lords = ["Mars","Venus","Mercury","Moon","Sun","Mercury","Venus",
             "Mars","Jupiter","Saturn","Saturn","Jupiter"]
    sign_index = int(longitude // 30) % 12
    return rashis[sign_index], lords[sign_index]


def get_kp_lords(longitude):
    """Return KP star & sub lord"""
    nakshatra_lords = ["Ketu","Venus","Sun","Moon","Mars","Rahu","Jupiter","Saturn","Mercury"]
    nak_index = int((longitude % 360) / (13.3333 / 9)) % 9
    star_lord = nakshatra_lords[nak_index]
    sub_lord = nakshatra_lords[(nak_index + 3) % 9]
    return star_lord, sub_lord


# ───────────────────────────────
# Routes
# ───────────────────────────────

@app.get("/")
def home():
    return {"message": "🔮 Kundli API v6.1 with Full Dasha, KP, Divisional, Transit Charts running!"}


# ─────────────── /city ───────────────
@app.get("/city")
def city_lookup(city: str):
    location = get_city_location(city)
    if not location:
        return {"error": "City not found."}
    return location


# ─────────────── /kundli ───────────────
@app.get("/kundli")
def kundli(y: int, m: int, d: int, hr: int, mn: int, city: str, tz: float):
    location = get_city_location(city)
    if not location:
        return {"error": "Invalid city."}

    lat, lon = location["Latitude"], location["Longitude"]
    utc_time = datetime(y, m, d, hr, mn) - timedelta(hours=tz)
    jd = swe.julday(utc_time.year, utc_time.month, utc_time.day, utc_time.hour + utc_time.minute / 60)

    houses, ascmc = swe.houses(jd, lat, lon)
    ascendant = round(ascmc[0], 2)

    planets = {
        "Sun": swe.SUN, "Moon": swe.MOON, "Mars": swe.MARS,
        "Mercury": swe.MERCURY, "Jupiter": swe.JUPITER,
        "Venus": swe.VENUS, "Saturn": swe.SATURN,
        "Rahu": swe.MEAN_NODE, "Ketu": swe.MEAN_NODE
    }

    planet_data = {}
    for p, const in planets.items():
        lon_val, _ = swe.calc_ut(jd, const)
        lon_val = lon_val[0] if isinstance(lon_val, tuple) else lon_val
        if p == "Ketu":
            lon_val = (lon_val + 180) % 360
        rashi, lord = get_rashi_lord(lon_val)
        planet_data[p] = {"longitude": round(lon_val, 2), "rashi": rashi, "lord": lord}

    house_data = {}
    for i, h in enumerate(houses, 1):
        rashi, lord = get_rashi_lord(h)
        house_data[f"House_{i}"] = {"degree": round(h, 2), "rashi": rashi, "lord": lord}

    return {
        "Local_Time_IST": f"{y}-{m:02d}-{d:02d} {hr:02d}:{mn:02d}",
        "UTC_Time": utc_time.strftime("%Y-%m-%d %H:%M:%S"),
        "Julian_Day": jd,
        "Ascendant": ascendant,
        "Planets": planet_data,
        "Houses": house_data
    }


# ─────────────── /kp_kundli ───────────────
@app.get("/kp_kundli")
def kp_kundli(y: int, m: int, d: int, hr: int, mn: int, city: str, tz: float):
    location = get_city_location(city)
    if not location:
        return {"error": "Invalid city."}
    lat, lon = location["Latitude"], location["Longitude"]
    utc_time = datetime(y, m, d, hr, mn) - timedelta(hours=tz)
    jd = swe.julday(utc_time.year, utc_time.month, utc_time.day,
                    utc_time.hour + utc_time.minute / 60)

    planets = {"Sun": swe.SUN, "Moon": swe.MOON, "Mars": swe.MARS,
               "Mercury": swe.MERCURY, "Jupiter": swe.JUPITER,
               "Venus": swe.VENUS, "Saturn": swe.SATURN,
               "Rahu": swe.MEAN_NODE, "Ketu": swe.MEAN_NODE}

    kp_planets, kp_houses = {}, {}
    for p, const in planets.items():
        lon_val, _ = swe.calc_ut(jd, const)
        lon_val = lon_val[0] if isinstance(lon_val, tuple) else lon_val
        if p == "Ketu": lon_val = (lon_val + 180) % 360
        rashi, lord = get_rashi_lord(lon_val)
        star, sub = get_kp_lords(lon_val)
        kp_planets[p] = {"Longitude": round(lon_val, 2), "Rashi": rashi,
                         "Sign_Lord": lord, "Star_Lord": star, "Sub_Lord": sub}

    houses, _ = swe.houses(jd, lat, lon)
    for i, h in enumerate(houses, 1):
        rashi, lord = get_rashi_lord(h)
        star, sub = get_kp_lords(h)
        kp_houses[f"House_{i}"] = {"Degree": round(h, 2), "Rashi": rashi,
                                   "Sign_Lord": lord, "Star_Lord": star, "Sub_Lord": sub}
    return {"KP_Planets": kp_planets, "KP_Houses": kp_houses}


# ─────────────── /dasha_full ───────────────
@app.get("/dasha_full")
def dasha_full(y: int, m: int, d: int, hr: int, mn: int, city: str, tz: float):
    location = get_city_location(city)
    if not location:
        return {"error": "Invalid city"}
    lat, lon = location["Latitude"], location["Longitude"]
    utc_time = datetime(y, m, d, hr, mn) - timedelta(hours=tz)
    jd = swe.julday(utc_time.year, utc_time.month, utc_time.day,
                    utc_time.hour + utc_time.minute / 60)

    moon_lon, _ = swe.calc_ut(jd, swe.MOON)
    moon_lon = moon_lon[0] if isinstance(moon_lon, tuple) else moon_lon
    nak_lords = ["Ketu","Venus","Sun","Moon","Mars","Rahu","Jupiter","Saturn","Mercury"]
    nak_index = int((moon_lon % 360) / 13.3333)
    moon_lord = nak_lords[nak_index % 9]
    dasha_order = nak_lords[nak_lords.index(moon_lord):] + nak_lords[:nak_lords.index(moon_lord)]
    years_table = {"Ketu":7,"Venus":20,"Sun":6,"Moon":10,"Mars":7,"Rahu":18,"Jupiter":16,"Saturn":19,"Mercury":17}

    start_date = datetime(y, m, d, hr, mn)
    maha_list = []

    for lord in dasha_order:
        maha_years = years_table[lord]
        end_date = start_date + timedelta(days=maha_years * 365.25)
        antar_list = []
        antar_start = start_date

        for sublord in dasha_order:
            antar_duration = maha_years * (years_table[sublord] / 120)
            antar_end = antar_start + timedelta(days=antar_duration * 365.25)
            antar_list.append({
                "Antar_Lord": sublord,
                "Start": antar_start.date(),
                "End": antar_end.date()
            })
            antar_start = antar_end

        maha_list.append({
            "Maha_Lord": lord,
            "Start": start_date.date(),
            "End": end_date.date(),
            "Antar_Dasha": antar_list
        })
        start_date = end_date

    return {"Nakshatra_Lord": moon_lord, "Full_Vimshottari_Dasha": maha_list}


# ─────────────── /divisional_chart ───────────────
@app.get("/divisional_chart")
def divisional_chart(y: int, m: int, d: int, hr: int, mn: int, city: str, tz: float, type: str = "D9"):
    divisions = {"D9": 9, "D10": 10, "D7": 7, "D12": 12}
    div = divisions.get(type.upper(), 9)
    division_size = 30 / div
    rashis = ["Aries","Taurus","Gemini","Cancer","Leo","Virgo","Libra",
              "Scorpio","Sagittarius","Capricorn","Aquarius","Pisces"]

    location = get_city_location(city)
    if not location:
        return {"error": "Invalid city"}
    lat, lon = location["Latitude"], location["Longitude"]
    utc_time = datetime(y, m, d, hr, mn) - timedelta(hours=tz)
    jd = swe.julday(utc_time.year, utc_time.month, utc_time.day,
                    utc_time.hour + utc_time.minute / 60)

    planets = {"Sun": swe.SUN, "Moon": swe.MOON, "Mars": swe.MARS,
               "Mercury": swe.MERCURY, "Jupiter": swe.JUPITER,
               "Venus": swe.VENUS, "Saturn": swe.SATURN,
               "Rahu": swe.MEAN_NODE, "Ketu": swe.MEAN_NODE}

    chart = {}
    for p, planet_const in planets.items():
        lon_val, _ = swe.calc_ut(jd, planet_const)
        lon_val = lon_val[0] if isinstance(lon_val, tuple) else lon_val
        if p == "Ketu": lon_val = (lon_val + 180) % 360
        sign_index = int(lon_val // 30)
        div_no = int((lon_val % 30) / division_size)
        div_rashi_index = (sign_index * div + div_no) % 12
        chart[p] = {"Longitude": round(lon_val, 2),
                    "Division_No": div_no + 1,
                    "Divisional_Rashi": rashis[div_rashi_index]}
    return {"Type": type.upper(), "Chart": chart}


# ─────────────── /transit_chart ───────────────
@app.get("/transit_chart")
def transit_chart(y: int, m: int, d: int, hr: int, mn: int, city: str, tz: float):
    natal = kundli(y, m, d, hr, mn, city, tz)
    now = datetime.utcnow()
    jd_now = swe.julday(now.year, now.month, now.day, now.hour + now.minute / 60)

    planets = {"Sun": swe.SUN, "Moon": swe.MOON, "Mars": swe.MARS,
               "Mercury": swe.MERCURY, "Jupiter": swe.JUPITER,
               "Venus": swe.VENUS, "Saturn": swe.SATURN,
               "Rahu": swe.MEAN_NODE, "Ketu": swe.MEAN_NODE}

    transit_data = {}
    for p, const in planets.items():
        lon_val, _ = swe.calc_ut(jd_now, const)
        lon_val = lon_val[0] if isinstance(lon_val, tuple) else lon_val
        if p == "Ketu": lon_val = (lon_val + 180) % 360
        rashi, _ = get_rashi_lord(lon_val)
        natal_rashi = natal["Planets"][p]["rashi"]
        transit_data[p] = {"Transit_Longitude": round(lon_val, 2),
                           "Transit_Rashi": rashi,
                           "Natal_Rashi": natal_rashi}
    return {"Transit_Date": now.strftime("%Y-%m-%d %H:%M:%S"), "Transit": transit_data}


# ─────────────── /pdf_kundli ───────────────
@app.get("/pdf_kundli")
def generate_pdf(y: int, m: int, d: int, hr: int, mn: int, city: str, tz: float):
    location = get_city_location(city)
    if not location:
        return {"error": "Invalid city"}
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
