"""
Unit tests for metar_decoder.py
================================
Each test feeds a realistic mock METAR string into decode_metar() and
asserts that specific fields are decoded to the expected plain-English values.
No network calls are made — all inputs are hard-coded strings.
"""

import pytest
from metar_decoder import decode_metar, generate_summary


# ── Helpers ───────────────────────────────────────────────────────────────────

def summary_value(decoded, label):
    """Return the summary value for a given label, or None if not present."""
    for item in generate_summary(decoded):
        if item['label'] == label:
            return item['value']
    return None


# ── Temperature & dew point ───────────────────────────────────────────────────

class TestTemperature:
    def test_positive_temp_converted_to_fahrenheit(self):
        d = decode_metar('METAR KLAX 011800Z 25010KT 10SM SKC 28/10 A2998')
        assert d['temperature_c'] == 28
        assert d['temperature_f'] == 82

    def test_negative_temp_m_prefix(self):
        """M prefix in METAR denotes below-zero Celsius."""
        d = decode_metar('METAR CYYZ 011600Z 01005KT 3SM -SN OVC010 M05/M08 A2985')
        assert d['temperature_c'] == -5
        assert d['temperature_f'] == 23

    def test_dewpoint_parsed(self):
        d = decode_metar('METAR KJFK 291451Z 27015KT 10SM FEW030 24/12 A3002')
        assert d['dewpoint_c'] == 12
        assert d['dewpoint_f'] == 54

    def test_negative_dewpoint(self):
        d = decode_metar('METAR CYYZ 011600Z 01005KT 3SM -SN OVC010 M05/M08 A2985')
        assert d['dewpoint_c'] == -8
        assert d['dewpoint_f'] == 18

    def test_humidity_feel_very_humid(self):
        """Temp/dew spread of ≤3° reads as Very humid."""
        d = decode_metar('METAR KATL 011930Z 18020KT 1SM +TSRA BKN010CB 25/23 A2990')
        assert 'Very humid' in summary_value(d, 'Dew Point')

    def test_humidity_feel_dry(self):
        """Temp/dew spread of >12° reads as Dry."""
        d = decode_metar('METAR KLAX 011800Z 25010KT 10SM SKC 28/10 A2998')
        assert 'Dry' in summary_value(d, 'Dew Point')


# ── Wind ──────────────────────────────────────────────────────────────────────

class TestWind:
    def test_directional_wind_converted_to_mph(self):
        """27015KT = 270° at 15 knots = 17 mph from the West."""
        d = decode_metar('METAR KJFK 291451Z 27015KT 10SM SKC 24/12 A3002')
        assert d['wind']['compass_full'] == 'West'
        assert d['wind']['speed_mph'] == 17
        assert d['wind']['gust_mph'] is None

    def test_gusting_wind(self):
        """27015G25KT = 15 kt steady, gusting 25 kt."""
        d = decode_metar('METAR KORD 011800Z 27015G25KT 10SM FEW030 20/08 A2996')
        assert d['wind']['speed_mph'] == 17
        assert d['wind']['gust_mph'] == 29

    def test_calm_winds(self):
        """00000KT means no wind."""
        d = decode_metar('METAR KSFO 011500Z 00000KT 10SM FEW015 18/12 A2994')
        assert d['wind']['calm'] is True
        assert d['wind']['description'] == 'Calm'

    def test_variable_wind_direction(self):
        """VRB05KT = variable direction at 5 knots."""
        d = decode_metar('METAR KBOS 011700Z VRB05KT 10SM SCT020 22/15 A3002')
        assert d['wind']['variable'] is True
        assert d['wind']['speed_mph'] == 6

    def test_variable_wind_direction_range(self):
        """280V350 appended after wind token sets the variable range.
        280° → W, 350° → N (round(350/22.5)%16 = 0 → N)."""
        d = decode_metar('METAR KJFK 011800Z 31010KT 280V350 10SM SKC 20/10 A3000')
        assert d['wind_var_range'] == 'W–N'


# ── Visibility ────────────────────────────────────────────────────────────────

