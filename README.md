# METAR Reader

A small Flask web app that fetches live METAR weather reports for any airport in the world and translates them from aviation shorthand into plain English.

**METAR** (Meteorological Aerodrome Report) is the standard format used by airports globally to broadcast current weather conditions. It looks like this:

```
METAR EGLL 291520Z 22015KT 7000 -RA BKN015 OVC030 16/14 Q1008
```

METAR Reader turns that into a friendly summary:

> 🌦️ Light Rain · 61°F / 16°C · Wind from the Southwest at 17 mph · Visibility 4.3 miles · Pressure 29.77 inHg

![Screenshot showing the METAR Reader UI with a weather card for KJFK](https://placehold.co/680x400?text=METAR+Reader+screenshot)

---

## Features

- Search any airport by its **ICAO code** (e.g. `KJFK`, `EGLL`, `OMDB`, `YSSY`)
- Live data from the [Aviation Weather Center](https://aviationweather.gov) public API
- Decodes all major METAR fields:
  - Weather condition with icon (Clear, Partly Cloudy, Rain, Snow, Thunderstorm, Fog, …)
  - Temperature in °F and °C
  - Dew point with humidity feel (Dry / Comfortable / Humid)
  - Wind direction, speed, and gusts in mph
  - Visibility in miles
  - Cloud layers with altitude
  - Barometric pressure in inHg and hPa
- Handles both US format (`10SM`, `A2992`) and international format (`9999`, `CAVOK`, `Q1013`)
- Quick-pick buttons for popular airports
- Raw METAR shown on demand for reference

---

## Requirements

- Python 3.8+
- pip

---

## Installation

```bash
# 1. Clone the repository
git clone https://github.com/your-username/metar-reader.git
cd metar-reader

# 2. (Recommended) Create and activate a virtual environment
python -m venv venv

# On macOS / Linux:
source venv/bin/activate

# On Windows:
venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt
```

---

## Running the app

```bash
python app.py
```

Then open your browser at **http://127.0.0.1:5000**.

> **Note:** Always access the app through the Flask URL above. Opening `templates/index.html` directly as a file will not work.

---

## Project structure

```
metar-reader/
├── app.py              # Flask app — routes and API fetch logic
├── metar_decoder.py    # Pure-Python METAR parser and plain-English generator
├── requirements.txt    # Python dependencies
└── templates/
    └── index.html      # Single-page UI (HTML, CSS, and JavaScript)
```

---

## How METAR decoding works

`metar_decoder.py` parses the METAR token by token following the ICAO Annex 3 / WMO No. 49 format:

| Token | Example | Decoded |
|---|---|---|
| Station ID | `KJFK` | John F. Kennedy International |
| Date/time | `291451Z` | Day 29, 14:51 UTC |
| Wind | `27015G25KT` | From the West at 17 mph, gusting 29 mph |
| Visibility | `10SM` / `9999` / `CAVOK` | 10 miles / >6 miles / Clear & >6 miles |
| Weather | `-RA` / `+TSRA` / `FZFG` | Light rain / Heavy thunderstorm rain / Freezing fog |
| Cloud cover | `BKN025` / `OVC010CB` | Broken clouds at 2,500 ft / Overcast with cumulonimbus |
| Temp/dew point | `24/12` / `M05/M08` | 75°F / 23°F |
| Altimeter | `A2996` / `Q1013` | 29.96 inHg / 1013 hPa |

---

## Data source

Weather data is fetched in real time from the **Aviation Weather Center** (NOAA):

```
https://aviationweather.gov/api/data/metar?ids={ICAO}&format=raw
```

No API key is required.

---

## License

MIT
