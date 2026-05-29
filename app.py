"""
METAR Reader — Flask web application
=====================================
Serves a single-page UI where users type an ICAO airport code and receive
a plain-English weather report decoded from the airport's live METAR feed.

Data source: Aviation Weather Center (aviationweather.gov) public API.
Decoding logic lives in metar_decoder.py.
"""

import re

import urllib3
import requests
from flask import Flask, jsonify, render_template, request

# Windows Python often cannot verify government-site SSL certificates without
# additional setup. aviationweather.gov is a known, trusted NOAA source, so
# we suppress the resulting InsecureRequestWarning rather than block requests.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from metar_decoder import decode_metar, generate_summary

app = Flask(__name__)

AWC_API = "https://aviationweather.gov/api/data/metar"


def fetch_raw_metar(icao):
    """Fetch the most recent raw METAR string for a given ICAO station code.

    Queries the Aviation Weather Center REST API and returns the first
    (most recent) line of the response, which is a single METAR string.

    Args:
        icao (str): 3–4 character ICAO airport code, e.g. "KJFK".

    Returns:
        tuple[str | None, str | None]: (raw_metar, error_message).
            Exactly one of the two values will be None — if the fetch
            succeeds, error_message is None; if it fails, raw_metar is None.
    """
    try:
        resp = requests.get(
            AWC_API,
            params={"ids": icao, "format": "raw", "hours": "2"},
            headers={"User-Agent": "METAR-Reader/1.0"},
            timeout=10,
            verify=False,  # see urllib3 warning suppression above
        )
        resp.raise_for_status()

        text = resp.text.strip()
        if not text:
            return None, f"No METAR data found for '{icao}'. Make sure it's a valid ICAO airport code."

        # The API can return several observations; take the first (most recent).
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        return lines[0], None

    except requests.exceptions.Timeout:
        return None, "Request timed out — the weather service may be slow. Please try again."
    except requests.exceptions.HTTPError as exc:
        code = exc.response.status_code if exc.response else "?"
        return None, f"The weather service returned an error (HTTP {code}). Check the airport code."
    except requests.exceptions.RequestException as exc:
        return None, f"Connection error: {exc}"


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    """Serve the main single-page UI."""
    return render_template("index.html")


@app.route("/fetch", methods=["POST"])
def fetch():
    """Fetch and decode a METAR for the requested ICAO code.

    Expects a JSON body: ``{"icao": "KJFK"}``

    Returns a JSON object with three keys:
        - ``raw``     – the unmodified METAR string from the API.
        - ``decoded`` – structured dictionary of parsed METAR fields.
        - ``summary`` – list of plain-English label/value pairs for the UI.

    On error, returns ``{"error": "<message>"}`` with an appropriate
    HTTP status code (400 for bad input, 404 for unknown airport).
    """
    body = request.get_json(silent=True) or {}
    icao = body.get("icao", "").strip().upper()

    if not icao:
        return jsonify({"error": "Please enter an airport code."}), 400

    if not re.match(r"^[A-Z0-9]{3,4}$", icao):
        return jsonify({
            "error": "Use a 3–4 character ICAO code (e.g. KJFK, EGLL, OMDB, YSSY)."
        }), 400

    raw, err = fetch_raw_metar(icao)
    if err:
        return jsonify({"error": err}), 404

    try:
        decoded = decode_metar(raw)
        summary = generate_summary(decoded)
        return jsonify({"raw": raw, "decoded": decoded, "summary": summary})
    except Exception as exc:
        # Decoding failed, but we can still return the raw METAR so the user
        # isn't left with nothing.
        return jsonify({
            "raw": raw,
            "decoded": None,
            "summary": [],
            "decode_error": str(exc),
        })


if __name__ == "__main__":
    app.run(debug=True, port=5000)
