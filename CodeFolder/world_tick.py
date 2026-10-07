# world_tick.py - Rad Earth
# Версия: 1.0.0
# Тикер мира. Симуляция: стычки, смерти, миграции, войны, события, радио.

import os
import json
import random
from datetime import datetime, timedelta

from config import (
    logger, WORLD_TICK_SECONDS, WORLD_EVENT_WEIGHTS,
    FACTION_RANKS, MAJOR_FACTIONS, REP_MIN, REP_MAX, clamp,
)
from database import (
    get_world_session,
    Faction, FactionRelation, War, NPC, Location,
    WorldEvent, Weather,
)
from npc_engine import (
    kill_npc, wound_npc, promote_npc, demote_npc,
    get_npcs_by_faction,
)
from faction_engine import (
    get_active_wars, get_wars_for_faction,
    declare_war, make_peace,
    recalculate_population, recalculate_all_populations,
)
from weather_system import weather_tick


# ==================== ОСНОВНОЙ ТИК ====================

_tick_count = 0
_last_tick_time = None


def world_tick():
    """Один тик мира. Вызывать раз в WORLD_TICK_SECONDS."""
    global _tick_count, _last_tick_time
    _tick_count += 1
    _last_tick_time = datetime.now()

    logger.info(f"🌍 Тик #{_tick_count}")

    world = get_world_session()
    try:
        # 1. Смена погоды
        weather_tick()

        # 2. События мира (стычки, смерть, торговля)
        event = roll_world_event()
        if event:
            process_event(event, world)

        # 3. Прогресс войн
        process_wars(world)

        # 4. Случайные смерти NPC (от ран, болезней)
        process_natural_deaths(world)

        # 5. Продвижение/понижение лояльных NPC
        process_promotions(world)

        # 6. Пересчёт численностей
        for fid in MAJOR_FACTIONS:
            recalculate_population(fid)

        # 7. Затухание старых событий (чистка)
        cleanup_old_events(world)

        world.commit()
        logger.info(f"✅ Тик #{_tick_count} завершён")
    except Exception as e:
        logger.error(f"Ошибка тика: {e}")
        world.rollback()
    finally:
        world.close()


# ==================== СОБЫТИЯ ====================

def roll_world_event():
    """Случайное событие мира по весам."""
    total_weight = sum(WORLD_EVENT_WEIGHTS.values())
    roll = random.uniform(0, total_weight)
    cumulative = 0
    for event_type, weight in WORLD_EVENT_WEIGHTS.items():
        cumulative += weight
        if roll <= cumulative:
            return event_type
    return 'rumor'


def process_event(event_type, world):
    """Обработать событие."""
    handlers = {
        'skirmish': event_skirmish,
        'mutant_attack': event_mutant_attack,
        'npc_death': event_npc_death,
        'trade': event_trade,
        'weather_shift': event_weather_shift,
        'festival': event_festival,
        'betrayal': event_betrayal,
        'discovery': event_discovery,
        'rumor': event_rumor,
    }
    handler = handlers.get(event_type)
    if handler:
        try:
            handler(world)
        except Exception as e:
            logger.error(f"Ошибка события {event_type}: {e}")


# ==================== ОБРАБОТЧИКИ СОБЫТИЙ ====================

def event_skirmish(world):
    """Стычка между двумя фракциями."""
    # Найти две живые фракции
    factions = world.query(Faction).filter(
        Faction.population_alive > 10
    ).all()

    if len(factions) < 2:
        return

    fa, fb = random.sample(factions, 2)

    # Проверить: враждуют?
    rel = world.query(FactionRelation).filter_by(
        faction_a=min(fa.id, fb.id),
        faction_b=max(fa.id, fb.id),
    ).first()

    if not rel:
        return

    # Стычки чаще у враждебных
    if rel.status == 'ally':
        return
    if rel.status == 'neutral' and random.random() < 0.7:
        return

    # Кто-то получает урон
    loser = random.choice([fa, fb])
    winner = fb if loser == fa else fa

    casualties = random.randint(2, 15)
    loser.population_alive = max(0, loser.population_alive - casualties)
    loser.morale = max(0, loser.morale - random.randint(1, 5))

    # Убить нескольких NPC
    _kill_random_npcs(loser.id, casualties, world, reason=f"Стычка с {winner.name}")

    # Записать событие
    event = WorldEvent(
        event_type='skirmish',
        faction_a=winner.id,
        faction_b=loser.id,
        location_id=_random_controller_location(loser.id, world),
        details=json.dumps({'casualties': casualties}),
        importance=5,
    )
    world.add(event)
    logger.info(f"⚔️ Стычка: {winner.id} vs {loser.id}, жертв {casualties} у {loser.id}")


