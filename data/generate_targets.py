"""
generate_targets.py
-------------------
Generates synthetic spy-themed targets and appends them to targets.json,
filling the file up to 1000 total entries.

Run with:  python data/generate_targets.py

Only Python stdlib is used (random, json, datetime).
"""

import json
import random
from datetime import date, timedelta, datetime

# ---------------------------------------------------------------------------
# File path (relative to the project root; adjust if needed)
# ---------------------------------------------------------------------------
DATA_FILE = "data/targets.json"
TARGET_TOTAL = 1000


# ---------------------------------------------------------------------------
# World city pool  (name, lat, lon)
# Used for current_location and known_whereabouts.
# ---------------------------------------------------------------------------
CITIES = [
    ("Moscow, Russia",          55.7558,   37.6173),
    ("Paris, France",           48.8566,    2.3522),
    ("Berlin, Germany",         52.5200,   13.4050),
    ("London, UK",              51.5074,   -0.1278),
    ("Vienna, Austria",         48.2082,   16.3738),
    ("Geneva, Switzerland",     46.2044,    6.1432),
    ("Istanbul, Turkey",        41.0082,   28.9784),
    ("Beijing, China",          39.9042,  116.4074),
    ("Shanghai, China",         31.2304,  121.4737),
    ("Tokyo, Japan",            35.6762,  139.6503),
    ("Seoul, South Korea",      37.5665,  126.9780),
    ("Dubai, UAE",              25.2048,   55.2708),
    ("Tehran, Iran",            35.6892,   51.3890),
    ("New Delhi, India",        28.6139,   77.2090),
    ("Nairobi, Kenya",          -1.2921,   36.8219),
    ("Lagos, Nigeria",           6.5244,    3.3792),
    ("Buenos Aires, Argentina", -34.6037, -58.3816),
    ("São Paulo, Brazil",       -23.5505, -46.6333),
    ("Mexico City, Mexico",     19.4326,  -99.1332),
    ("Washington, DC, USA",     38.9072,  -77.0369),
    ("New York, USA",           40.7128,  -74.0060),
    ("Los Angeles, USA",        34.0522, -118.2437),
    ("Singapore, Singapore",     1.3521,  103.8198),
    ("Bangkok, Thailand",       13.7563,  100.5018),
    ("Kuala Lumpur, Malaysia",   3.1390,  101.6869),
    ("Cairo, Egypt",            30.0444,   31.2357),
    ("Johannesburg, South Africa", -26.2041, 28.0473),
    ("Kyiv, Ukraine",           50.4501,   30.5234),
    ("Warsaw, Poland",          52.2297,   21.0122),
    ("Bucharest, Romania",      44.4268,   26.1025),
    ("Beirut, Lebanon",         33.8938,   35.5018),
    ("Karachi, Pakistan",       24.8607,   67.0011),
    ("Jakarta, Indonesia",      -6.2088,  106.8456),
]


# ---------------------------------------------------------------------------
# Name pools for people  (first names grouped loosely by region)
# ---------------------------------------------------------------------------
FIRST_NAMES = [
    # Russian / Eastern European
    "Alexei", "Boris", "Dmitri", "Fyodor", "Grigori", "Igor", "Ivan", "Kirill",
    "Leonid", "Mikhail", "Nikolai", "Pavel", "Ruslan", "Sergei", "Vadim", "Yuri",
    "Anya", "Elena", "Irina", "Katya", "Larisa", "Marina", "Natasha", "Olga",
    "Polina", "Sonja", "Tatiana", "Vera", "Zoya",
    # Western European
    "Adrian", "Bastian", "Cedric", "Dominik", "Erik", "Florian", "Georg",
    "Heinrich", "Jakob", "Karl", "Leopold", "Lukas", "Markus", "Norbert",
    "Otto", "Rainer", "Stefan", "Thomas", "Ulrich", "Wolfgang",
    "Amélie", "Brigitte", "Claudette", "Danielle", "Élodie", "Françoise",
    "Geneviève", "Hélène", "Isabelle", "Joëlle", "Kristine", "Léa",
    "Madeleine", "Nicole", "Odile", "Raphaëlle", "Simone",
    # Middle Eastern / Central Asian
    "Adnan", "Bassam", "Faisal", "Hassan", "Karim", "Mahmoud", "Nasser",
    "Omar", "Qassem", "Rashid", "Salim", "Tariq", "Walid", "Youssef", "Ziad",
    "Aisha", "Fatima", "Layla", "Mariam", "Nadia", "Rania", "Safia", "Yasmin",
    # South / East Asian
    "Akira", "Daisuke", "Haruto", "Kenji", "Makoto", "Naoki", "Ryo", "Shota",
    "Takashi", "Yuki",
    "Bao", "Chen", "Da-Wei", "Fang", "Guang", "Hao", "Jian", "Kang",
    "Lei", "Ming", "Peng", "Qiang", "Rui", "Wei", "Xiao", "Yan", "Zhen",
    "Ananya", "Deepa", "Kavya", "Meera", "Priya", "Riya", "Shreya", "Swati",
    "Arjun", "Kiran", "Nikhil", "Rahul", "Rohit", "Suresh", "Vikram",
    # African
    "Amara", "Chidi", "Emeka", "Ifeanyi", "Jide", "Kofi", "Kwame", "Leke",
    "Musa", "Nnamdi", "Olu", "Segun", "Tunde", "Yemi",
    "Abena", "Afia", "Akua", "Ama", "Efua", "Korkor", "Mawuli",
    # Latin American
    "Alejandro", "Carlos", "Diego", "Eduardo", "Felipe", "Gonzalo", "Héctor",
    "Javier", "Luis", "Mateo", "Nicolás", "Pablo", "Ramiro", "Sebastián",
    "Adriana", "Camila", "Daniela", "Fernanda", "Gabriela", "Juliana",
    "Lorena", "Mariana", "Natalia", "Paola", "Rocío", "Valeria",
]

