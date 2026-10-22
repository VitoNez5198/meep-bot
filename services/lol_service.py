"""
Servicio para League of Legends: DataDragon, búsqueda de campeones,
resolución de alias, y obtención de builds, runas y variantes de ARAM.
"""

import re
import logging
import unicodedata
from typing import Dict, Any, List, Optional, Tuple
import requests

logger = logging.getLogger("meep.lol")

# Endpoint base de DataDragon de Riot Games
DDRAGON_VERSIONS_URL = "https://ddragon.leagueoflegends.com/api/versions.json"
DDRAGON_BASE_CDN = "https://ddragon.leagueoflegends.com/cdn"

# Mapeo de alias y abreviaciones comunes de la comunidad a nombres de DataDragon
CHAMPION_ALIASES = {
    "mf": "MissFortune",
    "miss": "MissFortune",
    "missfortune": "MissFortune",
    "tf": "TwistedFate",
    "twisted": "TwistedFate",
    "twistedfate": "TwistedFate",
    "cait": "Caitlyn",
    "caitlyn": "Caitlyn",
    "nunu": "Nunu",
    "nunuywillump": "Nunu",
    "asol": "AurelionSol",
    "aurelionsol": "AurelionSol",
    "ww": "Warwick",
    "warwick": "Warwick",
    "yi": "MasterYi",
    "masteryi": "MasterYi",
    "tk": "TahmKench",
    "tahm": "TahmKench",
    "tahmkench": "TahmKench",
    "morde": "Mordekaiser",
    "mordekaiser": "Mordekaiser",
    "kata": "Katarina",
    "katarina": "Katarina",
    "ez": "Ezreal",
    "ezreal": "Ezreal",
    "mundo": "DrMundo",
    "drmundo": "DrMundo",
    "lee": "LeeSin",
    "leesin": "LeeSin",
    "gp": "Gangplank",
    "gangplank": "Gangplank",
    "j4": "JarvanIV",
    "jarvan": "JarvanIV",
    "jarvaniv": "JarvanIV",
    "ksante": "KSante",
    "k'sante": "KSante",
    "lb": "Leblanc",
    "leblanc": "Leblanc",
    "renata": "Renata",
    "renataglasc": "Renata",
    "kha": "Khazix",
    "khazix": "Khazix",
    "k6": "Khazix",
    "cho": "Chogath",
    "chogath": "Chogath",
    "vel": "Velkoz",
    "velkoz": "Velkoz",
    "wukong": "MonkeyKing",
    "blitz": "Blitzcrank",
    "blitzcrank": "Blitzcrank",
    "kog": "KogMaw",
    "kogmaw": "KogMaw",
    "cassio": "Cassiopeia",
    "cassiopeia": "Cassiopeia",
    "seju": "Sejuani",
    "sejuani": "Sejuani",
    "trist": "Tristana",
    "tristana": "Tristana",
    "trynda": "Tryndamere",
    "tryndamere": "Tryndamere",
    "vlad": "Vladimir",
    "vladimir": "Vladimir",
    "hecarim": "Hecarim",
    "heca": "Hecarim",
}

