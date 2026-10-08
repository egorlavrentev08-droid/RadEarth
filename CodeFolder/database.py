# database.py - Rad Earth
# Версия: 1.0.0
# SQLAlchemy-модели. Две базы: players.db (игроки) и world.db (мир).

from datetime import datetime
from sqlalchemy import (
    create_engine, Column, Integer, String, Float, DateTime,
    Boolean, ForeignKey, Text, Index,
)
from sqlalchemy.orm import declarative_base, sessionmaker, scoped_session, relationship

from config import PLAYERS_DB, WORLD_DB, logger


# ==================== БАЗЫ ====================

PlayersBase = declarative_base()
WorldBase = declarative_base()

players_engine = create_engine(f'sqlite:///{PLAYERS_DB}',
                                pool_size=10, max_overflow=20,
                                connect_args={'check_same_thread': False})
world_engine = create_engine(f'sqlite:///{WORLD_DB}',
                              pool_size=10, max_overflow=20,
                              connect_args={'check_same_thread': False})

PlayersSession = scoped_session(sessionmaker(bind=players_engine, expire_on_commit=False))
WorldSession = scoped_session(sessionmaker(bind=world_engine, expire_on_commit=False))


# ============================================================================
#                              PLAYERS.DB
# ============================================================================

class Player(PlayersBase):
    """Игрок. Один файл players.db может содержать много игроков
    (если позже сделаем мультиплеер). Пока — один."""
    __tablename__ = 'players'

    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)

    # Ресурсы
    radcoins = Column(Float, default=0)
    radfragments = Column(Integer, default=0)
    radcrystals = Column(Integer, default=0)

    # Прогресс
    level = Column(Integer, default=1)
    experience = Column(Integer, default=0)

    # Фракция игрока
    faction_id = Column(String, nullable=True)          # К какой фракции присоединился
    faction_rank = Column(String, nullable=True)        # Его ранг в этой фракции
    faction_rep = Column(Text, default='{}')            # JSON: {faction_id: rep}
    faction_rep_values = Column(Text, default='{}')     # Кэш для быстрого доступа

    # Локация
    current_location = Column(String, default='crossroads')
    location_history = Column(Text, default='[]')       # JSON: список последних локаций

    # Инвентарь
    inventory = Column(Text, default='[]')              # JSON: [{item, count, ...}]
    equipped = Column(Text, default='{}')               # JSON: {armor, weapon, ...}

    # Эффекты
    energy_drink_until = Column(DateTime, nullable=True)
    energy_drink_level = Column(String, default='strike')
    energy_drink_stacks = Column(Integer, default=0)

    cooldown_reducer_until = Column(DateTime, nullable=True)
    reducer_level = Column(String, default='basic')
    reducer_stacks = Column(Integer, default=0)

    # Кулдауны
    last_collection = Column(DateTime, nullable=True)
    next_collection_time = Column(DateTime, nullable=True)
    last_hunt = Column(DateTime, nullable=True)
    last_travel = Column(DateTime, nullable=True)

    # Класс
    user_class = Column(String, default='stalker')
    last_free_class_change = Column(DateTime, nullable=True)

    # Питомец
    pet = Column(String, nullable=True)

    # Статистика
    total_collects = Column(Integer, default=0)
    total_rc_earned = Column(Float, default=0)
    best_collect = Column(Float, default=0)
    mutants_killed = Column(Integer, default=0)
    bosses_killed = Column(Integer, default=0)
    npcs_killed = Column(Integer, default=0)
    npcs_helped = Column(Integer, default=0)
    deaths = Column(Integer, default=0)
    daily_streak = Column(Integer, default=0)
    last_collect_date = Column(DateTime, nullable=True)
    achievements = Column(Text, default='[]')

    # Сундуки
    chest_common = Column(Integer, default=0)
    chest_rare = Column(Integer, default=0)
    chest_epic = Column(Integer, default=0)
    chest_mythic = Column(Integer, default=0)
    chest_legendary = Column(Integer, default=0)

    # Прочее
    total_purchases = Column(Integer, default=0)
    last_seen = Column(DateTime, default=datetime.now)
    created_at = Column(DateTime, default=datetime.now)