LAST_NAMES = [
    # Russian
    "Volkov", "Petrov", "Morozov", "Sokolov", "Orlov", "Lebedev", "Ivanov",
    "Kuznetsov", "Popov", "Smirnov", "Novikov", "Fedorov", "Zhukov",
    "Drozdov", "Baranovsky", "Alekseyev", "Kozlov", "Nikitin", "Rykov",
    # German / Austrian
    "Bauer", "Fischer", "Hoffmann", "Klein", "Koch", "Krause", "Müller",
    "Schneider", "Schulz", "Wagner", "Weber", "Werner", "Wolf", "Zimmermann",
    "Brenner", "Kessler", "Ritter", "Steiner", "Vogt",
    # French
    "Bernard", "Blanc", "Bonnet", "Dupont", "Fontaine", "Garnier", "Girard",
    "Lambert", "Laurent", "Leroy", "Martin", "Moreau", "Petit", "Richard",
    "Simon", "Thomas", "Rousseau", "Charpentier", "Beaumont",
    # Arabic / Middle Eastern
    "Al-Amin", "Al-Bakr", "Al-Farouk", "Al-Hassan", "Al-Khalidi", "Al-Mansouri",
    "Al-Rashidi", "Al-Sayed", "Al-Sharif", "Al-Zahrani", "Hamdan", "Nasser",
    "Qureshi", "Shirazi", "Tehrani",
    # Chinese / Korean / Japanese
    "Chen", "Li", "Liu", "Wang", "Wu", "Zhang", "Zhao", "Zhou",
    "Kim", "Lee", "Park", "Choi", "Jung", "Ahn",
    "Hayashi", "Nakamura", "Sato", "Suzuki", "Tanaka", "Watanabe", "Yamamoto",
    # South Asian
    "Anand", "Bose", "Chatterjee", "Das", "Ghosh", "Gupta", "Joshi",
    "Kapoor", "Mehta", "Mishra", "Patel", "Rao", "Sharma", "Singh", "Verma",
    # African
    "Diallo", "Keita", "Konaté", "Kouyaté", "Mwangi", "Okafor", "Otieno",
    "Owusu", "Toure", "Traore", "Nkosi", "Dlamini", "Mensah", "Asante",
    # Latin American
    "Cruz", "García", "Gómez", "González", "Hernández", "López", "Martínez",
    "Morales", "Muñoz", "Pérez", "Ramírez", "Rodríguez", "Sánchez", "Torres",
    "Vega", "Ortega", "Reyes", "Castillo", "Rojas",
    # British / American
    "Carter", "Collins", "Edwards", "Evans", "Green", "Harris", "Hughes",
    "Jones", "Lewis", "Morgan", "Phillips", "Price", "Roberts", "Scott",
    "Taylor", "Thomas", "Turner", "Walker", "White", "Williams",
]


# ---------------------------------------------------------------------------
# Vehicle name components
# ---------------------------------------------------------------------------
VEHICLE_COLORS = [
    "Black", "White", "Gray", "Silver", "Dark Blue", "Olive", "Sand-Colored",
    "Red", "Forest Green", "Burgundy", "Charcoal", "Beige", "Navy", "Rust",
]

VEHICLE_TYPES = [
    "Sedan", "SUV", "Hatchback", "Van", "Pickup Truck", "Motorcycle",
    "Panel Van", "Station Wagon", "Jeep", "Minivan", "Cargo Truck",
    "Fishing Boat", "Speedboat", "Rigid Inflatable Boat", "Trawler",
    "Container Lorry", "Ambulance", "Tanker Truck",
]

VEHICLE_ADJECTIVES = [
    "Modified", "Armored", "Unmarked", "Rusted", "Reinforced", "Battered",
    "Nondescript", "Decommissioned", "Repainted", "Seized", "Stolen",
    "Converted", "Camouflaged",
]

