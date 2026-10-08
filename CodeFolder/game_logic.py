# game_logic.py - Rad Earth
# Версия: 1.0.0
# Основная игровая логика. Сбор, охота, вылазки, перемещение, сон, еда.

import os
import json
import random
from datetime import datetime, timedelta

from config import (
    logger, START_LOCATION, MAX_LEVEL,
    TRAVEL_TIME_PER_HOP, MAX_HOPS_WITHOUT_REST, FATIGUE_DAMAGE_PER_HOP,
    get_exp_for_level, clamp,
)
from database import (
    get_players_session, get_world_session,
    Player, PlayerLog, NPC, Location, Faction, WorldEvent,
)
from utils import (
    get_inventory, add_item_to_inventory, remove_item_from_inventory,
    get_item_count, get_equipped, save_equipped,
    add_experience, check_level_up,
    calculate_survive_chance, roll_loot,
    safe_log,
)
from faction_engine import (
    get_player_rep, change_player_rep, get_rep_status,
)
from economy_system import get_item
from dialog_system import start_dialog, process_choice


# ==================== СБОР ====================

def do_collect(player_id):
    """Сбор ресурсов в текущей локации."""
    players = get_players_session()
    world = get_world_session()
    try:
        player = players.query(Player).filter_by(id=player_id).first()
        if not player:
            return {'ok': False, 'message': 'Игрок не найден'}

        now = datetime.now()
        if player.next_collection_time and now < player.next_collection_time:
            remaining = player.next_collection_time - now
            h = remaining.seconds // 3600
            m = (remaining.seconds % 3600) // 60
            return {'ok': False, 'message': f'Следующий сбор через {h}ч {m}мин'}

        loc = world.query(Location).filter_by(id=player.current_location).first()
        if not loc:
            loc_id = START_LOCATION
            loc = world.query(Location).filter_by(id=loc_id).first()
            if loc:
                player.current_location = loc_id

        rc_mult = loc.rc_mult if loc else 1.0
        rf_mult = loc.rf_mult if loc else 1.0
        exp_mult = loc.exp_mult if loc else 1.0
        pet_mult = loc.pet_mult if loc else 1.0
        chest_mult = loc.chest_mult if loc else 1.0

        base_rc = random.randint(50, 150) + player.level * 5
        base_exp = random.randint(10, 50)

        # Бонусы от класса
        class_mults = _get_class_mults(player.user_class)
        rc_gain = int(base_rc * rc_mult * class_mults['rc'])
        exp_gain = int(base_exp * exp_mult * class_mults['exp'])

        rf_gain = 0
        if random.random() < 0.30 * rf_mult:
            rf_gain = random.randint(1, 5)

        # Критический сбор
        multiplier = 1
        if random.random() < 0.05:
            multiplier = 2
        elif random.random() < 0.01:
            multiplier = 5
        rc_gain *= multiplier

        # Эффекты
        if player.energy_drink_until and player.energy_drink_until > now:
            rc_gain = int(rc_gain * 1.15)
            rf_gain = int(rf_gain * 1.25)

        player.radcoins += rc_gain
        player.radfragments += rf_gain
        player.total_collects = (player.total_collects or 0) + 1
        player.total_rc_earned = (player.total_rc_earned or 0) + rc_gain
        if rc_gain > (player.best_collect or 0):
            player.best_collect = rc_gain

        level_up = check_level_up(player, exp_gain)

        # Кулдаун
        base_interval = random.randint(30, 120)
        if player.cooldown_reducer_until and player.cooldown_reducer_until > now:
            base_interval = base_interval // 2
        if player.pet == 'кайот':
            base_interval = base_interval // 2

        player.last_collection = now
        player.next_collection_time = now + timedelta(minutes=base_interval)

        # Найти лут
        loot_found = []
        junk_chance = 0.35
        if random.random() < junk_chance:
            junk = _roll_junk()
            for j in junk:
                add_item_to_inventory(player, j['id'], 1)
                loot_found.append(j['name'])

        # Сундук
        chest_found = None
        if random.random() < 0.05 * chest_mult:
            chest_type = random.choices(
                ['common', 'rare', 'epic', 'mythic', 'legendary'],
                weights=[70, 20, 7, 2.5, 0.5]
            )[0]
            chest_field = f'chest_{chest_type}'
            setattr(player, chest_field, (getattr(player, chest_field) or 0) + 1)
            chest_found = chest_type

        # Питомец
        pet_found = None
        if random.random() < 0.005 * pet_mult:
            pets = ['овчарка', 'волк', 'рысь', 'пума', 'попугай', 'кайот']
            pet_found = random.choice(pets)

        safe_log(player, 'collect', rc=rc_gain, rf=rf_gain, item=str(loot_found))
        players.commit()

        return {
            'ok': True,
            'rc': rc_gain,
            'rf': rf_gain,
            'exp': exp_gain,
            'multiplier': multiplier,
            'level_up': level_up,
            'loot': loot_found,
            'chest': chest_found,
            'pet': pet_found,
            'next_in_min': base_interval,
        }
    except Exception as e:
        logger.error(f"Ошибка сбора: {e}")
        players.rollback()
        return {'ok': False, 'message': str(e)}
    finally:
        players.close()
        world.close()


