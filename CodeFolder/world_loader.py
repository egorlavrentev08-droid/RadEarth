# world_loader.py - Rad Earth
# Версия: 1.0.0
# Загрузчик мира. Наполняет БД из JSON при первом запуске.
# Идемпотентен: повторный запуск не дублирует данные.

import os
import json
from datetime import datetime

from config import (
    logger, JSON_FACTIONS, JSON_FACTIONS_MINOR, JSON_LOCATIONS,
    JSON_NPCS_NAMED, JSON_NPCS_TEMPLATES, JSON_RADIO,
    JSON_WEATHER, JSON_ITEMS, JSON_ECONOMY,
    MAJOR_FACTIONS, LOCATIONS_LIST, FACTION_RANKS, FACTION_COLORS,
)
from database import (
    get_world_session, get_players_session,
    WorldBase, PlayersBase,
    world_engine, players_engine,
    Faction, Location, NPC, RadioHost, Weather,
    FactionRelation, War, WorldEvent,
)


# ==================== ГЛАВНАЯ ФУНКЦИЯ ====================

def load_world(force=False):
    """Загрузить весь мир из JSON в БД.

    force=False — только если БД пустая.
    force=True — пересоздать все таблицы и залить заново.
    """
    world = get_world_session()
    try:
        if force:
            logger.info("🌍 Полная перезагрузка мира...")
            WorldBase.metadata.drop_all(world_engine)
            WorldBase.metadata.create_all(world_engine)
            world.commit()

        # Проверить: если уже что-то есть и не force — не грузим
        existing = world.query(Faction).count()
        if existing > 0 and not force:
            logger.info(f"🌍 Мир уже загружен ({existing} фракций)")
            return False

        logger.info("🌍 Загрузка мира из JSON...")

        # Порядок важен!
        _load_factions(world)
        _load_locations(world)
        _load_named_npcs(world)
        _load_faction_relations(world)
        _load_radio_hosts(world)
        _load_initial_weather(world)

        world.commit()
        logger.info("✅ Мир загружен")
        return True
    except Exception as e:
        logger.error(f"Ошибка загрузки мира: {e}")
        world.rollback()
        raise
    finally:
        world.close()


# ==================== ЗАГРУЗКА ФРАКЦИЙ ====================

def _load_factions(world):
    """Загрузить все фракции."""
    # Крупные
    for fid in MAJOR_FACTIONS:
        path = os.path.join(JSON_FACTIONS, f"{fid}.json")
        data = _load_json(path)
        if not data:
            logger.warning(f"⚠️ Фракция {fid}: JSON не найден, пропуск")
            continue

        existing = world.query(Faction).filter_by(id=fid).first()
        if existing:
            continue

        faction = Faction(
            id=fid,
            name=data.get('name', fid),
            type=data.get('type', 'mixed'),
            desc=data.get('desc', ''),
            color=data.get('color', FACTION_COLORS.get(fid, '#aaaaaa')),
            leader_id=data.get('leader_id'),
            advisor_id=data.get('advisor_id'),
            treasury_coins=data.get('treasury_coins', 0),
            treasury_fragments=data.get('treasury_fragments', 0),
            treasury_crystals=data.get('treasury_crystals', 0),
            population_total=data.get('population_total', 0),
            population_alive=data.get('population_alive', 0),
            military_strength=data.get('military_strength', 100),
            discipline=data.get('discipline', 50),
            morale=data.get('morale', 50),
            is_at_war=json.dumps(data.get('at_war_with', [])),
            is_ally=json.dumps(data.get('allied_with', [])),
            is_neutral=json.dumps(data.get('neutral_with', [])),
            controlled_locations=json.dumps(data.get('controlled_locations', [])),
        )
        world.add(faction)
        logger.info(f"  ✅ Фракция: {faction.name}")

    # Мелкие (пока пропускаем, если папка пустая)
    minor_path = JSON_FACTIONS_MINOR
    if os.path.isdir(minor_path):
        for fname in os.listdir(minor_path):
            if not fname.endswith('.json'):
                continue
            path = os.path.join(minor_path, fname)
            data = _load_json(path)
            if not data:
                continue
            fid = data.get('id', fname.replace('.json', ''))
            existing = world.query(Faction).filter_by(id=fid).first()
            if existing:
                continue
            faction = Faction(
                id=fid,
                name=data.get('name', fid),
                type=data.get('type', 'minor'),
                desc=data.get('desc', ''),
                color=data.get('color', '#888888'),
                population_total=data.get('population_total', 0),
                population_alive=data.get('population_alive', 0),
                military_strength=data.get('military_strength', 50),
                discipline=data.get('discipline', 50),
                morale=data.get('morale', 50),
                controlled_locations=json.dumps(data.get('controlled_locations', [])),
            )
            world.add(faction)
            logger.info(f"  ✅ Мелкая фракция: {faction.name}")

    world.commit()