VEHICLE_MAKES = [
    "Mercedes-Benz S-Class", "BMW 5 Series", "Toyota Land Cruiser",
    "Ford Transit", "Audi A6", "Volkswagen Transporter", "Range Rover",
    "Mitsubishi Pajero", "Nissan Patrol", "Lexus LX", "Hyundai Tucson",
    "Honda CB500", "Yamaha MT-09", "Kawasaki Z900",
    "Zhongxing Pickup", "GAZ Gazelle", "UAZ Patriot",
]

VEHICLE_YEARS = list(range(2010, 2025))

VEHICLE_COLORS_SHORT = [
    "matte black", "flat white", "silver", "dark grey", "olive drab",
    "sand", "deep blue", "burgundy", "forest green", "rust orange",
]


# ---------------------------------------------------------------------------
# Building name components
# ---------------------------------------------------------------------------
BUILDING_PREFIXES = [
    "Abandoned", "Decommissioned", "Disused", "Former", "Converted",
    "Condemned", "Refurbished", "Secured", "Fortified", "Unmarked",
    "Remote", "Isolated", "Classified",
]

BUILDING_TYPES = [
    "Textile Mill", "Warehouse", "Storage Facility", "Printing Works",
    "Cold Storage Unit", "Dockside Depot", "Freight Terminal",
    "Factory", "Substation", "Communications Tower",
    "Apartment Block", "Villa", "Safe House", "Farmhouse",
    "Hotel Room {n}", "Office Suite {n}", "Storage Unit {n}",
    "Embassy Annex Building {l}", "Research Station", "Listening Post",
    "Data Center", "Signals Post", "Logistics Hub", "Harbor Depot",
    "Finance Tower", "Bunker", "Cellar Complex",
]

BUILDING_AREA_WORDS = [
    "Riverside", "Dockside", "Harborfront", "Industrial", "Coastal",
    "Downtown", "Northern", "Eastern", "Central", "Lakeside",
    "Port", "Old Town", "Border", "Mountain", "Valley",
]


# ---------------------------------------------------------------------------
# Activity fragment pools  (suspicious)
# ---------------------------------------------------------------------------
SUSPICIOUS_ACTIVITIES = [
    "Met with an unidentified individual at {place} and exchanged {item}.",
    "Accessed a restricted area at {facility} using falsified credentials.",
    "Transported an unmarked {container} from {location_a} to {location_b}.",
    "Was observed conducting a dead drop near {landmark}.",
    "Made three consecutive calls on a burner phone to a number registered to a defunct {entity}.",
    "Crossed the border using a forged {document} at a minor checkpoint.",
    "Transferred {amount} from an account in {city_a} to a shell company in {city_b}.",
    "Was photographed meeting with a known {intel_org} officer at {venue}.",
    "Deployed a surveillance device in the vicinity of a foreign diplomatic mission.",
    "Received a courier package with no return address originating from {city}.",
    "Was observed uploading an encrypted archive to a server registered in {country}.",
    "Held a clandestine meeting at a rented {property} with individuals on a known watchlist.",
    "Was intercepted carrying documents that matched classified material reported stolen from {facility}.",
    "Operated radio equipment from a vehicle parked outside a government building.",
    "Was seen accepting a sealed package from a person matching the description of an active red-notice subject.",
    "Made an unscheduled border crossing and returned within six hours with no declared goods.",
    "Was found to have rented multiple storage units in different districts under false names.",
    "Used a laser microphone to monitor a conversation inside a diplomatic compound.",
    "Arranged payment of {amount} through a hawala network to an unknown recipient in {city}.",
    "Was photographed accessing a rooftop adjacent to a government communications tower.",
]

SUSPICIOUS_PLACES = [
    "a waterfront café", "a park bench", "a car park stairwell",
    "a museum lobby", "a hotel bar", "a busy train station",
    "a private dining room", "a casino floor", "a botanical garden",
    "a sports stadium corridor",
]

SUSPICIOUS_ITEMS = [
    "a USB drive", "a sealed envelope", "a burner phone",
    "a laptop bag", "a rolled newspaper with documents inside",
    "a key to an unknown address", "a small hard drive",
    "a package wrapped in brown paper",
]

SUSPICIOUS_CONTAINERS = [
    "crate", "duffel bag", "diplomatic pouch", "suitcase",
    "briefcase", "waterproof case", "metal trunk",
]

SUSPICIOUS_FACILITIES = [
    "a telecommunications exchange", "a government archive",
    "a military logistics depot", "a satellite uplink facility",
    "a classified records office", "a foreign embassy compound",
]

SUSPICIOUS_LANDMARKS = [
    "a public monument", "a cemetery wall", "a park fountain",
    "a decommissioned phone box", "a loose paving stone",
    "the underside of a bridge", "a locker at a transport hub",
]