class TestVisibility:
    def test_statute_miles(self):
        d = decode_metar('METAR KLAX 011800Z 25010KT 10SM SKC 28/10 A2998')
        assert d['visibility']['miles'] == 10.0

    def test_cavok_sets_good_visibility(self):
        """CAVOK implies visibility >6 miles with no significant cloud."""
        d = decode_metar('METAR OMDB 011200Z 15004KT CAVOK 30/22 Q1005')
        assert d['visibility']['miles'] == 10
        assert d['cavok'] is True

    def test_9999_metric_max_visibility(self):
        d = decode_metar('METAR YSSY 290200Z 21022KT 9999 FEW018 19/15 Q1003')
        assert d['visibility']['miles'] == 10

    def test_metric_visibility_in_meters(self):
        """0800 = 800 m ≈ 0.5 miles."""
        d = decode_metar('METAR EGLL 011200Z 09005KT 0800 FG OVC002 08/07 Q1010')
        assert d['visibility']['miles'] == pytest.approx(0.5, abs=0.1)

    def test_fractional_statute_miles(self):
        """1/4SM = 0.25 miles."""
        d = decode_metar('METAR KSFO 012000Z 00000KT 1/4SM FG OVC002 12/11 A2995')
        assert d['visibility']['miles'] == pytest.approx(0.25)

    def test_low_visibility_description(self):
        d = decode_metar('METAR KSFO 012000Z 00000KT 1/4SM FG OVC002 12/11 A2995')
        assert 'Less than' in d['visibility']['description']


# ── Cloud cover & condition ───────────────────────────────────────────────────

class TestClouds:
    def test_skc_gives_clear_condition(self):
        d = decode_metar('METAR KLAX 011800Z 25010KT 10SM SKC 28/10 A2998')
        assert d['condition'] == 'Clear'

    def test_clr_gives_clear_condition(self):
        d = decode_metar('METAR KBWI 011755Z AUTO 19010KT 10SM CLR 23/11 A2993')
        assert d['condition'] == 'Clear'

    def test_few_gives_mostly_clear(self):
        d = decode_metar('METAR KJFK 291451Z 27015KT 10SM FEW030 24/12 A3002')
        assert d['condition'] == 'Mostly Clear'

    def test_sct_gives_partly_cloudy(self):
        d = decode_metar('METAR KBOS 011700Z VRB05KT 10SM SCT020 22/15 A3002')
        assert d['condition'] == 'Partly Cloudy'

    def test_bkn_gives_mostly_cloudy(self):
        d = decode_metar('METAR EGLL 291520Z 22015KT 7000 BKN015 16/14 Q1008')
        assert d['condition'] == 'Mostly Cloudy'

    def test_ovc_gives_overcast(self):
        """Weather phenomena take priority over cloud cover, so this METAR
        must have no wx token for the OVC layer to determine the condition."""
        d = decode_metar('METAR KJFK 011800Z 00000KT 10SM OVC020 18/15 A2990')
        assert d['condition'] == 'Overcast'

    def test_cloud_altitude_decoded(self):
        """BKN015 = broken clouds at 1,500 ft."""
        d = decode_metar('METAR EGLL 291520Z 22015KT 7000 BKN015 16/14 Q1008')
        assert d['clouds'][0]['altitude_ft'] == 1500

    def test_multiple_cloud_layers(self):
        d = decode_metar('METAR KJFK 291451Z 27015KT 10SM FEW030 SCT060 BKN120 24/12 A3002')
        assert len(d['clouds']) == 3
        assert d['clouds'][0]['code'] == 'FEW'
        assert d['clouds'][1]['code'] == 'SCT'
        assert d['clouds'][2]['code'] == 'BKN'

    def test_cumulonimbus_flag(self):
        """OVC010CB should mention cumulonimbus in the description."""
        d = decode_metar('METAR KATL 011930Z 18020KT 1SM +TSRA OVC010CB 25/23 A2990')
        assert 'cumulonimbus' in d['clouds'][0]['description'].lower()

    def test_cavok_produces_clear_cloud_entry(self):
        d = decode_metar('METAR OMDB 011200Z 15004KT CAVOK 30/22 Q1005')
        assert d['clouds'][0]['description'] == 'Clear skies'


# ── Weather phenomena ─────────────────────────────────────────────────────────

