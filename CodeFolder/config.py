# config.py - Rad Earth
# Версия: 1.0.0
# Фундамент. Все пути, константы, базовые настройки.

import os
import logging


# ==================== ИНФОРМАЦИЯ ИГРЫ ====================

GAME_NAME = "Rad Earth"
GAME_VERSION = "1.0.0"
GAME_SUBTITLE = "Симуляция Пустоши"


# ==================== ПУТИ ====================

# Корень проекта — на 2 уровня выше этого файла
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CODE_DIR = os.path.join(ROOT_DIR, 'CodeFolder')
JSON_DIR = os.path.join(ROOT_DIR, 'JsonFolder')
DB_DIR = os.path.join(ROOT_DIR, 'DatabaseFolder')
BACKUP_DIR = os.path.join(DB_DIR, 'backups')

# Подпапки JsonFolder
JSON_FACTIONS = os.path.join(JSON_DIR, 'factions')
JSON_FACTIONS_MINOR = os.path.join(JSON_FACTIONS, 'minor')
JSON_LOCATIONS = os.path.join(JSON_DIR, 'locations')
JSON_NPCS = os.path.join(JSON_DIR, 'npcs')
JSON_NPCS_NAMED = os.path.join(JSON_NPCS, 'named')
JSON_NPCS_TEMPLATES = os.path.join(JSON_NPCS, 'templates')
JSON_RADIO = os.path.join(JSON_DIR, 'radio')
JSON_WEATHER = os.path.join(JSON_DIR, 'weather')
JSON_ITEMS = os.path.join(JSON_DIR, 'items')
JSON_ECONOMY = os.path.join(JSON_DIR, 'economy')

# Файлы баз данных
PLAYERS_DB = os.path.join(DB_DIR, 'players.db')
WORLD_DB = os.path.join(DB_DIR, 'world.db')

# Создаём папки, если их нет
for _p in [CODE_DIR, JSON_DIR, DB_DIR, BACKUP_DIR,
           JSON_FACTIONS, JSON_FACTIONS_MINOR, JSON_LOCATIONS,
           JSON_NPCS, JSON_NPCS_NAMED, JSON_NPCS_TEMPLATES,
           JSON_RADIO, JSON_WEATHER, JSON_ITEMS, JSON_ECONOMY]:
    os.makedirs(_p, exist_ok=True)


# ==================== НАСТРОЙКИ ИГРОКА ====================

START_RADCOINS = 1000
START_RADFRAGMENTS = 0
START_RADCRYSTALS = 0
START_LEVEL = 1
START_EXPERIENCE = 0
START_LOCATION = 'crossroads'  # Перекрёсток — нейтральная стартовая точка

MAX_LEVEL = 100
MAX_INVENTORY_STACK = 999


# ==================== НАСТРОЙКИ МИРА ====================

# Тик мира — раз в сколько секунд симуляция «думает»
WORLD_TICK_SECONDS = 60          # Каждую минуту
WORLD_TICK_AGGRESSIVE = 5        # Быстрый тик для отладки

# Радио — как часто ведущий выдаёт новую фразу
RADIO_SPEAK_MIN = 5
RADIO_SPEAK_MAX = 10

# Радио — размер истории эфира
RADIO_HISTORY_SIZE = 50

# Погода — как часто меняется (в минутах)
WEATHER_CHANGE_MIN_MINUTES = 30
WEATHER_CHANGE_MAX_MINUTES = 120

# Сколько времени NPC живёт «по умолчанию», если не убит
NPC_AVG_LIFESPAN_DAYS = 30


# ==================== ЭКОНОМИКА ====================

# Репутация
REP_MIN = -100
REP_MAX = 100
REP_WAR_THRESHOLD = -50         # Ниже — фракция считает игрока врагом
REP_ALLY_THRESHOLD = 50         # Выше — союзник
REP_FRIEND_THRESHOLD = 20       # Выше — друг

# Модификаторы цен по репутации (множитель к базовой цене покупки)
REP_PRICE_MODIFIERS = [
    (-100, -50, 2.5),   # Враг — грабёж
    (-50, -20, 1.5),    # Недруг — завышено
    (-20, 20, 1.0),     # Нейтрал — обычно
    (20, 50, 0.85),     # Друг — скидка
    (50, 100, 0.7),     # Союзник — дёшево
]