SUSPICIOUS_ENTITIES = [
    "shipping company", "consulting firm", "import-export business",
    "telecommunications provider", "pharmaceutical distributor",
]

SUSPICIOUS_DOCUMENTS = [
    "Estonian passport", "Swiss diplomatic ID", "Hungarian press card",
    "UN observer credential", "corporate travel visa",
]

SUSPICIOUS_AMOUNTS = [
    "$50,000", "$200,000", "$1.4 million", "€80,000",
    "€350,000", "¥15 million", "$500,000 in cryptocurrency",
]

INTEL_ORGS = [
    "GRU", "SVR", "FSB", "MSS", "IRGC-IO", "ISI", "DGSE",
    "BND", "Mossad", "MI6", "CIA", "BfV",
]

SUSPICIOUS_VENUES = [
    "a private members' club", "a luxury hotel lobby",
    "an airport transit lounge", "a rooftop bar",
    "a consulate anteroom", "a rented conference room",
]

SUSPICIOUS_PROPERTIES = [
    "villa", "apartment", "safe house", "chalet", "townhouse",
]


# ---------------------------------------------------------------------------
# Activity fragment pools  (non-suspicious)
# ---------------------------------------------------------------------------
NON_SUSPICIOUS_ACTIVITIES = [
    "Attended a trade conference at the local convention center.",
    "Visited a gallery and spent several hours in the contemporary art wing.",
    "Had lunch at a well-known restaurant with family members.",
    "Attended a university public lecture on international economics.",
    "Was observed jogging in a public park in the early morning.",
    "Purchased groceries at a local market.",
    "Attended a religious service at a nearby place of worship.",
    "Enrolled in an evening language class.",
    "Visited a public library and spent two hours in the periodicals section.",
    "Attended a charity fundraiser dinner.",
    "Took a guided city tour as part of an apparent tourist group.",
    "Watched a film at a cinema in the city center.",
    "Dined at a popular restaurant in the main commercial district.",
    "Attended a sporting event as a spectator.",
    "Went for a walk along the waterfront promenade.",
    "Visited a botanical garden with what appeared to be a family member.",
    "Purchased books at a major bookseller.",
    "Attended a business networking event at a downtown hotel.",
    "Was seen at a public swimming pool during regular hours.",
    "Checked into a hotel under an apparently legitimate reservation.",
]


# ---------------------------------------------------------------------------
# Prior / charge fragment pools
# ---------------------------------------------------------------------------
PRIOR_TEMPLATES = [
    "Arrested by {agency} on suspicion of {offense}; charges dropped after {outcome}.",
    "Convicted in {country} court of {offense}; sentence {sentence}.",
    "Investigated by {agency} for {offense}; case closed without prosecution.",
    "Placed on {list} for alleged involvement in {offense}.",
    "Detained for {hours} hours on suspicion of {offense}; released without charge.",
    "Indicted on {count} counts of {offense}; remains at large.",
    "Named in a classified report as a suspected {role}.",
    "Flagged by {agency} as an unregistered foreign intelligence asset.",
    "Implicated in {offense} by a UN monitoring group; never formally charged.",
    "Survived an assassination attempt; circumstances suggest operational exposure.",
]

AGENCIES = [
    "Interpol", "the FBI", "the CIA", "MI5", "the BfV", "the DST",
    "local federal police", "a national counter-intelligence service",
    "financial intelligence authorities", "border security forces",
    "the DGSI", "the BND", "Swiss FINMA", "Europol", "the NCA",
]

OFFENSES = [
    "arms brokerage without a license",
    "money laundering through shell companies",
    "document forgery",
    "computer fraud and unauthorized access",
    "industrial espionage targeting a defense contractor",
    "illegal transfer of dual-use technology",
    "smuggling of undeclared currency",
    "facilitating sanctions evasion",
    "operating as an unregistered foreign agent",
    "trafficking in classified government documents",
    "conspiracy to commit wire fraud",
    "procurement of restricted military equipment",
]

PRIOR_OUTCOMES = [
    "key witness recanted", "48-hour hold exceeded",
    "insufficient admissible evidence", "diplomatic intervention",
    "jurisdictional dispute", "classified evidence sealed by court order",
]

PRIOR_SENTENCES = [
    "suspended", "served in full", "commuted after appeal",
    "never enforced due to flight from jurisdiction",
    "reduced on appeal to time served",
]

PRIOR_LISTS = [
    "an EU sanctions list", "the OFAC SDN list",
    "a UN Security Council sanctions list",
    "a classified intelligence watchlist",
    "a bilateral travel-ban register",
]

PRIOR_COUNTS = ["4", "7", "12", "16", "3"]

PRIOR_ROLES = [
    "double agent", "unregistered foreign intelligence asset",
    "courier for a state-backed network",
    "facilitator for a sanctions-evasion ring",
    "technical support operative for a foreign signals unit",
]