def event_mutant_attack(world):
    """Нападение мутантов на локацию."""
    locations = world.query(Location).all()
    if not locations:
        return

    loc = random.choice(locations)
    casualties = random.randint(1, 8)

    if loc.controller_faction_id:
        faction = world.query(Faction).filter_by(id=loc.controller_faction_id).first()
        if faction:
            faction.population_alive = max(0, faction.population_alive - casualties)
            _kill_random_npcs(loc.controller_faction_id, casualties, world,
                              reason='Убит мутантами')

    event = WorldEvent(
        event_type='mutant_attack',
        location_id=loc.id,
        details=json.dumps({'casualties': casualties}),
        importance=4,
    )
    world.add(event)
    logger.info(f"👾 Мутанты атаковали {loc.name}, жертв {casualties}")


def event_npc_death(world):
    """Естественная смерть известного NPC."""
    named = world.query(NPC).filter_by(is_named=True, is_alive=True).all()
    if not named:
        return

    npc = random.choice(named)
    if random.random() < 0.7:
        return  # не всегда умирают

    kill_npc(npc.id, reason='Естественная смерть')

    event = WorldEvent(
        event_type='npc_death',
        npc_id=npc.id,
        faction_a=npc.faction_id,
        location_id=npc.location_id,
        details=json.dumps({'name': npc.name, 'callsign': npc.callsign}),
        importance=6,
    )
    world.add(event)
    logger.info(f"💀 Умер NPC: {npc.name}")


def event_trade(world):
    """Торговая сделка между фракциями."""
    factions = world.query(Faction).all()
    if len(factions) < 2:
        return

    fa, fb = random.sample(factions, 2)

    # Торгуют только нейтралы/союзники
    rel = world.query(FactionRelation).filter_by(
        faction_a=min(fa.id, fb.id),
        faction_b=max(fa.id, fb.id),
    ).first()

    if not rel or rel.status == 'war':
        return

    # Прибыль
    amount = random.randint(100, 2000)
    fa.treasury_coins = (fa.treasury_coins or 0) + amount
    fb.treasury_coins = (fb.treasury_coins or 0) + int(amount * 0.8)

    event = WorldEvent(
        event_type='trade',
        faction_a=fa.id,
        faction_b=fb.id,
        details=json.dumps({'amount': amount}),
        importance=3,
    )
    world.add(event)
    logger.info(f"💰 Торговля: {fa.id} → {fb.id} на {amount}")


def event_weather_shift(world):
    """Резкая смена погоды."""
    from weather_system import roll_weather
    try:
        roll_weather()
        event = WorldEvent(
            event_type='weather_shift',
            importance=2,
        )
        world.add(event)
    except Exception as e:
        logger.error(f"Ошибка смены погоды: {e}")


def event_festival(world):
    """Праздник в поселении."""
    settlements = world.query(Location).filter(
        Location.type.in_(['city', 'settlement'])
    ).all()

    if not settlements:
        return

    loc = random.choice(settlements)

    if loc.controller_faction_id:
        faction = world.query(Faction).filter_by(id=loc.controller_faction_id).first()
        if faction:
            faction.morale = min(100, faction.morale + random.randint(3, 10))

    event = WorldEvent(
        event_type='festival',
        location_id=loc.id,
        faction_a=loc.controller_faction_id,
        importance=3,
    )
    world.add(event)
    logger.info(f"🎉 Праздник в {loc.name}")


def event_betrayal(world):
    """Предательство внутри фракции."""
    factions = world.query(Faction).filter(Faction.population_alive > 20).all()
    if not factions:
        return

    faction = random.choice(factions)

    # Понизить мораль
    faction.morale = max(0, faction.morale - random.randint(5, 15))
    faction.discipline = max(0, faction.discipline - random.randint(2, 8))

    # Убить одного NPC
    _kill_random_npcs(faction.id, 1, world, reason='Предательство')

    event = WorldEvent(
        event_type='betrayal',
        faction_a=faction.id,
        importance=5,
    )
    world.add(event)
    logger.info(f"🗡️ Предательство в {faction.id}")


def event_discovery(world):
    """Учёные что-то открыли."""
    lab = world.query(Location).filter_by(type='lab').first()
    if not lab:
        return

    if lab.controller_faction_id:
        faction = world.query(Faction).filter_by(id=lab.controller_faction_id).first()
        if faction:
            faction.treasury_crystals = (faction.treasury_crystals or 0) + random.randint(1, 5)

    event = WorldEvent(
        event_type='discovery',
        location_id=lab.id,
        faction_a=lab.controller_faction_id,
        importance=4,
    )
    world.add(event)
    logger.info(f"🔬 Открытие в {lab.name}")


def event_rumor(world):
    """Слух."""
    locations = world.query(Location).all()
    if not locations:
        return

    loc = random.choice(locations)
    event = WorldEvent(
        event_type='rumor',
        location_id=loc.id,
        importance=1,
    )
    world.add(event)


# ==================== ВОЙНЫ ====================