def _get_class_mults(user_class):
    """Множители добычи по классу."""
    return {
        'stalker':  {'rc': 1.0,  'rf': 1.0,  'exp': 1.0},
        'military': {'rc': 1.2,  'rf': 0.7,  'exp': 1.3},
        'bandit':   {'rc': 1.15, 'rf': 1.4,  'exp': 0.75},
        'scientist':{'rc': 0.8,  'rf': 1.25, 'exp': 1.5},
    }.get(user_class, {'rc': 1.0, 'rf': 1.0, 'exp': 1.0})


def _roll_junk():
    """Случайный хлам."""
    from economy_system import get_items_by_category
    junk_items = get_items_by_category('junk')
    if not junk_items:
        return []
    count = random.randint(1, 3)
    chosen = random.sample(list(junk_items.values()), min(count, len(junk_items)))
    return [{'id': it.get('id'), 'name': it.get('name')} for it in chosen]


# ==================== ОХОТА ====================

def do_hunt(player_id):
    """Охота. Найти мутанта или NPC, решить исход."""
    players = get_players_session()
    world = get_world_session()
    try:
        player = players.query(Player).filter_by(id=player_id).first()
        if not player:
            return {'ok': False, 'message': 'Игрок не найден'}

        if player.level < 2:
            return {'ok': False, 'message': 'Охота доступна со 2 уровня'}

        if player.user_class == 'scientist':
            return {'ok': False, 'message': 'Учёные не охотятся'}

        now = datetime.now()
        cooldown = timedelta(hours=6)
        if player.cooldown_reducer_until and player.cooldown_reducer_until > now:
            cooldown = timedelta(hours=3)
        if player.pet == 'кайот':
            cooldown = cooldown // 2

        if player.last_hunt and now - player.last_hunt < cooldown:
            remaining = cooldown - (now - player.last_hunt)
            h = remaining.seconds // 3600
            m = (remaining.seconds % 3600) // 60
            return {'ok': False, 'message': f'Охота через {h}ч {m}мин'}

        # Тип цели
        encounter_type = random.choice(['mutant', 'mutant', 'npc'])

        if encounter_type == 'mutant':
            result = _hunt_mutant(player)
        else:
            result = _hunt_npc(player, world)

        player.last_hunt = now
        safe_log(player, 'hunt', item=result.get('target_name', ''))
        players.commit()
        return result
    except Exception as e:
        logger.error(f"Ошибка охоты: {e}")
        players.rollback()
        return {'ok': False, 'message': str(e)}
    finally:
        players.close()
        world.close()