PRIOR_HOURS = ["18", "36", "48", "72"]

PRIOR_COUNTRIES = [
    "a Belgian", "an Italian", "a German", "a French", "a Swiss",
    "a Dutch", "an Austrian", "a Polish",
]


# ---------------------------------------------------------------------------
# Identifying characteristics pool
# ---------------------------------------------------------------------------
CHARACTERISTICS = [
    # Physical
    "Slim build, approximately {h} cm tall",
    "Stocky, broad-shouldered frame",
    "Tall and lean with a military bearing",
    "Short, approximately {h2} cm, with a compact athletic build",
    "Heavy-set with a prominent double chin",
    "Deep scar running across the {cheek} cheek",
    "Missing the tip of the {finger} finger on their {hand} hand",
    "Walks with a pronounced limp on the {side} leg",
    "Completely bald with a {color} beard",
    "Distinctive {color2} hair, kept very short",
    "Wears thick-framed glasses with a custom anti-reflective coating",
    "Has heterochromia — one brown eye, one green",
    "A faded tattoo of a compass rose on the inner left wrist",
    "A small anchor tattoo behind the {ear} ear",
    "A dragon tattoo covering the back of the left hand",
    "Geometric tattoo sleeve on the {arm} arm",
    "Tribal scarification marks on both forearms",
    "Large birthmark on the left side of the neck",
    "Prosthetic left {digit}, often concealed by a glove",
    # Behavioral / operational
    "Known to use at least three different aliases",
    "Always sits facing the entrance in any room",
    "Never uses a mobile phone registered in their own name",
    "Carries at least two mobile devices at all times",
    "Speaks {lang} fluently with no detectable accent",
    "Changes hair color and style frequently as an anti-surveillance measure",
    "Wears colored contact lenses to alter apparent eye color",
    "Known to run counter-surveillance routes before any meeting",
    "Favors outdoor cafés and always occupies a corner position",
    "Has a distinctive nervous habit of clicking a pen when under stress",
    "Rarely stays at the same accommodation more than two nights in a row",
    "Communicates primarily through encrypted messaging apps on burner devices",
    # Cover / documents
    "Carries business cards from a non-existent organization",
    "Holds dual citizenship documents under two different nationalities",
    "Has at least two known false passports in circulation",
    "Travels on a diplomatic passport that has been reported as stolen",
    "Cover occupation is listed as {cover} in public records",
]