class TestWeatherPhenomena:
    def test_light_rain(self):
        d = decode_metar('METAR EGLL 291520Z 22015KT 7000 -RA BKN015 16/14 Q1008')
        assert d['condition'] == 'Light Rain'
        assert any('rain' in wx.lower() for wx in d['weather_phenomena'])

    def test_heavy_rain(self):
        """+RA decodes to 'Heavy Rain' condition (not plain 'Rain')."""
        d = decode_metar('METAR KATL 011930Z 18020KT 1SM +RA OVC015 25/23 A2990')
        assert d['condition'] == 'Heavy Rain'
        assert any('heavy' in wx.lower() for wx in d['weather_phenomena'])

    def test_thunderstorm(self):
        d = decode_metar('METAR KATL 011930Z 18020KT 1SM +TSRA OVC010CB 25/23 A2990')
        assert d['condition'] == 'Thunderstorm'

    def test_snow(self):
        d = decode_metar('METAR CYYZ 011600Z 01005KT 3SM -SN OVC010 M05/M08 A2985')
        assert d['condition'] == 'Snow'

    def test_fog(self):
        d = decode_metar('METAR KSFO 012000Z 00000KT 1/4SM FG OVC002 12/11 A2995')
        assert d['condition'] == 'Fog'

    def test_freezing_fog(self):
        d = decode_metar('METAR KORD 012100Z 15005KT 1/4SM FZFG OVC002 M02/M03 A3001')
        assert d['condition'] == 'Freezing Rain'

    def test_haze(self):
        d = decode_metar('METAR KLAX 011800Z 25005KT 5SM HZ SKC 28/10 A2998')
        assert d['condition'] == 'Haze'


# ── Pressure ──────────────────────────────────────────────────────────────────

class TestPressure:
    def test_us_altimeter_inhg(self):
        """A2996 = 29.96 inHg."""
        d = decode_metar('METAR KJFK 291451Z 27015KT 10SM SKC 24/12 A2996')
        assert d['altimeter']['inhg'] == 29.96

    def test_international_qnh_hpa(self):
        """Q1008 = 1008 hPa."""
        d = decode_metar('METAR EGLL 291520Z 22015KT 7000 -RA BKN015 16/14 Q1008')
        assert d['altimeter']['hpa'] == 1008

    def test_pressure_converts_both_ways(self):
        """Both inHg and hPa should always be populated regardless of input format."""
        us = decode_metar('METAR KJFK 291451Z 27015KT 10SM SKC 24/12 A2996')
        intl = decode_metar('METAR EGLL 291520Z 22015KT 7000 -RA BKN015 16/14 Q1008')
        assert us['altimeter']['hpa'] is not None
        assert intl['altimeter']['inhg'] is not None


# ── Metadata ──────────────────────────────────────────────────────────────────

class TestMetadata:
    def test_station_id_parsed(self):
        d = decode_metar('METAR KJFK 291451Z 27015KT 10SM SKC 24/12 A3002')
        assert d['station'] == 'KJFK'

    def test_time_parsed(self):
        d = decode_metar('METAR KJFK 291451Z 27015KT 10SM SKC 24/12 A3002')
        assert d['time_utc'] == 'Day 29, 14:51 UTC'

    def test_metar_prefix_stripped(self):
        """METAR prefix should not interfere with parsing."""
        d = decode_metar('METAR KLAX 011800Z 25010KT 10SM SKC 28/10 A2998')
        assert d['station'] == 'KLAX'

    def test_speci_prefix_stripped(self):
        """SPECI (special report) should be treated the same as METAR."""
        d = decode_metar('SPECI KLAX 011823Z 25010KT 10SM SKC 28/10 A2998')
        assert d['station'] == 'KLAX'

    def test_auto_station_flag(self):
        d = decode_metar('METAR KBWI 011755Z AUTO 19010KT 10SM CLR 23/11 A2993')
        assert d['auto'] is True

    def test_non_auto_station(self):
        d = decode_metar('METAR KJFK 291451Z 27015KT 10SM SKC 24/12 A3002')
        assert d['auto'] is False

    def test_remarks_section_ignored(self):
        """Everything after RMK should not affect decoded fields."""
        with_rmk    = decode_metar('METAR KJFK 291451Z 27015KT 10SM SKC 24/12 A3002 RMK AO2 SLP171')
        without_rmk = decode_metar('METAR KJFK 291451Z 27015KT 10SM SKC 24/12 A3002')
        assert with_rmk['temperature_c'] == without_rmk['temperature_c']
        assert with_rmk['altimeter']['inhg'] == without_rmk['altimeter']['inhg']

    def test_raw_metar_preserved(self):
        """The original string should be stored verbatim in decoded['raw']."""
        raw = 'METAR KJFK 291451Z 27015KT 10SM SKC 24/12 A3002'
        d = decode_metar(raw)
        assert d['raw'] == raw
