import re

# ── Lookup tables ─────────────────────────────────────────────────────────────

WEATHER_DESCRIPTORS = {
    'MI': 'Shallow', 'PR': 'Partial', 'BC': 'Patches of', 'DR': 'Low Drifting',
    'BL': 'Blowing', 'SH': 'Shower', 'TS': 'Thunderstorm', 'FZ': 'Freezing',
}

WEATHER_PRECIPITATION = {
    'DZ': 'drizzle', 'RA': 'rain', 'SN': 'snow', 'SG': 'snow grains',
    'IC': 'ice crystals', 'PL': 'ice pellets', 'GR': 'hail',
    'GS': 'small hail', 'UP': 'unknown precipitation',
}

WEATHER_OBSCURATION = {
    'BR': 'mist', 'FG': 'fog', 'FU': 'smoke', 'VA': 'volcanic ash',
    'DU': 'widespread dust', 'SA': 'sand', 'HZ': 'haze', 'PY': 'spray',
}

WEATHER_OTHER = {
    'PO': 'dust/sand whirls', 'SQ': 'squalls', 'FC': 'funnel cloud',
    'SS': 'sandstorm', 'DS': 'duststorm', 'NSW': 'no significant weather',
}

ALL_WX = {**WEATHER_DESCRIPTORS, **WEATHER_PRECIPITATION, **WEATHER_OBSCURATION, **WEATHER_OTHER}

# (description, severity level 0-4)
CLOUD_AMOUNTS = {
    'SKC': ('Clear skies', 0),
    'CLR': ('Clear skies', 0),
    'NCD': ('No clouds detected', 0),
    'NSC': ('No significant clouds', 0),
    'FEW': ('A few clouds', 1),
    'SCT': ('Scattered clouds', 2),
    'BKN': ('Broken clouds', 3),
    'OVC': ('Overcast', 4),
    'VV':  ('Sky obscured', 4),
}

COMPASS_DIRS = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE',
                'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW']

