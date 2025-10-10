from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import swisseph as swe
from datetime import datetime, timedelta
import requests
import os
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

app = FastAPI(title="Kundli API", version="5.1")

# ---------- CORS ----------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Helpers ----------
OPENCAGE_KEY = "a2392dd959374245a15a09595501b3c9"

def get_city_location(city_name: str):
    url = f"https://api.opencagedata.com/geocode/v1/json?q={city_name}&key={OPENCAGE_KEY}"
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
    except Exception:
        return None
    data = r.json()
    if not data.get("results"):
        return None
    geom = data["results"][0]["geometry"]
    formatted = data["results"][0].get("formatted", city_name)
    return {"City": city_name, "Formatted_Location": formatted, "Latitude": geom["lat"], "Longitude": geom["lng"]}

# Vimshottari constants
VIM_ORDER = ["Ketu","Venus","Sun","Moon","Mars","Rahu","Jupiter","Saturn","Mercury"]
VIM_YEARS = {"Ketu":7,"Venus":20,"Sun":6,"Moon":10,"Mars":7,"Rahu":18,"Jupiter":16,"Saturn":19,"Mercury":17}
TOTAL_VIM = sum(VIM_YEARS.values())  # should be 120

def normalize_deg(d):
    d = float(d) % 360.0
    if d < 0:
        d += 360.0
    return d