def _hunt_mutant(player):
    """Охота на мутанта."""
    tier = random.choices([1, 2, 3, 4], weights=[50, 30, 15, 5])[0]

    targets = {
        1: ('Мутант 1 уровня', 30, 15, 10, 5),
        2: ('Мутант 2 уровня', 50, 25, 25, 15),
        3: ('Мутант 3 уровня', 80, 40, 60, 40),
        4: ('👑 БОСС ПУСТОШИ', 150, 70, 200, 100),
    }
    name, hp, dmg, rf, exp = targets[tier]

    survive = calculate_survive_chance(player, tier)
    survived = random.random() * 100 < survive

    if survived:
        player.radfragments += rf
        player.mutants_killed = (player.mutants_killed or 0) + 1
        if tier == 4:
            player.bosses_killed = (player.bosses_killed or 0) + 1

        level_up = check_level_up(player, exp)

        return {
            'ok': True, 'target_type': 'mutant', 'target_name': name,
            'target_tier': tier, 'survived': True, 'died': False,
            'rf': rf, 'exp': exp, 'level_up': level_up,
        }
    else:
        # Попытка спастись аптечкой
        medkits = get_item_count(player, 'аптечка')
        if medkits > 0:
            remove_item_from_inventory(player, 'аптечка', 1)
            if random.random() * 100 < survive:
                return {
                    'ok': True, 'target_type': 'mutant', 'target_name': name,
                    'target_tier': tier, 'survived': True, 'died': False,
                    'rf': rf // 2, 'exp': exp // 2, 'level_up': False,
                    'medkit_saved': True,
                }

        _player_died(player)
        return {
            'ok': True, 'target_type': 'mutant', 'target_name': name,
            'target_tier': tier, 'survived': False, 'died': True,
            'rf': 0, 'exp': 0,
        }


def _hunt_npc(player, world):
    """Охота на NPC (враждебной фракции)."""
    # Выбор фракции-цели
    player_faction = player.faction_id

    # Все фракции, кроме фракции игрока
    all_factions = ['volya', 'zavet', 'wagner', 'roman', 'iskhod', 'orda', 'bratva']
    possible = [f for f in all_factions if f != player_faction]

    if not possible:
        return {'ok': False, 'message': 'Некого искать'}

    # Приоритет — врагам игрока
    rep_map = json.loads(player.faction_rep or '{}')
    weights = []
    for f in possible:
        rep = rep_map.get(f, 0)
        if rep <= -50:
            weights.append(10)
        elif rep <= -20:
            weights.append(5)
        else:
            weights.append(1)

    target_faction = random.choices(possible, weights=weights)[0]

    # Найти живого NPC этой фракции
    npc = world.query(NPC).filter_by(
        faction_id=target_faction, is_alive=True
    ).first()

    if not npc:
        return {'ok': False, 'message': 'Нет подходящей цели'}

    tier = 1 if npc.rank in ('rookie', 'private', 'errand', 'novice',
                             'student', 'warrior', 'courier') else 2

    survive = calculate_survive_chance(player, tier)
    survived = random.random() * 100 < survive

    if survived:
        npc.is_alive = False
        npc.death_date = datetime.now()
        npc.death_reason = f"Убит игроком {player.username}"

        rf = random.randint(10, 30) * tier
        exp = random.randint(20, 50) * tier

        player.radfragments += rf
        player.npcs_killed = (player.npcs_killed or 0) + 1
        player.mutants_killed = (player.mutants_killed or 0) + 1

        # Репутация падает
        change_player_rep(player, target_faction, -15)

        level_up = check_level_up(player, exp)
        world.commit()

        faction_name = world.query(Faction).filter_by(id=target_faction).first()
        faction_name = faction_name.name if faction_name else target_faction

        return {
            'ok': True, 'target_type': 'npc', 'target_name': f"{npc.name} ({faction_name})",
            'target_tier': tier, 'survived': True, 'died': False,
            'rf': rf, 'exp': exp, 'level_up': level_up,
            'faction_id': target_faction,
        }
    else:
        medkits = get_item_count(player, 'аптечка')
        if medkits > 0:
            remove_item_from_inventory(player, 'аптечка', 1)
            if random.random() * 100 < survive:
                return {
                    'ok': True, 'target_type': 'npc', 'target_name': npc.name,
                    'target_tier': tier, 'survived': True, 'died': False,
                    'rf': 5, 'exp': 10, 'level_up': False,
                    'medkit_saved': True,
                }

        _player_died(player)
        return {
            'ok': True, 'target_type': 'npc', 'target_name': npc.name,
            'target_tier': tier, 'survived': False, 'died': True,
            'rf': 0, 'exp': 0,
        }


def _player_died(player):
    """Игрок погиб. Штрафы."""
    lost_rc = int(player.radcoins * 0.15)
    player.radcoins -= lost_rc
    player.deaths = (player.deaths or 0) + 1

    eq = get_equipped(player)
    if eq.get('armor') and random.random() < 0.4:
        eq['armor'] = None
    if eq.get('weapon') and random.random() < 0.4:
        eq['weapon'] = None
    save_equipped(player, eq)

    safe_log(player, 'death', rc=-lost_rc)


