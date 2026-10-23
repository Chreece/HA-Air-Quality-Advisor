"""Final beta16 labels for general sources, Home hub and away cooldown."""
from __future__ import annotations
import json
from pathlib import Path

DETAIL = {
    "en": {
        "pollen": "All discovered pollen providers are selected on first setup; later explicit empty selections stay empty.",
        "hub": "Shown only when Announcement Hub is installed. Enabling it routes announcements through the Hub when available.",
        "ai": "Choose Home Assistant default, a conversation agent, or a data-capable Task AI entity. Task AI selections use ai_task.generate_data.",
        "language": "Languages come from the selected TTS provider. Region codes are shown only when that provider offers multiple variants of the same language.",
        "cooldown": "After a fresh occupied-room source becomes empty, wait this many minutes before applying Away. Unknown or stale occupancy never starts Away.",
    },
    "el": {
        "pollen": "Στην πρώτη ρύθμιση επιλέγονται όλοι οι διαθέσιμοι πάροχοι γύρης. Μετέπειτα ρητή κενή επιλογή παραμένει κενή.",
        "hub": "Εμφανίζεται μόνο όταν είναι εγκατεστημένο το Announcement Hub. Όταν ενεργοποιηθεί, οι ανακοινώσεις δρομολογούνται μέσω του Hub όταν είναι διαθέσιμο.",
        "ai": "Επίλεξε την προεπιλογή Home Assistant, conversation agent ή Task AI που υποστηρίζει δεδομένα. Το Task AI χρησιμοποιεί ai_task.generate_data.",
        "language": "Οι γλώσσες προέρχονται από τον επιλεγμένο πάροχο TTS. Ο κωδικός χώρας εμφανίζεται μόνο όταν ο πάροχος υποστηρίζει πολλές παραλλαγές της ίδιας γλώσσας.",
        "cooldown": "Όταν μια έγκυρη πηγή κατειλημμένων χώρων γίνει κενή, περίμενε τόσα λεπτά πριν εφαρμοστεί το Away. Άγνωστα ή παλιά δεδομένα δεν ενεργοποιούν Away.",
    },
    "de": {
        "pollen": "Beim ersten Einrichten werden alle gefundenen Pollenquellen vorausgewählt. Eine später bewusst leere Auswahl bleibt leer.",
        "hub": "Wird nur angezeigt, wenn Announcement Hub installiert ist. Aktiviert wird darüber geroutet, sobald der Hub verfügbar ist.",
        "ai": "Home-Assistant-Standard, Conversation-Agent oder datenfähige Task-AI wählen. Task AI verwendet ai_task.generate_data.",
        "language": "Sprachen stammen vom gewählten TTS-Anbieter. Regionscodes erscheinen nur bei mehreren Varianten derselben Sprache.",
        "cooldown": "Nach einer frisch bestätigten leeren Raumbelegung so viele Minuten warten, bevor Away gilt. Unbekannte oder veraltete Daten lösen Away nicht aus.",
    },
    "fr": {
        "pollen": "Au premier réglage, toutes les sources de pollen trouvées sont présélectionnées. Un choix vide explicite ultérieur reste vide.",
        "hub": "Affiché seulement si Announcement Hub est installé. Une fois activé, les annonces passent par le Hub lorsqu'il est disponible.",
        "ai": "Choisissez la valeur par défaut, un agent conversationnel ou une entité Task AI compatible données. Task AI utilise ai_task.generate_data.",
        "language": "Les langues proviennent du fournisseur TTS choisi. Le code régional n'apparaît que s'il existe plusieurs variantes d'une même langue.",
        "cooldown": "Après qu'une source valide de pièces occupées devient vide, attendez ce nombre de minutes avant Away. Les données inconnues ou anciennes ne déclenchent jamais Away.",
    },
    "es": {
        "pollen": "En la primera configuración se preseleccionan todas las fuentes de polen encontradas. Una selección vacía explícita posterior permanece vacía.",
        "hub": "Solo aparece si Announcement Hub está instalado. Al activarlo, los anuncios usan el Hub cuando está disponible.",
        "ai": "Elige el valor predeterminado, un agente de conversación o una entidad Task AI compatible con datos. Task AI usa ai_task.generate_data.",
        "language": "Los idiomas proceden del proveedor TTS seleccionado. El código regional solo aparece cuando hay varias variantes del mismo idioma.",
        "cooldown": "Cuando una fuente válida de habitaciones ocupadas queda vacía, espera estos minutos antes de aplicar Away. Datos desconocidos o antiguos no activan Away.",
    },
}


def apply_beta16_i18n(root: Path) -> None:
    vocab = json.loads((root / "compact_locales.json").read_text(encoding="utf-8"))
    files = sorted((root / "translations").glob("*.json"))
    if set(vocab) != {p.stem for p in files} or len(files) != 38:
        raise ValueError("beta16 requires all 38 locale catalogs")
    for path in [root / "strings.json", *files]:
        lang = "en" if path.name == "strings.json" else path.stem
        words = vocab[lang]
        doc = json.loads(path.read_text(encoding="utf-8"))
        legacy = doc.get("options", {}).get("step", {})
        pollen_block = legacy.get("pollen", {})
        delivery = legacy.get("delivery", {})
        specifics = DETAIL.get(lang)
        generic = {
            "pollen": f"{words['select']} · {words['pollen']} · {words['source']}",
            "hub": f"Announcement Hub · {words['automatic']} {words['control']}",
            "ai": f"AI · conversation.* / ai_task.* · {words['select']}",
            "language": f"TTS · {words['source']} · language",
            "cooldown": f"{words['house']} · Away · cooldown (min)",
        }
        detail = specifics or generic
        for scope in ("config", "options"):
            setup = doc.setdefault(scope, {}).setdefault("step", {}).setdefault("setup_general", {})
            data = setup.setdefault("data", {})
            desc = setup.setdefault("data_description", {})
            data["pollen_entities"] = pollen_block.get("data", {}).get(
                "pollen_entity", f"{words['pollen']} · {words['source']}")
            data["use_announcement_hub"] = delivery.get("data", {}).get(
                "use_announcement_hub", "Announcement Hub")
            data["general_away_cooldown_minutes"] = generic["cooldown"]
            data["language"] = delivery.get("data", {}).get("language", "TTS language")
            data["ai_conversation_agent"] = delivery.get("data", {}).get(
                "ai_conversation_agent", "AI provider")
            desc["pollen_entities"] = detail["pollen"]
            desc["use_announcement_hub"] = detail["hub"]
            desc["general_away_cooldown_minutes"] = detail["cooldown"]
            desc["language"] = detail["language"]
            desc["ai_conversation_agent"] = detail["ai"]
        doc.setdefault("entity", {}).setdefault("number", {})[
            "home_global_occupancy_away_cooldown_minutes"
        ] = {"name": generic["cooldown"]}
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