# Модификаторы цен продажи (множитель к базовой цене продажи)
REP_SELL_MODIFIERS = [
    (-100, -50, 0.5),
    (-50, -20, 0.7),
    (-20, 20, 1.0),
    (20, 50, 1.15),
    (50, 100, 1.3),
]


# ==================== ФРАКЦИИ ====================

# 7 крупных фракций
MAJOR_FACTIONS = [
    'volya',
    'zavet',
    'wagner',
    'roman',
    'iskhod',
    'orda',
    'bratva',
]

# Стартовые численности (будут переопределены из JSON при загрузке мира)
FACTION_START_STRENGTH = {
    'volya': 700,
    'zavet': 500,
    'wagner': 400,
    'roman': 450,
    'iskhod': 400,
    'orda': 740,
    'bratva': 800,
}

# Цвета фракций (для UI)
FACTION_COLORS = {
    'volya': '#5fff8f',
    'zavet': '#66ccff',
    'wagner': '#ffaa44',
    'roman': '#ff5577',
    'iskhod': '#cc88ff',
    'orda': '#ffee66',
    'bratva': '#ff8844',
    'neutral': '#aaaaaa',
    'player': '#00ff88',
}


# ==================== ФЕОДАЛЬНАЯ ЛЕСТНИЦА ====================

# У каждой фракции своя структура. Ключи — роли, значения — «вес» (важность).
# Используется в faction_engine для продвижения NPC и для UI.
FACTION_RANKS = {
    'volya': {
        'leader': 'Лидер',
        'advisor': 'Советник',
        'veteran': 'Ветеран',
        'stalker': 'Сталкер',
        'rookie': 'Новичок',
    },
    'zavet': {
        'prophet': 'Пророк',
        'bishop': 'Епископ',
        'priest': 'Священник',
        'novice': 'Послушник',
        'believer': 'Верующий',
    },
    'wagner': {
        'general': 'Генерал',
        'colonel': 'Полковник',
        'captain': 'Капитан',
        'sergeant': 'Сержант',
        'private': 'Рядовой',
    },
    'roman': {
        'king': 'Король',
        'brigadier': 'Бригадир',
        'authority': 'Авторитет',
        'fighter': 'Боец',
        'errand': 'Шестёрка',
    },
    'iskhod': {
        'director': 'Директор',
        'council': 'Научный советник',
        'scientist': 'Учёный',
        'lab_assistant': 'Лаборант',
        'student': 'Аспирант',
    },
    'orda': {
        'khan': 'Хан',
        'noyon': 'Нойон',
        'tysyachnik': 'Тысячник',
        'sotnik': 'Сотник',
        'warrior': 'Воин',
    },
    'bratva': {
        'don': 'Дон',
        'capo': 'Капо',
        'desyatnik': 'Десятник',
        'trader': 'Торговец',
        'courier': 'Курьер',
    },
}


# ==================== ГЕНЕРАЦИЯ NPC ====================

# Шаблоны имён (используются npc_engine для генерации)
NPC_NAMES_MALE = [
    "Волк", "Клык", "Барс", "Штырь", "Кобра", "Гром", "Тень", "Дым",
    "Кремень", "Ржавый", "Немой", "Пепел", "Крюк", "Уголь", "Сажа",
    "Гвоздь", "Тихий", "Косой", "Хромой", "Пилот", "Дизель", "Бензин",
    "Гайка", "Винт", "Якорь", "Штурман", "Кабан", "Медведь", "Тур",
    "Филин", "Ворон", "Орел", "Сокол", "Ястреб", "Коршун", "Стриж",
]

NPC_NAMES_FEMALE = [
    "Заря", "Искра", "Пламя", "Вьюга", "Метель", "Зима", "Осень", "Весна",
    "Ласточка", "Синица", "Сова", "Лиса", "Тайга", "Роса", "Капля",
    "Смола", "Хвоя", "Сосна", "Береза", "Ночь", "Луна", "Звезда",
    "Комета", "Туча", "Молния", "Гроза",
]