# ==================== ПЕРЕМЕЩЕНИЕ ====================

def can_travel(player_id, to_location_id):
    """Можно ли игроку перейти в локацию."""
    players = get_players_session()
    world = get_world_session()
    try:
        player = players.query(Player).filter_by(id=player_id).first()
        if not player:
            return {'ok': False, 'message': 'Игрок не найден'}

        from_id = player.current_location
        from_loc = world.query(Location).filter_by(id=from_id).first()
        if not from_loc:
            return {'ok': False, 'message': 'Текущая локация не найдена'}

        connections = json.loads(from_loc.connections or '[]')
        if to_location_id not in connections:
            return {'ok': False, 'message': 'Нет пути в эту локацию'}

        to_loc = world.query(Location).filter_by(id=to_location_id).first()
        if not to_loc:
            return {'ok': False, 'message': 'Локация не найдена'}

        # Проверка враждебной территории
        if to_loc.controller_faction_id:
            rep = get_player_rep(player, to_loc.controller_faction_id)
            if rep <= -50:
                controller = world.query(Faction).filter_by(
                    id=to_loc.controller_faction_id
                ).first()
                name = controller.name if controller else to_loc.controller_faction_id
                return {'ok': False,
                        'message': f'{name} не пустит вас (репутация {rep})'}

        return {
            'ok': True,
            'from_loc': from_loc,
            'to_loc': to_loc,
            'travel_min': TRAVEL_TIME_PER_HOP,
        }
    finally:
        players.close()
        world.close()


def do_travel(player_id, to_location_id):
    """Перейти в другую локацию."""
    check = can_travel(player_id, to_location_id)
    if not check['ok']:
        return check

    players = get_players_session()
    world = get_world_session()
    try:
        player = players.query(Player).filter_by(id=player_id).first()
        player.current_location = to_location_id

        # История
        history = json.loads(player.location_history or '[]')
        history.append(to_location_id)
        player.location_history = json.dumps(history[-20:])

        to_loc = check['to_loc']
        safe_log(player, 'travel', item=to_location_id)
        players.commit()

        return {
            'ok': True,
            'message': f'Вы прибыли в {to_loc.name}',
            'location': {
                'id': to_loc.id,
                'name': to_loc.name,
                'type': to_loc.type,
                'desc': to_loc.desc,
                'controller': to_loc.controller_faction_id,
                'has_trader': to_loc.has_trader,
                'has_business': to_loc.has_business,
                'has_shops': to_loc.has_shops,
            }
        }
    except Exception as e:
        logger.error(f"Ошибка перемещения: {e}")
        players.rollback()
        return {'ok': False, 'message': str(e)}
    finally:
        players.close()
        world.close()


def get_available_travels(player_id):
    """Куда можно перейти из текущей локации."""
    players = get_players_session()
    world = get_world_session()
    try:
        player = players.query(Player).filter_by(id=player_id).first()
        if not player:
            return []

        from_loc = world.query(Location).filter_by(
            id=player.current_location
        ).first()
        if not from_loc:
            return []

        connections = json.loads(from_loc.connections or '[]')
        result = []
        for loc_id in connections:
            loc = world.query(Location).filter_by(id=loc_id).first()
            if not loc:
                continue

            can_enter = True
            reason = ''
            if loc.controller_faction_id:
                rep = get_player_rep(player, loc.controller_faction_id)
                if rep <= -50:
                    can_enter = False
                    controller = world.query(Faction).filter_by(
                        id=loc.controller_faction_id
                    ).first()
                    reason = f"{controller.name if controller else loc.controller_faction_id} не пустит"

            result.append({
                'id': loc.id,
                'name': loc.name,
                'type': loc.type,
                'desc': loc.desc,
                'controller': loc.controller_faction_id,
                'can_enter': can_enter,
                'reason': reason,
            })
        return result
    finally:
        players.close()
        world.close()


# ==================== ВЫЛАЗКА ====================