class PlayerLog(PlayersBase):
    """Лог действий игрока."""
    __tablename__ = 'player_logs'

    id = Column(Integer, primary_key=True)
    player_id = Column(Integer, ForeignKey('players.id'), nullable=False)
    action = Column(String, nullable=False)
    amount_rc = Column(Float, default=0)
    amount_rf = Column(Integer, default=0)
    amount_crystals = Column(Integer, default=0)
    item = Column(String, nullable=True)
    details = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.now)

    __table_args__ = (
        Index('idx_player_logs_player', 'player_id'),
        Index('idx_player_logs_time', 'timestamp'),
    )


class PlayerRelation(PlayersBase):
    """Отношение игрока к конкретному NPC (память о встречах)."""
    __tablename__ = 'player_relations'

    id = Column(Integer, primary_key=True)
    player_id = Column(Integer, ForeignKey('players.id'), nullable=False)
    npc_id = Column(String, nullable=False)              # ID NPC из world.db
    attitude = Column(Integer, default=0)                # -100..100
    met_at = Column(DateTime, default=datetime.now)
    notes = Column(Text, nullable=True)

    __table_args__ = (
        Index('idx_relation_player_npc', 'player_id', 'npc_id', unique=True),
    )


# ============================================================================
#                              WORLD.DB
# ============================================================================

class Faction(WorldBase):
    """Фракция."""
    __tablename__ = 'factions'

    id = Column(String, primary_key=True)                # 'volya', 'wagner', ...
    name = Column(String, nullable=False)                # Человеческое название
    type = Column(String, nullable=False)                # stalker / military / bandit / scientist / mixed
    desc = Column(Text, default='')
    color = Column(String, default='#aaaaaa')

    # Правитель и ключевые фигуры (ссылки на NPC.id)
    leader_id = Column(String, nullable=True)
    advisor_id = Column(String, nullable=True)

    # Ресурсы фракции
    treasury_coins = Column(Float, default=0)
    treasury_fragments = Column(Integer, default=0)
    treasury_crystals = Column(Integer, default=0)

    # Численность (агрегированно)
    population_total = Column(Integer, default=0)
    population_alive = Column(Integer, default=0)
    population_wounded = Column(Integer, default=0)

    # Боевая мощь (усреднённая)
    military_strength = Column(Integer, default=100)     # 0..1000
    discipline = Column(Integer, default=50)             # 0..100
    morale = Column(Integer, default=50)                 # 0..100

    # Статус
    is_at_war = Column(Text, default='[]')               # JSON: [faction_id, ...]
    is_ally = Column(Text, default='[]')                 # JSON: [faction_id, ...]
    is_neutral = Column(Text, default='[]')              # JSON

    # Территории — ссылки на Location.id
    controlled_locations = Column(Text, default='[]')    # JSON: [loc_id, ...]

    # Метаданные
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now)