COMPASS_FULL = {
    'N': 'North', 'NNE': 'North-Northeast', 'NE': 'Northeast',
    'ENE': 'East-Northeast', 'E': 'East', 'ESE': 'East-Southeast',
    'SE': 'Southeast', 'SSE': 'South-Southeast', 'S': 'South',
    'SSW': 'South-Southwest', 'SW': 'Southwest', 'WSW': 'West-Southwest',
    'W': 'West', 'WNW': 'West-Northwest', 'NW': 'Northwest',
    'NNW': 'North-Northwest',
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def _deg_to_compass(deg):
    return COMPASS_DIRS[round(deg / 22.5) % 16]

def _kt_to_mph(kt):
    return round(kt * 1.15078)

def _c_to_f(c):
    return round(c * 9 / 5 + 32)

def _parse_temp(s):
    return -int(s[1:]) if s.startswith('M') else int(s)

# ── Field decoders ────────────────────────────────────────────────────────────

def _decode_wind(token):
    if token in ('00000KT', '00000MPS'):
        return {'calm': True, 'description': 'Calm', 'speed_mph': 0}

    if token.startswith('VRB'):
        m = re.match(r'VRB(\d{2,3})(?:G(\d{2,3}))?(KT|MPS)$', token)
        if m:
            spd = int(m.group(1))
            gst = int(m.group(2)) if m.group(2) else None
            mph = _kt_to_mph(spd) if m.group(3) == 'KT' else round(spd * 2.237)
            gph = (_kt_to_mph(gst) if m.group(3) == 'KT' else round(gst * 2.237)) if gst else None
            desc = f'Variable at {mph} mph'
            if gph:
                desc += f', gusting {gph} mph'
            return {'calm': False, 'variable': True, 'speed_mph': mph, 'gust_mph': gph, 'description': desc}

    m = re.match(r'(\d{3})(\d{2,3})(?:G(\d{2,3}))?(KT|MPS)$', token)
    if not m:
        return None

    direction = int(m.group(1))
    spd = int(m.group(2))
    gst = int(m.group(3)) if m.group(3) else None
    unit = m.group(4)

    mph = _kt_to_mph(spd) if unit == 'KT' else round(spd * 2.237)
    gph = (_kt_to_mph(gst) if unit == 'KT' else round(gst * 2.237)) if gst else None

    compass = _deg_to_compass(direction)
    compass_full = COMPASS_FULL.get(compass, compass)
    desc = f'From the {compass_full} at {mph} mph'
    if gph:
        desc += f', gusting {gph} mph'

    return {
        'calm': False,
        'variable': False,
        'direction_deg': direction,
        'compass': compass,
        'compass_full': compass_full,
        'speed_mph': mph,
        'gust_mph': gph,
        'description': desc,
    }


def _decode_visibility(token):
    if token in ('9999', 'CAVOK'):
        return {'description': 'More than 6 miles', 'miles': 10}

    if re.match(r'^\d{4}$', token):
        meters = int(token)
        miles = round(meters / 1609.34, 1)
        if meters >= 9000:
            return {'description': 'More than 5 miles', 'miles': miles}
        return {'description': f'{miles} miles ({meters} m)', 'miles': miles}

    if token.endswith('SM'):
        val = token[:-2]
        if '/' in val:
            num, den = val.split('/')
            value = int(num) / int(den)
        else:
            value = float(val)
        if value >= 10:
            desc = 'More than 10 miles'
        elif value < 0.5:
            desc = f'Less than ½ mile'
        else:
            desc = f'{value:g} miles'
        return {'description': desc, 'miles': value}

    return {'description': token, 'miles': None}


def _decode_cloud(token):
    for code in ('SKC', 'CLR', 'NCD', 'NSC'):
        if token == code:
            return {'code': code, 'description': CLOUD_AMOUNTS[code][0], 'level': 0}

    m = re.match(r'^(FEW|SCT|BKN|OVC|VV)(\d{3})(CB|TCU)?$', token)
    if m:
        code, alt_hund, special = m.group(1), int(m.group(2)), m.group(3)
        alt_ft = alt_hund * 100
        label, level = CLOUD_AMOUNTS.get(code, (code, 2))
        desc = f'{label} at {alt_ft:,} ft'
        if special == 'CB':
            desc += ' — cumulonimbus (storm cells!)'
        elif special == 'TCU':
            desc += ' — towering cumulus'
        return {'code': code, 'description': desc, 'level': level, 'altitude_ft': alt_ft}

    return {'code': token, 'description': token, 'level': 1}


def _decode_wx(token):
    intensity = ''
    tok = token
    if tok.startswith('+'):
        intensity = 'Heavy '
        tok = tok[1:]
    elif tok.startswith('-'):
        intensity = 'Light '
        tok = tok[1:]
    elif tok.startswith('VC'):
        intensity = 'In vicinity: '
        tok = tok[2:]

    parts = []
    i = 0
    while i < len(tok):
        code = tok[i:i+2]
        if code in ALL_WX:
            parts.append(ALL_WX[code])
            i += 2
        else:
            i += 1

    return (intensity + ' '.join(parts)).strip() if parts else token


def _decode_altimeter(token):
    if re.match(r'^A\d{4}$', token):
        inhg = int(token[1:]) / 100
        hpa = round(inhg * 33.8639)
    elif re.match(r'^Q\d{4}$', token):
        hpa = int(token[1:])
        inhg = round(hpa / 33.8639, 2)
    else:
        return None
    return {'inhg': inhg, 'hpa': hpa, 'description': f'{inhg:.2f} inHg ({hpa} hPa)'}


# ── Main decoder ──────────────────────────────────────────────────────────────

def decode_metar(raw):
    raw = raw.strip()
    text = raw
    if text.startswith(('METAR ', 'SPECI ')):
        text = text[6:]

    tokens = text.split()
    result = {
        'raw': raw,
        'station': None,
        'time_utc': None,
        'auto': False,
        'wind': None,
        'wind_var_range': None,
        'visibility': None,
        'weather_phenomena': [],
        'clouds': [],
        'cavok': False,
        'temperature_c': None,
        'temperature_f': None,
        'dewpoint_c': None,
        'dewpoint_f': None,
        'altimeter': None,
        'condition': 'Unknown',
        'condition_icon': '🌡️',
    }

    idx = 0

    # Station ID
    if idx < len(tokens) and re.match(r'^[A-Z0-9]{3,4}$', tokens[idx]):
        result['station'] = tokens[idx]
        idx += 1

    # Date/time  DDHHMMZ
    if idx < len(tokens) and re.match(r'^\d{6}Z$', tokens[idx]):
        t = tokens[idx]
        result['time_utc'] = f"Day {t[:2]}, {t[2:4]}:{t[4:6]} UTC"
        idx += 1

    # Modifiers
    while idx < len(tokens) and tokens[idx] in ('AUTO', 'COR', 'NIL'):
        if tokens[idx] == 'AUTO':
            result['auto'] = True
        idx += 1

    # Wind
    if idx < len(tokens) and re.match(r'^(VRB|\d{3})\d{2,3}(?:G\d{2,3})?(KT|MPS)$', tokens[idx]):
        result['wind'] = _decode_wind(tokens[idx])
        idx += 1
        # Variable range e.g. 280V350
        if idx < len(tokens) and re.match(r'^\d{3}V\d{3}$', tokens[idx]):
            v1 = int(tokens[idx][:3])
            v2 = int(tokens[idx][4:])
            result['wind_var_range'] = f'{_deg_to_compass(v1)}–{_deg_to_compass(v2)}'
            idx += 1

    # CAVOK shortcut
    if idx < len(tokens) and tokens[idx] == 'CAVOK':
        result['cavok'] = True
        result['visibility'] = {'description': 'More than 6 miles', 'miles': 10}
        result['clouds'] = [{'code': 'CAVOK', 'description': 'Clear skies', 'level': 0}]
        idx += 1
    else:
        # Visibility
        if idx < len(tokens):
            tok = tokens[idx]
            if (re.match(r'^\d/\d+SM$', tok) or re.match(r'^\d+(?:\.\d+)?SM$', tok)
                    or tok in ('9999',) or re.match(r'^\d{4}$', tok)):
                result['visibility'] = _decode_visibility(tok)
                idx += 1
            elif (re.match(r'^\d+$', tok) and idx + 1 < len(tokens)
                  and re.match(r'^\d/\d+SM$', tokens[idx + 1])):
                # e.g. "1 1/2SM"
                whole = int(tok)
                num, den = tokens[idx + 1][:-2].split('/')
                value = whole + int(num) / int(den)
                result['visibility'] = {'description': f'{value:g} miles', 'miles': value}
                idx += 2

        # RVR — skip
        while idx < len(tokens) and re.match(r'^R\d+[LCR]?/', tokens[idx]):
            idx += 1

        # Weather phenomena
        wx_re = re.compile(
            r'^(\+|-|VC)?(MI|PR|BC|DR|BL|SH|TS|FZ)?'
            r'(DZ|RA|SN|SG|IC|PL|GR|GS|UP|BR|FG|FU|VA|DU|SA|HZ|PY|PO|SQ|FC|SS|DS|NSW)+'
            r'$'
        )
        while idx < len(tokens) and tokens[idx] != 'RMK':
            if wx_re.match(tokens[idx]):
                result['weather_phenomena'].append(_decode_wx(tokens[idx]))
                idx += 1
            else:
                break

        # Clouds
        cloud_re = re.compile(r'^(FEW|SCT|BKN|OVC|VV)\d{3}(?:CB|TCU)?$|^(SKC|CLR|NCD|NSC)$')
        while idx < len(tokens) and tokens[idx] != 'RMK':
            if cloud_re.match(tokens[idx]):
                result['clouds'].append(_decode_cloud(tokens[idx]))
                idx += 1
            else:
                break

    # Temperature/dew point  M?NN/M?NN
    temp_re = re.compile(r'^(M?\d+)/(M?\d*)$')
    while idx < len(tokens) and tokens[idx] != 'RMK':
        m = temp_re.match(tokens[idx])
        if m:
            result['temperature_c'] = _parse_temp(m.group(1))
            result['temperature_f'] = _c_to_f(result['temperature_c'])
            if m.group(2):
                result['dewpoint_c'] = _parse_temp(m.group(2))
                result['dewpoint_f'] = _c_to_f(result['dewpoint_c'])
            idx += 1
            break
        idx += 1

    # Altimeter
    while idx < len(tokens) and tokens[idx] != 'RMK':
        alt = _decode_altimeter(tokens[idx])
        if alt:
            result['altimeter'] = alt
            idx += 1
            break
        idx += 1

    result['condition'], result['condition_icon'] = _get_condition(result)
    return result


def _get_condition(d):
    for wx in d['weather_phenomena']:
        wl = wx.lower()
        if 'thunderstorm' in wl:
            return 'Thunderstorm', '⛈️'
        if 'hail' in wl:
            return 'Hail', '⛈️'
        if 'snow' in wl or 'ice pellets' in wl or 'snow grains' in wl:
            return 'Snow', '🌨️'
        if 'freezing' in wl:
            return 'Freezing Rain', '🌨️'
        if 'heavy rain' in wl or ('rain' in wl and 'heavy' in wl):
            return 'Heavy Rain', '🌧️'
        if 'rain' in wl or 'drizzle' in wl:
            return ('Light Rain', '🌦️') if 'light' in wl else ('Rain', '🌧️')
        if 'fog' in wl:
            return 'Fog', '🌫️'
        if 'mist' in wl:
            return 'Mist', '🌁'
        if 'haze' in wl:
            return 'Haze', '🌫️'
        if 'smoke' in wl:
            return 'Smoke', '🌫️'
        if 'sandstorm' in wl or 'duststorm' in wl or 'dust' in wl:
            return 'Dust / Sand', '🌪️'
        if 'squall' in wl:
            return 'Squalls', '🌪️'
        if 'funnel' in wl:
            return 'Tornado / Funnel Cloud', '🌪️'

    max_level = max((c.get('level', 0) for c in d['clouds']), default=0)
    mapping = {0: ('Clear', '☀️'), 1: ('Mostly Clear', '🌤️'),
               2: ('Partly Cloudy', '⛅'), 3: ('Mostly Cloudy', '🌥️'), 4: ('Overcast', '☁️')}
    return mapping.get(max_level, ('Clear', '☀️'))


# ── Plain-English summary ─────────────────────────────────────────────────────

def generate_summary(decoded):
    items = []

    if decoded['temperature_c'] is not None:
        items.append({
            'icon': '🌡️', 'label': 'Temperature',
            'value': f"{decoded['temperature_f']}°F / {decoded['temperature_c']}°C",
        })

    if decoded['dewpoint_c'] is not None:
        spread = (decoded['temperature_c'] or 0) - decoded['dewpoint_c']
        feel = 'Very humid' if spread <= 3 else 'Humid' if spread <= 6 else 'Comfortable' if spread <= 12 else 'Dry'
        items.append({
            'icon': '💧', 'label': 'Dew Point',
            'value': f"{decoded['dewpoint_f']}°F / {decoded['dewpoint_c']}°C  ·  {feel}",
        })

    if decoded['wind']:
        w = decoded['wind']
        val = w['description']
        if decoded.get('wind_var_range'):
            val += f" (varying {decoded['wind_var_range']})"
        items.append({'icon': '💨', 'label': 'Wind', 'value': val})

    if decoded['visibility']:
        items.append({'icon': '👁️', 'label': 'Visibility', 'value': decoded['visibility']['description']})

    if decoded['weather_phenomena']:
        items.append({
            'icon': '🌦️', 'label': 'Weather',
            'value': ',  '.join(decoded['weather_phenomena']),
            'wide': True,
        })

    if decoded['clouds']:
        items.append({
            'icon': '☁️', 'label': 'Clouds',
            'value': ';  '.join(c['description'] for c in decoded['clouds']),
            'wide': True,
        })

    if decoded['altimeter']:
        items.append({'icon': '📊', 'label': 'Pressure', 'value': decoded['altimeter']['description']})

    if decoded.get('auto'):
        items.append({'icon': 'ℹ️', 'label': 'Note', 'value': 'Automated station — no human observer', 'wide': True})

    return items