def start_expedition(player_id):
    """Начать вылазку в текущей локации."""
    players = get_players_session()
    world = get_world_session()
    try:
        player = players.query(Player).filter_by(id=player_id).first()
        if not player:
            return {'ok': False, 'message': 'Игрок не найден'}

        loc = world.query(Location).filter_by(id=player.current_location).first()
        loc_name = loc.name if loc else 'Пустошь'
        danger_base = loc.danger_bonus if loc else 0

        state = {
            'visited': 0,
            'max_events': random.randint(4, 9),
            'log': [],
            'alive': True,
            'total_rc': 0,
            'total_rf': 0,
            'total_exp': 0,
            'total_items': [],
            'danger': danger_base,
            'current_event': None,
            'location': player.current_location,
            'location_name': loc_name,
        }
        return {'ok': True, 'state': state}
    finally:
        players.close()
        world.close()


def expedition_next_event(player_id, state):
    """Получить следующее событие вылазки."""
    events = ['ruins', 'cache', 'mutant_weak', 'trap', 'anomaly',
              'corpse', 'radiation', 'safe_house', 'junk_pile', 'old_car']
    chosen = random.choice(events)
    event = _get_expedition_event(chosen)
    return event


def _get_expedition_event(event_key):
    """Данные события вылазки."""
    EVENTS = {
        'ruins': {
            'id': 'ruins', 'title': '🏚️ РУИНЫ',
            'desc': 'Разрушенное здание. Что-то блестит в глубине.',
            'choices': [
                {'text': '🔦 Войти', 'action': 'ruins_enter'},
                {'text': '👣 Обойти', 'action': 'skip'},
            ],
        },
        'cache': {
            'id': 'cache', 'title': '📦 ТАЙНИК',
            'desc': 'Под обломками небольшой тайник.',
            'choices': [
                {'text': '🔓 Вскрыть', 'action': 'cache_open'},
                {'text': '👣 Мимо', 'action': 'skip'},
            ],
        },
        'mutant_weak': {
            'id': 'mutant_weak', 'title': '🧬 МУТАНТ',
            'desc': 'Существо не заметило вас.',
            'choices': [
                {'text': '⚔️ Атаковать', 'action': 'mutant_attack'},
                {'text': '🤫 Спрятаться', 'action': 'skip'},
            ],
        },
        'trap': {
            'id': 'trap', 'title': '⚠️ ЛОВУШКА',
            'desc': 'Подозрительная растяжка.',
            'choices': [
                {'text': '🔍 Обезвредить', 'action': 'trap_defuse'},
                {'text': '👣 Обойти', 'action': 'skip'},
            ],
        },
        'anomaly': {
            'id': 'anomaly', 'title': '✨ АНОМАЛИЯ',
            'desc': 'Воздух дрожит.',
            'choices': [
                {'text': '🔬 Исследовать', 'action': 'anomaly_study'},
                {'text': '👣 Обойти', 'action': 'skip'},
            ],
        },
        'corpse': {
            'id': 'corpse', 'title': '💀 ТРУП',
            'desc': 'Тело сталкера.',
            'choices': [
                {'text': '🎒 Обыскать', 'action': 'corpse_loot'},
                {'text': '👣 Уйти', 'action': 'skip'},
            ],
        },
        'radiation': {
            'id': 'radiation', 'title': '☢️ РАДИАЦИЯ',
            'desc': 'Счётчик трещит.',
            'choices': [
                {'text': '💊 Пройти', 'action': 'radiation_cross'},
                {'text': '👣 Обойти', 'action': 'skip'},
            ],
        },
        'safe_house': {
            'id': 'safe_house', 'title': '🏠 УБЕЖИЩЕ',
            'desc': 'Можно передохнуть.',
            'choices': [
                {'text': '😴 Отдохнуть', 'action': 'rest'},
                {'text': '👣 Дальше', 'action': 'skip'},
            ],
        },
        'junk_pile': {
            'id': 'junk_pile', 'title': '🗑️ ХЛАМ',
            'desc': 'Куча мусора. Вдруг что-то ценное?',
            'choices': [
                {'text': '🔍 Разгрести', 'action': 'junk_pile'},
                {'text': '👣 Мимо', 'action': 'skip'},
            ],
        },
        'old_car': {
            'id': 'old_car', 'title': '🚗 МАШИНА',
            'desc': 'Ржавый автомобиль. Багажник закрыт.',
            'choices': [
                {'text': '🔓 Открыть', 'action': 'old_car'},
                {'text': '👣 Мимо', 'action': 'skip'},
            ],
        },
    }
    return EVENTS.get(event_key, EVENTS['ruins'])