# Позывные (уникальный идентификатор NPC)
NPC_CALLSIGNS = [
    "Призрак", "Циклоп", "Пуля", "Дробь", "Клеймо", "Шрам", "Мишень",
    "Осколок", "Молчун", "Сон", "Мор", "Глюк", "Байт", "Вирус", "Лом",
    "Хвост", "Уголек", "Ремонтник", "Сварщик", "Токарь", "Столяр",
    "Часовой", "Дозор", "Скиталец", "Пилигрим", "Отшельник", "Мышь",
]


# ==================== ЛОКАЦИИ ====================

# 16 стартовых локаций (заполняются из JSON)
LOCATIONS_LIST = [
    'crossroads', 'volya_city', 'zavet_city', 'wagner_base',
    'roman_city', 'iskhod_lab', 'orda_base', 'bratva_hub',
    'dead_city', 'old_village', 'dark_forest', 'poison_swamp',
    'north_mountains', 'anomaly_zone', 'metro_ruins', 'sewers',
]


# ==================== СОБЫТИЯ МИРА ====================

# Веса для событий, которые происходят в мире каждый тик
WORLD_EVENT_WEIGHTS = {
    'skirmish': 30,      # Стычка между фракциями
    'mutant_attack': 20, # Нападение мутантов на локацию
    'npc_death': 15,     # Смерть NPC (естественная или в бою)
    'trade': 10,         # Торговая сделка
    'weather_shift': 10, # Резкая смена погоды
    'festival': 3,       # Праздник в поселении
    'betrayal': 2,       # Предательство внутри фракции
    'discovery': 5,      # Открытие (учёные нашли что-то)
    'rumor': 5,          # Слух
}


# ==================== СИСТЕМА ПУТЕШЕСТВИЙ ====================

# Сколько времени занимает переход между локациями (в секундах реального времени)
TRAVEL_TIME_PER_HOP = 30

# Максимальное количество переходов без отдыха (иначе усталость)
MAX_HOPS_WITHOUT_REST = 5

# Урон от усталости за каждый лишний переход (к «опасности»)
FATIGUE_DAMAGE_PER_HOP = 5


# ==================== РАЗНОЕ ====================

# Форматы дат
DATE_FORMAT = "%Y-%m-%d"
DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"

# Случайное зерно (None = не фиксировано)
RANDOM_SEED = None

# Отладка
DEBUG = True
VERBOSE = True


# ==================== ЛОГГЕР ====================

LOG_FILE = os.path.join(ROOT_DIR, 'rad_earth.log')

logging.basicConfig(
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    level=logging.DEBUG if DEBUG else logging.INFO,
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler(),
    ]
)

logger = logging.getLogger('rad_earth')


# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

def get_faction_rank_name(faction_id, rank_key):
    """Человеческое название ранга."""
    ranks = FACTION_RANKS.get(faction_id, {})
    return ranks.get(rank_key, rank_key)


def get_faction_color(faction_id):
    """Цвет фракции."""
    return FACTION_COLORS.get(faction_id, FACTION_COLORS['neutral'])


def get_rep_tier(rep):
    """Категория репутации по числу."""
    if rep <= REP_WAR_THRESHOLD:
        return 'war', 'Враг'
    if rep <= -20:
        return 'unfriendly', 'Недруг'
    if rep < REP_FRIEND_THRESHOLD:
        return 'neutral', 'Нейтрал'
    if rep < REP_ALLY_THRESHOLD:
        return 'friendly', 'Друг'
    return 'ally', 'Союзник'


def get_rep_price_modifier(rep):
    """Множитель цены покупки от репутации."""
    for lo, hi, mult in REP_PRICE_MODIFIERS:
        if lo <= rep < hi:
            return mult
    return 1.0


def get_rep_sell_modifier(rep):
    """Множитель цены продажи от репутации."""
    for lo, hi, mult in REP_SELL_MODIFIERS:
        if lo <= rep < hi:
            return mult
    return 1.0


def clamp(value, min_value, max_value):
    """Ограничить значение диапазоном."""
    return max(min_value, min(value, max_value))