def get_rashi_from_long(longitude):
    # 0-30 Aries, 30-60 Taurus ... (we'll return index + 1 if needed)
    lon = normalize_deg(longitude)
    idx = int(lon // 30) % 12
    rashis = ["Aries","Taurus","Gemini","Cancer","Leo","Virgo","Libra","Scorpio","Sagittarius","Capricorn","Aquarius","Pisces"]
    return rashis[idx], idx+1

# ---------- Dasha calculation functions ----------

def compute_vimshottari_full(moon_longitude, birth_dt):
    """
    Returns nested Vimshottari structure:
    - Finds moon nakshatra lord (current Maha)
    - Calculates remaining of current Maha at birth
    - Builds sequence of Maha -> Antar -> Pratyantar with start/end dates
    """
    moon_lon = normalize_deg(moon_longitude)

    # Nakshatra index and fraction inside nakshatra
    # 27 nakshatras, each 13°20' = 13.333333... deg
    nak_deg = 13.333333333333334
    nak_index = int(moon_lon // nak_deg)  # 0..26
    # fraction within natal nakshatra measured from start of that nakshatra
    start_of_nak = nak_index * nak_deg
    frac_in_nak = (moon_lon - start_of_nak) / nak_deg  # 0..1

    # Lord of the nakshatra: mapping of 27 nakshatras to Vimshottari order repeated
    # Standard mapping: Ketu,Venus,Sun,Moon,Mars,Rahu,Jupiter,Saturn,Mercury repeat...
    # So nakshatra_lord_index = nak_index % 9 -> pick from VIM_ORDER
    nak_lord = VIM_ORDER[nak_index % 9]

    # Current Maha planet at birth is nak_lord
    current_maha = nak_lord
    # fraction of Maha elapsed = frac_in_nak (since nakshatra progress maps to maha progress)
    # remaining portion (of the Maha) = (1 - frac_in_nak)
    # remaining years in current Maha at birth:
    maha_total_years = VIM_YEARS[current_maha]
    remaining_current_maha_years = (1.0 - frac_in_nak) * maha_total_years

    # Build Maha sequence starting from current_maha
    start_idx = VIM_ORDER.index(current_maha)
    maha_sequence = VIM_ORDER[start_idx:] + VIM_ORDER[:start_idx]

    results = []
    # Start from birth_dt: the remainder of current Maha runs from birth to birth + remaining_current_maha_years
    maha_start = birth_dt
    maha_end = birth_dt + timedelta(days=remaining_current_maha_years * 365.25)
    # For the current maha we treat start_date as birth (we are giving remaining forward durations).
    # If you want full maha history (past), additional logic required.
    for i, maha in enumerate(maha_sequence):
        if i == 0:
            years = remaining_current_maha_years
            start = maha_start
            end = maha_end
        else:
            years = VIM_YEARS[maha]
            start = results[-1]["End_Date"]  # previous end is next start
            end = start + timedelta(days=years * 365.25)

        # Now compute Antardashas inside this maha
        antars = []
        antar_start = start
        for antar_planet in VIM_ORDER:
            antar_years = years * (VIM_YEARS[antar_planet] / TOTAL_VIM)
            antar_end = antar_start + timedelta(days=antar_years * 365.25)

            # Compute pratyantar subdivisions inside this antar
            pratyantars = []
            praty_start = antar_start
            for praty_planet in VIM_ORDER:
                praty_years = antar_years * (VIM_YEARS[praty_planet] / TOTAL_VIM)
                praty_end = praty_start + timedelta(days=praty_years * 365.25)
                pratyantars.append({
                    "Planet": praty_planet,
                    "Start_Date": praty_start.date().isoformat(),
                    "End_Date": praty_end.date().isoformat(),
                    "Years": round(praty_years, 6)
                })
                praty_start = praty_end

            antars.append({
                "Planet": antar_planet,
                "Start_Date": antar_start.date().isoformat(),
                "End_Date": antar_end.date().isoformat(),
                "Years": round(antar_years, 6),
                "Pratyantar": pratyantars
            })

            antar_start = antar_end

        results.append({
            "Planet": maha,
            "Start_Date": start.date().isoformat(),
            "End_Date": end.date().isoformat(),
            "Years": round(years, 6),
            "Antar": antars
        })

    return {
        "Moon_Longitude": round(moon_lon, 6),
        "Nakshatra_Index": nak_index,
        "Nakshatra_Lord": nak_lord,
        "MahaSequenceStartFrom": current_maha,
        "Vimshottari": results
    }

# ---------- Endpoints ----------

@app.get("/")
def home():
    return {"message": "Kundli Engine API running (with full Vimshottari support)."}

@app.get("/city")
def city_lookup(city: str):
    loc = get_city_location(city)
    if not loc:
        raise HTTPException(status_code=404, detail="City not found")
    return loc

@app.get("/kundli")
def kundli(y: int, m: int, d: int, hr: int, mn: int, city: str, tz: float):
    loc = get_city_location(city)
    if not loc:
        raise HTTPException(status_code=400, detail="Invalid city")
    lat, lon = loc["Latitude"], loc["Longitude"]

    # Convert local time (tz offset hours) to UTC datetime
    local_dt = datetime(y, m, d, hr, mn)
    utc_dt = local_dt - timedelta(hours=tz)
    jd = swe.julday(utc_dt.year, utc_dt.month, utc_dt.day, utc_dt.hour + utc_dt.minute/60.0)

    houses, ascmc = swe.houses(jd, lat, lon)
    ascendant = round(ascmc[0], 4)

    planet_consts = {
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
    for pname, pconst in planet_consts.items():
        lon_val, _ = swe.calc_ut(jd, pconst)
        lon_val = lon_val[0] if isinstance(lon_val, tuple) else lon_val
        if pname == "Ketu":
            lon_val = (lon_val + 180.0) % 360.0
        rashi, _ = get_rashi_from_long(lon_val)
        planet_data[pname] = {"longitude": round(lon_val, 6), "rashi": rashi}

    house_data = {}
    for i, hdeg in enumerate(houses, 1):
        rashi, _ = get_rashi_from_long(hdeg)
        house_data[f"House_{i}"] = {"degree": round(hdeg % 360.0, 6), "rashi": rashi}

    return {
        "Local_Time_IST": local_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "UTC_Time": utc_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "Julian_Day": jd,
        "Ascendant": ascendant,
        "Planets": planet_data,
        "Houses": house_data
    }

@app.get("/dasha")
def dasha_simple(y: int, m: int, d: int, hr: int, mn: int, city: str, tz: float):
    """
    Backwards-compatible simpler output: returns top-level Vimshottari (Maha list)
    Use /dasha_full for full nested Antars & Pratyantars
    """
    loc = get_city_location(city)
    if not loc:
        raise HTTPException(status_code=400, detail="Invalid city")
    lat, lon = loc["Latitude"], loc["Longitude"]
    local_dt = datetime(y, m, d, hr, mn)
    utc_dt = local_dt - timedelta(hours=tz)
    jd = swe.julday(utc_dt.year, utc_dt.month, utc_dt.day, utc_dt.hour + utc_dt.minute/60.0)
    moon_lon, _ = swe.calc_ut(jd, swe.MOON)
    moon_lon = moon_lon[0] if isinstance(moon_lon, tuple) else moon_lon

    full = compute_vimshottari_full(moon_lon, local_dt)
    # Provide a summarized view (top-level only)
    summary = []
    for m in full["Vimshottari"]:
        summary.append({
            "Planet": m["Planet"],
            "Start_Date": m["Start_Date"],
            "End_Date": m["End_Date"],
            "Years": m["Years"]
        })
    return {"Birth_Moon_Longitude": round(full["Moon_Longitude"],6), "Nakshatra_Lord": full["Nakshatra_Lord"], "Vimshottari_Summary": summary}

@app.get("/dasha_full")
def dasha_full(y: int, m: int, d: int, hr: int, mn: int, city: str, tz: float):
    loc = get_city_location(city)
    if not loc:
        raise HTTPException(status_code=400, detail="Invalid city")
    lat, lon = loc["Latitude"], loc["Longitude"]
    local_dt = datetime(y, m, d, hr, mn)
    utc_dt = local_dt - timedelta(hours=tz)
    jd = swe.julday(utc_dt.year, utc_dt.month, utc_dt.day, utc_dt.hour + utc_dt.minute/60.0)
    moon_lon, _ = swe.calc_ut(jd, swe.MOON)
    moon_lon = moon_lon[0] if isinstance(moon_lon, tuple) else moon_lon

    full = compute_vimshottari_full(moon_lon, local_dt)
    return full

# PDF endpoint (unchanged behavior)
@app.get("/pdf_kundli")
def generate_pdf(y: int, m: int, d: int, hr: int, mn: int, city: str, tz: float):
    loc = get_city_location(city)
    if not loc:
        raise HTTPException(status_code=400, detail="Invalid city")
    kund = kundli(y, m, d, hr, mn, city, tz)  # reuse kundli endpoint logic
    file_path = f"kundli_report_{city}.pdf"
    c = canvas.Canvas(file_path, pagesize=A4)
    c.setFont("Helvetica", 12)
    c.drawString(50, 800, f"Kundli Report - City: {city}")
    c.drawString(50, 780, f"Date & Time (Local): {kund['Local_Time_IST']}")
    c.drawString(50, 760, f"Lat: {loc['Latitude']}, Lon: {loc['Longitude']}, TZ: {tz}")
    c.drawString(50, 740, "Planetary Details:")
    y_pos = 720
    for p, data in kund["Planets"].items():
        c.drawString(60, y_pos, f"{p} → {data['rashi']} | Lon: {data['longitude']}°")
        y_pos -= 18
    y_pos -= 10
    c.drawString(50, y_pos, "House Details:")
    y_pos -= 20
    for h, data in kund["Houses"].items():
        c.drawString(60, y_pos, f"{h} → {data['rashi']} | Deg: {data['degree']}°")
        y_pos -= 18
    c.save()
    return FileResponse(file_path, media_type='application/pdf', filename=file_path)
