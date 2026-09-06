# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals
#HetWeer4.2r7
import re
import socket
import io
import time
import json
import os  # <-- NEU: Für os.path Operationen
from os.path import join, exists
from Screens.Console import Console
from Tools.LoadPixmap import loadPNG
from Tools.Directories import SCOPE_PLUGINS, resolveFilename  # <-- NEU: Für Enigma2 Pfad-Auflösung
from Plugins.Plugin import PluginDescriptor
from Screens.Screen import Screen
from Components.MenuList import MenuList
from Screens.VirtualKeyBoard import VirtualKeyBoard
try:
    # Python 3
    from urllib.request import urlopen, urlretrieve, Request
    from urllib.parse import quote
    from urllib.error import HTTPError, URLError
except ImportError:
    # Python 2
    from urllib2 import urlopen, Request, HTTPError, URLError
    from urllib import urlretrieve

try:
    text_type = unicode
except NameError:
    text_type = str
from Components.Label import Label
from Components.ScrollLabel import ScrollLabel
from Components.ActionMap import ActionMap, HelpableActionMap
from Components.Converter.ClockToText import ClockToText
from Components.Pixmap import Pixmap, MovingPixmap
from Screens.MessageBox import MessageBox
from enigma import ePicLoad, getDesktop, eTimer
from enigma import eLabel, eListboxPythonMultiContent, gFont, RT_HALIGN_LEFT, RT_HALIGN_RIGHT, RT_HALIGN_CENTER
from Components.AVSwitch import AVSwitch
import os
from Tools.Directories import resolveFilename, SCOPE_CONFIG, SCOPE_PLUGINS
from Screens.HelpMenu import HelpableScreen
from Components.FileList import FileList
from time import gmtime, strftime, time, localtime
import datetime, time
import struct
import math
import gettext



PLUGIN_NAME = "HetWeather"
PLUGIN_PATH = os.path.dirname(os.path.abspath(__file__))
LOCALE_PATH = os.path.join(PLUGIN_PATH, "locale")

# HetWeer-Icons liegen direkt hier:
# /usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/icon
ICON_PATH = os.path.join(PLUGIN_PATH, "Images", "icon")

def get_icon_file(code):
    """Find a HetWeer icon. The WMO mapper uses legacy names such as a,b,c,aa,bb."""
    if code is None:
        return None
    code_str = str(code).strip()
    if not code_str or code_str.lower() in ("na", "none"):
        return None
    if code_str.lower().endswith(".png"):
        code_str = code_str[:-4]

    # IMPORTANT: _wmo_to_icon() returns names like a, b, c, f, aa, bb, ...
    # Therefore the exact filename must be tested first.
    candidates = [
        os.path.join(ICON_PATH, code_str + ".png"),
        os.path.join(ICON_PATH, code_str + "a.png"),
    ]
    if code_str.isdigit():
        candidates.extend([
            os.path.join(ICON_PATH, "%02d.png" % int(code_str)),
            os.path.join(ICON_PATH, "%02da.png" % int(code_str)),
        ])

    for path in candidates:
        if os.path.isfile(path):
            print("HetWeer: Icon gefunden: %s" % path)
            return path

    print("HetWeer: Icon NICHT gefunden: code=%s ICON_PATH=%s" % (code_str, ICON_PATH))
    return None

def _init_translation():
    languages = []
    try:
        from Components.config import config
        lang = getattr(getattr(config, "osd", None), "language", None)
        lang = getattr(lang, "value", "") or ""
    except Exception:
        lang = ""
    if lang:
        languages.append(lang)
        languages.append(lang.split(".")[0])
        languages.append(lang.split("_")[0])
        languages.append(lang.split("-")[0])
    languages.extend(["en", "nl"])
    # preserve order and remove duplicates
    languages = list(dict.fromkeys([x for x in languages if x]))
    try:
        return gettext.translation(PLUGIN_NAME, localedir=LOCALE_PATH,
                                   languages=languages, fallback=True).gettext
    except Exception:
        return gettext.gettext

_ = _init_translation()



def _read_text(response, encoding="utf-8"):
    """Return HTTP response data as unicode/text on Python 2 and 3."""
    data = response.read()
    try:
        return data.decode(encoding, "replace")
    except (AttributeError, UnicodeDecodeError):
        return data

def safe_urlretrieve(url, filename, timeout=10):
    """Download a file with a timeout and validate PNG downloads."""
    tmpname = filename + ".download"
    try:
        response = urlopen(url, timeout=timeout)
        try:
            data = response.read()
        finally:
            response.close()
        if not data:
            raise IOError("lege download")
        if filename.lower().endswith('.png') and not is_png(data):
            raise IOError("geen geldige PNG ontvangen")
        with open(tmpname, 'wb') as f:
            f.write(data)
        os.replace(tmpname, filename)
        return filename
    except (HTTPError, URLError, IOError, OSError, socket.timeout, ValueError) as e:
        try:
            if os.path.exists(tmpname):
                os.remove(tmpname)
        except Exception:
            pass
        print("HetWeer: download mislukt (%s): %s" % (url, e))
        return None

versienummer = "4.4.0"

#WeerInfoCurVer = 4.2r7
def transhtml(text):
    text = text.replace('&nbsp;', ' ').replace('&szlig;', 'ss').replace('&quot;', '"').replace('&ndash;', '-').replace('&Oslash;', '').replace('&bdquo;', '"').replace('&ldquo;', '"').replace('&rsquo;', "'").replace('&gt;', '>').replace('&lt;', '<').replace('&shy;', '')
    text = text.replace('&copy;.*', ' ').replace('&amp;', '&').replace('&uuml;', 'ü').replace('&auml;', 'ä').replace('&ouml;', 'ö').replace('&eacute;', 'e').replace('&hellip;', '...').replace('&egrave;', 'è').replace('&agrave;', 'à').replace('&mdash;', '-')
    text = text.replace('&Uuml;', 'Ue').replace('&Auml;', 'Ae').replace('&Ouml;', 'Oe').replace('&#034;', '"').replace('&#039;', "'").replace('&#34;', '"').replace('&#38;', 'und').replace('&#39;', "'").replace('&#133;', '...').replace('&#196;', 'Ä').replace('&#214;', 'Ö').replace('&#220;', 'Ü').replace('&#223;', 'ß').replace('&#228;', 'ä').replace('&#246;', 'ö').replace('&#252;', 'ü')
    text = text.replace('&#8211;', '-').replace('&#8212;', '—').replace('&#8216;', "'").replace('&#8217;', "'").replace('&#8220;', '"').replace('&#8221;', '"').replace('&#8230;', '...').replace('&#8242;', "'").replace('&#8243;', '"')
    text = text.replace('<u>', '').replace('</u>', '').replace('<b>', '').replace('</b>', '').replace('&deg;', '°').replace('&ordm;', '°').replace('&euml;', 'e').replace('<em>', '').replace('</em>', '').replace('&aacute;', 'a').replace('&ocio;', 'o')
    return text

def icontotext(icon):
    text = ""
    if icon == "a":
        text = _("Zonnig / Helder")
    elif icon == "aa":
        text = _("Heldere nacht")
    elif icon == "b":
        text = _("Zon met (lichte) bewolking")
    elif icon == "bb":
        text = _("Lichte bewolking")
    elif icon == "c":
        text = _("Zwaar bewolkt")
    elif icon == "cc":
        text = _("Zwaar bewolkt")
    elif icon == "d":
        text = _("Wisselvallig met kans op nevel")
    elif icon == "dd":
        text = _("Wisselvallig met kans op nevel")
    elif icon == "f":
        text = _("Zonnig met kans op buien")
    elif icon == "ff":
        text = _("Bewolkt met kans op buien")
    elif icon == "g":
        text = _("Zon met kans op buien of onweer")
    elif icon == "gg":
        text = _("Buien en kans op onweer")
    elif icon == "j":
        text = _("Overwegend   zonnig")
    elif icon == "jj":
        text = _("Overwegend   helder")
    elif icon == "m":
        text = _("Zwaar bewolkt  buien mogelijk")
    elif icon == "mm":
        text = _("Zwaar bewolkt  buien mogelijk")
    elif icon == "n":
        text = _("Zon met kans op nevel")
    elif icon == "nn":
        text = _("Helder met kans nevel")
    elif icon == "q":
        text = _("Zwaar bewolkt  hevige buien")
    elif icon == "qq":
        text = _("Zwaar bewolkt  hevige buien")
    elif icon == "r":
        text = _("Bewolkt")
    elif icon == "rr":
        text = _("Bewolkt")
    elif icon == "s":
        text = _("Zwaar bewolkt  onweersbuien")
    elif icon == "ss":
        text = _("Zwaar bewolkt  onweersbuien")
    elif icon == "t":
        text = _("Zwaar bewolkt en zware sneeuwval")
    elif icon == "tt":
        text = _("Zwaar bewolkt en zware sneeuwval")
    elif icon == "u":
        text = _("Wisselend bewolkt lichte sneeuwval")
    elif icon == "uu":
        text = _("Wisselend bewolkt lichte sneeuwval")
    elif icon == "v":
        text = _("Zwaar bewolkt lichte sneeuwval")
    elif icon == "vv":
        text = _("Zwaar bewolkt lichte sneeuwval")
    elif icon == "w":
        text = _("Zwaarbewolkt winterse neerslag")
    elif icon == "ww":
        text = _("Zwaarbewolkt winterse neerslag")
    else:
        text = _("Geen info")
    return text

def winddirtext(dirtext):
    text = ""
    if dirtext == "N":
        text = _("Noord")
    elif dirtext == "NO":
        text = _("NoordOost")
    elif dirtext == "O":
        text = _("Oost")
    elif dirtext == "ZO":
        text = _("ZuidOost")
    elif dirtext == "Z":
        text = _("Zuid")
    elif dirtext == "ZW":
        text = _("ZuidWest")
    elif dirtext == "W":
        text = _("West")
    elif dirtext == "NW":
        text = _("NoordWest")
    return text

def get_image_info(pic):
    try:
        with open(pic, "rb") as f:
            data = f.read()
    except (IOError, OSError):
        return 0
    if is_png(data) and len(data) >= 24:
        w, h = struct.unpack(">LL", data[16:24])
        return int(w), int(h)
    return 0

def is_png(data):
    return (data[:8] == b"\211PNG\r\n\032\n" and data[12:16] == b"IHDR")

def checkInternet():
    """Quick connectivity test against an official Buienradar endpoint."""
    try:
        response = urlopen(
            "https://image.buienradar.nl/2.0/image/single/RadarMapRainNL?height=1&width=1",
            timeout=5
        )
        try:
            response.read(16)
        finally:
            response.close()
        return True
    except (HTTPError, URLError, socket.timeout, OSError, IOError):
        return False

def getScale():
    return AVSwitch().getFramebufferScale()

sz_w = getDesktop(0).size().width()
state = ["","","","","","",""]

SavedLokaleWeer = []

weatherData = ["ohka"]
lockaaleStad = ""
selectedWeerDay = 0
CITY_DB_PATH = "/etc/enigma2/hetweer-cities.json"

CITY_ALIASES = {
    "ratingen": "Ratingen, Germany",
    "koeln": "Köln, Germany",
    "cologne": "Köln, Germany",
    "duesseldorf": "Düsseldorf, Germany",
    "dusseldorf": "Düsseldorf, Germany",
    "muenchen": "München, Germany",
    "munich": "München, Germany",
    "nuernberg": "Nürnberg, Germany",
    "nuremberg": "Nürnberg, Germany",
    "frankfurt am main": "Frankfurt am Main, Germany",
    "berlin de": "Berlin, Germany",
    "amsterdam nl": "Amsterdam, Netherlands",
    "brussels be": "Brussels, Belgium",
}

def _city_key(city):
    value = text_type(city or '').strip().lower()
    value = value.replace('ä', 'ae').replace('ö', 'oe').replace('ü', 'ue').replace('ß', 'ss')
    value = re.sub(r'\s+', ' ', value)
    return value

def _load_city_db():
    try:
        if not os.path.exists(CITY_DB_PATH):
            return {}
        with io.open(CITY_DB_PATH, encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (IOError, OSError, ValueError, TypeError):
        return {}

def _save_city_db(db):
    try:
        directory = os.path.dirname(CITY_DB_PATH)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)
        tmp = CITY_DB_PATH + '.tmp'
        with io.open(tmp, 'w', encoding='utf-8') as f:
            json.dump(db, f, ensure_ascii=False, indent=2, sort_keys=True)
        os.replace(tmp, CITY_DB_PATH)
        return True
    except (IOError, OSError, TypeError, ValueError):
        return False

def _parse_city_input(city):
    """Return a clean geocoding name and optional country code."""
    value = text_type(city or '').strip()
    if not value:
        return '', None
    m = re.match(r'^(.+?)[/_ ,]+([a-zA-Z]{2})$', value)
    if m:
        name = m.group(1).strip()
        code = m.group(2).lower()
        if code in ('de','nl','be','gb','fr','it','pl','at','ch','es','pt','dk','se','no','fi'):
            return name, code
    countries = {
        'germany': 'de', 'deutschland': 'de',
        'netherlands': 'nl', 'niederlande': 'nl', 'holland': 'nl',
        'belgium': 'be', 'belgien': 'be',
        'united kingdom': 'gb', 'great britain': 'gb', 'england': 'gb',
        'france': 'fr', 'frankreich': 'fr',
        'italy': 'it', 'italien': 'it',
        'poland': 'pl', 'polen': 'pl',
        'austria': 'at', 'österreich': 'at', 'oesterreich': 'at',
        'switzerland': 'ch', 'schweiz': 'ch',
        'denmark': 'dk', 'dänemark': 'dk', 'daenemark': 'dk',
        'sweden': 'se', 'schweden': 'se',
        'norway': 'no', 'norwegen': 'no',
        'finland': 'fi', 'finnland': 'fi',
    }
    m = re.match(r'^(.+?)[, ]+(.+)$', value)
    if m:
        name = m.group(1).strip()
        country_name = m.group(2).strip().lower()
        code = countries.get(country_name)
        if code:
            return name, code
    return value, None

