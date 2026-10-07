# weather_system.py - Rad Earth
# Версия: 1.0.0
# Погода. Циклы, эффекты, смена по времени, влияние на игру.

import os
import json
import random
from datetime import datetime, timedelta

from config import (
    logger, JSON_WEATHER,
    WEATHER_CHANGE_MIN_MINUTES, WEATHER_CHANGE_MAX_MINUTES,
)
from database import get_world_session, Weather


# ==================== ДЕФОЛТНАЯ ПОГОДА ====================

DEFAULT_WEATHER_TYPES = {
    'clear': {
        'name': '☀️ Ясно',
        'desc': 'Солнце печёт, видимость отличная.',
        'rc_mult': 1.0, 'rf_mult': 1.0, 'exp_mult': 1.0,
        'danger_add': 0,
        'weight': 20,
    },
    'cloudy': {
        'name': '🌤️ Облачно',
        'desc': 'Спокойная погода, ветра почти нет.',
        'rc_mult': 1.0, 'rf_mult': 1.0, 'exp_mult': 1.0,
        'danger_add': 0,
        'weight': 25,
    },
    'rain': {
        'name': '🌧️ Дождь',
        'desc': 'Слякоть, грязь, плохая видимость.',
        'rc_mult': 0.95, 'rf_mult': 1.05, 'exp_mult': 1.0,
        'danger_add': 5,
        'weight': 15,
    },
    'storm': {
        'name': '⛈️ Гроза',
        'desc': 'Молнии бьют в антенны, радио трещит.',
        'rc_mult': 0.9, 'rf_mult': 1.1, 'exp_mult': 1.0,
        'danger_add': 10,
        'weight': 8,
    },
    'fog': {
        'name': '🌫️ Туман',
        'desc': 'Ничего не видно дальше пары метров.',
        'rc_mult': 0.9, 'rf_mult': 1.0, 'exp_mult': 1.1,
        'danger_add': 8,
        'weight': 12,
    },
    'radiation_storm': {
        'name': '☢️ Радиоактивный шторм',
        'desc': 'Смертельная пыль в воздухе. Без укрытия — смерть.',
        'rc_mult': 0.7, 'rf_mult': 1.5, 'exp_mult': 1.2,
        'danger_add': 25,
        'weight': 3,
    },
    'windy': {
        'name': '🌪️ Ветрено',
        'desc': 'Песок бьёт в лицо, тяжело идти.',
        'rc_mult': 0.95, 'rf_mult': 1.0, 'exp_mult': 1.0,
        'danger_add': 3,
        'weight': 10,
    },
    'snow': {
        'name': '❄️ Снег',
        'desc': 'Холодно, но красиво. Следы видно.',
        'rc_mult': 0.9, 'rf_mult': 1.05, 'exp_mult': 1.0,
        'danger_add': 6,
        'weight': 5,
    },
    'blizzard': {
        'name': '🌨️ Метель',
        'desc': 'Ледяной ветер, видимость нулевая.',
        'rc_mult': 0.8, 'rf_mult': 1.1, 'exp_mult': 1.0,
        'danger_add': 15,
        'weight': 2,
    },
    'clear_night': {
        'name': '🌌 Ясно, ночь',
        'desc': 'Звёзды видны. Ночью опаснее.',
        'rc_mult': 0.9, 'rf_mult': 1.15, 'exp_mult': 1.1,
        'danger_add': 12,
        'weight': 15,
    },
}


# ==================== ЗАГРУЗКА ====================

_WEATHER_CACHE = None


def load_weather_types():
    """Загрузить типы погоды из JSON (или дефолт)."""
    global _WEATHER_CACHE
    if _WEATHER_CACHE is not None:
        return _WEATHER_CACHE

    path = os.path.join(JSON_WEATHER, 'types.json')
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if data:
                _WEATHER_CACHE = data
                return _WEATHER_CACHE
        except Exception as e:
            logger.error(f"Ошибка чтения погоды: {e}")

    _WEATHER_CACHE = DEFAULT_WEATHER_TYPES
    return _WEATHER_CACHE


def reload_weather():
    """Сбросить кэш."""
    global _WEATHER_CACHE
    _WEATHER_CACHE = None


# ==================== ТЕКУЩАЯ ПОГОДА ====================

def get_current_weather():
    """Текущая погода (запись в БД)."""
    world = get_world_session()
    try:
        w = world.query(Weather).order_by(Weather.id.desc()).first()
        return w
    finally:
        world.close()


def _pick_random_weather(season=None):
    """Выбрать случайный тип погоды с учётом весов."""
    types = load_weather_types()
    if not types:
        return None

    keys = list(types.keys())
    weights = [types[k].get('weight', 10) for k in keys]
    chosen = random.choices(keys, weights=weights, k=1)[0]
    return chosen, types[chosen]


