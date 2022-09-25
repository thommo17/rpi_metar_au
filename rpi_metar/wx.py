"""Weather parsing utilities."""
import logging
import re
from enum import Enum
from fractions import Fraction
from rpi_metar.leds import GREEN, RED, BLUE, MAGENTA, YELLOW, BLACK, ORANGE, WHITE, CYAN
from datetime import datetime, timedelta

log = logging.getLogger(__name__)


class FlightCategory(Enum):
    VFR = GREEN
    IFR = YELLOW
    MVFR = BLUE
    LIFR = RED
    UNKNOWN = BLACK
    OFF = BLACK
    MISSING = BLACK
    THUNDERSTORM = MAGENTA
    WINDY = ORANGE
    BOOTUP = CYAN

def get_conditions(metar_info):
    """Returns the visibility, ceiling, wind speed, and gusts for a given airport from some metar info."""
    log.debug(metar_info)
    visibility = ceiling = None
    ztime = datetime.utcnow()
    speed = gust = 0
    # Visibility

    # Match metric visibility and convert to SM
    match = re.search(r'(?P<CAVOK>CAVOK)|(\s(?P<visibility>\d{4}|\/{4})\s)|(\s(?P<visibilityKM>\d{2}.[KM]|\/{2})\s)', metar_info)
    if match.group('visibility'):
        try:
            visibility = float(match.group('visibility')) / 1609
        except ValueError:
            visibility = 10
        except ZeroDivisionError:
            visibility = None
        except AttributeError:
            visibility = None
    if match.group('CAVOK'):
        visibility = 10
    if match.group('visibilityKM'):
        visibility = 10

    # Match SM Visibility
    # We may have fractions, e.g. 1/8SM or 1 1/2SM
    # Or it will be whole numbers, e.g. 2SM
    # There's also variable wind speeds, followed by vis, e.g. 300V360 1/2SM
    match = re.search(r'(?P<visibility>\b(?:\d+\s+)?\d+(?:/\d)?)SM', metar_info)
    if match:
        visibility = match.group('visibility')
        try:
            visibility = float(sum(Fraction(s) for s in visibility.split()))
        except ZeroDivisionError:
            visibility = None
    # Ceiling Normal
    match = re.search(r'(SCT|VV|BKN|OVC)(?P<ceiling>\d{3})', metar_info)
    if match:
        ceiling = int(match.group('ceiling')) * 100  # It is reported in hundreds of feet

    #Ceiling NCD
    match = re.search(r'(?P<NCD> NCD )', metar_info)
    if match:
        ceiling = 10000  # It is reported in hundreds of feet

    # Wind info
    match = re.search(r'\b\d{3}(?P<speed>\d{2,3})G?(?P<gust>\d{2,3})?KT', metar_info)
    if match:
        speed = int(match.group('speed'))
        gust = int(match.group('gust')) if match.group('gust') else 0

    # METAR time
    match = re.search(r'(?P<UTC>\d{6})(?:Z)', metar_info)
    if match:
        ztime = match.group('UTC')
        ztime_object = datetime.strptime(ztime, '%d%H%M')
        ztime_object = ztime_object.replace(year=ztime_object.now().year,month=ztime_object.now().month)
        Z_limit = datetime.utcnow() - timedelta(minutes=90)
        if ztime_object < Z_limit:
            visibility = 12345678
            ceiling = 12345678


    return (visibility, ceiling, speed, gust)

def get_flight_category(visibility, ceiling):
    """Converts weather conditions into a category."""
    log.debug('Finding category for %s, %s', visibility, ceiling)

    # Unlimited ceiling
    if visibility and ceiling is None:
        ceiling = 10000

    # http://www.faraim.org/aim/aim-4-03-14-446.html
    try:
        if visibility and ceiling == 12345678:
            return FlightCategory.MISSING
        elif visibility < 1 or ceiling < 500:
            return FlightCategory.LIFR
        elif 1 <= visibility < 3 or 500 <= ceiling < 1000:
            return FlightCategory.IFR
        elif 3 <= visibility <= 5 or 1000 <= ceiling <= 3000:
            return FlightCategory.MVFR
        elif visibility > 5 and ceiling > 3000:
            return FlightCategory.VFR
    except (TypeError, ValueError):
        log.exception('Failed to get flight category from {vis}, {ceil}'.format(
            vis=visibility,
            ceil=ceiling
        ))