GERMAN_CITY_DB = {
    "ratingen": {"name": "Ratingen", "latitude": 51.2953, "longitude": 6.8493, "timezone": "Europe/Berlin", "country": "Germany", "country_code": "de"},
    "ratingen, germany": {"name": "Ratingen", "latitude": 51.2953, "longitude": 6.8493, "timezone": "Europe/Berlin", "country": "Germany", "country_code": "de"},
    "duesseldorf": {"name": "Düsseldorf", "latitude": 51.2277, "longitude": 6.7735, "timezone": "Europe/Berlin", "country": "Germany", "country_code": "de"},
    "dusseldorf": {"name": "Düsseldorf", "latitude": 51.2277, "longitude": 6.7735, "timezone": "Europe/Berlin", "country": "Germany", "country_code": "de"},
    "koeln": {"name": "Köln", "latitude": 50.9375, "longitude": 6.9603, "timezone": "Europe/Berlin", "country": "Germany", "country_code": "de"},
    "muenchen": {"name": "München", "latitude": 48.1351, "longitude": 11.5820, "timezone": "Europe/Berlin", "country": "Germany", "country_code": "de"},
    "berlin": {"name": "Berlin", "latitude": 52.5200, "longitude": 13.4050, "timezone": "Europe/Berlin", "country": "Germany", "country_code": "de"},
    "hamburg": {"name": "Hamburg", "latitude": 53.5511, "longitude": 9.9937, "timezone": "Europe/Berlin", "country": "Germany", "country_code": "de"},
    "frankfurt am main": {"name": "Frankfurt am Main", "latitude": 50.1109, "longitude": 8.6821, "timezone": "Europe/Berlin", "country": "Germany", "country_code": "de"},
    "nuernberg": {"name": "Nürnberg", "latitude": 49.4521, "longitude": 11.0767, "timezone": "Europe/Berlin", "country": "Germany", "country_code": "de"},
}

def _geocode_city(city, save=True):
    """Resolve a place to coordinates, with aliases and a persistent local DB."""
    original = text_type(city or '').strip()
    if not original:
        return None
    db = _load_city_db()
    key = _city_key(original)
    if key in db:
        return db[key]

    query, country = _parse_city_input(original)
    local_key = _city_key(query)
    if local_key in GERMAN_CITY_DB:
        entry = dict(GERMAN_CITY_DB[local_key])
        if save:
            db[key] = entry
            db[_city_key(entry["name"])] = entry
            _save_city_db(db)
        return entry
    alias = CITY_ALIASES.get(_city_key(query))
    if alias:
        query = alias
        country = None

    attempts = [query]
    if country:
        attempts.insert(0, query + ' ' + country)
    result = None
    last_error = None
    for attempt in attempts:
        try:
            params = "name=%s&count=10&language=en&format=json" % quote(attempt)
            if country:
                params += "&countryCode=%s" % quote(country)
            url = "https://geocoding-api.open-meteo.com/v1/search?" + params
            response = urlopen(Request(url, headers={"User-Agent": "HetWeer/4.3.4 OpenATV"}), timeout=10)
            try:
                data = json.loads(_read_text(response))
            finally:
                response.close()
            results = data.get('results') or []
            for candidate in results:
                if candidate.get('latitude') is not None and candidate.get('longitude') is not None:
                    result = candidate
                    break
            if result:
                break
        except Exception as e:
            last_error = e

    if not result:
        if last_error:
            print("HetWeer: geocoding fout voor %s: %s" % (original, last_error))
        return None

    entry = {
        'name': text_type(result.get('name') or query),
        'latitude': float(result['latitude']),
        'longitude': float(result['longitude']),
        'timezone': text_type(result.get('timezone') or 'auto'),
        'country': text_type(result.get('country') or ''),
        'country_code': text_type(result.get('country_code') or '').lower(),
    }
    if save:
        db[_city_key(original)] = entry
        db[_city_key(entry['name'])] = entry
        _save_city_db(db)
    return entry

def _wind_direction(degrees):
    try:
        d = float(degrees) % 360.0
    except (TypeError, ValueError):
        return "NA"
    directions = ["N", "NO", "O", "ZO", "Z", "ZW", "W", "NW"]
    return directions[int((d + 22.5) / 45.0) % 8]

def _beaufort_from_kmh(speed):
    """Convert km/h to the standard Beaufort number."""
    try:
        kmh = float(speed)
    except (TypeError, ValueError):
        return None
    limits = [1, 5, 11, 19, 28, 38, 49, 61, 74, 88, 102, 117]
    for beaufort, upper in enumerate(limits):
        if kmh < upper:
            return beaufort
    return 12

def _wmo_to_icon(code, is_day=True):
    """Map WMO weather codes to the legacy HetWeer icon names."""
    try:
        code = int(code)
    except (TypeError, ValueError):
        return "a" if is_day else "aa"
    if code == 0:
        return "a" if is_day else "aa"
    if code in (1, 2):
        return "b" if is_day else "bb"
    if code == 3:
        return "c" if is_day else "cc"
    if code in (45, 48):
        return "n" if is_day else "nn"
    if code in (51, 53, 55, 56, 57):
        return "f" if is_day else "ff"
    if code in (61, 63, 65, 66, 67, 80, 81, 82):
        return "g" if is_day else "gg"
    if code in (71, 73, 75, 77, 85, 86):
        return "u" if is_day else "uu"
    if code in (95,):
        return "s" if is_day else "ss"
    if code in (96, 99):
        return "q" if is_day else "qq"
    return "r" if is_day else "rr"

def _build_weather_data(api_data):
    """Convert Open-Meteo JSON to the data structure used by the old UI."""
    hourly = api_data.get('hourly') or {}
    daily = api_data.get('daily') or {}
    current = api_data.get('current') or {}
    times = hourly.get('time') or []
    if not times:
        raise ValueError("Open-Meteo: keine Stundenwerte")

    def arr(name):
        values = hourly.get(name) or []
        return values if isinstance(values, list) else []

    h_temp = arr('temperature_2m')
    h_apparent = arr('apparent_temperature')
    h_precip_prob = arr('precipitation_probability')
    h_wind = arr('wind_speed_10m')
    h_winddir = arr('wind_direction_10m')
    h_code = arr('weather_code')
    h_isday = arr('is_day')

    current_time = text_type(current.get('time') or '')
    current_index = 0
    if current_time:
        candidates = [i for i, value in enumerate(times) if text_type(value) <= current_time]
        if candidates:
            current_index = candidates[-1]
    today = text_type(times[current_index])[:10]

    hourly_records = []
    for i, iso in enumerate(times):
        if i >= len(h_temp):
            break
        day = text_type(iso)[:10]
        isday = bool(h_isday[i]) if i < len(h_isday) and h_isday[i] is not None else True
        temp = h_temp[i]
        apparent = h_apparent[i] if i < len(h_apparent) else None
        precip = h_precip_prob[i] if i < len(h_precip_prob) else None
        wind = h_wind[i] if i < len(h_wind) else None
        winddir = h_winddir[i] if i < len(h_winddir) else None
        wcode = h_code[i] if i < len(h_code) else 0
        try:
            hour = int(text_type(iso)[11:13])
        except (ValueError, TypeError):
            hour = 0
        hourly_records.append({
            'time': iso,
            'date': day,
            'hour': hour,
            'temperature': temp,
            'feeltemperature': apparent,
            'precipitation': round(float(precip), 0) if precip is not None else None,
            'precipation': round(float(precip), 0) if precip is not None else None,
            'precipitationProbability': round(float(precip), 0) if precip is not None else None,
            'windspeed': round(float(wind), 0) if wind is not None else None,
            'windpower': round(float(wind), 0) if wind is not None else None,
            'winddirection': _wind_direction(winddir),
            'winddirectiondegrees': winddir,
            'iconcode': _wmo_to_icon(wcode, isday),
            'weathercode': wcode,
        })

    by_day = {}
    for record in hourly_records:
        by_day.setdefault(record['date'], []).append(record)

    daily_time = daily.get('time') or []
    d_min = daily.get('temperature_2m_min') or []
    d_max = daily.get('temperature_2m_max') or []
    d_code = daily.get('weather_code') or []
    d_wind = daily.get('wind_speed_10m_max') or []
    d_winddir = daily.get('wind_direction_10m_dominant') or []
    d_precip = daily.get('precipitation_probability_max') or []
    d_rain = daily.get('precipitation_sum') or []

    days = []
    for i, day_date in enumerate(daily_time[:8]):
        day_hours = by_day.get(text_type(day_date), [])
        if text_type(day_date) == today and day_hours:
            idx = 0
            for j, rec in enumerate(day_hours):
                if rec['time'][:13] >= current_time[:13]:
                    idx = j
                    break
            day_hours = day_hours[idx:] + day_hours[:idx]
        minv = d_min[i] if i < len(d_min) else None
        maxv = d_max[i] if i < len(d_max) else None
        code = d_code[i] if i < len(d_code) else 0
        wind = d_wind[i] if i < len(d_wind) else None
        winddir = d_winddir[i] if i < len(d_winddir) else None
        precip = d_precip[i] if i < len(d_precip) else None
        rain = d_rain[i] if i < len(d_rain) else None
        days.append({
            'date': text_type(day_date) + 'T12:00:00',
            'mintemperature': minv,
            'maxtemperature': maxv,
            'mintemp': minv,
            'maxtemp': maxv,
            'windspeed': wind,
            'winddirection': _wind_direction(winddir),
            'beaufort': _beaufort_from_kmh(wind),
            'iconcode': _wmo_to_icon(code, True),
            'weathercode': code,
            'precipitation_probability': precip,
            'precipitation_sum': rain,
            'hours': day_hours,
        })

    result = {
        'days': days,
        'current': {
            'temperature': current.get('temperature_2m'),
            'feeltemperature': current.get('apparent_temperature'),
            'winddirection': _wind_direction(current.get('wind_direction_10m')),
            'windspeed': current.get('wind_speed_10m'),
            'iconcode': _wmo_to_icon(current.get('weather_code'), bool(current.get('is_day', 1))),
            'weathercode': current.get('weather_code'),
            'time': current.get('time'),
        },
    }
    return result

def getLocWeer(iscity=None):
    global lockaaleStad, weatherData
    inputCity = text_type(iscity).strip() if iscity is not None else ''
    try:
        if not inputCity:
            response = urlopen("https://ip-api.com/json", timeout=5)
            try:
                geo = json.loads(_read_text(response))
            finally:
                response.close()
            inputCity = text_type(geo.get('city') or '').strip()
        if not inputCity:
            return False

        location = _geocode_city(inputCity, save=True)
        if not location:
            query_name, _country = _parse_city_input(inputCity)
            if query_name and _city_key(query_name) != _city_key(inputCity):
                location = _geocode_city(query_name, save=True)
        if not location:
            print("HetWeer: Ort/Geocoding nicht verfügbar für %s" % inputCity)
            return False

        latitude = float(location['latitude'])
        longitude = float(location['longitude'])
        resolved_name = text_type(location.get('name') or inputCity)
        timezone = text_type(location.get('timezone') or 'auto')

        params = (
            "latitude=%.6f&longitude=%.6f&current="
            "temperature_2m,apparent_temperature,weather_code,is_day,wind_speed_10m,wind_direction_10m"
            "&hourly=temperature_2m,apparent_temperature,precipitation_probability,"
            "weather_code,wind_speed_10m,wind_direction_10m,is_day"
            "&daily=temperature_2m_min,temperature_2m_max,weather_code,wind_speed_10m_max,"
            "wind_direction_10m_dominant,precipitation_probability_max,precipitation_sum"
            "&forecast_days=8&timezone=%s&temperature_unit=celsius&wind_speed_unit=kmh"
            % (latitude, longitude, quote(timezone))
        )
        forecast_url = "https://api.open-meteo.com/v1/forecast?" + params
        print("HetWeer: Wetterabfrage %s" % forecast_url)
        response = urlopen(Request(forecast_url, headers={"User-Agent": "HetWeer/4.3.5 OpenATV", "Accept": "application/json"}), timeout=20)
        try:
            data = json.loads(_read_text(response))
        finally:
            response.close()
        weatherData = _build_weather_data(data)
        lockaaleStad = resolved_name
        print("HetWeer: %s -> %.6f, %.6f (%s)" % (resolved_name, latitude, longitude, timezone))
        return True
    except (HTTPError, URLError, socket.timeout, OSError, IOError, ValueError, KeyError, TypeError) as e:
        print("HetWeer: getLocWeer fout voor %s: %s" % (inputCity, e))
        return False
    except Exception as e:
        print("HetWeer: onverwachte fout in getLocWeer: %s" % e)
        return False

def weatherchat(country):
    urls = {
        "nl/Nederland/weerbericht": "https://www.buienradar.nl/nederland/weerbericht/weerbericht",
        "be/Belgie/weerbericht": "https://www.buienradar.be/belgie/weerbericht/weerbericht",
        "nl/wereldwijd/europa": "https://www.buienradar.nl/wereldwijd/europa/weerbericht",
    }
    url = urls.get(country)
    if not url:
        url = "https://www.buienradar." + country.lstrip("/")
        if not url.endswith("/weerbericht"):
            url += "/weerbericht"

    def clean_html(fragment):
        fragment = re.sub(r'<br\s*/?>', '\n', fragment, flags=re.IGNORECASE)
        fragment = re.sub(r'</(p|div|li|h[1-6])\s*>', '\n', fragment, flags=re.IGNORECASE)
        fragment = re.sub(r'<[^>]+>', '', fragment)
        fragment = fragment.replace('&nbsp;', ' ')
        fragment = re.sub(r'&(?:amp|lt|gt|quot|apos);', lambda m: {
            '&amp;': '&', '&lt;': '<', '&gt;': '>',
            '&quot;': '"', '&apos;': "'"
        }.get(m.group(0), m.group(0)), fragment)
        fragment = re.sub(r'\s+', ' ', fragment).strip()
        return fragment

    try:
        req = Request(url, headers={"User-Agent": "Mozilla/5.0 (Enigma2 HetWeer)"})
        response = urlopen(req, timeout=10)
        try:
            kaas = _read_text(response)
        finally:
            response.close()

        container = re.search(
            r'<div[^>]*id=["\']readarea["\'][^>]*class=["\']description["\'][^>]*>(.*?)</div>',
            kaas, re.DOTALL | re.IGNORECASE)
        if container:
            body = container.group(1)
            paragraphs = re.findall(r'<p\b[^>]*>(.*?)</p\s*>', body, re.DOTALL | re.IGNORECASE)
            cleaned = []
            for item in paragraphs:
                text = clean_html(item)
                if text:
                    cleaned.append('<p>' + text + '</p>')
            if cleaned:
                return ''.join(cleaned)
            text = clean_html(body)
            if text:
                return '<p>' + text + '</p>'

        h1 = re.search(r'<h1\b[^>]*>(.*?)</h1\s*>', kaas, re.DOTALL | re.IGNORECASE)
        paragraphs = re.findall(r'<p\b[^>]*>(.*?)</p\s*>', kaas, re.DOTALL | re.IGNORECASE)
        cleaned = []
        if h1:
            title = clean_html(h1.group(1))
            if title:
                cleaned.append('<p>' + title + '</p>')
        for item in paragraphs:
            text = clean_html(item)
            if len(text) >= 30:
                cleaned.append('<p>' + text + '</p>')
        if cleaned:
            return ''.join(cleaned)

        print("HetWeer: weatherchat: geen weerbericht gevonden voor %s (%s)" % (country, url))
        return _("Geen weerbericht beschikbaar")
    except (HTTPError, URLError, socket.timeout, OSError, ValueError) as e:
        print("HetWeer: weatherchat fout voor %s: %s" % (country, e))
        return _("Weerbericht tijdelijk niet beschikbaar")