# ==================== ЗАГРУЗКА ЛОКАЦИЙ ====================

def _load_locations(world):
    """Загрузить все локации."""
    for loc_id in LOCATIONS_LIST:
        path = os.path.join(JSON_LOCATIONS, f"{loc_id}.json")
        data = _load_json(path)
        if not data:
            logger.warning(f"⚠️ Локация {loc_id}: JSON не найден, пропуск")
            continue

        existing = world.query(Location).filter_by(id=loc_id).first()
        if existing:
            continue

        loc = Location(
            id=loc_id,
            name=data.get('name', loc_id),
            type=data.get('type', 'wild'),
            desc=data.get('desc', ''),
            controller_faction_id=data.get('controller_faction_id'),
            rc_mult=data.get('rc_mult', 1.0),
            rf_mult=data.get('rf_mult', 1.0),
            exp_mult=data.get('exp_mult', 1.0),
            pet_mult=data.get('pet_mult', 1.0),
            chest_mult=data.get('chest_mult', 1.0),
            danger_bonus=data.get('danger_bonus', 0),
            encounter_chance=data.get('encounter_chance', 0.1),
            has_trader=data.get('has_trader', False),
            has_business=data.get('has_business', False),
            has_shops=data.get('has_shops', False),
            has_medbay=data.get('has_medbay', False),
            has_barracks=data.get('has_barracks', False),
            connections=json.dumps(data.get('connections', [])),
        )
        world.add(loc)
        logger.info(f"  ✅ Локация: {loc.name}")

    world.commit()


# ==================== ЗАГРУЗКА ИМЕНОВАННЫХ NPC ====================

def _load_named_npcs(world):
    """Загрузить ключевых NPC из JsonFolder/npcs/named/."""
    if not os.path.isdir(JSON_NPCS_NAMED):
        return

    for fname in os.listdir(JSON_NPCS_NAMED):
        if not fname.endswith('.json'):
            continue
        path = os.path.join(JSON_NPCS_NAMED, fname)
        data = _load_json(path)
        if not data:
            continue

        npc_id = data.get('id', fname.replace('.json', ''))
        existing = world.query(NPC).filter_by(id=npc_id).first()
        if existing:
            continue

        npc = NPC(
            id=npc_id,
            name=data.get('name', 'Неизвестный'),
            callsign=data.get('callsign'),
            gender=data.get('gender', 'male'),
            faction_id=data.get('faction_id'),
            rank=data.get('rank'),
            role=data.get('role'),
            is_named=True,
            is_alive=True,
            loyalty=data.get('loyalty', 50),
            aggression=data.get('aggression', 50),
            intelligence=data.get('intelligence', 50),
            combat_skill=data.get('combat_skill', 50),
            hp_current=data.get('hp_max', 100),
            hp_max=data.get('hp_max', 100),
            is_trader=data.get('is_trader', False),
            trader_type=data.get('trader_type'),
            location_id=data.get('location_id'),
            dialog_file=data.get('dialog_file', npc_id),
        )
        world.add(npc)
        logger.info(f"  ✅ NPC: {npc.name} ({npc.id})")

    world.commit()


# ==================== ДИПЛОМАТИЯ ====================

def _load_faction_relations(world):
    """Инициализировать отношения между фракциями."""
    factions = world.query(Faction).all()
    faction_ids = [f.id for f in factions]

    for i, fa in enumerate(faction_ids):
        for fb in faction_ids[i+1:]:
            existing = world.query(FactionRelation).filter_by(
                faction_a=fa, faction_b=fb
            ).first()
            if existing:
                continue

            # Читаем статусы из фракции
            faction_a_obj = world.query(Faction).filter_by(id=fa).first()
            at_war = json.loads(faction_a_obj.is_at_war or '[]')
            allied = json.loads(faction_a_obj.is_ally or '[]')

            if fb in at_war:
                relation = -75
                status = 'war'
            elif fb in allied:
                relation = 75
                status = 'ally'
            else:
                relation = 0
                status = 'neutral'

            rel = FactionRelation(
                faction_a=fa, faction_b=fb,
                relation=relation, status=status,
            )
            world.add(rel)

    world.commit()