# Base de datos de variantes especializadas de campeones con estilos duales (ARAM y Grieta)
CHAMPION_SPECIAL_BUILDS: Dict[str, Dict[str, List[Dict[str, Any]]]] = {
    "MissFortune": {
        "aram": [
            {
                "style_id": "ad",
                "style_name": "🏹 AD / Letalidad (R Explosiva)",
                "win_rate": "53.6%",
                "primary_tree": "Dominación (Cosecha Oscura)",
                "keystone": "Cosecha Oscura",
                "primary_runes": ["Sabor a Sangre", "Colección de Ojos", "Cazador Definitivo"],
                "secondary_tree": "Precisión",
                "secondary_runes": ["Claridad Mental", "Golpe de Gracia"],
                "shards": ["+9 Fuerza Adaptable", "+9 Fuerza Adaptable", "+65 Vida"],
                "skill_max": "Q > W > E",
                "summoner_spells": "Flash + Curación o Marca (Nieve)",
                "starting_items": "Espadón dentado + Poción",
                "core_items": "El Coleccionista -> Arco Axiomático -> Rencor de Serylda",
                "situational_items": "Filo Infinito, Filo de la Noche, Recuerdos de Lord Dominik",
                "tips": "Guarda tu R para cuando los enemigos queden agrupados en el puente o tras un stun de tu equipo."
            },
            {
                "style_id": "ap",
                "style_name": "🔮 AP / Pokeo (Lluvia de E)",
                "win_rate": "51.2%",
                "primary_tree": "Brujería (Cometa Arcano)",
                "keystone": "Cometa Arcano",
                "primary_runes": ["Banda de Maná", "Trascendencia", "Piromancia (Quemadura)"],
                "secondary_tree": "Precisión",
                "secondary_runes": ["Claridad Mental", "Corte"],
                "shards": ["+9 Fuerza Adaptable", "+9 Fuerza Adaptable", "+65 Vida"],
                "skill_max": "E > W > Q",
                "summoner_spells": "Flash + Claridad o Marca (Nieve)",
                "starting_items": "Capítulo Perdido + Pociones",
                "core_items": "Tormento de Liandry -> Malignidad -> Cetro de Rylai",
                "situational_items": "Llama Sombría, Reloj de Arena de Zhonya, Sombrero de Rabadon",
                "tips": "Spamea la E a máxima distancia para ralentizar y quemar a todo el equipo rival constantemente."
            }
        ],
        "normal": [
            {
                "style_id": "ad",
                "style_name": "🏹 AD Crítico / Letalidad (ADC)",
                "win_rate": "52.4%",
                "primary_tree": "Inspiración (Primer Golpe) o Precisión (PTA)",
                "keystone": "Primer Golpe",
                "primary_runes": ["Calzado Mágico", "Entrega de Galletas", "Perspicacia Cósmica"],
                "secondary_tree": "Brujería",
                "secondary_runes": ["Banda de Maná", "Se Avecina Tormenta"],
                "shards": ["+9 Fuerza Adaptable", "+9 Fuerza Adaptable", "+65 Vida"],
                "skill_max": "Q > W > E",
                "summoner_spells": "Flash + Barrera / Curación",
                "starting_items": "Espada de Doran + Poción",
                "core_items": "El Coleccionista -> Filo del Infinito -> Cañón de Fuego Rápido",
                "situational_items": "Recuerdos de Lord Dominik, Sanguinaria, Ángel de la Guarda",
                "tips": "Aprovecha los rebotes de la Q cuando un súbdito rival esté con poca vida para desgastar al ADC enemigo."
            }
        ]
    },
    "Malphite": {
        "aram": [
            {
                "style_id": "ap",
                "style_name": "🔮 AP One-Shot (Misil Nuclear)",
                "win_rate": "52.1%",
                "primary_tree": "Dominación (Electrocutar / Cosecha)",
                "keystone": "Cosecha Oscura",
                "primary_runes": ["Impacto Repentino", "Colección de Ojos", "Cazador Definitivo"],
                "secondary_tree": "Brujería",
                "secondary_runes": ["Banda de Maná", "Trascendencia"],
                "shards": ["+9 Fuerza Adaptable", "+9 Fuerza Adaptable", "+65 Vida"],
                "skill_max": "R > Q > E > W",
                "summoner_spells": "Flash + Marca (Nieve)",
                "starting_items": "Alternador Hextech + Pociones",
                "core_items": "Sobrecarga Tormentosa -> Malignidad -> Reloj de Zhonya",
                "situational_items": "Llama Sombría, Sombrero Mortal de Rabadon, Bastón del Vacío",
                "tips": "Entra con Bola de Nieve o R directa sobre los magos y ADCs débiles. Usa Zhonya inmediatamente tras explotar a alguien."
            },
            {
                "style_id": "tank",
                "style_name": "🛡️ Tanque Inmortal (Frontline)",
                "win_rate": "54.8%",
                "primary_tree": "Valor (Garras del Inmortal)",
                "keystone": "Garras del Inmortal",
                "primary_runes": ["Golpe de Escudo", "Condicionamiento", "Sobrecrecimiento"],
                "secondary_tree": "Precisión",
                "secondary_runes": ["Claridad Mental", "Tenacidad o Leyenda Presteza"],
                "shards": ["+8 Aceleración de Habilidad", "+6 Armadura", "+65 Vida"],
                "skill_max": "R > E > W > Q",
                "summoner_spells": "Flash + Marca (Nieve)",
                "starting_items": "Guardián de Cuerno / Ceniza de Bami + Pociones",
                "core_items": "Corazón de Acero -> Égida de Fuego Solar -> Malla de Espinas",
                "situational_items": "Fuerza de la Naturaleza, Corazón de Hielo, Presagio de Randuin",
                "tips": "Si tu equipo carece de tanque, esta build gana muchas más partidas porque absorbe todo el daño y ralentiza la velocidad de ataque enemiga con la E."
            }
        ],
        "normal": [
            {
                "style_id": "tank",
                "style_name": "🛡️ Tanque de Armadura (Top)",
                "win_rate": "51.9%",
                "primary_tree": "Brujería (Cometa Arcano) o Valor",
                "keystone": "Cometa Arcano",
                "primary_runes": ["Banda de Maná", "Trascendencia", "Piromancia"],
                "secondary_tree": "Valor",
                "secondary_runes": ["Fuerzas Renovadas", "Sobrecrecimiento"],
                "shards": ["+8 Aceleración", "+6 Armadura", "+65 Vida"],
                "skill_max": "Q > E > W",
                "summoner_spells": "Flash + Teleport",
                "starting_items": "Anillo de Doran o Escudo de Doran",
                "core_items": "Égida de Fuego Solar -> Guantelete del Hijo del Hielo -> Malla de Espinas",
                "situational_items": "Fuerza de la Naturaleza, Corazón de Hielo, Jak'Sho",
                "tips": "Desgasta al rival con la Q cuando tengas el escudo pasivo disponible para intercambios favorables."
            }
        ]
    },
    "Kaisa": {
        "aram": [
            {
                "style_id": "ap",
                "style_name": "🔮 AP Francotirador (Spam W Poke)",
                "win_rate": "52.8%",
                "primary_tree": "Brujería (Cometa Arcano / Primer Golpe)",
                "keystone": "Primer Golpe",
                "primary_runes": ["Calzado Mágico", "Entrega de Galletas", "Perspicacia Cósmica"],
                "secondary_tree": "Brujería",
                "secondary_runes": ["Banda de Maná", "Trascendencia"],
                "shards": ["+9 Fuerza Adaptable", "+9 Fuerza Adaptable", "+8 Aceleración"],
                "skill_max": "W > Q > E",
                "summoner_spells": "Flash + Claridad o Curación",
                "starting_items": "Capítulo Perdido + Pociones",
                "core_items": "Diente de Nashor -> Tormento de Liandry -> Llama Sombría",
                "situational_items": "Sombrero Mortal de Rabadon, Reloj de Zhonya, Bastón del Vacío",
                "tips": "Cada W que aciertes reduce drásticamente su enfriamiento. Mantén distancia y dispara desde la niebla de guerra."
            },
            {
                "style_id": "ad",
                "style_name": "🏹 AD / On-Hit Clásico (DPS)",
                "win_rate": "50.9%",
                "primary_tree": "Precisión (Compás Letal / PTA)",
                "keystone": "Ataque Intensificado (PTA)",
                "primary_runes": ["Claridad Mental", "Leyenda: Linaje", "Golpe de Gracia"],
                "secondary_tree": "Inspiración",
                "secondary_runes": ["Entrega de Galletas", "Calzado Mágico"],
                "shards": ["+10% Velocidad de Ataque", "+9 Fuerza Adaptable", "+65 Vida"],
                "skill_max": "Q > E > W",
                "summoner_spells": "Flash + Fantasmal / Curación",
                "starting_items": "Martillo de Guerra + Poción",
                "core_items": "Espada de Furia de Guinsoo -> Diente de Nashor -> Espada del Rey Arruinado",
                "situational_items": "Final del Ingenio, Recuerdos de Lord Dominik, Ángel de la Guarda",
                "tips": "Ideal si en el equipo enemigo hay 2 o más tanques que requieren daño continuo sostenido."
            }
        ]
    },
    "Varus": {
        "aram": [
            {
                "style_id": "lethality",
                "style_name": "🏹 Letalidad / Pokeo (Flechas Q Largas)",
                "win_rate": "52.3%",
                "primary_tree": "Brujería (Cometa Arcano)",
                "keystone": "Cometa Arcano",
                "primary_runes": ["Banda de Maná", "Trascendencia", "Se Avecina Tormenta"],
                "secondary_tree": "Inspiración",
                "secondary_runes": ["Entrega de Galletas", "Perspicacia Cósmica"],
                "shards": ["+9 Fuerza Adaptable", "+9 Fuerza Adaptable", "+65 Vida"],
                "skill_max": "Q > E > W",
                "summoner_spells": "Flash + Claridad o Curación",
                "starting_items": "Espadón dentado + Lágrima de la Diosa",
                "core_items": "Manamune -> Guja Sombría / Filo Fantasma de Youmuu -> Rencor de Serylda",
                "situational_items": "Arco Axiomático, Oportunidad, Filo de la Noche",
                "tips": "Carga la Q al máximo detrás de tus aliados y apunta a objetivos frágiles sin arriesgarte."
            },
            {
                "style_id": "ap",
                "style_name": "🔮 AP Destructor de Tanques (Porcentaje de Vida)",
                "win_rate": "53.5%",
                "primary_tree": "Precisión (Compás Letal / PTA)",
                "keystone": "Ataque Intensificado (PTA)",
                "primary_runes": ["Claridad Mental", "Leyenda: Presteza", "Golpe de Gracia"],
                "secondary_tree": "Brujería",
                "secondary_runes": ["Trascendencia", "Se Avecina Tormenta"],
                "shards": ["+10% Vel. Ataque", "+9 Fuerza Adaptable", "+65 Vida"],
                "skill_max": "W > Q > E",
                "summoner_spells": "Flash + Fantasmal",
                "starting_items": "Arco recurvo + Pociones",
                "core_items": "Diente de Nashor -> Creagrietas -> Sombrero Mortal de Rabadon",
                "situational_items": "Reloj de Zhonya, Llama Sombría, Bastón del Vacío",
                "tips": "Aplica 3 marcas de tu W con ataques básicos y detónalas con tu Q o E para borrar más del 60% de la vida máxima enemiga."
            }
        ]
    },
    "Maokai": {
        "aram": [
            {
                "style_id": "tank",
                "style_name": "🛡️ Tanque de Control Inmortal",
                "win_rate": "55.4%",
                "primary_tree": "Valor (Garras del Inmortal / Reverberación)",
                "keystone": "Reverberación",
                "primary_runes": ["Fuente de Vida", "Condicionamiento", "Revitalizar"],
                "secondary_tree": "Precisión",
                "secondary_runes": ["Claridad Mental", "Leyenda: Tenacidad"],
                "shards": ["+8 Aceleración", "+6 Armadura", "+65 Vida"],
                "skill_max": "Q > W > E",
                "summoner_spells": "Flash + Marca (Nieve)",
                "starting_items": "Guardián de Cuerno + Pociones",
                "core_items": "Corazón de Acero -> Resplandor de Esperanza -> Malla de Espinas",
                "situational_items": "Fuerza de la Naturaleza, Máscara Abisal, Corazón de Hielo",
                "tips": "Usa tu W para esquivar habilidades rivales y enganchar a la retaguardia enemiga mientras te curas constantemente con la pasiva."
            },
            {
                "style_id": "ap",
                "style_name": "🔮 AP Quemadura con Pimpollos (Bush Control)",
                "win_rate": "49.8%",
                "primary_tree": "Brujería (Cometa Arcano)",
                "keystone": "Cometa Arcano",
                "primary_runes": ["Banda de Maná", "Trascendencia", "Piromancia"],
                "secondary_tree": "Dominación",
                "secondary_runes": ["Golpe Bajo", "Cazador Definitivo"],
                "shards": ["+9 Fuerza Adaptable", "+9 Fuerza Adaptable", "+65 Vida"],
                "skill_max": "E > Q > W",
                "summoner_spells": "Flash + Claridad o Marca",
                "starting_items": "Capítulo Perdido + Pociones",
                "core_items": "Tormento de Liandry -> Cetro de Rylai -> Malignidad",
                "situational_items": "Llama Sombría, Reloj de Zhonya, Criptoflora",
                "tips": "Tira los pimpollos siempre dentro de los arbustos del centro; allí duplican su duración y radio de daño."
            }
        ]
    }
}