class startScreen(Screen):
    sz_w = getDesktop(0).size().width()
    if sz_w > 1800:
        skin = """
        <screen name="startScreen" position="fill" flags="wfNoBorder">
            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/borders/bigline87.png" position="0,0" size="1920,87" />
            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/borders/smallline3.png" position="0,87" size="1920,3" zPosition="1" />
            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/borders/smallline3.png" position="0,1020" size="1920,3" zPosition="1" />
            <widget source="global.CurrentTime" render="Label" position="1665,20" size="225,37" transparent="1" zPosition="1" font="Regular;36" borderColor="black" borderWidth="1" valign="center" halign="right">
  <convert type="ClockToText">Format:H:%M:%S</convert>
</widget>
            <widget source="global.CurrentTime" render="Label" position="1440,52" size="450,37" transparent="1" zPosition="1" font="Regular;24" borderColor="black" borderWidth="1" valign="center" halign="right" foregroundColor="green">
  <convert type="ClockToText">Format:%a %d.%m.%y</convert>
</widget>
            <widget source="session.VideoPicture" render="Pig" position="40,173" size="720,405" backgroundColor="#ff000000" zPosition="1" />
            <widget source="session.CurrentService" render="Label" position="30,104" size="720,51" zPosition="1" transparent="1" font="Regular;28" borderColor="black" borderWidth="1" noWrap="1" valign="center" halign="center"><convert type="ServiceName">Name</convert></widget>
            <widget name="list" position="920,110" size="975,375" scrollbarMode="showOnDemand" font="Regular;51" itemHeight="63" selectionPixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/list/list97563.png" />\n
            <widget name="mess1" position="884,1034" size="500,30" foregroundColor="green" font="Console;24" />\n            <widget name="version" position="1410,1030" size="480,34" foregroundColor="white" transparent="1" font="Regular;22" halign="right" valign="center" />\n
            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/lo/nlflaghd.png" position="794,114" size="71,49" alphatest="on" />
            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/lo/beflaghd.png" position="794,177" size="71,49" alphatest="on" />
            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/lo/euflaghd.png" position="794,240" size="71,49" alphatest="on" />
            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/lo/lokaalhd.png" position="794,303" size="71,49" alphatest="on" />
            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/buttons/red34.png" position="192,1032" size="34,34" alphatest="blend" />
            <widget name="key_red" position="242,1030" size="370,38" zPosition="1" transparent="1" font="Regular;34" borderColor="black" borderWidth="1" halign="left" />
            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/buttons/green34.png" position="628,1032" size="34,34" alphatest="blend" />
            <widget name="key_green" position="678,1030" size="370,38" zPosition="1" transparent="1" font="Regular;34" borderColor="black" borderWidth="1" halign="left" />
<widget source="Title" render="Label" position="46,34" size="850,52" font="Bold; 32" noWrap="1" transparent="1" valign="center" halign="left" zPosition="1" foregroundColor="blue" backgroundColor="black" />
        </screen>"""

    else:
        skin = """
        <screen name="startScreen" position="fill" flags="wfNoBorder">
            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/borders/bigline87.png" position="0,0" size="1920,87" />
            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/borders/smallline3.png" position="0,87" size="1920,3" zPosition="1" />
            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/borders/smallline3.png" position="0,1020" size="1920,3" zPosition="1" />
            <widget source="global.CurrentTime" render="Label" position="1665,20" size="225,37" transparent="1" zPosition="1" font="Regular;36" borderColor="black" borderWidth="1" valign="center" halign="right">
  <convert type="ClockToText">Format:H:%M:%S</convert>
</widget>
            <widget source="global.CurrentTime" render="Label" position="1440,52" size="450,37" transparent="1" zPosition="1" font="Regular;24" borderColor="black" borderWidth="1" valign="center" halign="right" foregroundColor="green">
  <convert type="ClockToText">Format:%a %d.%m.%y</convert>
</widget>
            <widget source="session.VideoPicture" render="Pig" position="40,173" size="720,405" backgroundColor="#ff000000" zPosition="1" />
            <widget source="session.CurrentService" render="Label" position="30,104" size="720,51" zPosition="1" transparent="1" font="Regular;28" borderColor="black" borderWidth="1" noWrap="1" valign="center" halign="center"><convert type="ServiceName">Name</convert></widget>
            <widget name="list" position="920,110" size="975,375" scrollbarMode="showOnDemand" font="Regular;51" itemHeight="63" selectionPixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/list/list97563.png" />\n
            <widget name="mess1" position="884,1034" size="500,30" foregroundColor="green" font="Console;24" />\n            <widget name="version" position="1410,1030" size="480,34" foregroundColor="white" transparent="1" font="Regular;22" halign="right" valign="center" />\n
            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/lo/nlflaghd.png" position="794,114" size="71,49" alphatest="on" />
            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/lo/beflaghd.png" position="794,177" size="71,49" alphatest="on" />
            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/lo/euflaghd.png" position="794,240" size="71,49" alphatest="on" />
            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/lo/lokaalhd.png" position="794,303" size="71,49" alphatest="on" />
            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/buttons/red34.png" position="192,1032" size="34,34" alphatest="blend" />
            <widget name="key_red" position="242,1030" size="370,38" zPosition="1" transparent="1" font="Regular;34" borderColor="black" borderWidth="1" halign="left" />
            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/buttons/green34.png" position="628,1032" size="34,34" alphatest="blend" />
            <widget name="key_green" position="678,1030" size="370,38" zPosition="1" transparent="1" font="Regular;34" borderColor="black" borderWidth="1" halign="left" />
<widget source="Title" render="Label" position="46,34" size="850,52" font="Bold; 32" noWrap="1" transparent="1" valign="center" halign="left" zPosition="1" foregroundColor="blue" backgroundColor="black" />
        </screen>"""

    titleValues = ["Nederland", "Belgie", "Europa", "WeerInfo"]
    titleNames = [_(x) for x in titleValues]
    def __init__(self, session):
        self.session = session
        self["mess1"] = ScrollLabel("")
        self["version"] = Label("HetWeer v" + versienummer)
        self["key_red"] = Label(_("Exit"))
        self["key_green"] = Label(_("Ok"))
        self.skin = startScreen.skin
        Screen.__init__(self, session)
        list = []
        for x in startScreen.titleNames:
            list.append((x))
        self["list"] = MenuList(list)
        self["actions"] = ActionMap(["WizardActions"], {"ok": self.go, "back": self.close}, -1)
        self["ColorActions"] = HelpableActionMap(self, "ColorActions", {"red": self.exit, "green": self.go}, -1)
        dir = "/tmp/HetWeer/"
        if not os.path.exists(dir):
            os.makedirs(dir)

    def go(self):
        global state
        index = self["list"].getSelectedIndex()
        state[0] = startScreen.titleValues[index]
        if state[0] == "WeerInfo":
            self.session.open(localcityscreen)
        else:
            self.session.open(weatherMenuSub)

    def exit(self):
        self.close()

    def checkupg(self):
        self.session.open(
            MessageBox,
            _("Automatische update is momenteel niet beschikbaar."),
            MessageBox.TYPE_INFO
        )

    def htwUpdateMain(self):
        self.checkupg()

    def htwinfoUpdate(self, htwmupg):
        self.checkupg()

