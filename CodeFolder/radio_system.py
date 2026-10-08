# radio_system.py - Rad Earth
# Версия: 1.0.0
# Радиоэфир. Ведущий, склейка новостей из событий мира, шаблоны, история.

import os
import json
import random
from datetime import datetime, timedelta

from config import (
    logger, JSON_RADIO, RADIO_SPEAK_MIN, RADIO_SPEAK_MAX,
    RADIO_HISTORY_SIZE,
)
from database import (
    get_world_session,
    WorldEvent, Faction, NPC, Location, RadioHost,
)


# ==================== ЗАГРУЗКА ====================

_HOSTS_CACHE = None
_TEMPLATES_CACHE = None


def _load_json(path, default=None):
    if not os.path.exists(path):
        return default if default is not None else {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Ошибка чтения {path}: {e}")
        return default if default is not None else {}


def load_hosts():
    """Загрузить ведущих."""
    global _HOSTS_CACHE
    if _HOSTS_CACHE is not None:
        return _HOSTS_CACHE
    path = os.path.join(JSON_RADIO, 'hosts.json')
    _HOSTS_CACHE = _load_json(path, {})
    return _HOSTS_CACHE


def load_templates():
    """Загрузить шаблоны новостей."""
    global _TEMPLATES_CACHE
    if _TEMPLATES_CACHE is not None:
        return _TEMPLATES_CACHE
    path = os.path.join(JSON_RADIO, 'templates.json')
    _TEMPLATES_CACHE = _load_json(path, {})
    return _TEMPLATES_CACHE


def reload_radio():
    """Сбросить кэш."""
    global _HOSTS_CACHE, _TEMPLATES_CACHE
    _HOSTS_CACHE = None
    _TEMPLATES_CACHE = None


# ==================== СОЗДАНИЕ ВЕДУЩИХ В БД ====================

def ensure_hosts_in_db():
    """Создать ведущих в БД, если их нет."""
    hosts_data = load_hosts()
    if not hosts_data:
        return

    world = get_world_session()
    try:
        for host_id, data in hosts_data.items():
            existing = world.query(RadioHost).filter_by(id=host_id).first()
            if existing:
                continue
            host = RadioHost(
                id=host_id,
                name=data.get('name', host_id),
                callsign=data.get('callsign'),
                faction_id=data.get('faction_id'),
                style=data.get('style', 'neutral'),
                bio=data.get('bio', ''),
                is_active=data.get('is_active', True),
            )
            world.add(host)
        world.commit()
        logger.info(f"✅ Радиоведущие загружены")
    except Exception as e:
        logger.error(f"Ошибка создания ведущих: {e}")
        world.rollback()
    finally:
        world.close()


def get_active_host():
    """Выбрать активного ведущего."""
    world = get_world_session()
    try:
        hosts = world.query(RadioHost).filter_by(is_active=True).all()
        if not hosts:
            return None
        return random.choice(hosts)
    finally:
        world.close()


def get_host(host_id):
    """Получить ведущего по ID."""
    world = get_world_session()
    try:
        return world.query(RadioHost).filter_by(id=host_id).first()
    finally:
        world.close()


# ==================== СОБЫТИЯ ====================

def get_recent_events(limit=10, min_importance=1):
    """Последние события мира для эфира."""
    world = get_world_session()
    try:
        events = world.query(WorldEvent).filter(
            WorldEvent.importance >= min_importance
        ).order_by(WorldEvent.timestamp.desc()).limit(limit).all()
        return events
    finally:
        world.close()


def mark_events_broadcasted(event_ids):
    """Пометить события как вышедшие в эфир."""
    if not event_ids:
        return
    world = get_world_session()
    try:
        world.query(WorldEvent).filter(
            WorldEvent.id.in_(event_ids)
        ).update({'is_broadcasted': True}, synchronize_session=False)
        world.commit()
    finally:
        world.close()


# ==================== СБОРКА НОВОСТИ ====================

def build_news_item(event, world):
    """Собрать одну новость из события."""
    templates = load_templates()
    etype = event.event_type

    template_set = templates.get(etype, {})
    if isinstance(template_set, list):
        template = random.choice(template_set) if template_set else f"Событие: {etype}"
    elif isinstance(template_set, dict):
        template = template_set.get('default', f"Событие: {etype}")
    else:
        template = f"Событие: {etype}"

    # Получаем данные для подстановки
    faction_a = None
    faction_b = None
    loc_name = None
    npc_name = None

    if event.faction_a:
        f = world.query(Faction).filter_by(id=event.faction_a).first()
        faction_a = f.name if f else event.faction_a

    if event.faction_b:
        f = world.query(Faction).filter_by(id=event.faction_b).first()
        faction_b = f.name if f else event.faction_b

    if event.location_id:
        loc = world.query(Location).filter_by(id=event.location_id).first()
        loc_name = loc.name if loc else event.location_id

    if event.npc_id:
        npc = world.query(NPC).filter_by(id=event.npc_id).first()
        npc_name = npc.name if npc else event.npc_id

    # Простая подстановка
    try:
        text = template.format(
            faction_a=faction_a or "неизвестной фракции",
            faction_b=faction_b or "неизвестной фракции",
            location=loc_name or "неизвестной локации",
            npc=npc_name or "неизвестного сталкера",
        )
    except (KeyError, IndexError):
        text = template

    return text


def compose_broadcast(host=None):
    """Собрать полную передачу: приветствие + новости + погода + прощание."""
    world = get_world_session()
    try:
        if host is None:
            host = get_active_host()

        templates = load_templates()
        events = get_recent_events(limit=5, min_importance=2)

        parts = []

        # Приветствие
        greetings = templates.get('greetings', [])
        if greetings:
            parts.append(random.choice(greetings))
        elif host:
            parts.append(f"— Приветствую, Пустошь. С вами {host.name}.")

        # Новости
        event_ids = []
        if events:
            intro = templates.get('intro_news', "Сводка новостей:")
            parts.append(intro)

            for event in events[:3]:
                news = build_news_item(event, world)
                parts.append("— " + news)
                event_ids.append(event.id)

        # Погода
        weather_line = _weather_line(templates)
        if weather_line:
            parts.append(weather_line)

        # Прощание
        farewells = templates.get('farewells', [])
        if farewells:
            parts.append(random.choice(farewells))
        elif host:
            parts.append(f"— Это был {host.name}. Оставайтесь живыми.")

        # Пометить события
        if event_ids:
            mark_events_broadcasted(event_ids)

        return {
            'host_id': host.id if host else None,
            'host_name': host.name if host else 'Неизвестный',
            'parts': parts,
            'text': "\n".join(parts),
            'event_ids': event_ids,
            'timestamp': datetime.now().isoformat(),
        }
    finally:
        world.close()


def _weather_line(templates):
    """Строка о погоде."""
    weather_lines = templates.get('weather', [])
    if weather_lines:
        return random.choice(weather_lines)
    return "— А теперь о погоде: в Пустоши всё как обычно."


# ==================== ИСТОРИЯ ЭФИРА ====================

_RADIO_HISTORY = []


def add_to_history(broadcast):
    """Добавить в историю эфира."""
    global _RADIO_HISTORY
    _RADIO_HISTORY.append(broadcast)
    if len(_RADIO_HISTORY) > RADIO_HISTORY_SIZE:
        _RADIO_HISTORY = _RADIO_HISTORY[-RADIO_HISTORY_SIZE:]


def get_history(limit=10):
    """История эфира."""
    return _RADIO_HISTORY[-limit:]


def get_last_broadcast():
    """Последний эфир."""
    return _RADIO_HISTORY[-1] if _RADIO_HISTORY else None


# ==================== ТИКЕР ЭФИРА ====================

_last_broadcast_time = None


def maybe_broadcast():
    """Проверить: не пора ли вещать? Возвращает текст эфира или None."""
    global _last_broadcast_time
    now = datetime.now()

    if _last_broadcast_time is None:
        _last_broadcast_time = now - timedelta(seconds=RADIO_SPEAK_MIN)
    interval = random.randint(RADIO_SPEAK_MIN, RADIO_SPEAK_MAX)

    if (now - _last_broadcast_time).total_seconds() >= interval:
        broadcast = compose_broadcast()
        add_to_history(broadcast)
        _last_broadcast_time = now
        return broadcast

    return None


def force_broadcast():
    """Принудительно выпустить эфир."""
    broadcast = compose_broadcast()
    add_to_history(broadcast)
    return broadcast


# ==================== ДЕФОЛТНЫЕ ШАБЛОНЫ (если JSON пуст) ====================

DEFAULT_TEMPLATES = {
    'greetings': [
        "📻 — Добрый день, Пустошь. В эфире последние новости.",
        "📻 — Приветствую всех выживших. С вами радио Пустоши.",
        "📻 — Добрый день, сталкеры. Слушайте свежие вести.",
    ],
    'intro_news': "📻 — Сводка событий:",
    'weather': [
        "📻 — А теперь о погоде. На Пустошь опускается туман.",
        "📻 — А теперь о погоде. Сегодня ясно, но вечером возможен дождь.",
        "📻 — А теперь о погоде. Ветер усиливается, будьте осторожны.",
    ],
    'farewells': [
        "📻 — Оставайтесь живыми.",
        "📻 — До следующего эфира.",
        "📻 — Берегите себя.",
    ],
    'skirmish': [
        "— Стычка между {faction_a} и {faction_b} в районе {location}.",
        "— {faction_a} и {faction_b} схлестнулись в {location}.",
        "— Перестрелка: {faction_a} против {faction_b}.",
    ],
    'npc_death': [
        "— Погиб {npc}.",
        "— Не стало {npc}.",
        "— {npc} больше не с нами.",
    ],
    'mutant_attack': [
        "— Мутанты атаковали {location}.",
        "— Нападение мутантов на {location}.",
        "— Неспокойно в {location} — мутанты.",
    ],
    'trade': [
        "— Торговля между {faction_a} и {faction_b}.",
        "— Сделка: {faction_a} и {faction_b}.",
    ],
    'weather_shift': [
        "— Резкая смена погоды в {location}.",
    ],
    'festival': [
        "— Праздник в {location}.",
    ],
    'betrayal': [
        "— Предательство в {faction_a}.",
    ],
    'discovery': [
        "— Учёные обнаружили что-то новое в {location}.",
    ],
    'rumor': [
        "— Слух: в {location} происходит что-то странное.",
    ],
}


def ensure_default_templates():
    """Если templates.json пуст — не страшно, есть дефолт."""
    path = os.path.join(JSON_RADIO, 'templates.json')
    data = _load_json(path, None)
    if not data:
        logger.warning("templates.json пуст, будут использоваться дефолтные")
        return DEFAULT_TEMPLATES
    return data


# Обновим load_templates чтобы использовал дефолт
_original_load_templates = load_templates
def load_templates():
    global _TEMPLATES_CACHE
    if _TEMPLATES_CACHE is not None:
        return _TEMPLATES_CACHE
    path = os.path.join(JSON_RADIO, 'templates.json')
    data = _load_json(path, None)
    if not data:
        data = DEFAULT_TEMPLATES
    _TEMPLATES_CACHE = data
    return _TEMPLATES_CACHE