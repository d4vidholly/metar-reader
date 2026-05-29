import re
import urllib3
import requests
from flask import Flask, jsonify, render_template, request

# Windows Python often can't verify government-site SSL certs without extra setup;
# suppress the InsecureRequestWarning since aviationweather.gov is a known trusted source.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from metar_decoder import decode_metar, generate_summary

app = Flask(__name__)

AWC_API = "https://aviationweather.gov/api/data/metar"


def fetch_raw_metar(icao):
    """Return (raw_metar_string, error_message)."""
    try:
        resp = requests.get(
            AWC_API,
            params={"ids": icao, "format": "raw", "hours": "2"},
            headers={"User-Agent": "METAR-Reader/1.0"},
            timeout=10,
            verify=False,
        )
        resp.raise_for_status()
        text = resp.text.strip()
        if not text:
            return None, f"No METAR data found for '{icao}'. Make sure it's a valid ICAO airport code."

        # Take the first (most recent) non-empty line
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        return lines[0], None

    except requests.exceptions.Timeout:
        return None, "Request timed out — the weather service may be slow. Please try again."
    except requests.exceptions.HTTPError as exc:
        code = exc.response.status_code if exc.response else "?"
        return None, f"The weather service returned an error (HTTP {code}). Check the airport code."
    except requests.exceptions.RequestException as exc:
        return None, f"Connection error: {exc}"


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/fetch", methods=["POST"])
def fetch():
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
        # Still return the raw METAR even if decoding fails
        return jsonify({
            "raw": raw,
            "decoded": None,
            "summary": [],
            "decode_error": str(exc),
        })


if __name__ == "__main__":
    app.run(debug=True, port=5000)