class weeroverview(Screen):
    sz_w = getDesktop(0).size().width()

    def __init__(self, session):
        global weatherData
        # Auswahl des aktuellen Tages für die 7-Tage-/Stundenansicht
        self.selected = 0
        dataDagen = weatherData["days"]

        protemp = []
        peocpic = ""
        try:
            for procdays in dataDagen:
                for prochours in procdays["hours"]:
                    protemp.append(round(prochours["temperature"]))
                if len(protemp) > 3:
                    break
        except Exception:
            pass
        while len(protemp) < 2:
            protemp.append(protemp[-1] if protemp else 0)
        if protemp[0] > protemp[1]:
            peocpic = "tempcold.png"
        elif protemp[0] < protemp[1]:
            peocpic = "temphot.png"
        else:
            peocpic = "tempeven.png"

        if sz_w > 1800:
            skin = """
                <screen name="weeroverview" position="fill" flags="wfNoBorder">
                    <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/backgroundhd.png" position="center,center" size="1920,1080" zPosition="0" alphatest="on" />
                    <widget source="global.CurrentTime" render="Label" position="1665,22" size="225,37" transparent="1" zPosition="5" font="Regular;36" borderColor="black" borderWidth="1" valign="center" halign="right">
  <convert type="ClockToText">Format:%H:%M:%S</convert>
</widget>
                    <widget source="global.CurrentTime" render="Label" position="1440,52" size="450,37" transparent="1" zPosition="5" font="Regular;24" borderColor="black" borderWidth="1" valign="center" halign="right" foregroundColor="green">
  <convert type="ClockToText">Format:%a %d.%m.%y</convert>
</widget>
                    <widget name="currentWeatherIcon" position="620,113" size="140,140" zPosition="4" alphatest="on" />
                    <widget name="yellowdot" position="60,389" size="36,36" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/buttons/yeldot.png" zPosition="6" alphatest="on" />
                    <widget name="city1" position="608,56" size="705,64" zPosition="5" valign="center" halign="center" font="Regular;48" transparent="1" borderColor="black" borderWidth="1" foregroundColor="bpSide" />
                    <widget name="bigtemp1" position="760,130" size="353,118" zPosition="5" valign="center" halign="left" font="Regular;108" transparent="1" borderColor="black" borderWidth="1" />
                    <widget name="bigweathertype1" position="770,270" size="480,40" zPosition="5" valign="center" halign="left" font="Regular;28" transparent="1" borderColor="black" borderWidth="1" foregroundColor="green" />
                    <widget name="GevoelsTemp1" position="775,230" size="354,40" zPosition="5" valign="center" halign="left" font="Regular;28" transparent="1" borderColor="black" borderWidth="1" foregroundColor="blue" />
                    <widget name="winddir1" position="770,315" size="345,40" zPosition="5" valign="center" halign="left" font="Regular;28" transparent="1" borderColor="black" borderWidth="1" foregroundColor="yellow" />
                <widget name="bigWeerIcon10" position="111,522" size="100,100" zPosition="2" alphatest="on" />
                <widget name="bigDirIcon10" position="133,555" size="42,42" zPosition="3" alphatest="on" />
                <widget name="smallday20" position="111,469" size="210,30" zPosition="3" valign="center" halign="center" font="Regular; 25" borderColor="black" borderWidth="1" transparent="1" />
                <widget name="midtemp20" position="226,531" size="80,36" zPosition="3" font="Regular;32" borderColor="black" borderWidth="1" transparent="1" foregroundColor="blue" />
                <widget name="minitemp20" position="242,604" size="45,22" zPosition="3" valign="center" halign="left" font="Regular;18" borderColor="black" borderWidth="1" transparent="1" />
                <widget name="weertype20" position="111,625" size="210,100" zPosition="3" valign="center" halign="center" font="Regular; 22" borderColor="black" borderWidth="1" transparent="1" foregroundColor="bpSide" />
                <widget name="dayIcon00" position="120,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon01" position="336,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon02" position="552,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon03" position="768,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon04" position="984,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon05" position="1200,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon06" position="1416,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon07" position="1632,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="bigWeerIcon11" position="357,520" size="100,100" zPosition="2" alphatest="on" />
                <widget name="bigDirIcon11" position="385,546" size="42,42" zPosition="3" alphatest="on" />
                <widget name="smallday21" position="359,469" size="210,30" zPosition="3" valign="center" halign="center" font="Regular; 25" borderColor="black" borderWidth="1" transparent="1" />
                <widget name="midtemp21" position="464,532" size="80,36" zPosition="3" font="Regular;32" borderColor="black" borderWidth="1" transparent="1" foregroundColor="blue" />
                <widget name="minitemp21" position="479,593" size="45,22" zPosition="3" valign="center" halign="left" font="Regular;18" borderColor="black" borderWidth="1" transparent="1" foregroundColor="green" />
                <widget name="weertype21" position="358,625" size="210,100" zPosition="3" valign="center" halign="center" font="Regular; 22" borderColor="black" borderWidth="1" transparent="1" foregroundColor="bpSide" />
                <widget name="dayIcon10" position="120,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon11" position="336,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon12" position="552,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon13" position="768,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon14" position="984,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon15" position="1200,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon16" position="1416,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon17" position="1632,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="bigWeerIcon12" position="603,522" size="100,100" zPosition="2" alphatest="on" />
                <widget name="bigDirIcon12" position="631,548" size="42,42" zPosition="3" alphatest="on" />
                <widget name="smallday22" position="606,469" size="210,30" zPosition="3" valign="center" halign="center" font="Regular;22" borderColor="black" borderWidth="1" transparent="1" />
                <widget name="midtemp22" position="717,532" size="80,36" zPosition="3" font="Regular;32" borderColor="black" borderWidth="1" transparent="1" foregroundColor="blue" />
                <widget name="minitemp22" position="732,593" size="45,22" zPosition="3" valign="center" halign="left" font="Regular;18" borderColor="black" borderWidth="1" transparent="1" foregroundColor="green" />
                <widget name="weertype22" position="603,625" size="210,100" zPosition="3" valign="center" halign="center" font="Regular; 22" borderColor="black" borderWidth="1" transparent="1" foregroundColor="bpSide" />
                <widget name="dayIcon20" position="120,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon21" position="336,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon22" position="552,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon23" position="768,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon24" position="984,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon25" position="1200,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon26" position="1416,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon27" position="1632,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="bigWeerIcon13" position="853,522" size="100,100" zPosition="2" alphatest="on" />
                <widget name="bigDirIcon13" position="880,551" size="42,42" zPosition="3" alphatest="on" />
                <widget name="smallday23" position="852,469" size="210,30" zPosition="3" valign="center" halign="left" font="Regular;22" borderColor="black" borderWidth="1" transparent="1" />
                <widget name="midtemp23" position="975,532" size="80,36" zPosition="3" font="Regular;32" borderColor="black" borderWidth="1" transparent="1" foregroundColor="blue" />
                <widget name="minitemp23" position="986,593" size="45,22" zPosition="3" valign="center" halign="left" font="Regular;18" borderColor="black" borderWidth="1" transparent="1" foregroundColor="green" />
                <widget name="weertype23" position="852,625" size="210,100" zPosition="3" valign="center" halign="center" font="Regular; 22" borderColor="black" borderWidth="1" transparent="1" foregroundColor="bpSide" />
                <widget name="dayIcon30" position="120,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon31" position="336,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon32" position="552,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon33" position="768,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon34" position="984,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon35" position="1200,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon36" position="1416,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon37" position="1632,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="bigWeerIcon14" position="1098,522" size="100,100" zPosition="2" alphatest="on" />
                <widget name="bigDirIcon14" position="1127,549" size="42,42" zPosition="3" alphatest="on" />
                <widget name="smallday24" position="1101,469" size="210,30" zPosition="3" valign="center" halign="left" font="Regular;22" borderColor="black" borderWidth="1" transparent="1" />
                <widget name="midtemp24" position="1211,532" size="80,36" zPosition="3" font="Regular;32" borderColor="black" borderWidth="1" transparent="1" foregroundColor="blue" />
                <widget name="minitemp24" position="1227,593" size="45,22" zPosition="3" valign="center" halign="left" font="Regular;18" borderColor="black" borderWidth="1" transparent="1" foregroundColor="green" />
                <widget name="weertype24" position="1097,625" size="210,100" zPosition="3" valign="center" halign="center" font="Regular; 22" borderColor="black" borderWidth="1" transparent="1" foregroundColor="bpSide" />
                <widget name="dayIcon40" position="120,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon41" position="336,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon42" position="552,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon43" position="768,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon44" position="984,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon45" position="1200,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon46" position="1416,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon47" position="1632,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="bigWeerIcon15" position="1348,522" size="100,100" zPosition="2" alphatest="on" />
                <widget name="bigDirIcon15" position="1377,551" size="42,42" zPosition="3" alphatest="on" />
                <widget name="smallday25" position="1352,469" size="210,30" zPosition="3" valign="center" halign="center" font="Regular;22" borderColor="black" borderWidth="1" transparent="1" />
                <widget name="midtemp25" position="1469,532" size="80,36" zPosition="3" font="Regular;32" borderColor="black" borderWidth="1" transparent="1" foregroundColor="blue" />
                <widget name="minitemp25" position="1486,593" size="45,22" zPosition="3" valign="center" halign="left" font="Regular;18" borderColor="black" borderWidth="1" transparent="1" foregroundColor="green" />
                <widget name="weertype25" position="1345,625" size="210,100" zPosition="3" valign="center" halign="center" font="Regular; 22" borderColor="black" borderWidth="1" transparent="1" foregroundColor="bpSide" />
                <widget name="dayIcon50" position="120,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon51" position="336,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon52" position="552,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon53" position="768,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon54" position="984,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon55" position="1200,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon56" position="1416,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon57" position="1632,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="bigWeerIcon16" position="1594,522" size="100,100" zPosition="2" alphatest="on" />
                <widget name="bigDirIcon16" position="1625,550" size="42,42" zPosition="3" alphatest="on" />
                <widget name="smallday26" position="1594,469" size="210,30" zPosition="3" valign="center" halign="center" font="Regular;22" borderColor="black" borderWidth="1" transparent="1" />
                <widget name="midtemp26" position="1713,532" size="80,36" zPosition="3" font="Regular;32" borderColor="black" borderWidth="1" transparent="1" foregroundColor="blue" />
                <widget name="minitemp26" position="1723,593" size="45,22" zPosition="3" valign="center" halign="left" font="Regular;18" borderColor="black" borderWidth="1" transparent="1" foregroundColor="green" />
                <widget name="weertype26" position="1596,625" size="210,100" zPosition="3" valign="center" halign="center" font="Regular; 22" borderColor="black" borderWidth="1" transparent="1" foregroundColor="bpSide" />
                <widget name="dayIcon60" position="120,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon61" position="336,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon62" position="552,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon63" position="768,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon64" position="984,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon65" position="1200,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon66" position="1416,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon67" position="1632,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayhour30" position="195,779" size="90,36" zPosition="3" valign="center" halign="right" font="Regular;33" transparent="1" borderColor="black" borderWidth="1" />
                <widget name="daytemp30" position="120,870" size="180,54" zPosition="3" valign="center" halign="left" font="Regular;48" transparent="1" borderColor="black" borderWidth="1" />
                <widget name="daypercent30" position="168,945" size="120,30" zPosition="3" valign="center" halign="left" font="Regular;27" transparent="1" borderColor="black" borderWidth="1" />
                <widget name="dayspeed30" position="168,986" size="123,32" zPosition="3" valign="center" halign="left" font="Regular;27" transparent="1" borderColor="black" borderWidth="1" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/windhd/turbinehd.png" position="119,983" size="38,38" zPosition="3" alphatest="on" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/windhd/druphd.png" position="120,945" size="15,23" zPosition="3" alphatest="on" />
                <widget name="dayhour31" position="411,779" size="90,36" zPosition="3" valign="center" halign="right" font="Regular;33" transparent="1" borderColor="black" borderWidth="1" />
                <widget name="daytemp31" position="336,870" size="180,54" zPosition="3" valign="center" halign="left" font="Regular;48" transparent="1" borderColor="black" borderWidth="1" />
                <widget name="daypercent31" position="384,945" size="120,30" zPosition="3" valign="center" halign="left" font="Regular;27" transparent="1" borderColor="black" borderWidth="1" />
                <widget name="dayspeed31" position="384,986" size="123,32" zPosition="3" valign="center" halign="left" font="Regular;27" transparent="1" borderColor="black" borderWidth="1" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/windhd/turbinehd.png" position="335,983" size="38,38" zPosition="3" alphatest="on" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/windhd/druphd.png" position="336,945" size="15,23" zPosition="3" alphatest="on" />
                <widget name="dayhour32" position="627,779" size="90,36" zPosition="3" valign="center" halign="right" font="Regular;33" transparent="1" borderColor="black" borderWidth="1" />
                <widget name="daytemp32" position="552,870" size="180,54" zPosition="3" valign="center" halign="left" font="Regular;48" transparent="1" borderColor="black" borderWidth="1" />
                <widget name="daypercent32" position="600,945" size="120,30" zPosition="3" valign="center" halign="left" font="Regular;27" transparent="1" borderColor="black" borderWidth="1" />
                <widget name="dayspeed32" position="600,986" size="123,32" zPosition="3" valign="center" halign="left" font="Regular;27" transparent="1" borderColor="black" borderWidth="1" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/windhd/turbinehd.png" position="551,983" size="38,38" zPosition="3" alphatest="on" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/windhd/druphd.png" position="552,945" size="15,23" zPosition="3" alphatest="on" />
                <widget name="dayhour33" position="843,779" size="90,36" zPosition="3" valign="center" halign="right" font="Regular;33" transparent="1" borderColor="black" borderWidth="1" />
                <widget name="daytemp33" position="768,870" size="180,54" zPosition="3" valign="center" halign="left" font="Regular;48" transparent="1" borderColor="black" borderWidth="1" />
                <widget name="daypercent33" position="816,945" size="120,30" zPosition="3" valign="center" halign="left" font="Regular;27" transparent="1" borderColor="black" borderWidth="1" />
                <widget name="dayspeed33" position="816,986" size="123,32" zPosition="3" valign="center" halign="left" font="Regular;27" transparent="1" borderColor="black" borderWidth="1" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/windhd/turbinehd.png" position="767,983" size="38,38" zPosition="3" alphatest="on" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/windhd/druphd.png" position="768,945" size="15,23" zPosition="3" alphatest="on" />
                <widget name="dayhour34" position="1059,779" size="90,36" zPosition="3" valign="center" halign="right" font="Regular;33" transparent="1" borderColor="black" borderWidth="1" />
                <widget name="daytemp34" position="984,870" size="180,54" zPosition="3" valign="center" halign="left" font="Regular;48" transparent="1" borderColor="black" borderWidth="1" />
                <widget name="daypercent34" position="1032,945" size="120,30" zPosition="3" valign="center" halign="left" font="Regular;27" transparent="1" borderColor="black" borderWidth="1" />
                <widget name="dayspeed34" position="1032,986" size="123,32" zPosition="3" valign="center" halign="left" font="Regular;27" transparent="1" borderColor="black" borderWidth="1" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/windhd/turbinehd.png" position="983,983" size="38,38" zPosition="3" alphatest="on" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/windhd/druphd.png" position="984,945" size="15,23" zPosition="3" alphatest="on" />
                <widget name="dayhour35" position="1275,779" size="90,36" zPosition="3" valign="center" halign="right" font="Regular;33" transparent="1" borderColor="black" borderWidth="1" />
                <widget name="daytemp35" position="1200,870" size="180,54" zPosition="3" valign="center" halign="left" font="Regular;48" transparent="1" borderColor="black" borderWidth="1" />
                <widget name="daypercent35" position="1248,945" size="120,30" zPosition="3" valign="center" halign="left" font="Regular;27" transparent="1" borderColor="black" borderWidth="1" />
                <widget name="dayspeed35" position="1248,986" size="123,32" zPosition="3" valign="center" halign="left" font="Regular;27" transparent="1" borderColor="black" borderWidth="1" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/windhd/turbinehd.png" position="1199,983" size="38,38" zPosition="3" alphatest="on" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/windhd/druphd.png" position="1200,945" size="15,23" zPosition="3" alphatest="on" />
                <widget name="dayhour36" position="1491,779" size="90,36" zPosition="3" valign="center" halign="right" font="Regular;33" transparent="1" borderColor="black" borderWidth="1" />
                <widget name="daytemp36" position="1416,870" size="180,54" zPosition="3" valign="center" halign="left" font="Regular;48" transparent="1" borderColor="black" borderWidth="1" />
                <widget name="daypercent36" position="1464,945" size="120,30" zPosition="3" valign="center" halign="left" font="Regular;27" transparent="1" borderColor="black" borderWidth="1" />
                <widget name="dayspeed36" position="1464,986" size="123,32" zPosition="3" valign="center" halign="left" font="Regular;27" transparent="1" borderColor="black" borderWidth="1" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/windhd/turbinehd.png" position="1415,983" size="38,38" zPosition="3" alphatest="on" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/windhd/druphd.png" position="1416,945" size="15,23" zPosition="3" alphatest="on" />
                <widget name="dayhour37" position="1707,779" size="90,36" zPosition="3" valign="center" halign="right" font="Regular;33" transparent="1" borderColor="black" borderWidth="1" />
                <widget name="daytemp37" position="1632,870" size="180,54" zPosition="3" valign="center" halign="left" font="Regular;48" transparent="1" borderColor="black" borderWidth="1" />
                <widget name="daypercent37" position="1680,945" size="120,30" zPosition="3" valign="center" halign="left" font="Regular;27" transparent="1" borderColor="black" borderWidth="1" />
                <widget name="dayspeed37" position="1680,986" size="123,32" zPosition="3" valign="center" halign="left" font="Regular;27" transparent="1" borderColor="black" borderWidth="1" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/windhd/turbinehd.png" position="1631,983" size="38,38" zPosition="3" alphatest="on" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/windhd/druphd.png" position="1632,945" size="15,23" zPosition="3" alphatest="on" />
                    <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/windhd/%s" position="1112,155" size="90,80" zPosition="2" transparent="0" alphatest="blend" />
        </screen>""".replace("%PEOCPIC%", peocpic)
        else:
            skin = """
            <screen name="weeroverview" position="fill" flags="wfNoBorder">
                    <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/backgroundhd.png" position="center,center" size="1920,1080" zPosition="0" alphatest="on" />
                    <widget source="global.CurrentTime" render="Label" position="1665,22" size="225,37" transparent="1" zPosition="5" font="Regular;36" borderColor="black" borderWidth="1" valign="center" halign="right">
  <convert type="ClockToText">Format:%H:%M:%S</convert>
</widget>
                    <widget source="global.CurrentTime" render="Label" position="1440,52" size="450,37" transparent="1" zPosition="5" font="Regular;24" borderColor="black" borderWidth="1" valign="center" halign="right" foregroundColor="green">
  <convert type="ClockToText">Format:%a %d.%m.%y</convert>
</widget>
                    <widget name="currentWeatherIcon" position="900,70" size="140,140" zPosition="4" alphatest="on" />
                    <widget name="yellowdot" position="264,479" size="36,36" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/buttons/yeldot.png" zPosition="6" alphatest="on" />
                    <widget name="city1" position="608,56" size="705,64" zPosition="5" valign="center" halign="center" font="Regular;48" transparent="1" borderColor="black" borderWidth="1" />
                    <widget name="bigtemp1" position="760,130" size="353,118" zPosition="5" valign="center" halign="left" font="Regular;108" transparent="1" borderColor="black" borderWidth="1" />
                    <widget name="bigweathertype1" position="770,270" size="480,40" zPosition="5" valign="center" halign="left" font="Regular;28" transparent="1" borderColor="black" borderWidth="1" />
                    <widget name="GevoelsTemp1" position="775,230" size="354,40" zPosition="5" valign="center" halign="left" font="Regular;28" transparent="1" borderColor="black" borderWidth="1" />
                    <widget name="winddir1" position="770,315" size="345,40" zPosition="5" valign="center" halign="left" font="Regular;28" transparent="1" borderColor="black" borderWidth="1" />
                <widget name="bigWeerIcon10" position="107,404" size="150,150" zPosition="2" alphatest="on" />
                <widget name="bigDirIcon10" position="113,420" size="42,42" zPosition="3" alphatest="on" />
                <widget name="smallday20" position="118,480" size="120,24" zPosition="3" valign="center" halign="left" font="Regular;22" borderColor="black" borderWidth="1" transparent="1" />
                <widget name="midtemp20" position="174,406" size="80,36" zPosition="3" font="Regular;32" borderColor="black" borderWidth="1" transparent="1" />
                <widget name="minitemp20" position="176,449" size="45,22" zPosition="3" valign="center" halign="left" font="Regular;18" borderColor="black" borderWidth="1" transparent="1" />
                <widget name="weertype20" position="115,507" size="138,44" zPosition="3" valign="center" halign="center" font="Regular;16" borderColor="black" borderWidth="1" transparent="1" />
                <widget name="dayIcon00" position="120,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon01" position="336,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon02" position="552,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon03" position="768,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon04" position="984,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon05" position="1200,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon06" position="1416,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon07" position="1632,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="bigWeerIcon11" position="321,405" size="150,150" zPosition="2" alphatest="on" />
                <widget name="bigDirIcon11" position="325,438" size="42,42" zPosition="3" alphatest="on" />
                <widget name="smallday21" position="330,407" size="120,24" zPosition="3" valign="center" halign="left" font="Regular;22" borderColor="black" borderWidth="1" transparent="1" />
                <widget name="midtemp21" position="376,464" size="80,36" zPosition="3" font="Regular;32" borderColor="black" borderWidth="1" transparent="1" />
                <widget name="minitemp21" position="382,437" size="45,22" zPosition="3" valign="center" halign="left" font="Regular;18" borderColor="black" borderWidth="1" transparent="1" />
                <widget name="weertype21" position="325,508" size="138,44" zPosition="3" valign="center" halign="center" font="Regular;16" borderColor="black" borderWidth="1" transparent="1" />
                <widget name="dayIcon10" position="120,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon11" position="336,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon12" position="552,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon13" position="768,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon14" position="984,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon15" position="1200,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon16" position="1416,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon17" position="1632,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="bigWeerIcon12" position="534,405" size="150,150" zPosition="2" alphatest="on" />
                <widget name="bigDirIcon12" position="540,433" size="42,42" zPosition="3" alphatest="on" />
                <widget name="smallday22" position="548,406" size="120,24" zPosition="3" valign="center" halign="left" font="Regular;22" borderColor="black" borderWidth="1" transparent="1" />
                <widget name="midtemp22" position="596,434" size="80,36" zPosition="3" font="Regular;32" borderColor="black" borderWidth="1" transparent="1" />
                <widget name="minitemp22" position="611,481" size="45,22" zPosition="3" valign="center" halign="left" font="Regular;18" borderColor="black" borderWidth="1" transparent="1" />
                <widget name="weertype22" position="541,510" size="138,44" zPosition="3" valign="center" halign="center" font="Regular;16" borderColor="black" borderWidth="1" transparent="1" />
                <widget name="dayIcon20" position="120,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon21" position="336,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon22" position="552,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon23" position="768,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon24" position="984,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon25" position="1200,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon26" position="1416,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon27" position="1632,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="bigWeerIcon13" position="747,405" size="150,150" zPosition="2" alphatest="on" />
                <widget name="bigDirIcon13" position="751,431" size="42,42" zPosition="3" alphatest="on" />
                <widget name="smallday23" position="758,405" size="120,24" zPosition="3" valign="center" halign="left" font="Regular;22" borderColor="black" borderWidth="1" transparent="1" />
                <widget name="midtemp23" position="804,434" size="80,36" zPosition="3" font="Regular;32" borderColor="black" borderWidth="1" transparent="1" />
                <widget name="minitemp23" position="818,479" size="45,22" zPosition="3" valign="center" halign="left" font="Regular;18" borderColor="black" borderWidth="1" transparent="1" />
                <widget name="weertype23" position="751,511" size="138,44" zPosition="3" valign="center" halign="center" font="Regular;16" borderColor="black" borderWidth="1" transparent="1" />
                <widget name="dayIcon30" position="120,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon31" position="336,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon32" position="552,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon33" position="768,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon34" position="984,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon35" position="1200,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon36" position="1416,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon37" position="1632,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="bigWeerIcon14" position="960,405" size="150,150" zPosition="2" alphatest="on" />
                <widget name="bigDirIcon14" position="963,434" size="42,42" zPosition="3" alphatest="on" />
                <widget name="smallday24" position="972,406" size="120,24" zPosition="3" valign="center" halign="left" font="Regular;22" borderColor="black" borderWidth="1" transparent="1" />
                <widget name="midtemp24" position="1024,433" size="80,36" zPosition="3" font="Regular;32" borderColor="black" borderWidth="1" transparent="1" />
                <widget name="minitemp24" position="1041,477" size="45,22" zPosition="3" valign="center" halign="left" font="Regular;18" borderColor="black" borderWidth="1" transparent="1" />
                <widget name="weertype24" position="965,508" size="138,44" zPosition="3" valign="center" halign="center" font="Regular;16" borderColor="black" borderWidth="1" transparent="1" />
                <widget name="dayIcon40" position="120,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon41" position="336,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon42" position="552,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon43" position="768,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon44" position="984,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon45" position="1200,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon46" position="1416,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon47" position="1632,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="bigWeerIcon15" position="1173,405" size="150,150" zPosition="2" alphatest="on" />
                <widget name="bigDirIcon15" position="1176,433" size="42,42" zPosition="3" alphatest="on" />
                <widget name="smallday25" position="1184,407" size="120,24" zPosition="3" valign="center" halign="left" font="Regular;22" borderColor="black" borderWidth="1" transparent="1" />
                <widget name="midtemp25" position="1230,435" size="80,36" zPosition="3" font="Regular;32" borderColor="black" borderWidth="1" transparent="1" />
                <widget name="minitemp25" position="1245,480" size="45,22" zPosition="3" valign="center" halign="left" font="Regular;18" borderColor="black" borderWidth="1" transparent="1" />
                <widget name="weertype25" position="1177,507" size="138,44" zPosition="3" valign="center" halign="center" font="Regular;16" borderColor="black" borderWidth="1" transparent="1" />
                <widget name="dayIcon50" position="120,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon51" position="336,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon52" position="552,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon53" position="768,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon54" position="984,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon55" position="1200,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon56" position="1416,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon57" position="1632,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="bigWeerIcon16" position="1386,405" size="150,150" zPosition="2" alphatest="on" />
                <widget name="bigDirIcon16" position="1393,441" size="42,42" zPosition="3" alphatest="on" />
                <widget name="smallday26" position="1396,410" size="120,24" zPosition="3" valign="center" halign="left" font="Regular;22" borderColor="black" borderWidth="1" transparent="1" />
                <widget name="midtemp26" position="1445,441" size="80,36" zPosition="3" font="Regular;32" borderColor="black" borderWidth="1" transparent="1" />
                <widget name="minitemp26" position="1458,482" size="45,22" zPosition="3" valign="center" halign="left" font="Regular;18" borderColor="black" borderWidth="1" transparent="1" />
                <widget name="weertype26" position="1393,509" size="138,44" zPosition="3" valign="center" halign="center" font="Regular;16" borderColor="black" borderWidth="1" transparent="1" />
                <widget name="dayIcon60" position="120,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon61" position="336,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon62" position="552,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon63" position="768,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon64" position="984,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon65" position="1200,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon66" position="1416,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayIcon67" position="1632,779" size="72,72" zPosition="2" alphatest="on" />
                <widget name="dayhour30" position="195,779" size="90,36" zPosition="3" valign="center" halign="right" font="Regular;33" transparent="1" borderColor="black" borderWidth="1" />
                <widget name="daytemp30" position="120,870" size="180,54" zPosition="3" valign="center" halign="left" font="Regular;48" transparent="1" borderColor="black" borderWidth="1" />
                <widget name="daypercent30" position="168,945" size="120,30" zPosition="3" valign="center" halign="left" font="Regular;27" transparent="1" borderColor="black" borderWidth="1" />
                <widget name="dayspeed30" position="168,986" size="123,32" zPosition="3" valign="center" halign="left" font="Regular;27" transparent="1" borderColor="black" borderWidth="1" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/windhd/turbinehd.png" position="119,983" size="38,38" zPosition="3" alphatest="on" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/windhd/druphd.png" position="120,945" size="15,23" zPosition="3" alphatest="on" />
                <widget name="dayhour31" position="411,779" size="90,36" zPosition="3" valign="center" halign="right" font="Regular;33" transparent="1" borderColor="black" borderWidth="1" />
                <widget name="daytemp31" position="336,870" size="180,54" zPosition="3" valign="center" halign="left" font="Regular;48" transparent="1" borderColor="black" borderWidth="1" />
                <widget name="daypercent31" position="384,945" size="120,30" zPosition="3" valign="center" halign="left" font="Regular;27" transparent="1" borderColor="black" borderWidth="1" />
                <widget name="dayspeed31" position="384,986" size="123,32" zPosition="3" valign="center" halign="left" font="Regular;27" transparent="1" borderColor="black" borderWidth="1" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/windhd/turbinehd.png" position="335,983" size="38,38" zPosition="3" alphatest="on" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/windhd/druphd.png" position="336,945" size="15,23" zPosition="3" alphatest="on" />
                <widget name="dayhour32" position="627,779" size="90,36" zPosition="3" valign="center" halign="right" font="Regular;33" transparent="1" borderColor="black" borderWidth="1" />
                <widget name="daytemp32" position="552,870" size="180,54" zPosition="3" valign="center" halign="left" font="Regular;48" transparent="1" borderColor="black" borderWidth="1" />
                <widget name="daypercent32" position="600,945" size="120,30" zPosition="3" valign="center" halign="left" font="Regular;27" transparent="1" borderColor="black" borderWidth="1" />
                <widget name="dayspeed32" position="600,986" size="123,32" zPosition="3" valign="center" halign="left" font="Regular;27" transparent="1" borderColor="black" borderWidth="1" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/windhd/turbinehd.png" position="551,983" size="38,38" zPosition="3" alphatest="on" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/windhd/druphd.png" position="552,945" size="15,23" zPosition="3" alphatest="on" />
                <widget name="dayhour33" position="843,779" size="90,36" zPosition="3" valign="center" halign="right" font="Regular;33" transparent="1" borderColor="black" borderWidth="1" />
                <widget name="daytemp33" position="768,870" size="180,54" zPosition="3" valign="center" halign="left" font="Regular;48" transparent="1" borderColor="black" borderWidth="1" />
                <widget name="daypercent33" position="816,945" size="120,30" zPosition="3" valign="center" halign="left" font="Regular;27" transparent="1" borderColor="black" borderWidth="1" />
                <widget name="dayspeed33" position="816,986" size="123,32" zPosition="3" valign="center" halign="left" font="Regular;27" transparent="1" borderColor="black" borderWidth="1" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/windhd/turbinehd.png" position="767,983" size="38,38" zPosition="3" alphatest="on" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/windhd/druphd.png" position="768,945" size="15,23" zPosition="3" alphatest="on" />
                <widget name="dayhour34" position="1059,779" size="90,36" zPosition="3" valign="center" halign="right" font="Regular;33" transparent="1" borderColor="black" borderWidth="1" />
                <widget name="daytemp34" position="984,870" size="180,54" zPosition="3" valign="center" halign="left" font="Regular;48" transparent="1" borderColor="black" borderWidth="1" />
                <widget name="daypercent34" position="1032,945" size="120,30" zPosition="3" valign="center" halign="left" font="Regular;27" transparent="1" borderColor="black" borderWidth="1" />
                <widget name="dayspeed34" position="1032,986" size="123,32" zPosition="3" valign="center" halign="left" font="Regular;27" transparent="1" borderColor="black" borderWidth="1" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/windhd/turbinehd.png" position="983,983" size="38,38" zPosition="3" alphatest="on" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/windhd/druphd.png" position="984,945" size="15,23" zPosition="3" alphatest="on" />
                <widget name="dayhour35" position="1275,779" size="90,36" zPosition="3" valign="center" halign="right" font="Regular;33" transparent="1" borderColor="black" borderWidth="1" />
                <widget name="daytemp35" position="1200,870" size="180,54" zPosition="3" valign="center" halign="left" font="Regular;48" transparent="1" borderColor="black" borderWidth="1" />
                <widget name="daypercent35" position="1248,945" size="120,30" zPosition="3" valign="center" halign="left" font="Regular;27" transparent="1" borderColor="black" borderWidth="1" />
                <widget name="dayspeed35" position="1248,986" size="123,32" zPosition="3" valign="center" halign="left" font="Regular;27" transparent="1" borderColor="black" borderWidth="1" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/windhd/turbinehd.png" position="1199,983" size="38,38" zPosition="3" alphatest="on" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/windhd/druphd.png" position="1200,945" size="15,23" zPosition="3" alphatest="on" />
                <widget name="dayhour36" position="1491,779" size="90,36" zPosition="3" valign="center" halign="right" font="Regular;33" transparent="1" borderColor="black" borderWidth="1" />
                <widget name="daytemp36" position="1416,870" size="180,54" zPosition="3" valign="center" halign="left" font="Regular;48" transparent="1" borderColor="black" borderWidth="1" />
                <widget name="daypercent36" position="1464,945" size="120,30" zPosition="3" valign="center" halign="left" font="Regular;27" transparent="1" borderColor="black" borderWidth="1" />
                <widget name="dayspeed36" position="1464,986" size="123,32" zPosition="3" valign="center" halign="left" font="Regular;27" transparent="1" borderColor="black" borderWidth="1" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/windhd/turbinehd.png" position="1415,983" size="38,38" zPosition="3" alphatest="on" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/windhd/druphd.png" position="1416,945" size="15,23" zPosition="3" alphatest="on" />
                <widget name="dayhour37" position="1707,779" size="90,36" zPosition="3" valign="center" halign="right" font="Regular;33" transparent="1" borderColor="black" borderWidth="1" />
                <widget name="daytemp37" position="1632,870" size="180,54" zPosition="3" valign="center" halign="left" font="Regular;48" transparent="1" borderColor="black" borderWidth="1" />
                <widget name="daypercent37" position="1680,945" size="120,30" zPosition="3" valign="center" halign="left" font="Regular;27" transparent="1" borderColor="black" borderWidth="1" />
                <widget name="dayspeed37" position="1680,986" size="123,32" zPosition="3" valign="center" halign="left" font="Regular;27" transparent="1" borderColor="black" borderWidth="1" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/windhd/turbinehd.png" position="1631,983" size="38,38" zPosition="3" alphatest="on" />
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/windhd/druphd.png" position="1632,945" size="15,23" zPosition="3" alphatest="on" />
                    <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/windhd/%PEOCPIC%" position="1112,155" size="90,80" zPosition="2" transparent="0" alphatest="blend" />""".replace("%PEOCPIC%", peocpic)
        self.session = session
        self.skin = skin
        Screen.__init__(self, session)
        self["city1"] = Label(lockaaleStad)
        self["currentWeatherIcon"] = Pixmap()
        self["currentWeatherIcon"].hide()
        for day in range(0, 7):
            self["bigWeerIcon1"+str(day)] = Pixmap()
            self["bigWeerIcon1"+str(day)].hide()
            self["bigDirIcon1"+str(day)] = Pixmap()
            self["bigDirIcon1"+str(day)].hide()
        self["bigtemp1"] = Label("")
        self["bigweathertype1"] = Label("")
        self["GevoelsTemp1"] = Label("")
        self["winddir1"] = Label("East")
        self["yellowdot"] = MovingPixmap()
        for uur in range(0, 8):
            self["dayhour3"+str(uur)] = Label("00h")
            self["daytemp3"+str(uur)] = Label("--°C")
            self["daypercent3"+str(uur)] = Label("--%")
            self["dayspeed3"+str(uur)] = Label("--km/u")
            for day in range(0, 7):
                self["dayIcon"+str(day)+str(uur)] = Pixmap()
                self["dayIcon"+str(day)+str(uur)].hide()
        dataDagen = weatherData["days"]
        for day in range(0,7):
            dagen = dataDagen[day]
            iconclass = "na"
            if dagen.get("iconcode"):
                iconclass = dagen["iconcode"]
            info1 = ""
            info2 = ""
            info3 = ""
            info4 = ""
            info5 = ""
            if dagen.get("date"):
                mydate = text_type(dagen["date"])[:10]
                try:
                    unixtimecode = time.mktime(datetime.datetime(
                        int(mydate[:4]), int(mydate[5:7]), int(mydate[8:10])
                    ).timetuple())
                    info1 += str(strftime("%A", localtime(unixtimecode))).title()[:2]
                    info1 += str(strftime(" %d", localtime(unixtimecode)))
                except (ValueError, TypeError, OverflowError):
                    info1 = ""
            if dagen.get("mintemp"):
                info2 += '{:>3}'.format(str("%.0f" % dagen["mintemp"])+"°")
            elif dagen.get("mintemperature"):
                info2 += '{:>3}'.format( str("%.0f" % dagen["mintemperature"])+"°")
            else:
                info2 += "--.-°C"
            if dagen.get("maxtemp"):
                info3 += '{:>3}'.format(str("%.0f" % dagen["maxtemp"])+"°")
            elif dagen.get("maxtemperature"):
                info3 += '{:>3}'.format(str("%.0f" % dagen["maxtemperature"])+"°")
            else:
                info3 += "--.-°C"
            if dagen.get("beaufort"):
                info4 += str(dagen["beaufort"])
            else:
                info4 += "-"
            if dagen.get("windspeed"):
                info5 += str(dagen["windspeed"])+"KM/H"
            else:
                info5 += "--KM/H"
            self["smallday2"+str(day)] = Label(info1)
            self["midtemp2"+str(day)] = Label(info3)
            self["minitemp2"+str(day)] = Label(info2)
            self["weertype2"+str(day)] = Label(icontotext(iconclass))
            self["myActionMap"] = ActionMap(["SetupActions"], {"left": self.left, "right": self.right, "cancel": self.cancel}, -1)

        # Erst nach dem Skin/Layout ist .instance der Pixmaps verfügbar.
        self.onLayoutFinish.append(self.updateFrameselect)

    def left(self):
        self.selected -= 1
        self.updateFrameselect()

    def right(self):
        self.selected += 1
        self.updateFrameselect()

    def _hour_value(self, hour_data, *keys, default=""):
        if not isinstance(hour_data, dict):
            return default
        for key in keys:
            value = hour_data.get(key)
            if value is not None and value != "":
                return value
        return default

    def updateFrameselect(self):
        if self.selected < 0:
            self.selected = 6
        elif self.selected > 6:
            self.selected = 0

        if sz_w > 1800:
            self["yellowdot"].moveTo(286 + (248 * self.selected), 481, 1)
        else:
            self["yellowdot"].moveTo(184 + (165 * self.selected), 314, 1)
        self["yellowdot"].startMoving()

        global weatherData
        dataDagen = weatherData.get("days", [])

        # --- 1. Hauptansicht / Aktuelles Wetter oben ---
        self["bigtemp1"].setText("NA")
        self["bigweathertype1"].setText("na")
        self["GevoelsTemp1"].setText(_("GevoelsTemp NA°C"))
        self["winddir1"].setText(_("Windrichting NA"))

        if dataDagen and "hours" in dataDagen[0] and len(dataDagen[0]["hours"]) > 0:
            try:
                current_hour = dataDagen[0]["hours"][0]
                temperature = self._hour_value(current_hour, "temperature", default=None)
                feeltemperature = self._hour_value(current_hour, "feeltemperature", default=None)
                winddirection = self._hour_value(current_hour, "winddirection", default="NA")
                iconcode = self._hour_value(current_hour, "iconcode", default="na")

                if temperature is not None:
                    self["bigtemp1"].setText('{:>4}'.format(str("%.1f" % float(temperature))))
                if feeltemperature is not None:
                    self["GevoelsTemp1"].setText(_("GevoelsTemp ") + str("%.0f" % float(feeltemperature)) + "°C")
                self["winddir1"].setText(_("Windrichting ") + str(winddirection))
                self["bigweathertype1"].setText(icontotext(str(iconcode)))

                main_icon_path = get_icon_file(iconcode)
                if main_icon_path and "currentWeatherIcon" in self and self["currentWeatherIcon"].instance is not None:
                    self["currentWeatherIcon"].instance.setPixmap(loadPNG(main_icon_path))
                    self["currentWeatherIcon"].show()
            except (TypeError, ValueError, IndexError, KeyError):
                pass

        # --- 2. Tages-Kacheln Mitte (Icons für alle 7 Tage) ---
        for day_idx in range(0, 7):
            widget_name = f"bigWeerIcon1{day_idx}"
            if widget_name in self:
                if day_idx < len(dataDagen):
                    day_iconcode = dataDagen[day_idx].get("iconcode", "na")
                    day_icon_path = get_icon_file(day_iconcode)
                    print("HetWeer: Tag %d iconcode=%s path=%s widget=%s" % (day_idx, day_iconcode, day_icon_path, widget_name))
                    if day_icon_path and self[widget_name].instance is not None:
                        try:
                            pix = loadPNG(day_icon_path)
                            if pix:
                                self[widget_name].instance.setPixmap(pix)
                                self[widget_name].show()
                        except Exception as e:
                            print("HetWeer: Tagesicon Fehler %s: %s" % (widget_name, e))
                    else:
                        self[widget_name].show()
                else:
                    self[widget_name].show()

        # --- 3. Stunden-Kacheln unten (Icons für die 8 Zeitintervalle) ---
        dataPerUur = dataDagen[self.selected].get("hours", []) if self.selected < len(dataDagen) else []

        for perUurUpdate in range(0, 8):
            # Verstecke zunächst alle Stunden-Icons für alle Tage
            for day in range(0, 7):
                w_name = f"dayIcon{day}{perUurUpdate}"
                if w_name in self:
                    self[w_name].hide()

            current_widget = f"dayIcon{self.selected}{perUurUpdate}"

            if self.selected == 0:
                jumppoint = int(math.ceil(len(dataPerUur) / 8.0)) if len(dataPerUur) > 0 else 1
            else:
                jumppoint = 3

            if jumppoint < 1:
                jumppoint = 1

            target_index = perUurUpdate * jumppoint

            if target_index < len(dataPerUur):
                hour_data = dataPerUur[target_index]
                hour = self._hour_value(hour_data, "hour", default="")
                temperature = self._hour_value(hour_data, "temperature", default=None)
                precipitation = self._hour_value(
                    hour_data, "precipitation", "precipation",
                    "precipitationProbability", "precipitationchance", default="--"
                )
                windspeed = self._hour_value(hour_data, "windspeed", "windpower", default="--")
                hour_iconcode = self._hour_value(hour_data, "iconcode", default="na")

                # Stunden-Icon laden & anzeigen
                hour_icon_path = get_icon_file(hour_iconcode)
                if current_widget in self:
                    if hour_icon_path and self[current_widget].instance is not None:
                        self[current_widget].instance.setPixmap(loadPNG(hour_icon_path))
                    self[current_widget].show()

                # Werte in Labels schreiben
                self[f"dayhour3{perUurUpdate}"].setText(str(hour) + ("h" if hour != "" else ""))
                
                if temperature is not None:
                    try:
                        temp_text = "%.0f" % float(temperature) + "°C"
                    except (TypeError, ValueError):
                        temp_text = "--°C"
                else:
                    temp_text = "--°C"

                self[f"daytemp3{perUurUpdate}"].setText('{:>4}'.format(temp_text))
                self[f"daypercent3{perUurUpdate}"].setText(f"{precipitation}%")
                self[f"dayspeed3{perUurUpdate}"].setText(f"{windspeed}Km/u")
            else:
                self[f"dayhour3{perUurUpdate}"].setText("")
                self[f"daytemp3{perUurUpdate}"].setText("")
                self[f"daypercent3{perUurUpdate}"].setText("")
                self[f"dayspeed3{perUurUpdate}"].setText("")

    def cancel(self):
        self.close(None)

