"""
Integration tests for app.py Flask routes
==========================================
Uses Flask's built-in test client. The fetch_raw_metar function is patched
with unittest.mock so no real network requests are made during testing.
"""

import pytest
from unittest.mock import patch
import app as flask_app

SAMPLE_METAR = 'METAR KJFK 291451Z 27015KT 10SM FEW030 SCT250 24/12 A3002 RMK AO2'


@pytest.fixture
def client():
    flask_app.app.config['TESTING'] = True
    with flask_app.app.test_client() as c:
        yield c


# ── GET / ─────────────────────────────────────────────────────────────────────

class TestIndex:
    def test_returns_200(self, client):
        r = client.get('/')
        assert r.status_code == 200

    def test_returns_html(self, client):
        r = client.get('/')
        assert b'METAR' in r.data
        assert b'<html' in r.data.lower()


# ── POST /fetch — input validation ────────────────────────────────────────────

class TestFetchValidation:
    def test_empty_icao_returns_400(self, client):
        r = client.post('/fetch', json={'icao': ''})
        assert r.status_code == 400
        assert 'error' in r.get_json()

    def test_missing_icao_key_returns_400(self, client):
        r = client.post('/fetch', json={})
        assert r.status_code == 400

    def test_icao_too_long_returns_400(self, client):
        r = client.post('/fetch', json={'icao': 'TOOLONG'})
        assert r.status_code == 400

    def test_icao_with_special_chars_returns_400(self, client):
        r = client.post('/fetch', json={'icao': 'KJ!K'})
        assert r.status_code == 400

    def test_lowercase_icao_is_accepted(self, client):
        """Input should be normalised to uppercase before lookup."""
        with patch('app.fetch_raw_metar', return_value=(SAMPLE_METAR, None)):
            r = client.post('/fetch', json={'icao': 'kjfk'})
        assert r.status_code == 200


# ── POST /fetch — successful decode ──────────────────────────────────────────

class TestFetchSuccess:
    def test_returns_200_with_valid_icao(self, client):
        with patch('app.fetch_raw_metar', return_value=(SAMPLE_METAR, None)):
            r = client.post('/fetch', json={'icao': 'KJFK'})
        assert r.status_code == 200

    def test_response_contains_raw_metar(self, client):
        with patch('app.fetch_raw_metar', return_value=(SAMPLE_METAR, None)):
            r = client.post('/fetch', json={'icao': 'KJFK'})
        assert r.get_json()['raw'] == SAMPLE_METAR

    def test_station_id_decoded_correctly(self, client):
        with patch('app.fetch_raw_metar', return_value=(SAMPLE_METAR, None)):
            r = client.post('/fetch', json={'icao': 'KJFK'})
        assert r.get_json()['decoded']['station'] == 'KJFK'

    def test_temperature_decoded(self, client):
        with patch('app.fetch_raw_metar', return_value=(SAMPLE_METAR, None)):
            r = client.post('/fetch', json={'icao': 'KJFK'})
        decoded = r.get_json()['decoded']
        assert decoded['temperature_c'] == 24
        assert decoded['temperature_f'] == 75

    def test_summary_list_is_populated(self, client):
        with patch('app.fetch_raw_metar', return_value=(SAMPLE_METAR, None)):
            r = client.post('/fetch', json={'icao': 'KJFK'})
        summary = r.get_json()['summary']
        assert isinstance(summary, list)
        assert len(summary) > 0

    def test_summary_contains_temperature_entry(self, client):
        with patch('app.fetch_raw_metar', return_value=(SAMPLE_METAR, None)):
            r = client.post('/fetch', json={'icao': 'KJFK'})
        labels = [item['label'] for item in r.get_json()['summary']]
        assert 'Temperature' in labels

    def test_no_error_key_on_success(self, client):
        with patch('app.fetch_raw_metar', return_value=(SAMPLE_METAR, None)):
            r = client.post('/fetch', json={'icao': 'KJFK'})
        assert 'error' not in r.get_json()


# ── POST /fetch — API / upstream errors ──────────────────────────────────────

class TestFetchErrors:
    def test_unknown_airport_returns_404(self, client):
        with patch('app.fetch_raw_metar', return_value=(None, "No METAR data found for 'ZZZZ'.")):
            r = client.post('/fetch', json={'icao': 'ZZZZ'})
        assert r.status_code == 404
        assert 'error' in r.get_json()

    def test_api_timeout_returns_error_message(self, client):
        with patch('app.fetch_raw_metar', return_value=(None, 'Request timed out')):
            r = client.post('/fetch', json={'icao': 'KJFK'})
        assert r.status_code == 404
        assert 'timed out' in r.get_json()['error'].lower()

    def test_connection_error_returns_error_message(self, client):
        with patch('app.fetch_raw_metar', return_value=(None, 'Connection error')):
            r = client.post('/fetch', json={'icao': 'KJFK'})
        assert r.status_code == 404
        assert 'error' in r.get_json()