def process_wars(world):
    """Прогресс активных войн."""
    wars = world.query(War).filter_by(is_active=True).all()
    if not wars:
        return

    for war in wars:
        fa = world.query(Faction).filter_by(id=war.faction_a).first()
        fb = world.query(Faction).filter_by(id=war.faction_b).first()

        if not fa or not fb:
            war.is_active = False
            continue

        # Случайный урон
        if random.random() < 0.4:
            loser = random.choice([fa, fb])
            casualties = random.randint(1, 8)
            loser.population_alive = max(0, loser.population_alive - casualties)

            if loser == fa:
                war.casualties_a = (war.casualties_a or 0) + casualties
            else:
                war.casualties_b = (war.casualties_b or 0) + casualties

            _kill_random_npcs(loser.id, casualties, world,
                              reason=f"Война с {'b' if loser == fa else 'a'}")

        # Проверка: не пора ли завершить
        if random.random() < 0.02:
            _attempt_peace(war, fa, fb, world)

        # Проверка: кто-то вымер
        if fa.population_alive <= 5 or fb.population_alive <= 5:
            winner = fb if fa.population_alive <= 5 else fa
            war.is_active = False
            war.ended_at = datetime.now()
            war.winner = winner.id
            logger.info(f"🏆 Война окончена. Победитель: {winner.id}")

    world.commit()


def _attempt_peace(war, fa, fb, world):
    """Попытка мира."""
    # Мир чаще, если обе стороны истощены
    if fa.population_alive < 100 and fb.population_alive < 100:
        make_peace(world, fa.id, fb.id)
        war.is_active = False
        war.ended_at = datetime.now()
        logger.info(f"🕊️ Мир между {fa.id} и {fb.id}")


# ==================== СМЕРТИ ====================

def process_natural_deaths(world):
    """Случайные смерти NPC (раненые, старые)."""
    # Найти раненых NPC
    wounded = world.query(NPC).filter(
        NPC.is_alive == True,
        NPC.hp_current < NPC.hp_max,
    ).limit(50).all()

    for npc in wounded:
        # Лечение или смерть
        if random.random() < 0.3:
            # Восстановление
            npc.hp_current = min(npc.hp_max, npc.hp_current + random.randint(5, 20))
        elif random.random() < 0.05:
            # Смерть от ран
            kill_npc(npc.id, reason='Умер от ран')


# ==================== ПРОДВИЖЕНИЯ ====================

def process_promotions(world):
    """Иногда NPC продвигаются по службе."""
    candidates = world.query(NPC).filter(
        NPC.is_alive == True,
        NPC.loyalty >= 70,
        NPC.rank != None,
    ).limit(20).all()

    for npc in candidates:
        if random.random() < 0.1:
            promote_npc(npc.id)


# ==================== ЧИСТКА ====================

def cleanup_old_events(world):
    """Удалить события старше 3 дней."""
    cutoff = datetime.now() - timedelta(days=3)
    old = world.query(WorldEvent).filter(
        WorldEvent.timestamp < cutoff
    ).all()
    for e in old:
        world.delete(e)


# ==================== ХЕЛПЕРЫ ====================

def _kill_random_npcs(faction_id, count, world, reason=''):
    """Убить N случайных живых NPC фракции."""
    if count <= 0:
        return
    npcs = world.query(NPC).filter_by(
        faction_id=faction_id, is_alive=True
    ).limit(count * 3).all()

    if not npcs:
        return

    chosen = random.sample(npcs, min(count, len(npcs)))
    for npc in chosen:
        npc.is_alive = False
        npc.death_date = datetime.now()
        npc.death_reason = reason


def _random_controller_location(faction_id, world):
    """Случайная локация под контролем фракции."""
    faction = world.query(Faction).filter_by(id=faction_id).first()
    if not faction:
        return None
    locs = json.loads(faction.controlled_locations or '[]')
    if not locs:
        return None
    return random.choice(locs)


# ==================== ЗАПУСК ТИКЕРА ====================

def start_ticker(root=None, interval_seconds=None):
    """Запустить тикер в отдельном потоке (для tkinter).

    Если root передан — используем root.after() для планирования.
    """
    if interval_seconds is None:
        interval_seconds = WORLD_TICK_SECONDS

    def _tick_loop():
        try:
            world_tick()
        except Exception as e:
            logger.error(f"Ошибка в тикере: {e}")
        finally:
            if root:
                root.after(interval_seconds * 1000, _tick_loop)

    if root:
        # Планируем первый тик через 5 секунд
        root.after(5000, _tick_loop)
        logger.info(f"🌍 Тикер мира запущен (интервал {interval_seconds}с)")
    else:
        # Прямой вызов (для тестов)
        world_tick()


# ==================== РУЧНОЙ ЗАПУСК ====================

def force_skirmish():
    """Принудительная стычка (для тестов)."""
    world = get_world_session()
    try:
        event_skirmish(world)
        world.commit()
    finally:
        world.close()


def force_war(faction_a, faction_b):
    """Принудительно объявить войну."""
    world = get_world_session()
    try:
        declare_war(world, faction_a, faction_b, reason='Тест')
    finally:
        world.close()


def get_recent_events(limit=20):
    """Последние события."""
    world = get_world_session()
    try:
        return world.query(WorldEvent).order_by(
            WorldEvent.timestamp.desc()
        ).limit(limit).all()
    finally:
        world.close()


if __name__ == '__main__':
    # Прямой запуск — один тик
    world_tick()