class weatherMenuSub(Screen):
    sz_w = getDesktop(0).size().width()
    if sz_w > 1800:
        skin = """
        <screen name="weatherMenuSub" position="fill" flags="wfNoBorder">
            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/borders/bigline87.png" position="0,0" size="1920,87"/>
            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/borders/smallline3.png" position="0,87" size="1920,3" zPosition="1"/>
            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/borders/smallline3.png" position="0,1020" size="1920,3" zPosition="1"/>
            <widget source="global.CurrentTime" render="Label" position="1665,22" size="225,37" transparent="1" zPosition="1" font="Regular;36" borderColor="black" borderWidth="1" valign="center" halign="right"><convert type="ClockToText">Format:%-H:%M</convert></widget>
            <widget source="global.CurrentTime" render="Label" position="1440,52" size="450,37" transparent="1" zPosition="1" font="Regular;24" borderColor="black" borderWidth="1" valign="center" halign="right"><convert type="ClockToText">Date</convert></widget>
            <widget source="session.VideoPicture" render="Pig" position="30,120" size="720,405" backgroundColor="#ff000000" zPosition="1"/>
            <widget source="session.CurrentService" render="Label" position="30,125" size="720,30" zPosition="1" foregroundColor="white" transparent="1" font="Regular;28"
            borderColor="black" borderWidth="1" noWrap="1" valign="center" halign="center">
            <convert type="ServiceName">Name</convert>
            </widget>
            <widget name="list" position="840,110" size="975,800" scrollbarMode="showOnDemand" font="Regular;51" itemHeight="63" selectionPixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/list/list97563.png"/>\n
            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/buttons/red34.png" position="192,1032" size="34,34" alphatest="blend"/>
            <widget name="key_red" position="242,1030" size="370,38" zPosition="1" transparent="1" font="Regular;34" borderColor="black" borderWidth="1" halign="left"/>
        </screen>"""

    else:
        skin = """
        <screen name="weatherMenuSub" position="fill" flags="wfNoBorder">
            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/borders/bigline88.png" position="0,0" size="1280,88"/>
            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/borders/smallline2.png" position="0,88" size="1280,2" zPosition="1"/>
            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/borders/smallline2.png" position="0,630" size="1280,2" zPosition="1"/>
            <widget source="global.CurrentTime" render="Label" position="1070,30" size="150,55" transparent="1" zPosition="1" font="Regular;24" borderColor="black" borderWidth="1" valign="center" halign="right"><convert type="ClockToText">Format:%-H:%M</convert></widget>
            <widget source="global.CurrentTime" render="Label" position="920,50" size="300,55" transparent="1" zPosition="1" font="Regular;16" borderColor="black" borderWidth="1" valign="center" halign="right"><convert type="ClockToText">Date</convert></widget>
            <widget source="session.VideoPicture" render="Pig" position="85,110" size="417,243" backgroundColor="#ff000000" zPosition="1"/>
            <widget source="session.CurrentService" render="Label" position="85,89" size="417,20" zPosition="1" foregroundColor="white" transparent="1" font="Regular;19"
            borderColor="black" borderWidth="1" noWrap="1" valign="center" halign="center">
            <convert type="ServiceName">Name</convert>
            </widget>
            <widget name="list" position="560,106" size="650,600" scrollbarMode="showOnDemand" font="Regular;28" itemHeight="43" selectionPixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/list/list65043.png"/>\n
            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/buttons/red26.png" position="145,643" size="26,26" alphatest="on"/>
            <widget name="key_red" position="185,643" size="220,28" zPosition="1" transparent="1" font="Regular;24" borderColor="black" borderWidth="1" halign="left"/>
        </screen>"""

    listNamesnl = ["Weerbericht", "Temperatuur", "Buienradar", "Motregenradar", "Onweerradar", "Wolkenradar", "Mistradar", "Hagelradar", "Sneeuwradar", "Zonradar", "Zonkracht-UV", "Satelliet"]
    listNamesbe = ["Weerbericht", "Buienradar", "Motregenradar", "Onweerradar", "Wolkenradar", "Hagelradar", "Sneeuwradar", "Zonradar", "Zonkracht-UV", "Satelliet"]
    listNameseu = ["Weerbericht", "Buienradar", "Onweerradar", "Zonkracht-UV", "Satelliet"]
    def __init__(self, session):
        self.session = session
        self["key_red"] = Label(_("Exit"))
        self.skin = weatherMenuSub.skin
        Screen.__init__(self, session)
        list = []
        self.countries = None 
        if state[0] == "Belgie": 
            self.countries = weatherMenuSub.listNamesbe
        elif state[0] == "Nederland":
            self.countries = weatherMenuSub.listNamesnl
        elif state[0] == "Europa":
            self.countries = weatherMenuSub.listNameseu    
        
        for x in self.countries:
            list.append(_(x))
        self["list"] = MenuList(list)
        self["actions"] = ActionMap(["WizardActions"], {"ok": self.go, "back": self.close}, -1)
        self["ColorActions"] = HelpableActionMap(self, "ColorActions", {"red": self.exit}, -1)

    def go(self):
        sz_w = getDesktop(0).size().width()
        isSD = sz_w <= 1800
        newView = isSD
        newView = True
        type = self.countries[self["list"].getSelectedIndex()]
        tt = time.time()
        tt = round(tt / (5 * 60))
        tt = tt * (5 * 60)
        tt -= (5 * 60)
        aantalfotos = 20
        tijdstap = 5
        locurl = ""
        picturedownloadurl = ""
        loctype = ""
        
        def openScreenRadar():
            if not type == 'Weerbericht':
                distro = 'unknown'
                try:
                    f = open('/etc/opkg/all-feed.conf', 'r')
                    oeline = f.readline().strip().lower()
                    f.close()
                    distro = oeline.split()[1].replace('-all', '')
                except:
                    pass

                if distro == 'openatv'or distro == 'hdfreaks'or distro == 'openhdf':  
                    self.session.open(radarScreenoatv)
                else:
                    self.session.open(radarScreenop)
                    
        global typename
        global wchat
        global legend
        typename = type
        legend = True 
        if state[0] == "Belgie" and newView:
            if type == "Weerbericht":
                wchat = weatherchat("be/Belgie/weerbericht")
                self.session.open(weathertalk)
            elif type == "Buienradar":
                safe_urlretrieve('https://image.buienradar.nl/2.0/image/single/RadarMapRainNL?height=512&width=500&renderBackground=True&renderBranding=True&renderText=True', '/tmp/HetWeer/00.png')
            elif type == "Motregenradar":
                safe_urlretrieve('https://api.buienradar.nl/image/1.0/drizzlemapnl/?ext=png&l=2&hist=50&forc=0&step=0&h=512&w=550', '/tmp/HetWeer/00.png')
            elif type == "Wolkenradar":
                safe_urlretrieve('https://api.buienradar.nl/image/1.0/cloudmapnl/?ext=png&l=2&hist=50&forc=0&step=0&h=512&w=550', '/tmp/HetWeer/00.png')
            elif type == "Zonradar":
                safe_urlretrieve('https://api.buienradar.nl/image/1.0/sunmapnl/?ext=png&l=2&hist=0&forc=50&step=0&h=512&w=550', '/tmp/HetWeer/00.png')
                legend = False
            elif type == "Onweerradar":
                safe_urlretrieve('https://api.buienradar.nl/image/1.0/lightningnl/?ext=png&l=2&hist=50&forc=0&step=0&h=512&w=550', '/tmp/HetWeer/00.png')
            elif type == "Hagelradar":
                safe_urlretrieve('https://api.buienradar.nl/image/1.0/hailnl/?ext=png&l=2&hist=10&forc=1&step=0&w=550&h=512', '/tmp/HetWeer/00.png')
            elif type == "Sneeuwradar":
                safe_urlretrieve('https://api.buienradar.nl/image/1.0/snowmapnl/?ext=png&l=2&hist=10&forc=1&step=0&w=550&h=512', '/tmp/HetWeer/00.png')
            elif type == "Satelliet":
                safe_urlretrieve('https://image.buienradar.nl/2.0/image/single/SatelliteNL?height=512&width=500&renderBackground=True&renderBranding=True&renderText=True&cb=%d' % int(time.time() // 300), '/tmp/HetWeer/00.png')
                legend = False
            elif type == "Zonkracht-UV":
                safe_urlretrieve('https://api.buienradar.nl/image/1.0/sunpowereu/?ext=png&l=2&hist=0&forc=30&step=0&w=550&h=512', '/tmp/HetWeer/00.png')
                legend = False
            if not type == "Weerbericht":
                openScreenRadar()

        elif state[0] == "Nederland" and newView:
            if type == "Weerbericht":
                wchat = weatherchat("nl/Nederland/weerbericht")
                self.session.open(weathertalk)
            elif type == "Temperatuur":
                safe_urlretrieve('https://api.buienradar.nl/image/1.0/weathermapnl/?ext=png&l=2&hist=12&forc=1&step=0&type=temperatuur&w=550&h=512', '/tmp/HetWeer/00.png')
                legend = False
            elif type == "Buienradar":
                safe_urlretrieve('https://image.buienradar.nl/2.0/image/single/RadarMapRainNL?height=512&width=500&renderBackground=True&renderBranding=True&renderText=True', '/tmp/HetWeer/00.png')
            elif type == "Motregenradar":
                safe_urlretrieve('https://api.buienradar.nl/image/1.0/drizzlemapnl/?ext=png&l=2&hist=50&forc=0&step=0&h=512&w=550', '/tmp/HetWeer/00.png')
            elif type == "Wolkenradar":
                safe_urlretrieve('https://api.buienradar.nl/image/1.0/cloudmapnl/?ext=png&l=2&hist=50&forc=0&step=0&h=512&w=550', '/tmp/HetWeer/00.png')
            elif type == "Sneeuwradar":
                safe_urlretrieve('https://api.buienradar.nl/image/1.0/snowmapnl/?ext=png&l=2&hist=10&forc=1&step=0&w=550&h=512', '/tmp/HetWeer/00.png')
            elif type == "Mistradar":
                safe_urlretrieve('https://api.buienradar.nl/image/1.0/weathermapnl/?type=zicht&ext=png&l=2&hist=9&forc=1&step=0&w=550&h=512', '/tmp/HetWeer/00.png')
                legend = False
            elif type == "Zonradar":
                safe_urlretrieve('https://api.buienradar.nl/image/1.0/sunmapnl/?ext=png&l=2&hist=0&forc=50&step=0&h=512&w=550', '/tmp/HetWeer/00.png')
                legend = False
            elif type == "Onweerradar":
                safe_urlretrieve('https://api.buienradar.nl/image/1.0/lightningnl/?ext=png&l=2&hist=50&forc=0&step=0&h=512&w=550', '/tmp/HetWeer/00.png')
            elif type == "Hagelradar":
                safe_urlretrieve('https://api.buienradar.nl/image/1.0/hailnl/?ext=png&l=2&hist=10&forc=1&step=0&w=550&h=512', '/tmp/HetWeer/00.png')
            elif type == "Satelliet":
                safe_urlretrieve('https://image.buienradar.nl/2.0/image/single/SatelliteNL?height=512&width=500&renderBackground=True&renderBranding=True&renderText=True&cb=%d' % int(time.time() // 300), '/tmp/HetWeer/00.png')
                legend = False
            elif type == "Zonkracht-UV":
                safe_urlretrieve('https://api.buienradar.nl/image/1.0/sunpowereu/?ext=png&l=2&hist=0&forc=30&step=0&w=550&h=512', '/tmp/HetWeer/00.png')
                legend = False
            if not type == "Weerbericht":
                openScreenRadar()

        elif state[0] == "Europa" and newView:
            if type == "Weerbericht":
                wchat = weatherchat("nl/wereldwijd/europa")
                self.session.open(weathertalk)
            elif type == "Buienradar":
                safe_urlretrieve('https://api.buienradar.nl/image/1.0/radarmapeu/?ext=png&l=2&hist=0&forc=50&step=0&h=512&w=550', '/tmp/HetWeer/00.png')
            elif type == "Onweerradar":
                safe_urlretrieve('https://api.buienradar.nl/image/1.0/radarcloudseu/?ext=png&l=2&hist=30&forc=0&step=0&h=512&w=550', '/tmp/HetWeer/00.png')
            elif type == "Satelliet":
                safe_urlretrieve('https://image.buienradar.nl/2.0/image/single/SatelliteEU?height=512&width=500&renderBackground=True&renderBranding=True&renderText=True&cb=%d' % int(time.time() // 300), '/tmp/HetWeer/00.png')
                legend = False
            elif type == "Zonkracht-UV":
                safe_urlretrieve('https://api.buienradar.nl/image/1.0/sunpowereu/?ext=png&l=2&hist=0&forc=30&step=0&w=550&h=512', '/tmp/HetWeer/00.png')
                legend = False
            if not type == "Weerbericht":
                openScreenRadar()
        
        if not newView:
            picturedownloadurl = "https://api.buienradar.nl/image/1.0/" + loctype
            for x in range(0, aantalfotos):
                turl = time.strftime("20%y%m%d%H%M", time.localtime(tt))
                dir = "/tmp/HetWeer/%02d.png" % (aantalfotos - (x + 1))
                tt += tijdstap * 60
                print(picturedownloadurl+ turl)
                safe_urlretrieve(picturedownloadurl + turl, dir)

            if os.path.exists('/tmp/HetWeer/00.png'):
                try:
                    self.session.open(aantalfotos)
                except:
                    return
            else:
                print('00.png doenst exists, go back!')
                return
    def exit(self):
        self.close(weatherMenuSub)

class weathertalk(Screen):
    def __init__(self, session):
        self.session = session
        sz_w = getDesktop(0).size().width()
        if sz_w > 1800:
            skin = """
            <screen name="weerbericht" position="fill" flags="wfNoBorder">
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/borders/bigline87.png" position="0,0" size="1920,87"/>
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/borders/smallline3.png" position="0,87" size="1920,3" zPosition="1"/>
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/borders/smallline3.png" position="0,1020" size="1920,3" zPosition="1"/>
                <widget source="global.CurrentTime" render="Label" position="1665,22" size="225,37" transparent="1" zPosition="1" font="Regular;36" borderColor="black" borderWidth="1" valign="center" halign="right"><convert type="ClockToText">Format:%-H:%M</convert></widget>
                <widget source="global.CurrentTime" render="Label" position="1440,52" size="450,37" transparent="1" zPosition="1" font="Regular;24" borderColor="black" borderWidth="1" valign="center" halign="right"><convert type="ClockToText">Date</convert></widget>
                <widget name="PAG" position="1780,940" size="104,52" valign="top" halign="left" zPosition="11" font="Regular;46" borderColor="black" borderWidth="1" transparent="1"/>
                <widget name="weerchat" position="150,150" size="1620,794" zPosition="11" font="Regular;46" borderColor="black" borderWidth="1" transparent="1"/>
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/buttons/red34.png" position="192,1032" size="34,34" alphatest="blend"/>
                <widget name="key_red" position="242,1030" size="370,38" zPosition="1" transparent="1" font="Regular;34" borderColor="black" borderWidth="1" halign="left"/>
            </screen>"""

        else:
            skin = """
            <screen name="weerbericht" position="fill" flags="wfNoBorder">
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/borders/bigline88.png" position="0,0" size="1280,88"/>
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/borders/smallline2.png" position="0,88" size="1280,2" zPosition="1"/>
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/borders/smallline2.png" position="0,630" size="1280,2" zPosition="1"/>
                <widget source="global.CurrentTime" render="Label" position="1070,30" size="150,55" transparent="1" zPosition="1" font="Regular;24" borderColor="black" borderWidth="1" valign="center" halign="right"><convert type="ClockToText">Format:%-H:%M</convert></widget>
                <widget source="global.CurrentTime" render="Label" position="920,50" size="300,55" transparent="1" zPosition="1" font="Regular;16" borderColor="black" borderWidth="1" valign="center" halign="right"><convert type="ClockToText">Date</convert></widget>
                <widget name="PAG" position="1180,580" size="72,36" valign="top" halign="left" zPosition="11" font="Regular;32" borderColor="black" borderWidth="1" transparent="1"/>
                <widget name="weerchat" position="100,100" size="1100,500" valign="top" halign="left" zPosition="11" font="Regular;32" borderColor="black" borderWidth="1" transparent="1"/>
                <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/buttons/red26.png" position="145,643" size="26,26" alphatest="on"/>
                <widget name="key_red" position="185,643" size="220,28" zPosition="3" transparent="1" font="Regular;24" borderColor="black" borderWidth="1" halign="left"/>
            </screen>"""

        Screen.__init__(self, session)
        self.skin = skin
        global wchat
        self.indexpage = 0
        list = []
        regx = '''<p>(.*?)</p>'''
        match = re.findall(regx, wchat, re.DOTALL)
        self.wchattext=match
        if not self.wchattext:
            self.wchattext = [_('Geen weerbericht beschikbaar')]
        self["weerchat"] = Label(transhtml(self.wchattext[self.indexpage]))
        self["PAG"] = Label("1/"+str(len(self.wchattext)))

        self["actions"] = ActionMap(["WizardActions"], {"left": self.left, "right": self.right, "back": self.close}, -1)
        self["ColorActions"] = HelpableActionMap(self, "ColorActions", {"red": self.exit}, -1)
        self["key_red"] = Label(_("Exit"))

    def left(self):
        if self.indexpage<=0:
            self.indexpage=0
        else:
            self.indexpage=self.indexpage-1
        self["weerchat"].setText(transhtml(self.wchattext[self.indexpage]))
        self["PAG"].setText(str(self.indexpage+1)+"/"+str(len(self.wchattext)))

    def right(self):
        if self.indexpage>=len(self.wchattext)-1:
            self.indexpage=len(self.wchattext)-1
        else:
            self.indexpage=self.indexpage+1
        self["weerchat"].setText(transhtml(self.wchattext[self.indexpage]))
        self["PAG"].setText(str(self.indexpage+1)+"/"+str(len(self.wchattext)))

    def exit(self):
        self.close(weathertalk)


class radarScreenoatv(Screen):
    def __init__(self, session):
        global pos
        self['radarname'] = Label(typename)
        self.weerpng = '/tmp/HetWeer/00.png'
        picformat = get_image_info('/tmp/HetWeer/00.png')
        if not picformat:
            self.weerpng = '/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/lo/busy.png'
            picformat = get_image_info(self.weerpng)
        if not isinstance(picformat, tuple):
            picformat = (550, 512)
        sz_w = getDesktop(0).size().width()
        legendinfo = ''
        if sz_w > 1800:
            if legend:
                legendinfo = """<ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/lo/legende.png" zPosition="6" position="705,545" size="270,333" alphatest="on"/>"""
            skin = """
            <screen position="fill" title="HetWeer">
            <widget name="picd" position="685,284" size="39600,900" pixmap="/tmp/HetWeer/00.png" zPosition="1" alphatest="on"/>""" + legendinfo + """
            <widget name="radarname" position="center,290" size="550,64" zPosition="7" halign="center" transparent="1" font="Regular;30" borderColor="black" borderWidth="2"/>
            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/borders/framehdatv.png" zPosition="6" position="center,center" size="1920,1080" alphatest="on"/>
            </screen>"""
    
        else:   
            if legend:
                legendinfo = """<ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/lo/legendehd.png" zPosition="6" position="370,222" size="270,333" alphatest="on"/>"""
            skin = """
            <screen position="fill" title="HetWeer">
            <widget name="picd" position="365,86" size="19800,512" pixmap="/tmp/HetWeer/00.png" zPosition="1" alphatest="on"/>""" + legendinfo + """
            <widget name="radarname" position="center,94" size="550,64" zPosition="6" halign="center" transparent="1" font="Regular;30" borderColor="black" borderWidth="2"/>
            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/borders/framesdatv.png" zPosition="6" position="0,80" size="1280,523" alphatest="on"/>
            </screen>"""
        
        self.session = session
        self.skin = skin
        Screen.__init__(self, session)
        self.slidePicTimer = eTimer()
        self.slidePicTimer.callback.append(self.updatePic)
        self['picd'] = MovingPixmap()
        pos = 0
        self.slidePicTimer.start(750)
        self['actions'] = ActionMap(['WizardActions'], {'back': self.close}, -1)

    def updatePic(self):
        global pos
        if sz_w > 1800:
            self['picd'].moveTo((pos * -550)+685, 284, 1)
        else:
            global picadjust
            postt=(pos * -550)+365
            if postt<-8000:
                pos=0
            self['picd'].moveTo((pos * -550)+365, 86, 1)
        pos += 1
        image_info = get_image_info('/tmp/HetWeer/00.png')
        image_width = image_info[0] if isinstance(image_info, tuple) else 550
        if pos >= max(1, image_width // 550):
            pos = 0
            
        self['picd'].startMoving()


class radarScreenop(Screen):
    def __init__(self, session):
        global typename
        self["radarname"] = Label(typename)
        self.weerpng = "/tmp/HetWeer/00.png"
        picformat = get_image_info("/tmp/HetWeer/00.png")
        if not picformat:
            self.weerpng = "/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/lo/busy.png"
            picformat = get_image_info(self.weerpng)
        if not isinstance(picformat, tuple):
            picformat = (550, 512)
        self.scaler = 1.25
        sz_w = getDesktop(0).size().width()
        global legend
        legendinfo = ""
        if sz_w > 1800:
            self.scaler= 2.0
        if sz_w > 1800:
            if legend:
                legendinfo = """<ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/lo/legendehd.png" zPosition="6" position="460,630" size="270,333" alphatest="on"/>"""
            skin = """
            <screen position="fill" size=\""""+str(int(550*self.scaler-16))+""","""+str(int(512*self.scaler))+"""">
            <widget name="picd" position="400,28" size=\""""+str(int(picformat[0]*self.scaler))+""","""+str(int(picformat[1]*self.scaler))+"""" zPosition="5" alphatest="on"/>"""+legendinfo+"""
            <widget name="radarname" position="center,50" size="600,72" zPosition="6" halign="center" transparent="1" font="Regular;60" borderColor="black" borderWidth="2"/>
            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/borders/framehdop.png" zPosition="6" position="center,center" size="1920,1080" alphatest="on"/>
            </screen>"""
        
        else:
            if legend:
                legendinfo = """<ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/lo/legende.png" zPosition="6" position="326,390" size="180,222" alphatest="on"/>"""
            skin = """
            <screen position="fill" size=\""""+str(int(370*self.scaler-16))+""","""+str(int(512*self.scaler))+"""">
            <widget name="picd" position="305,36" size=\""""+str(int(picformat[0]*self.scaler))+""","""+str(int(picformat[1]*self.scaler))+"""" zPosition="5" alphatest="on"/>"""+legendinfo+"""
            <widget name="radarname" position="center,56" size="400,52" zPosition="6" halign="center" transparent="1" font="Regular;40" borderColor="black" borderWidth="2"/>
            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/borders/framesdop.png" zPosition="6" position="center,center" size="1280,650" alphatest="on"/>
            </screen>"""

        self.session = session
        self.skin = skin
        Screen.__init__(self, session)
        self.slidePicTimer = eTimer()
        self.slidePicTimer.callback.append(self.updatePic)
        self["picd"] = MovingPixmap()
        global pos
        pos = 0
        self.Scale = AVSwitch().getFramebufferScale()
        self.slidePicTimer.start(750)
        self["actions"] = ActionMap(["WizardActions"], {"back": self.close}, -1)
        self.PicLoad = ePicLoad()
        self.PicLoadPerformance = ePicLoad()
        self.picPath = self.weerpng
        self.PicLoad.PictureData.get().append(self.DecodePicture1)
        self.onLayoutFinish.append(self.ShowPicture1)
        self.PicLoad.startDecode(self.picPath)
    def DecodePicture1(self, PicInfo = ""):
        if self.picPath is not None:
            ptr = self.PicLoad.getData()
            self["picd"].instance.setPixmap(ptr)

    def ShowPicture1(self):
        if self.picPath is not None:
            self.PicLoad.setPara([
                self["picd"].instance.size().width(),
                self["picd"].instance.size().height(),
                self.Scale[0],
                self.Scale[1],
                0,
                1,
                "#0x000000"])
            self.PicLoad.startDecode(self.picPath)

    def updatePic(self):
        global pos
        if sz_w > 1800:
            self["picd"].moveTo((pos*(-550*self.scaler)-15+415),28,1)
                         
        else:
            global picadjust
            postt=(pos * -687.5)
            if postt<-8000:
                pos=0
            self['picd'].moveTo((pos *(-550*self.scaler))+300, 36, 1)
        pos += 1
        image_info = get_image_info('/tmp/HetWeer/00.png')
        image_width = image_info[0] if isinstance(image_info, tuple) else 550
        if pos >= max(1, int(image_width / (550 * self.scaler))):
            pos = 0
            
        self['picd'].startMoving()

class localcityscreen(Screen):
    sz_w = getDesktop(0).size().width()
    if sz_w > 1800:
        skin = """
        <screen name="localcityscreen" position="fill" flags="wfNoBorder">
            <widget name="favor" position="30,7" size="1600,75" transparent="1" zPosition="1" font="Regular;36" borderColor="black" borderWidth="1" valign="center" halign="left" foregroundColor="green" />
            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/borders/bigline87.png" position="0,0" size="1920,87" />
            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/borders/smallline3.png" position="0,87" size="1920,3" zPosition="1" />
            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/borders/smallline3.png" position="0,1020" size="1920,3" zPosition="1" />
            <widget source="global.CurrentTime" render="Label" position="1665,22" size="225,37" transparent="1" zPosition="1" font="Regular;36" borderColor="black" borderWidth="1" valign="center" halign="right">
  <convert type="ClockToText">Format:%H:%M:%S</convert>
</widget>
            <widget source="global.CurrentTime" render="Label" position="1440,52" size="450,37" transparent="1" zPosition="1" font="Regular;24" borderColor="black" borderWidth="1" valign="center" halign="right" foregroundColor="green">
  <convert type="ClockToText">Format:%a %d.%m.%y</convert>
</widget>
            <widget source="session.VideoPicture" render="Pig" position="27,178" size="720,405" backgroundColor="#ff000000" zPosition="1" />
            <widget source="session.CurrentService" render="Label" position="30,99" size="720,56" zPosition="1" transparent="1" font="Regular;28" borderColor="black" borderWidth="1" noWrap="1" valign="center" halign="center">
                <convert type="ServiceName">Name</convert>
            </widget>
            <widget name="list" position="840,210" size="900,630" scrollbarMode="showOnDemand" font="Regular;51" itemHeight="63" selectionPixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/list/list97563.png" />\n
            <widget name="plaatsn" position="840,120" size="375,70" valign="center" halign="left" zPosition="3" foregroundColor="yellow" font="Regular;63" borderColor="black" borderWidth="1" transparent="1" />
            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/buttons/red34.png" position="192,1032" size="34,34" alphatest="blend" />
            <widget name="key_red" position="242,1030" size="370,38" zPosition="1" transparent="1" font="Regular;34" borderColor="black" borderWidth="1" halign="left" />
            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/buttons/green34.png" position="628,1032" size="34,34" alphatest="blend" />
            <widget name="key_green" position="678,1030" size="370,38" zPosition="1" transparent="1" font="Regular;34" borderColor="black" borderWidth="1" halign="left" />
            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/buttons/yellow34.png" position="1064,1032" size="34,34" alphatest="blend" />
            <widget name="key_yellow" position="1114,1030" size="370,38" zPosition="1" transparent="1" font="Regular;34" borderColor="black" borderWidth="1" halign="left" />
        </screen>"""

    else:
        skin = """
        <screen name="localcityscreen" position="fill" flags="wfNoBorder">
            <widget name="favor" position="30,7" size="1600,75" transparent="1" zPosition="1" font="Regular;36" borderColor="black" borderWidth="1" valign="center" halign="left" foregroundColor="green" />
            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/borders/bigline87.png" position="0,0" size="1920,87" />
            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/borders/smallline3.png" position="0,87" size="1920,3" zPosition="1" />
            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/borders/smallline3.png" position="0,1020" size="1920,3" zPosition="1" />
            <widget source="global.CurrentTime" render="Label" position="1665,22" size="225,37" transparent="1" zPosition="1" font="Regular;36" borderColor="black" borderWidth="1" valign="center" halign="right">
  <convert type="ClockToText">Format:%H:%M:%S</convert>
</widget>
            <widget source="global.CurrentTime" render="Label" position="1440,52" size="450,37" transparent="1" zPosition="1" font="Regular;24" borderColor="black" borderWidth="1" valign="center" halign="right" foregroundColor="green">
  <convert type="ClockToText">Format:%a %d.%m.%y</convert>
</widget>
            <widget source="session.VideoPicture" render="Pig" position="27,178" size="720,405" backgroundColor="#ff000000" zPosition="1" />
            <widget source="session.CurrentService" render="Label" position="30,99" size="720,56" zPosition="1" transparent="1" font="Regular;28" borderColor="black" borderWidth="1" noWrap="1" valign="center" halign="center">
                <convert type="ServiceName">Name</convert>
            </widget>
            <widget name="list" position="840,210" size="900,630" scrollbarMode="showOnDemand" font="Regular;51" itemHeight="63" selectionPixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/list/list97563.png" />\n
            <widget name="plaatsn" position="840,120" size="375,70" valign="center" halign="left" zPosition="3" foregroundColor="yellow" font="Regular;63" borderColor="black" borderWidth="1" transparent="1" />
            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/buttons/red34.png" position="192,1032" size="34,34" alphatest="blend" />
            <widget name="key_red" position="242,1030" size="370,38" zPosition="1" transparent="1" font="Regular;34" borderColor="black" borderWidth="1" halign="left" />
            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/buttons/green34.png" position="628,1032" size="34,34" alphatest="blend" />
            <widget name="key_green" position="678,1030" size="370,38" zPosition="1" transparent="1" font="Regular;34" borderColor="black" borderWidth="1" halign="left" />
            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/HetWeer/Images/buttons/yellow34.png" position="1064,1032" size="34,34" alphatest="blend" />
            <widget name="key_yellow" position="1114,1030" size="370,38" zPosition="1" transparent="1" font="Regular;34" borderColor="black" borderWidth="1" halign="left" />
        </screen>"""

    def __init__(self, session):
        self.session = session
        self.skin = localcityscreen.skin
        self["favor"] = Label(_("Favoriete Locaties"))
        self["plaatsn"] = Label(_("Locatie:"))
        self["key_red"] = Label(_("Exit"))
        self["key_green"] = Label(_("Locatie +"))
        self["key_yellow"] = Label(_("Locatie -"))
        Screen.__init__(self, session)
        list = []
        global SavedLokaleWeer
        for x in SavedLokaleWeer:
            list.append((str(x)))
        self["list"] = MenuList(list)
        self["actions"] = ActionMap(["WizardActions"], {"ok": self.go, "back": self.close}, -1)
        self["ColorActions"] = HelpableActionMap(self, "ColorActions", {"red": self.exit, "yellow": self.removeLoc, "green": self.addLoc}, -1)

    def exit(self):
        self.close()

    def addLoc(self):
        self.session.openWithCallback(self.searchCity, VirtualKeyBoard, title=_("Enter Ortsname, z.B. Ratingen, London/GB oder München"), text="")

    def searchCity(self, searchterm = None):
        if searchterm is not None:
            searchterm = text_type(searchterm).strip()
            if not searchterm:
                return
            # Only add a place when it can actually be resolved. This replaces
            # the old misleading "add it to the database" message: the place
            # is now really added to the local coordinate database.
            location = _geocode_city(searchterm, save=True)
            if not location:
                self.session.open(
                    MessageBox,
                    _("Ort nicht gefunden: Schreibweise prüfen oder z.B. Stadt/Land eingeben."),
                    MessageBox.TYPE_INFO
                )
                return
            canonical = text_type(location.get('name') or searchterm)
            if canonical not in SavedLokaleWeer:
                SavedLokaleWeer.append(canonical)
            try:
                with io.open("/etc/enigma2/hetweer.cfg", "w", encoding="utf-8") as file:
                    for x in SavedLokaleWeer:
                        file.write(text_type(x) + "\n")
            except (IOError, OSError, UnicodeError) as e:
                print("HetWeer: kann Favoriten nicht speichern: %s" % e)
            print("HetWeer: Ort hinzugefügt: %s" % canonical)
            self.close()
            self.close()

    def go(self):
        if len(SavedLokaleWeer)>0:
            index = self["list"].getSelectedIndex()
            print("index: "+ str(index))
            if getLocWeer(SavedLokaleWeer[index].rstrip()):
                time.sleep(1)
                self.session.open(weeroverview)
            else:
                self.session.open(MessageBox, _("Downloadfehler: Schreibweise prüfen oder Stadt/Land eingeben."), MessageBox.TYPE_INFO)

    def removeLoc(self):
        if len(SavedLokaleWeer)>0:
            index = self["list"].getSelectedIndex()
            SavedLokaleWeer.remove(SavedLokaleWeer[index])
            file = io.open("/etc/enigma2/hetweer.cfg", "w", encoding="utf-8")
            for x in SavedLokaleWeer:
                file.write(text_type(x)+"\n")
            file.close()
            self.close()
            self.close()

pos = 0

def main(session, **kwargs):
    """Open the plugin immediately; network errors are handled per action."""
    global SavedLokaleWeer
    SavedLokaleWeer = []
    locdirsave = "/etc/enigma2/hetweer.cfg"
    try:
        if os.path.exists(locdirsave):
            with io.open(locdirsave, encoding="utf-8") as f:
                for line in f:
                    location = line.strip()
                    if location:
                        SavedLokaleWeer.append(location)
    except (IOError, OSError, UnicodeError) as e:
        print("HetWeather: kan favorieten niet lezen: %s" % e)
    print("start-----------:" + str(SavedLokaleWeer))
    try:
        if not os.path.exists('/tmp/HetWeather'):
            os.makedirs('/tmp/HetWeather')
    except OSError:
        pass
    session.open(startScreen)

def menu(menuid, **kwargs):
    if menuid == "mainmenu":
        return [
            (_("HetWeather"), main, "HetWeather_mainmenu", 50)
        ]
    return []


def Plugins(path, **kwargs):
    global plugin_path
    plugin_path = path
    return [
        PluginDescriptor(
            name=_("HetWeather"),
            description=_("BuienRadar & WeerInfo, versie {version}").format(version=versienummer),
            icon="Images/weerinfo.png",
            where=[
                PluginDescriptor.WHERE_EXTENSIONSMENU,
                PluginDescriptor.WHERE_PLUGINMENU
            ],
            fnc=main
        ),
        PluginDescriptor(
            where=PluginDescriptor.WHERE_MENU,
            fnc=menu
        )
    ]