# ==================== ВЕДУЩИЕ РАДИО ====================

def _load_radio_hosts(world):
    """Загрузить радиоведущих."""
    path = os.path.join(JSON_RADIO, 'hosts.json')
    data = _load_json(path, default=None)

    if not data:
        # Дефолтный ведущий
        existing = world.query(RadioHost).filter_by(id='host_main').first()
        if not existing:
            host = RadioHost(
                id='host_main',
                name='Ведущий',
                callsign='Голос Пустоши',
                style='neutral',
                bio='Неизвестный. Голос в эфире.',
                is_active=True,
            )
            world.add(host)
            logger.info("  ✅ Ведущий по умолчанию")
        world.commit()
        return

    for host_id, hdata in data.items():
        existing = world.query(RadioHost).filter_by(id=host_id).first()
        if existing:
            continue
        host = RadioHost(
            id=host_id,
            name=hdata.get('name', host_id),
            callsign=hdata.get('callsign'),
            faction_id=hdata.get('faction_id'),
            style=hdata.get('style', 'neutral'),
            bio=hdata.get('bio', ''),
            is_active=hdata.get('is_active', True),
        )
        world.add(host)

    world.commit()


# ==================== ПОГОДА ====================

def _load_initial_weather(world):
    """Установить начальную погоду."""
    from weather_system import roll_weather
    # roll_weather работает через свою сессию — не в рамках world
    try:
        roll_weather()
    except Exception as e:
        logger.warning(f"Не удалось установить начальную погоду: {e}")


# ==================== ГЕНЕРАЦИЯ NPC ====================

def generate_world_npcs():
    """Сгенерировать рядовых NPC для всех фракций (после загрузки)."""
    from npc_engine import generate_all_faction_npcs, create_faction_leaders

    logger.info("👥 Генерация NPC...")
    generate_all_faction_npcs()
    create_faction_leaders()
    logger.info("✅ NPC сгенерированы")


# ==================== ПРОВЕРКА ЦЕЛОСТНОСТИ ====================

def validate_world():
    """Проверить, что мир загружен корректно."""
    world = get_world_session()
    try:
        factions_count = world.query(Faction).count()
        locations_count = world.query(Location).count()
        npcs_count = world.query(NPC).count()
        hosts_count = world.query(RadioHost).count()

        result = {
            'factions': factions_count,
            'locations': locations_count,
            'npcs': npcs_count,
            'hosts': hosts_count,
            'ok': factions_count >= 7 and locations_count >= 10,
        }

        if not result['ok']:
            logger.warning(f"⚠️ Мир не полный: {result}")
        else:
            logger.info(f"✅ Мир валиден: {result}")

        return result
    finally:
        world.close()


# ==================== СБРОС ====================

def reset_world():
    """Полный сброс мира (только world.db, игроки не тронуты)."""
    logger.warning("⚠️ Сброс мира...")
    return load_world(force=True)


# ==================== ХЕЛПЕРЫ ====================

def _load_json(path, default=None):
    """Загрузить JSON."""
    if not os.path.exists(path):
        return default
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Ошибка чтения {path}: {e}")
        return default


# ==================== ИНИЦИАЛИЗАЦИЯ ====================

def ensure_world_loaded():
    """Проверить, что мир загружен. Если нет — загрузить и сгенерировать NPC."""
    world = get_world_session()
    try:
        factions_count = world.query(Faction).count()
    finally:
        world.close()

    if factions_count == 0:
        logger.info("🌍 Первый запуск: загрузка мира...")
        load_world()

        # После загрузки — генерация NPC
        world = get_world_session()
        try:
            npcs_count = world.query(NPC).count()
        finally:
            world.close()

        if npcs_count < 100:
            generate_world_npcs()

        validate_world()
    else:
        logger.info(f"🌍 Мир уже загружен ({factions_count} фракций)")


if __name__ == '__main__':
    # Прямой запуск — перезагрузить мир
    load_world(force=True)