def _next_change_time():
    """Когда следующая смена погоды."""
    minutes = random.randint(
        WEATHER_CHANGE_MIN_MINUTES,
        WEATHER_CHANGE_MAX_MINUTES
    )
    return datetime.now() + timedelta(minutes=minutes)


def set_weather(weather_type, weather_data, duration_minutes=None):
    """Установить новую погоду."""
    world = get_world_session()
    try:
        # Удалить предыдущую
        old = world.query(Weather).all()
        for w in old:
            world.delete(w)

        if duration_minutes is None:
            duration_minutes = random.randint(
                WEATHER_CHANGE_MIN_MINUTES,
                WEATHER_CHANGE_MAX_MINUTES
            )

        now = datetime.now()
        weather = Weather(
            weather_type=weather_type,
            name=weather_data.get('name', weather_type),
            description=weather_data.get('desc', ''),
            rc_mult=weather_data.get('rc_mult', 1.0),
            rf_mult=weather_data.get('rf_mult', 1.0),
            exp_mult=weather_data.get('exp_mult', 1.0),
            danger_add=weather_data.get('danger_add', 0),
            started_at=now,
            ends_at=now + timedelta(minutes=duration_minutes),
        )
        world.add(weather)
        world.commit()
        logger.info(f"🌤️ Погода изменена: {weather.name}")
        return weather
    except Exception as e:
        logger.error(f"Ошибка смены погоды: {e}")
        world.rollback()
        return None
    finally:
        world.close()


def roll_weather():
    """Установить случайную погоду."""
    result = _pick_random_weather()
    if not result:
        return None
    weather_type, weather_data = result
    return set_weather(weather_type, weather_data)


def init_weather():
    """Инициализировать погоду при первом запуске."""
    current = get_current_weather()
    if not current:
        roll_weather()


# ==================== ТИК ====================

def weather_tick():
    """Тик погоды. Если время пришло — сменить."""
    now = datetime.now()
    current = get_current_weather()

    if not current:
        roll_weather()
        return

    if current.ends_at and now >= current.ends_at:
        roll_weather()
        logger.info("🌤️ Погода изменилась (тик)")


# ==================== ЭФФЕКТЫ ====================

def get_weather_modifiers():
    """Модификаторы текущей погоды."""
    current = get_current_weather()
    if not current:
        return {
            'weather_type': 'clear',
            'name': '☀️ Ясно',
            'desc': '',
            'rc_mult': 1.0, 'rf_mult': 1.0, 'exp_mult': 1.0,
            'danger_add': 0,
        }

    return {
        'weather_type': current.weather_type,
        'name': current.name,
        'desc': current.description,
        'rc_mult': current.rc_mult,
        'rf_mult': current.rf_mult,
        'exp_mult': current.exp_mult,
        'danger_add': current.danger_add,
    }


def get_weather_view():
    """Текущая погода для UI."""
    current = get_current_weather()
    if not current:
        return {
            'name': '☀️ Ясно',
            'desc': 'Спокойная погода.',
            'time_left_min': 0,
        }

    now = datetime.now()
    time_left = 0
    if current.ends_at:
        delta = current.ends_at - now
        time_left = max(0, int(delta.total_seconds() // 60))

    return {
        'type': current.weather_type,
        'name': current.name,
        'desc': current.description,
        'rc_mult': current.rc_mult,
        'rf_mult': current.rf_mult,
        'exp_mult': current.exp_mult,
        'danger_add': current.danger_add,
        'time_left_min': time_left,
    }


def weather_short_line():
    """Короткая строка о погоде для UI."""
    w = get_weather_view()
    return f"{w['name']}  ({w['time_left_min']}м)"


def weather_full_line():
    """Полное описание погоды."""
    w = get_weather_view()
    parts = [w['name']]
    if w.get('desc'):
        parts.append(f"— {w['desc']}")
    if w.get('time_left_min'):
        parts.append(f"⏱ Ещё {w['time_left_min']}м")
    return "  ".join(parts)


def describe_modifiers():
    """Описание модификаторов погоды."""
    w = get_weather_view()
    parts = []

    if w.get('rc_mult', 1.0) != 1.0:
        delta = int((w['rc_mult'] - 1.0) * 100)
        parts.append(f"☢️ {'+' if delta > 0 else ''}{delta}%")
    if w.get('rf_mult', 1.0) != 1.0:
        delta = int((w['rf_mult'] - 1.0) * 100)
        parts.append(f"☣️ {'+' if delta > 0 else ''}{delta}%")
    if w.get('exp_mult', 1.0) != 1.0:
        delta = int((w['exp_mult'] - 1.0) * 100)
        parts.append(f"⚠️ {'+' if delta > 0 else ''}{delta}%")
    if w.get('danger_add', 0):
        parts.append(f"☢ Опасность +{w['danger_add']}")

    return "  |  ".join(parts) if parts else "— Обычная погода —"