CHARACTERISTIC_FILLS = {
    "{h}": ["168", "172", "175", "180", "185"],
    "{h2}": ["155", "158", "160", "163"],
    "{cheek}": ["left", "right"],
    "{finger}": ["index", "ring", "little", "middle"],
    "{hand}": ["left", "right"],
    "{side}": ["left", "right"],
    "{color}": ["dark", "grey", "auburn", "silver", "black"],
    "{color2}": ["silver", "jet-black", "auburn", "platinum", "sandy"],
    "{ear}": ["left", "right"],
    "{arm}": ["left", "right"],
    "{digit}": ["ring finger", "index finger", "little finger"],
    "{lang}": ["Russian", "Arabic", "Mandarin", "French", "German",
               "Farsi", "Turkish", "Spanish", "English"],
    "{cover}": ["import-export consultant", "software engineer",
                "freelance journalist", "NGO program officer",
                "financial analyst", "academic researcher",
                "shipping logistics manager"],
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def random_date(start_year: int = 2020, end_year: int = 2026) -> str:
    """Return a random date string YYYY-MM-DD within the given year range."""
    start = date(start_year, 1, 1)
    end = date(end_year, 3, 9)        # today's date (teaching app)
    delta = (end - start).days
    return (start + timedelta(days=random.randint(0, delta))).isoformat()


def random_birthday(min_age: int = 28, max_age: int = 75) -> str:
    """Return a random birthday string for a person of plausible spy age."""
    today = date(2026, 3, 9)
    age = random.randint(min_age, max_age)
    birth_year = today.year - age
    try:
        birth_date = date(birth_year, random.randint(1, 12), random.randint(1, 28))
    except ValueError:
        birth_date = date(birth_year, 1, 1)
    return birth_date.isoformat()


def random_timestamp(start_year: int = 2023, end_year: int = 2026) -> str:
    """Return a random ISO-8601 UTC timestamp string."""
    d = random_date(start_year, end_year)
    hour = random.randint(0, 23)
    minute = random.choice([0, 15, 30, 45])
    return f"{d}T{hour:02d}:{minute:02d}:00Z"


def fill_template(template: str) -> str:
    """Replace simple {placeholder} tokens in a template with random values."""
    result = template
    # Inline substitution tables for activity templates
    substitutions = {
        "{place}": SUSPICIOUS_PLACES,
        "{item}": SUSPICIOUS_ITEMS,
        "{container}": SUSPICIOUS_CONTAINERS,
        "{location_a}": [c[0] for c in CITIES],
        "{location_b}": [c[0] for c in CITIES],
        "{facility}": SUSPICIOUS_FACILITIES,
        "{landmark}": SUSPICIOUS_LANDMARKS,
        "{entity}": SUSPICIOUS_ENTITIES,
        "{document}": SUSPICIOUS_DOCUMENTS,
        "{amount}": SUSPICIOUS_AMOUNTS,
        "{city_a}": [c[0] for c in CITIES],
        "{city_b}": [c[0] for c in CITIES],
        "{city}": [c[0] for c in CITIES],
        "{country}": [c[0].split(",")[-1].strip() for c in CITIES],
        "{intel_org}": INTEL_ORGS,
        "{venue}": SUSPICIOUS_VENUES,
        "{property}": SUSPICIOUS_PROPERTIES,
    }
    for token, options in substitutions.items():
        if token in result:
            result = result.replace(token, random.choice(options), 1)
    return result


def fill_characteristic(template: str) -> str:
    """Fill characteristic templates with their specific random values."""
    result = template
    for token, options in CHARACTERISTIC_FILLS.items():
        if token in result:
            result = result.replace(token, random.choice(options), 1)
    return result


def fill_prior(template: str) -> str:
    """Fill prior record templates."""
    subs = {
        "{agency}": AGENCIES,
        "{offense}": OFFENSES,
        "{outcome}": PRIOR_OUTCOMES,
        "{sentence}": PRIOR_SENTENCES,
        "{list}": PRIOR_LISTS,
        "{count}": PRIOR_COUNTS,
        "{role}": PRIOR_ROLES,
        "{hours}": PRIOR_HOURS,
        "{country}": PRIOR_COUNTRIES,
    }
    result = template
    for token, options in subs.items():
        if token in result:
            result = result.replace(token, random.choice(options), 1)
    return result


def pick_city() -> dict:
    """Return a current_location dict for a random city."""
    name, lat, lon = random.choice(CITIES)
    # Add a small random offset so targets in the same city are not stacked
    lat_offset = random.uniform(-0.05, 0.05)
    lon_offset = random.uniform(-0.05, 0.05)
    return {"lat": round(lat + lat_offset, 4), "lon": round(lon + lon_offset, 4)}


ASSOCIATION_DESCRIPTIONS = [
    "Observed meeting at undisclosed location",
    "Linked through shared communications channel",
    "Co-located during surveillance window",
    "Connected via financial transaction records",
    "Identified as operational contact",
    "Spotted together at border crossing",
    "Named in intercepted correspondence",
    "Shared safe house access confirmed",
    "Appeared in same travel manifest",
    "Connected through intermediary network",
]


def pick_associations(existing_keys: list, count_range=(0, 4)) -> list:
    """Pick a random subset of existing target keys as association objects."""
    n = random.randint(*count_range)
    if not existing_keys or n == 0:
        return []
    # Don't associate with more targets than exist
    n = min(n, len(existing_keys))
    selected = random.sample(existing_keys, n)
    return [
        {
            "target_name": key,
            "description": random.choice(ASSOCIATION_DESCRIPTIONS),
        }
        for key in selected
    ]


def make_suspicious_activities(n: int) -> list:
    """Generate n suspicious activity records."""
    activities = []
    templates = random.sample(SUSPICIOUS_ACTIVITIES, min(n, len(SUSPICIOUS_ACTIVITIES)))
    for tmpl in templates:
        activities.append({
            "timestamp": random_timestamp(),
            "description": fill_template(tmpl),
        })
    return activities


def make_non_suspicious_activities(n: int) -> list:
    """Generate n non-suspicious activity records."""
    activities = []
    chosen = random.sample(NON_SUSPICIOUS_ACTIVITIES, min(n, len(NON_SUSPICIOUS_ACTIVITIES)))
    for desc in chosen:
        activities.append({
            "timestamp": random_timestamp(),
            "description": desc,
        })
    return activities


def make_whereabouts(n: int) -> list:
    """Generate n known whereabout records."""
    whereabouts = []
    cities_used = random.sample(CITIES, min(n, len(CITIES)))
    for city_name, _, _ in cities_used:
        start = random_date(2019, 2025)
        # End date is either ongoing (today) or a past date
        if random.random() < 0.4:
            end = "2026-03-09"
        else:
            end = random_date(2020, 2026)
            # Ensure end >= start
            if end < start:
                end = start
        whereabouts.append({
            "city": city_name,
            "start_date": start,
            "end_date": end,
        })
    return whereabouts


def make_priors(n: int) -> list:
    """Generate n prior record entries."""
    priors = []
    for _ in range(n):
        tmpl = random.choice(PRIOR_TEMPLATES)
        priors.append({
            "date": random_date(2000, 2025),
            "description": fill_prior(tmpl),
        })
    return priors


def make_characteristics(n: int) -> list:
    """Generate n identifying characteristic strings."""
    chosen = random.sample(CHARACTERISTICS, min(n, len(CHARACTERISTICS)))
    return [fill_characteristic(c) for c in chosen]


# ---------------------------------------------------------------------------
# Target generators
# ---------------------------------------------------------------------------

def generate_person_name(existing_names: set) -> str:
    """Generate a unique full name not already in the dataset."""
    for _ in range(500):   # try up to 500 times before giving up
        first = random.choice(FIRST_NAMES)
        last = random.choice(LAST_NAMES)
        name = f"{first} {last}"
        if name not in existing_names:
            return name
    # Fallback: append a number to guarantee uniqueness
    base = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
    suffix = 2
    candidate = f"{base} {suffix}"
    while candidate in existing_names:
        suffix += 1
        candidate = f"{base} {suffix}"
    return candidate


def generate_person(existing_keys: list, existing_names: set) -> tuple[str, dict]:
    """Return (name, record_dict) for a new person target."""
    name = generate_person_name(existing_names)
    city_name, lat, lon = random.choice(CITIES)
    lat_offset = random.uniform(-0.05, 0.05)
    lon_offset = random.uniform(-0.05, 0.05)

    record = {
        "type": "person",
        "current_location": {
            "lat": round(lat + lat_offset, 4),
            "lon": round(lon + lon_offset, 4),
        },
        "birthday": random_birthday(),
        "associations": pick_associations(existing_keys, count_range=(0, 4)),
        "identifying_characteristics": make_characteristics(random.randint(1, 3)),
        "suspicious_activities":     make_suspicious_activities(random.randint(0, 5)),
        "nonsuspicious_activities":  make_non_suspicious_activities(random.randint(0, 5)),
        "known_whereabouts":         make_whereabouts(random.randint(1, 4)),
        "priors":                    make_priors(random.randint(0, 3)),
    }
    return name, record


def generate_vehicle_name(existing_names: set) -> str:
    """Generate a unique vehicle name like 'The Gray Hatchback' or
    'The Modified Fishing Boat'."""
    for _ in range(500):
        pattern = random.choice([
            # "The {Color} {Type}"
            lambda: f"The {random.choice(VEHICLE_COLORS)} {random.choice(VEHICLE_TYPES)}",
            # "The {Adjective} {Type}"
            lambda: f"The {random.choice(VEHICLE_ADJECTIVES)} {random.choice(VEHICLE_TYPES)}",
            # "The {Color} {Adjective} {Type}"
            lambda: (
                f"The {random.choice(VEHICLE_COLORS)} "
                f"{random.choice(VEHICLE_ADJECTIVES)} "
                f"{random.choice(VEHICLE_TYPES)}"
            ),
        ])
        name = pattern()
        if name not in existing_names:
            return name
    # Fallback
    return f"The Unknown Vehicle {random.randint(100, 999)}"


def generate_vehicle(existing_keys: list, existing_names: set) -> tuple[str, dict]:
    """Return (name, record_dict) for a new vehicle target."""
    name = generate_vehicle_name(existing_names)

    year = random.choice(VEHICLE_YEARS)
    make = random.choice(VEHICLE_MAKES)
    color = random.choice(VEHICLE_COLORS_SHORT)
    city_name, lat, lon = random.choice(CITIES)

    record = {
        "type": "vehicle",
        "current_location": {
            "lat": round(lat + random.uniform(-0.05, 0.05), 4),
            "lon": round(lon + random.uniform(-0.05, 0.05), 4),
        },
        # Vehicles use birthday as manufacture/registration year
        "birthday": f"{year}-{random.randint(1,12):02d}-{random.randint(1,28):02d}",
        "associations": pick_associations(existing_keys, count_range=(1, 4)),
        "identifying_characteristics": [
            f"{year} {make}, {color} finish",
            random.choice([
                "License plates found to be registered to a non-existent owner",
                "VIN plate is a known counterfeit",
                "Registered to a shell company with no traceable principals",
                "Previously reported stolen; reappeared with new plates",
                "License plate alternates between multiple known sets",
            ]),
            random.choice([
                "Interior modified to conceal documents or equipment",
                "Concealed compartment identified under the rear floor",
                "Fitted with a roof-mounted antenna disguised as standard equipment",
                "Armored to B4 standard with ballistic glass",
                "Mobile surveillance suite installed in the rear cargo area",
                "Signal-dampening lining detected during a technical search",
            ]),
        ] + make_characteristics(random.randint(0, 2)),
        "suspicious_activities":    make_suspicious_activities(random.randint(0, 5)),
        "nonsuspicious_activities": make_non_suspicious_activities(random.randint(0, 3)),
        "known_whereabouts":        make_whereabouts(random.randint(1, 3)),
        "priors":                   make_priors(random.randint(0, 2)),
    }
    return name, record


def generate_building_name(existing_names: set) -> str:
    """Generate a unique building name like 'Abandoned Textile Mill'
    or 'Dockside Storage Unit 14'."""
    for _ in range(500):
        btype = random.choice(BUILDING_TYPES)
        # Fill in numeric/letter placeholders
        btype = btype.replace("{n}", str(random.randint(2, 99)))
        btype = btype.replace("{l}", random.choice(list("ABCDEFGH")))

        pattern = random.choice([
            # "{Prefix} {Type}"
            lambda bt=btype: f"{random.choice(BUILDING_PREFIXES)} {bt}",
            # "{Area} {Type}"
            lambda bt=btype: f"{random.choice(BUILDING_AREA_WORDS)} {bt}",
            # "{Area} {Prefix} {Type}"
            lambda bt=btype: (
                f"{random.choice(BUILDING_AREA_WORDS)} "
                f"{random.choice(BUILDING_PREFIXES)} {bt}"
            ),
        ])
        name = pattern()
        if name not in existing_names:
            return name
    return f"Facility {random.randint(100, 9999)}"


def generate_building(existing_keys: list, existing_names: set) -> tuple[str, dict]:
    """Return (name, record_dict) for a new building target."""
    name = generate_building_name(existing_names)

    city_name, lat, lon = random.choice(CITIES)
    # Buildings were established anywhere from decades ago to recently
    established_year = random.randint(1940, 2024)

    record = {
        "type": "building",
        "current_location": {
            "lat": round(lat + random.uniform(-0.1, 0.1), 4),
            "lon": round(lon + random.uniform(-0.1, 0.1), 4),
        },
        # Buildings use birthday as construction/establishment date
        "birthday": f"{established_year}-{random.randint(1,12):02d}-01",
        "associations": pick_associations(existing_keys, count_range=(1, 4)),
        "identifying_characteristics": [
            random.choice([
                "Externally unremarkable; shows no obvious signs of active use",
                "Blackout curtains on all windows regardless of time of day",
                "CCTV cameras covering all approaches, recently installed",
                "No signage; entry via unmarked side door only",
                "Reinforced steel door disguised behind a standard wooden facade",
                "RF shielding material detected in the exterior cladding",
                "Sub-level space not listed on official building plans",
                "Multiple dead-letter drop points identified in the surrounding area",
            ]),
            random.choice([
                "Ownership traced through three shell companies to an unidentified beneficial owner",
                "Registered to a defunct import-export company",
                "Listed as vacant in municipal records despite clear signs of occupation",
                "Power consumption far exceeds what the declared use would require",
                "Filed as a storage unit but thermal imaging shows regular human presence",
            ]),
        ] + make_characteristics(random.randint(0, 2)),
        "suspicious_activities":    make_suspicious_activities(random.randint(0, 5)),
        "nonsuspicious_activities": make_non_suspicious_activities(random.randint(0, 3)),
        "known_whereabouts": [
            {
                "city": city_name,
                "start_date": f"{established_year}-01-01",
                "end_date": "2026-03-09",
            }
        ],
        "priors": make_priors(random.randint(0, 2)),
    }
    return name, record


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    # 1. Load existing data
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data: dict = json.load(f)

    existing_count = len(data)
    needed = TARGET_TOTAL - existing_count

    if needed <= 0:
        print(f"File already contains {existing_count} targets. Nothing to do.")
        return

    print(f"Existing targets: {existing_count}. Generating {needed} new targets...")

    # Set of existing names (keys) for uniqueness checks
    existing_names: set = set(data.keys())

    # 2. Decide how many of each type to generate
    #    Approximately 70% people, 15% vehicles, 15% buildings
    n_vehicles  = round(needed * 0.15)
    n_buildings = round(needed * 0.15)
    n_people    = needed - n_vehicles - n_buildings

    type_plan = (
        [("person",   generate_person)]   * n_people  +
        [("vehicle",  generate_vehicle)]  * n_vehicles +
        [("building", generate_building)] * n_buildings
    )
    random.shuffle(type_plan)   # mix the order so associations feel more natural

    # 3. Generate targets one by one, adding each to data before generating
    #    the next so it can appear in later association lists.
    generated = 0
    for target_type, generator_fn in type_plan:
        # Pass current keys as the pool for associations
        current_keys = list(data.keys())
        key, record = generator_fn(current_keys, existing_names)

        data[key] = record
        existing_names.add(key)
        generated += 1

        if generated % 100 == 0:
            print(f"  ...{generated}/{needed} generated")

    # 4. Write back to file
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    # 5. Summary
    type_counts = {}
    for record in data.values():
        t = record.get("type", "unknown")
        type_counts[t] = type_counts.get(t, 0) + 1

    print(f"\nDone!")
    print(f"Generated {generated} new targets. Total: {len(data)}")
    print("Breakdown by type:")
    for t, c in sorted(type_counts.items()):
        print(f"  {t:10s}: {c}")


if __name__ == "__main__":
    main()