class NPC(WorldBase):
    """NPC. Ключевые и рядовые. Пока — все ключевые хранятся полностью.
    Рядовые — генерируются из шаблонов при загрузке, потом «сливаются» в статистику."""
    __tablename__ = 'npcs'

    id = Column(String, primary_key=True)                # Уникальный ID (например, 'volya_001')
    name = Column(String, nullable=False)                # Имя (например, 'Волк')
    callsign = Column(String, nullable=True)             # Позывной (уникальный идентификатор в фракции)
    gender = Column(String, default='male')              # male / female / other

    # Принадлежность
    faction_id = Column(String, ForeignKey('factions.id'), nullable=True)
    rank = Column(String, nullable=True)                 # Ключ ранга из config.FACTION_RANKS
    role = Column(String, nullable=True)                 # 'leader', 'advisor', 'trader', 'soldier', ...
    is_named = Column(Boolean, default=False)            # True — ключевой NPC с полной историей
    is_alive = Column(Boolean, default=True)
    is_blocked = Column(Boolean, default=False)

    # Характеристики
    loyalty = Column(Integer, default=50)                # 0..100
    aggression = Column(Integer, default=50)             # 0..100
    intelligence = Column(Integer, default=50)           # 0..100
    combat_skill = Column(Integer, default=50)           # 0..100

    # Здоровье
    hp_current = Column(Integer, default=100)
    hp_max = Column(Integer, default=100)

    # Экономика (если торговец)
    is_trader = Column(Boolean, default=False)
    trader_type = Column(String, nullable=True)          # 'weapons', 'junk', 'components', 'mixed'

    # Репутация с игроком (для ключевых — точная, для рядовых — усреднённая из отношения фракции)
    player_relationship = Column(Integer, default=0)     # -100..100

    # Текущее местоположение
    location_id = Column(String, ForeignKey('locations.id'), nullable=True)

    # Диалоги (ссылка на JSON-файл с репликами для ключевых NPC)
    dialog_file = Column(String, nullable=True)

    # Метаданные
    birth_date = Column(DateTime, default=datetime.now)
    death_date = Column(DateTime, nullable=True)
    death_reason = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now)

    __table_args__ = (
        Index('idx_npcs_faction', 'faction_id'),
        Index('idx_npcs_location', 'location_id'),
        Index('idx_npcs_alive', 'is_alive'),
    )


class Location(WorldBase):
    """Локация."""
    __tablename__ = 'locations'

    id = Column(String, primary_key=True)                # 'crossroads', 'volya_city', ...
    name = Column(String, nullable=False)
    type = Column(String, nullable=False)                # 'wild', 'city', 'lab', ...
    desc = Column(Text, default='')

    # Контроль
    controller_faction_id = Column(String, ForeignKey('factions.id'), nullable=True)

    # Характеристики добычи
    rc_mult = Column(Float, default=1.0)
    rf_mult = Column(Float, default=1.0)
    exp_mult = Column(Float, default=1.0)
    pet_mult = Column(Float, default=1.0)
    chest_mult = Column(Float, default=1.0)

    # Опасность
    danger_bonus = Column(Integer, default=0)
    encounter_chance = Column(Float, default=0.1)

    # Контент
    has_trader = Column(Boolean, default=False)
    has_business = Column(Boolean, default=False)
    has_shops = Column(Boolean, default=False)
    has_medbay = Column(Boolean, default=False)
    has_barracks = Column(Boolean, default=False)

    # Связи
    connections = Column(Text, default='[]')             # JSON: [loc_id, ...]

    # Метаданные
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now)


class WorldEvent(WorldBase):
    """Событие мира (для симуляции и радио)."""
    __tablename__ = 'world_events'

    id = Column(Integer, primary_key=True)
    event_type = Column(String, nullable=False)          # 'skirmish', 'npc_death', 'trade', ...
    location_id = Column(String, ForeignKey('locations.id'), nullable=True)
    faction_a = Column(String, ForeignKey('factions.id'), nullable=True)
    faction_b = Column(String, ForeignKey('factions.id'), nullable=True)
    npc_id = Column(String, ForeignKey('npcs.id'), nullable=True)
    details = Column(Text, nullable=True)                # JSON с доп. данными
    importance = Column(Integer, default=1)              # 1..10 — чем важнее, тем чаще в радио
    is_broadcasted = Column(Boolean, default=False)      # Уже прошло в радио?
    timestamp = Column(DateTime, default=datetime.now)

    __table_args__ = (
        Index('idx_events_time', 'timestamp'),
        Index('idx_events_type', 'event_type'),
        Index('idx_events_broadcast', 'is_broadcasted'),
    )