def expedition_choice(player_id, state, action):
    """Обработать выбор в событии вылазки."""
    players = get_players_session()
    try:
        player = players.query(Player).filter_by(id=player_id).first()
        if not player:
            return {'ok': False, 'message': 'Игрок не найден'}

        state['visited'] += 1
        state['current_event'] = None

        if action == 'skip':
            state['log'].append('👣 Прошли мимо.')

        elif action == 'ruins_enter':
            if random.random() < 0.6:
                rc = random.randint(50, 200)
                state['total_rc'] += rc
                state['log'].append(f'🏚️ Найдено {rc} RC')
            else:
                state['danger'] += random.randint(10, 30)
                state['log'].append('🏚️ Обвал!')

        elif action == 'cache_open':
            if random.random() < 0.7:
                rc = random.randint(100, 400)
                state['total_rc'] += rc
                state['log'].append(f'📦 Найдено {rc} RC')
            else:
                state['log'].append('📦 Пусто.')

        elif action == 'mutant_attack':
            if random.random() < 0.75:
                rf = random.randint(3, 15)
                state['total_rf'] += rf
                state['log'].append(f'⚔️ Победа! +{rf} RF')
            else:
                state['danger'] += random.randint(15, 35)
                state['log'].append('⚔️ Ранение!')

        elif action == 'trap_defuse':
            if random.random() < 0.55:
                rc = random.randint(50, 150)
                state['total_rc'] += rc
                state['log'].append(f'🔍 +{rc} RC')
            else:
                state['danger'] += random.randint(20, 45)
                state['log'].append('💥 Ловушка сработала!')

        elif action == 'anomaly_study':
            if random.random() < 0.4:
                rf = random.randint(30, 80)
                state['total_rf'] += rf
                state['log'].append(f'✨ +{rf} RF')
            else:
                state['danger'] += random.randint(25, 60)
                state['log'].append('☢️ Аномалия обожгла!')

        elif action == 'corpse_loot':
            if random.random() < 0.65:
                rc = random.randint(50, 300)
                state['total_rc'] += rc
                state['log'].append(f'💀 +{rc} RC')
            else:
                state['log'].append('💀 Пусто.')

        elif action == 'radiation_cross':
            state['danger'] += random.randint(15, 35)
            rf = random.randint(10, 30)
            state['total_rf'] += rf
            state['log'].append(f'☢️ +{rf} RF, опасно!')

        elif action == 'rest':
            heal = random.randint(15, 35)
            state['danger'] = max(0, state['danger'] - heal)
            state['log'].append(f'😴 Отдых, -{heal}% опасности')

        elif action == 'junk_pile':
            junk = _roll_junk()
            for j in junk:
                add_item_to_inventory(player, j['id'], 1)
                state['total_items'].append(j['name'])
            state['log'].append(f'🗑️ Найдено {len(junk)} шт хлама')

        elif action == 'old_car':
            if random.random() < 0.5:
                junk = _roll_junk()
                for j in junk:
                    add_item_to_inventory(player, j['id'], 1)
                    state['total_items'].append(j['name'])
                state['log'].append(f'🚗 +{len(junk)} хлама')
            else:
                state['danger'] += random.randint(5, 15)
                state['log'].append('🚗 Сигнализация!')

        # Проверка смерти
        if state['danger'] >= 100:
            state['alive'] = False
            _player_died(player)
            players.commit()
            return {'ok': True, 'state': state, 'died': True}

        if state['visited'] >= state['max_events']:
            # Финал
            player.radcoins += state['total_rc']
            player.radfragments += state['total_rf']
            check_level_up(player, state['total_exp'])
            players.commit()
            return {'ok': True, 'state': state, 'ended': True}

        players.commit()
        return {'ok': True, 'state': state, 'continue': True}

    except Exception as e:
        logger.error(f"Ошибка события вылазки: {e}")
        players.rollback()
        return {'ok': False, 'message': str(e)}
    finally:
        players.close()