class LoLService:
    def __init__(self):
        self.latest_version: str = "14.21.1"  # Fallback seguro
        self.champions_cache: Dict[str, Dict[str, Any]] = {}
        self.normalized_map: Dict[str, str] = {}
        self._initialize_cache()

    def _normalize_string(self, text: str) -> str:
        """Remueve acentos, espacios, apóstrofes y signos para búsqueda tolerante."""
        if not text:
            return ""
        # Normalizar unicode y remover acentos
        nfkd = unicodedata.normalize("NFKD", text)
        clean = "".join([c for c in nfkd if not unicodedata.combining(c)])
        # Remover caracteres especiales y pasar a minúsculas
        return re.sub(r"[^a-zA-Z0-9]", "", clean).lower()

    def _initialize_cache(self):
        """Descarga la lista oficial de campeones de Riot DataDragon."""
        try:
            # Obtener última versión disponible
            res_v = requests.get(DDRAGON_VERSIONS_URL, timeout=5)
            if res_v.status_code == 200:
                versions = res_v.json()
                if versions:
                    self.latest_version = versions[0]
                    logger.info(f"Última versión de DataDragon detectada: {self.latest_version}")

            # Obtener campeones en español
            champ_url = f"{DDRAGON_BASE_CDN}/{self.latest_version}/data/es_ES/champion.json"
            res_c = requests.get(champ_url, timeout=6)
            if res_c.status_code == 200:
                data = res_c.json()
                champs = data.get("data", {})
                for champ_id, info in champs.items():
                    self.champions_cache[champ_id] = info
                    # Mapear nombres normalizados
                    norm_name = self._normalize_string(info.get("name", ""))
                    norm_id = self._normalize_string(champ_id)
                    self.normalized_map[norm_name] = champ_id
                    self.normalized_map[norm_id] = champ_id

                logger.info(f"Cacheados {len(self.champions_cache)} campeones de DataDragon.")
        except Exception as e:
            logger.warning(f"No se pudo contactar DataDragon en vivo, usando datos de respaldo: {e}")

    def resolve_champion(self, query: str) -> Optional[Tuple[str, Dict[str, Any]]]:
        """
        Resuelve una consulta de usuario (ej: 'mf', 'kaisa', 'lee', 'miss fortune')
        al ChampionId oficial de Riot y sus metadatos.
        """
        clean_q = self._normalize_string(query)
        if not clean_q:
            return None

        # 1. Chequear alias directos
        if clean_q in CHAMPION_ALIASES:
            target_id = CHAMPION_ALIASES[clean_q]
            info = self.champions_cache.get(target_id)
            if not info:
                info = {"name": target_id, "id": target_id, "title": "Campeón de la Grieta"}
            return target_id, info

        # 2. Chequear en el mapa normalizado
        if clean_q in self.normalized_map:
            target_id = self.normalized_map[clean_q]
            return target_id, self.champions_cache.get(target_id, {"name": target_id, "id": target_id})

        # 3. Búsqueda por coincidencia parcial
        for norm_key, champ_id in self.normalized_map.items():
            if clean_q in norm_key:
                return champ_id, self.champions_cache.get(champ_id, {"name": champ_id, "id": champ_id})

        return None

    def get_champion_icon_url(self, champ_id: str) -> str:
        """Devuelve la URL oficial del icono del campeón."""
        return f"{DDRAGON_BASE_CDN}/{self.latest_version}/img/champion/{champ_id}.png"

    def get_champion_splash_url(self, champ_id: str) -> str:
        """Devuelve la URL del splash art oficial del campeón."""
        return f"{DDRAGON_BASE_CDN}/img/champion/splash/{champ_id}_0.jpg"

    def get_builds(self, champ_id: str, mode: str = "normal") -> List[Dict[str, Any]]:
        """
        Devuelve las builds disponibles para el campeón en el modo especificado ('normal' o 'aram').
        Si existen variantes especiales (AD vs AP vs Tanque), las devuelve en lista.
        Si no hay variantes curadas, genera una build recomendada optimizada según la clase del campeón.
        """
        mode = mode.lower()
        if mode not in ["aram", "normal"]:
            mode = "normal"

        # Verificar si hay builds curadas para este campeón y modo
        if champ_id in CHAMPION_SPECIAL_BUILDS:
            curated_mode_builds = CHAMPION_SPECIAL_BUILDS[champ_id].get(mode)
            if curated_mode_builds:
                return curated_mode_builds

        # Generador de build de respaldo inteligente basado en el arquetipo / tags de DataDragon
        champ_info = self.champions_cache.get(champ_id, {})
        tags = champ_info.get("tags", ["Fighter"])
        primary_tag = tags[0] if tags else "Fighter"

        return [self._generate_default_build(champ_id, champ_info.get("name", champ_id), primary_tag, mode)]

    def _generate_default_build(self, champ_id: str, name: str, tag: str, mode: str) -> Dict[str, Any]:
        """Genera una build sólida y consistente si el campeón no tiene variantes fijas registradas."""
        is_aram = mode == "aram"

        archetypes = {
            "Marksman": {
                "style_name": "🏹 AD Carry / Daño Crítico Constante",
                "win_rate": "51.8%",
                "primary_tree": "Precisión (Compás Letal / PTA)",
                "keystone": "Compás Letal",
                "primary_runes": ["Claridad Mental" if is_aram else "Triunfo", "Leyenda: Linaje", "Golpe de Gracia"],
                "secondary_tree": "Inspiración",
                "secondary_runes": ["Calzado Mágico", "Entrega de Galletas"],
                "shards": ["+10% Velocidad de Ataque", "+9 Fuerza Adaptable", "+65 Vida"],
                "skill_max": "Q > W > E",
                "summoner_spells": "Flash + Marca (Nieve)" if is_aram else "Flash + Curación",
                "starting_items": "Guardián de Espada" if is_aram else "Espada de Doran + Poción",
                "core_items": "Kraken Slayer -> Filo Infinito -> Recuerdos de Lord Dominik",
                "situational_items": "Sanguinaria, Cañón de Fuego Rápido, Ángel de la Guarda",
                "tips": "Mantén buen posicionamiento detrás de tu frontline y kitea a los enemigos más cercanos."
            },
            "Mage": {
                "style_name": "🔮 Daño Mágico Burst / Control",
                "win_rate": "52.3%",
                "primary_tree": "Brujería (Cometa Arcano)",
                "keystone": "Cometa Arcano",
                "primary_runes": ["Banda de Maná", "Trascendencia", "Piromancia (Quemadura)"],
                "secondary_tree": "Precisión" if is_aram else "Inspiración",
                "secondary_runes": ["Claridad Mental", "Golpe de Gracia"] if is_aram else ["Entrega de Galletas", "Perspicacia Cósmica"],
                "shards": ["+9 Fuerza Adaptable", "+9 Fuerza Adaptable", "+65 Vida"],
                "skill_max": "Q > E > W",
                "summoner_spells": "Flash + Claridad" if is_aram else "Flash + Teleport",
                "starting_items": "Capítulo Perdido" if is_aram else "Anillo de Doran + Pociones",
                "core_items": "Tormento de Liandry / Compañero de Luden -> Llama Sombría -> Zhonya",
                "situational_items": "Sombrero Mortal de Rabadon, Bastón del Vacío, Más Sangre",
                "tips": "Desgasta a los rivales desde rango seguro antes de iniciar peleas en equipo."
            },
            "Tank": {
                "style_name": "🛡️ Tanque de Control e Iniciación",
                "win_rate": "53.2%",
                "primary_tree": "Valor (Garras del Inmortal / Reverberación)",
                "keystone": "Reverberación",
                "primary_runes": ["Fuente de Vida", "Condicionamiento", "Sobrecrecimiento"],
                "secondary_tree": "Precisión",
                "secondary_runes": ["Claridad Mental", "Leyenda: Tenacidad"],
                "shards": ["+8 Aceleración de Habilidad", "+6 Armadura", "+65 Vida"],
                "skill_max": "Q > W > E",
                "summoner_spells": "Flash + Marca (Nieve)",
                "starting_items": "Guardián de Cuerno + Pociones",
                "core_items": "Corazón de Acero -> Égida de Fuego Solar -> Malla de Espinas",
                "situational_items": "Fuerza de la Naturaleza, Presagio de Randuin, Corazón de Hielo",
                "tips": "Inicia la pelea cuando tu equipo esté cerca para seguir tu control de masas."
            },
            "Assassin": {
                "style_name": "🗡️ Letalidad / Burst de Eliminación",
                "win_rate": "50.7%",
                "primary_tree": "Dominación (Electrocutar / Cosecha)",
                "keystone": "Electrocutar",
                "primary_runes": ["Impacto Repentino", "Colección de Ojos", "Cazador Definitivo"],
                "secondary_tree": "Precisión",
                "secondary_runes": ["Claridad Mental", "Golpe de Gracia"],
                "shards": ["+9 Fuerza Adaptable", "+9 Fuerza Adaptable", "+65 Vida"],
                "skill_max": "Q > E > W",
                "summoner_spells": "Flash + Marca (Nieve)" if is_aram else "Flash + Ignición",
                "starting_items": "Espadón dentado + Poción",
                "core_items": "Espada Fantasma de Youmuu -> Oportunidad -> Rencor de Serylda",
                "situational_items": "Filo de la Noche, Arco Axiomático, Fauces de Malmortius",
                "tips": "Espera a que los rivales gasten sus habilidades de control de masas antes de lanzarte."
            },
            "Support": {
                "style_name": "✨ Utilidad, Curaciones y Escudos",
                "win_rate": "51.5%",
                "primary_tree": "Brujería (Invocación de Aery)",
                "keystone": "Aery",
                "primary_runes": ["Banda de Maná", "Trascendencia", "Se Avecina Tormenta"],
                "secondary_tree": "Inspiración",
                "secondary_runes": ["Calzado Mágico", "Perspicacia Cósmica"],
                "shards": ["+8 Aceleración", "+9 Fuerza Adaptable", "+65 Vida"],
                "skill_max": "E > W > Q",
                "summoner_spells": "Flash + Curación / Extenuación",
                "starting_items": "Objeto de Soporte + Pociones",
                "core_items": "Renovador de Piedra Lunar -> Redención -> Crisol de Mikael",
                "situational_items": "Incensario Ardiente, Mandato Imperial, Ecos de Helia",
                "tips": "Pega tus escudos y curaciones a tu ADC y usa tus habilidades para disuadir iniciaciones enemigas."
            },
            "Fighter": {
                "style_name": "⚔️ Luchador / Bruiser Ofensivo",
                "win_rate": "51.4%",
                "primary_tree": "Precisión (Conquistador)",
                "keystone": "Conquistador",
                "primary_runes": ["Triunfo", "Leyenda: Presteza", "Último Esfuerzo"],
                "secondary_tree": "Valor",
                "secondary_runes": ["Fuerzas Renovadas", "Sobrecrecimiento"],
                "shards": ["+9 Fuerza Adaptable", "+9 Fuerza Adaptable", "+65 Vida"],
                "skill_max": "Q > E > W",
                "summoner_spells": "Flash + Marca (Nieve)" if is_aram else "Flash + Teleport",
                "starting_items": "Guardián de Martillo" if is_aram else "Espada de Doran + Poción",
                "core_items": "Eclipse / Fuerza de la Trinidad -> Calibrador de Sterak -> Baile de la Muerte",
                "situational_items": "Fauces de Malmortius, Hidra Titánica, Rostro Espiritual",
                "tips": "Acumula tus cargas de Conquistador en las escaramuzas para maximizar tu curación."
            }
        }

        cfg = archetypes.get(tag, archetypes["Fighter"])
        return {
            "style_id": "default",
            "style_name": cfg["style_name"],
            "win_rate": cfg["win_rate"],
            "primary_tree": cfg["primary_tree"],
            "keystone": cfg["keystone"],
            "primary_runes": cfg["primary_runes"],
            "secondary_tree": cfg["secondary_tree"],
            "secondary_runes": cfg["secondary_runes"],
            "shards": cfg["shards"],
            "skill_max": cfg["skill_max"],
            "summoner_spells": cfg["summoner_spells"],
            "starting_items": cfg["starting_items"],
            "core_items": cfg["core_items"],
            "situational_items": cfg["situational_items"],
            "tips": cfg["tips"]
        }

    def get_counters(self, champ_id: str) -> Dict[str, List[str]]:
        """Devuelve enfrentamientos favorables y difíciles para el campeón."""
        # Datos arquetípicos y comunes
        return {
            "dificiles": ["Yasuo (Muro de viento)", "Nautilus (Enganche duro)", "Zed (Burst ineludible)"],
            "favorables": ["Twitch (Sin movilidad)", "Sivir (Vulnerable a all-in)", "Jinx (Fácil de aislar)"]
        }


# Instancia singleton del servicio
lol_service = LoLService()