class RadioHost(WorldBase):
    """Радиоведущий."""
    __tablename__ = 'radio_hosts'

    id = Column(String, primary_key=True)                # 'host_main', 'host_military', ...
    name = Column(String, nullable=False)
    callsign = Column(String, nullable=True)
    faction_id = Column(String, ForeignKey('factions.id'), nullable=True)
    style = Column(String, default='neutral')            # 'neutral', 'military', 'bandit', 'scientist'
    bio = Column(Text, default='')
    is_active = Column(Boolean, default=True)


class Weather(WorldBase):
    """Текущее состояние погоды (одна запись)."""
    __tablename__ = 'weather'

    id = Column(Integer, primary_key=True)
    weather_type = Column(String, nullable=False)        # 'clear', 'storm', ...
    name = Column(String, nullable=False)                # '☀️ Ясно'
    description = Column(Text, default='')
    rc_mult = Column(Float, default=1.0)
    rf_mult = Column(Float, default=1.0)
    exp_mult = Column(Float, default=1.0)
    danger_add = Column(Integer, default=0)
    started_at = Column(DateTime, default=datetime.now)
    ends_at = Column(DateTime, nullable=True)


class FactionRelation(WorldBase):
    """Отношение между фракциями (дипломатия)."""
    __tablename__ = 'faction_relations'

    id = Column(Integer, primary_key=True)
    faction_a = Column(String, ForeignKey('factions.id'), nullable=False)
    faction_b = Column(String, ForeignKey('factions.id'), nullable=False)
    relation = Column(Integer, default=0)                # -100..100
    status = Column(String, default='neutral')           # 'war', 'neutral', 'ally'
    last_change = Column(DateTime, default=datetime.now)

    __table_args__ = (
        Index('idx_faction_rel_pair', 'faction_a', 'faction_b', unique=True),
    )


class War(WorldBase):
    """Активная война между фракциями."""
    __tablename__ = 'wars'

    id = Column(Integer, primary_key=True)
    faction_a = Column(String, ForeignKey('factions.id'), nullable=False)
    faction_b = Column(String, ForeignKey('factions.id'), nullable=False)
    started_at = Column(DateTime, default=datetime.now)
    ended_at = Column(DateTime, nullable=True)
    winner = Column(String, nullable=True)
    casualties_a = Column(Integer, default=0)
    casualties_b = Column(Integer, default=0)
    reason = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)


class TravelPath(WorldBase):
    """Кэш переходов между локациями (для быстрого доступа)."""
    __tablename__ = 'travel_paths'

    id = Column(Integer, primary_key=True)
    from_loc = Column(String, ForeignKey('locations.id'), nullable=False)
    to_loc = Column(String, ForeignKey('locations.id'), nullable=False)
    time_minutes = Column(Integer, default=30)
    danger = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)

    __table_args__ = (
        Index('idx_travel_pair', 'from_loc', 'to_loc', unique=True),
    )


# ==================== СОЗДАНИЕ ТАБЛИЦ ====================

def init_players_db():
    """Создать таблицы в players.db."""
    PlayersBase.metadata.create_all(players_engine)
    logger.info("✅ players.db инициализирована")


def init_world_db():
    """Создать таблицы в world.db."""
    WorldBase.metadata.create_all(world_engine)
    logger.info("✅ world.db инициализирована")


def init_all():
    """Создать всё."""
    init_players_db()
    init_world_db()


# ==================== УТИЛИТЫ СЕССИЙ ====================

def get_players_session():
    """Сессия игроков."""
    return PlayersSession()


def get_world_session():
    """Сессия мира."""
    return WorldSession()


def close_all():
    """Закрыть обе сессии."""
    try:
        PlayersSession.remove()
    except Exception:
        pass
    try:
        WorldSession.remove()
    except Exception:
        pass


# Автоинициализация при импорте
init_all()