"""Final generator pass for the minimal per-area environment entities."""
from __future__ import annotations

import json
from pathlib import Path

# Translatable only for entities owned by this integration. Raw third-party
# climate/sensor entity names remain untouched in every language.
NAMES = {
    "en": ("Environment overview", "Surface humidity (calculated)"),
    "el": ("Επισκόπηση περιβάλλοντος", "Υγρασία επιφάνειας (υπολογισμένη)"),
    "de": ("Raumklima-Übersicht", "Oberflächenfeuchte (berechnet)"),
    "fr": ("Aperçu de l'environnement", "Humidité de surface (calculée)"),
    "es": ("Resumen ambiental", "Humedad superficial (calculada)"),
    "ar": ("نظرة عامة على البيئة", "رطوبة السطح (محسوبة)"),
    "bg": ("Преглед на средата", "Повърхностна влажност (изчислена)"),
    "bn": ("পরিবেশের সারসংক্ষেপ", "পৃষ্ঠের আর্দ্রতা (গণনাকৃত)"),
    "cs": ("Přehled prostředí", "Povrchová vlhkost (vypočtená)"),
    "da": ("Miljøoversigt", "Overfladefugtighed (beregnet)"),
    "fa": ("نمای کلی محیط", "رطوبت سطح (محاسبه‌شده)"),
    "fi": ("Ympäristön yhteenveto", "Pintakosteus (laskettu)"),
    "he": ("סקירת הסביבה", "לחות פני השטח (מחושבת)"),
    "hi": ("पर्यावरण अवलोकन", "सतह की आर्द्रता (गणना)"),
    "hr": ("Pregled okoliša", "Površinska vlažnost (izračunata)"),
    "hu": ("Környezeti áttekintés", "Felületi páratartalom (számított)"),
    "id": ("Ringkasan lingkungan", "Kelembapan permukaan (terhitung)"),
    "it": ("Panoramica ambiente", "Umidità superficiale (calcolata)"),
    "ja": ("環境の概要", "表面湿度（計算値）"),
    "ko": ("환경 개요", "표면 습도(계산값)"),
    "nb": ("Miljøoversikt", "Overflatefuktighet (beregnet)"),
    "nl": ("Omgevingsoverzicht", "Oppervlaktevochtigheid (berekend)"),
    "pl": ("Przegląd środowiska", "Wilgotność powierzchni (obliczona)"),
    "pt": ("Visão geral do ambiente", "Humidade da superfície (calculada)"),
    "pt-BR": ("Visão geral do ambiente", "Umidade da superfície (calculada)"),
    "ro": ("Prezentare generală a mediului", "Umiditate de suprafață (calculată)"),
    "ru": ("Обзор среды", "Влажность поверхности (расчётная)"),
    "sk": ("Prehľad prostredia", "Povrchová vlhkosť (vypočítaná)"),
    "sr": ("Преглед окружења", "Влажност површине (израчуната)"),
    "sv": ("Miljööversikt", "Ytfuktighet (beräknad)"),
    "ta": ("சுற்றுச்சூழல் மேலோட்டம்", "மேற்பரப்பு ஈரப்பதம் (கணக்கிடப்பட்டது)"),
    "th": ("ภาพรวมสภาพแวดล้อม", "ความชื้นพื้นผิว (คำนวณ)"),
    "tr": ("Ortam özeti", "Yüzey nemi (hesaplanan)"),
    "uk": ("Огляд середовища", "Вологість поверхні (розрахункова)"),
    "ur": ("ماحول کا جائزہ", "سطح کی نمی (حساب شدہ)"),
    "vi": ("Tổng quan môi trường", "Độ ẩm bề mặt (tính toán)"),
    "zh-Hans": ("环境概览", "表面湿度（计算值）"),
    "zh-Hant": ("環境概覽", "表面濕度（計算值）"),
}


def apply_area_entities_i18n(root: Path) -> None:
    translations = root / "translations"
    for path in (root / "strings.json", *sorted(translations.glob("*.json"))):
        locale = "en" if path.name == "strings.json" else path.stem
        names = NAMES.get(locale)
        if names is None:
            raise ValueError(f"Missing area entity translations: {locale}")
        document = json.loads(path.read_text(encoding="utf-8"))
        entities = document.setdefault("entity", {}).setdefault("sensor", {})
        entities["area_overview"] = {"name": names[0]}
        entities["area_surface_humidity"] = {"name": names[1]}
        path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
