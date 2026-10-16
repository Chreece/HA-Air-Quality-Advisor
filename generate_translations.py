"""Build HA's canonical strings.json and shipped UI translations."""
from __future__ import annotations
import json
from pathlib import Path

root = Path(__file__).parent / 'custom_components' / 'air_quality_advisor'
lang = {
'en': {
 'title':'Air Quality Advisor',
 'steps': [
  ('Areas', 'Areas with Window-class binary sensors are preselected during initial setup; covers are excluded. The detected window count appears beside each area. In reconfiguration, your existing selection is preserved, and areas with missing contacts are marked ⚠.', 'Areas to monitor'),
  ('Outdoor air quality', 'Choose one or more supported outdoor air-quality sensors. Valid high readings block ventilation. Unknown, stale or unavailable readings are ignored as blockers and shown separately as incomplete data.', 'Outdoor air-quality sensors'),
  ('Weather and warnings', 'Select weather providers and, optionally, weather-warning sensors. Rain, storms, excessive wind, extreme temperatures and active or unavailable warnings block opening. An unavailable selected provider is treated cautiously.', 'Weather entities'),
  ('Announcements (optional)', 'The recommendation sensor always works without announcements. Enable notifications and/or speech only if wanted. Announcement Hub, when enabled and available, handles room-aware routing. For standalone output, choose notification targets and a TTS engine with players.', 'Output language (automatic uses Home Assistant language)'),
  ('Advanced thresholds', 'These limits apply to instantaneous sensor values and are configurable guidance, not health or exposure standards. AQI assumes the US 0–500 scale by default; change the limits for any differently scaled provider.', 'Thresholds'),
 ],
 'fields': {'weather_warnings':'Weather warning sensors (optional)','use_announcement_hub':'Use Announcement Hub if available', 'automatic_tts':'Speak new recommendations automatically', 'automatic_notifications':'Notify about new recommendations automatically', 'notify_entities':'Direct notification entities', 'tts_engine':'Direct TTS engine', 'media_players':'Direct TTS media players', 'language':'Language'},
 'errors':{'invalid_outdoor':'Select at least one supported outdoor sensor.', 'no_outdoor':'No supported outdoor sensor was found. Add an AQI, CO₂, PM2.5, PM10 or VOC entity with compatible units first.', 'invalid_weather':'Select at least one weather entity.', 'invalid_warning':'A weather-warning sensor is no longer supported.', 'missing_notify':'Enable Announcement Hub or choose a notification entity.', 'missing_tts':'Enable Announcement Hub or select a TTS engine and media player.', 'temperature_range':'The minimum temperature must be lower than the maximum.', 'no_areas':'Select at least one area.', 'no_window_areas':'No areas with window contacts were found. Assign a binary sensor with device class Window to a Home Assistant area; covers do not count.', 'invalid_areas':'An area is no longer available as a window area.'},
 'entity':'Window recommendations', 'status':{'open':'Open windows', 'close':'Close windows', 'idle':'No action', 'blocked':'Outdoor conditions not suitable'},
 'service':'Announce air-quality recommendations', 'service_description':'Speak and/or notify the currently recommended windows and reasons. Choose a language independently for each call.',
 'service_fields':{'language':'Override message language', 'channels':'Message channels', 'areas':'Only these areas (optional)'},
},
'de': {
 'title':'Luftqualitätsberater',
 'steps': [
  ('Bereiche', 'Bei der Ersteinrichtung werden Bereiche mit Binärsensoren der Geräteklasse Fenster vorausgewählt. Cover zählen nicht. Bestehende Auswahlen bleiben bei Änderungen erhalten; fehlende Fensterkontakte erscheinen mit ⚠.', 'Zu überwachende Bereiche'),
  ('Außenluftqualität', 'Wähle unterstützte Außenluftsensoren. Erhöhte gültige Messwerte verhindern Lüftungsempfehlungen. Unbekannte, veraltete oder nicht verfügbare Werte gelten nicht als Gefahr, werden aber als fehlende Daten angezeigt.', 'Außenluftsensoren'),
  ('Wetter und Warnungen', 'Wähle Wetterentitäten und optional Wetterwarnsensoren. Regen, Sturm, starker Wind, extreme Temperaturen und aktive/unbekannte Warnungen verhindern Empfehlungen zum Öffnen.', 'Wetterentitäten'),
  ('Ansagen (optional)', 'Der Empfehlungssensor funktioniert auch ohne Ansagen. Benachrichtigungen und Sprache sind optional. Announcement Hub übernimmt gegebenenfalls die Raumzuordnung; sonst bitte direkte Ausgaben wählen.', 'Ausgabesprache (automatisch: Home Assistant)'),
  ('Erweiterte Grenzwerte', 'Diese Grenzwerte beziehen sich auf Momentanmessungen und sind keine medizinischen Expositionsgrenzen. AQI verwendet standardmäßig die US-Skala 0–500.', 'Grenzwerte'),
 ],
 'fields': {'weather_warnings':'Wetterwarnsensoren (optional)', 'use_announcement_hub':'Announcement Hub verwenden, falls vorhanden', 'automatic_tts':'Neue Empfehlungen automatisch sprechen', 'automatic_notifications':'Neue Empfehlungen automatisch melden', 'notify_entities':'Direkte Benachrichtigungsentitäten', 'tts_engine':'Direkte TTS-Engine', 'media_players':'Direkte TTS-Mediaplayer', 'language':'Sprache'},
 'errors':{'invalid_outdoor':'Mindestens einen unterstützten Außenluftsensor auswählen.', 'no_outdoor':'Kein unterstützter Außenluftsensor erkannt. Zuerst eine passende AQI-, CO₂-, Feinstaub- oder VOC-Entität hinzufügen.', 'invalid_weather':'Mindestens eine Wetterentität auswählen.', 'invalid_warning':'Wetterwarnsensor wird nicht mehr unterstützt.', 'missing_notify':'Announcement Hub oder eine Benachrichtigungsentität wählen.', 'missing_tts':'Announcement Hub oder TTS-Engine und Mediaplayer wählen.', 'temperature_range':'Mindesttemperatur muss unter der Höchsttemperatur liegen.', 'no_areas':'Mindestens einen Bereich auswählen.', 'no_window_areas':'Keine Fensterkontakte erkannt. Weise einem Bereich einen Binärsensor der Geräteklasse Fenster zu; Cover zählen nicht.', 'invalid_areas':'Ein Bereich ist nicht mehr als Fensterbereich verfügbar.'},
 'entity':'Fensterempfehlungen', 'status':{'open':'Fenster öffnen', 'close':'Fenster schließen', 'idle':'Keine Aktion', 'blocked':'Außenbedingungen ungeeignet'},
 'service':'Luftqualitäts-Empfehlungen ausgeben', 'service_description':'Aktuelle Fensterempfehlungen mit Begründung sprechen und/oder melden. Sprache bei jedem Aufruf wählbar.',
 'service_fields':{'language':'Nachrichtensprache überschreiben', 'channels':'Ausgabekanäle', 'areas':'Nur diese Bereiche (optional)'},
},
'el': {
 'title':'Σύμβουλος ποιότητας αέρα',
 'steps': [
  ('Χώροι', 'Στην αρχική ρύθμιση προεπιλέγονται οι χώροι με δυαδικούς αισθητήρες κατηγορίας «Παράθυρο». Τα cover δεν υπολογίζονται. Στην επαναρύθμιση διατηρούνται οι επιλογές και οι χώροι χωρίς επαφή παραθύρου σημειώνονται με ⚠.', 'Χώροι προς παρακολούθηση'),
  ('Ποιότητα εξωτερικού αέρα', 'Επίλεξε υποστηριζόμενους αισθητήρες εξωτερικού αέρα. Οι έγκυρες υψηλές τιμές εμποδίζουν το άνοιγμα. Άγνωστες, παλιές ή μη διαθέσιμες τιμές δεν θεωρούνται επικίνδυνες, αλλά εμφανίζονται ως ελλιπή δεδομένα.', 'Αισθητήρες εξωτερικού αέρα'),
  ('Καιρός και προειδοποιήσεις', 'Επίλεξε οντότητες καιρού και, προαιρετικά, αισθητήρες προειδοποιήσεων. Βροχή, καταιγίδες, άνεμος, ακραίες θερμοκρασίες ή άγνωστες/ενεργές προειδοποιήσεις εμποδίζουν το άνοιγμα.', 'Οντότητες καιρού'),
  ('Ανακοινώσεις (προαιρετικά)', 'Ο αισθητήρας συστάσεων λειτουργεί και χωρίς ανακοινώσεις. Ενεργοποίησε ειδοποιήσεις ή ομιλία αν το επιθυμείς. Το Announcement Hub, εφόσον υπάρχει, αναλαμβάνει τη δρομολόγηση ανά δωμάτιο.', 'Γλώσσα εξόδου (αυτόματη: Home Assistant)'),
  ('Προχωρημένα όρια', 'Τα όρια εφαρμόζονται σε στιγμιαίες μετρήσεις, όχι σε ιατρικά πρότυπα έκθεσης. Ο AQI χρησιμοποιεί αρχικά την κλίμακα ΗΠΑ 0–500· προσαρμόστε τον σε άλλες κλίμακες.', 'Όρια'),
 ],
 'fields':{'weather_warnings':'Αισθητήρες προειδοποιήσεων καιρού (προαιρετικά)', 'use_announcement_hub':'Χρήση Announcement Hub όταν υπάρχει', 'automatic_tts':'Αυτόματες φωνητικές συστάσεις', 'automatic_notifications':'Αυτόματες ειδοποιήσεις συστάσεων', 'notify_entities':'Οντότητες άμεσων ειδοποιήσεων', 'tts_engine':'Μηχανή άμεσης ομιλίας', 'media_players':'Συσκευές αναπαραγωγής ομιλίας', 'language':'Γλώσσα'},
 'errors':{'invalid_outdoor':'Επέλεξε τουλάχιστον έναν υποστηριζόμενο εξωτερικό αισθητήρα.', 'no_outdoor':'Δεν βρέθηκε συμβατός εξωτερικός αισθητήρας. Πρόσθεσε πρώτα μία οντότητα AQI, CO₂, PM2.5, PM10 ή VOC.', 'invalid_weather':'Επέλεξε τουλάχιστον μία οντότητα καιρού.', 'invalid_warning':'Ο αισθητήρας προειδοποίησης δεν υποστηρίζεται πλέον.', 'missing_notify':'Επίλεξε Announcement Hub ή μια οντότητα ειδοποιήσεων.', 'missing_tts':'Επίλεξε Announcement Hub ή μηχανή ομιλίας και media player.', 'temperature_range':'Η ελάχιστη θερμοκρασία πρέπει να είναι μικρότερη της μέγιστης.', 'no_areas':'Επίλεξε τουλάχιστον έναν χώρο.', 'no_window_areas':'Δεν εντοπίστηκαν επαφές παραθύρων. Αντιστοίχισε σε χώρο έναν δυαδικό αισθητήρα κατηγορίας «Παράθυρο». Τα cover δεν υπολογίζονται.', 'invalid_areas':'Κάποιος χώρος δεν είναι πλέον διαθέσιμος ως χώρος με παράθυρο.'},
 'entity':'Συστάσεις παραθύρων', 'status':{'open':'Άνοιγμα παραθύρων', 'close':'Κλείσιμο παραθύρων', 'idle':'Δεν απαιτείται ενέργεια', 'blocked':'Ακατάλληλες εξωτερικές συνθήκες'},
 'service':'Ανακοίνωση συστάσεων αέρα', 'service_description':'Προφορική ή οπτική ανακοίνωση προτεινόμενων παραθύρων και αιτιών, με ξεχωριστή γλώσσα ανά ενέργεια.',
 'service_fields':{'language':'Αλλαγή γλώσσας μηνύματος', 'channels':'Κανάλια μηνυμάτων', 'areas':'Μόνο αυτοί οι χώροι (προαιρετικά)'},
},
}
lang['fr'] = {
 'title':'Conseiller qualité de l’air',
 'steps': [
  ('Pièces', 'À la première configuration, les zones dotées de capteurs binaires de classe Fenêtre sont présélectionnées. Les covers sont exclus. Les sélections existantes sont conservées ; les zones sans contact sont marquées ⚠.', 'Zones à surveiller'),
  ('Qualité de l’air extérieur', 'Sélectionnez des capteurs extérieurs compatibles. Une mesure élevée valide bloque la ventilation. Les valeurs inconnues, périmées ou indisponibles ne sont pas considérées dangereuses, mais sont signalées comme données manquantes.', 'Capteurs extérieurs'),
  ('Météo et alertes', 'Choisissez les entités météo et éventuellement les alertes. Pluie, vent fort, températures extrêmes et alertes actives ou inconnues empêchent l’ouverture.', 'Entités météo'),
  ('Annonces (facultatif)', 'Le capteur fonctionne sans annonces. Activez la voix ou les notifications uniquement si nécessaire. Announcement Hub peut gérer les destinations par pièce.', 'Langue de sortie (auto : Home Assistant)'),
  ('Seuils avancés', 'Ces seuils concernent les valeurs instantanées, pas des normes médicales. Par défaut, l’AQI utilise l’échelle américaine 0–500.', 'Seuils'),
 ],
 'fields': {'weather_warnings':'Capteurs d’alerte météo (facultatif)', 'use_announcement_hub':'Utiliser Announcement Hub s’il est disponible', 'automatic_tts':'Annoncer automatiquement les nouvelles recommandations', 'automatic_notifications':'Notifier automatiquement les nouvelles recommandations', 'notify_entities':'Destinations de notification directes', 'tts_engine':'Moteur TTS direct', 'media_players':'Lecteurs média TTS directs', 'language':'Langue'},
 'errors':{'invalid_outdoor':'Sélectionnez au moins un capteur extérieur pris en charge.', 'no_outdoor':'Aucun capteur extérieur compatible détecté.', 'invalid_weather':'Choisissez au moins une entité météo.', 'invalid_warning':'Capteur d’alerte météo non pris en charge.', 'missing_notify':'Activez Announcement Hub ou sélectionnez une notification.', 'missing_tts':'Activez Announcement Hub ou sélectionnez un moteur TTS et un lecteur.', 'temperature_range':'La température minimale doit être inférieure à la maximale.', 'no_areas':'Sélectionnez au moins une zone.', 'no_window_areas':'Aucun contact de fenêtre détecté. Attribuez un capteur binaire de classe Fenêtre à une zone ; les covers sont exclus.', 'invalid_areas':'Une zone n’est plus disponible parmi les zones avec fenêtre.'},
 'entity':'Recommandations de fenêtres', 'status':{'open':'Ouvrir les fenêtres', 'close':'Fermer les fenêtres', 'idle':'Aucune action', 'blocked':'Conditions extérieures défavorables'},
 'service':'Annoncer les recommandations de qualité de l’air', 'service_description':'Annonce vocale ou notification des fenêtres et motifs, avec langue propre à chaque appel.',
 'service_fields':{'language':'Langue du message', 'channels':'Canaux de sortie', 'areas':'Seulement ces zones (facultatif)'},
}
lang['es'] = {
 'title':'Asesor de calidad del aire',
 'steps': [
  ('Áreas', 'En la configuración inicial se preseleccionan las áreas con sensores binarios de clase Ventana. No se incluyen covers. Al reconfigurar se conservan las selecciones existentes y las áreas sin contacto se marcan con ⚠.', 'Áreas supervisadas'),
  ('Calidad del aire exterior', 'Selecciona sensores exteriores compatibles. Una lectura válida por encima del límite bloquea la ventilación. Las lecturas desconocidas, antiguas o no disponibles son neutrales y se muestran como datos incompletos.', 'Sensores de aire exterior'),
  ('Tiempo y alertas', 'Selecciona entidades meteorológicas y alertas opcionales. Lluvia, viento fuerte, temperaturas extremas y avisos activos o desconocidos impiden abrir.', 'Entidades meteorológicas'),
  ('Anuncios (opcional)', 'El sensor funciona sin anuncios. Activa voz y avisos solo si deseas. Announcement Hub puede gestionar la distribución por habitación.', 'Idioma de salida (auto: Home Assistant)'),
  ('Umbrales avanzados', 'Los límites se aplican a lecturas instantáneas, no a normas médicas. El AQI predeterminado usa la escala estadounidense 0–500.', 'Umbrales'),
 ],
 'fields': {'weather_warnings':'Sensores de alerta meteorológica (opcional)', 'use_announcement_hub':'Usar Announcement Hub si está disponible', 'automatic_tts':'Anunciar automáticamente recomendaciones nuevas', 'automatic_notifications':'Enviar automáticamente avisos nuevos', 'notify_entities':'Destinos directos de notificación', 'tts_engine':'Motor TTS directo', 'media_players':'Reproductores TTS directos', 'language':'Idioma'},
 'errors':{'invalid_outdoor':'Selecciona al menos un sensor exterior compatible.', 'no_outdoor':'No hay sensores exteriores compatibles.', 'invalid_weather':'Selecciona al menos una entidad meteorológica.', 'invalid_warning':'Alerta meteorológica no compatible.', 'missing_notify':'Activa Announcement Hub o selecciona notificaciones.', 'missing_tts':'Activa Announcement Hub o selecciona un motor TTS y reproductor.', 'temperature_range':'La temperatura mínima debe ser inferior a la máxima.', 'no_areas':'Selecciona al menos un área.', 'no_window_areas':'No se encontraron contactos de ventana. Asigna un sensor binario de clase Ventana a un área; los covers no cuentan.', 'invalid_areas':'Un área ya no está disponible como área con ventanas.'},
 'entity':'Recomendaciones de ventanas', 'status':{'open':'Abrir ventanas', 'close':'Cerrar ventanas', 'idle':'Sin acción', 'blocked':'Condiciones exteriores desfavorables'},
 'service':'Anunciar recomendaciones de aire', 'service_description':'Comunicar ventanas y razones por voz o notificación, con idioma por acción.',
 'service_fields':{'language':'Idioma del mensaje', 'channels':'Canales de salida', 'areas':'Solo estas áreas (opcional)'},
}
threshold_labels = {
 'outdoor_aqi':'Maximum outdoor AQI', 'outdoor_co2':'Maximum outdoor CO₂ (ppm)',
 'outdoor_pm25':'Maximum outdoor PM2.5 (µg/m³)', 'outdoor_pm10':'Maximum outdoor PM10 (µg/m³)',
 'outdoor_voc':'Maximum outdoor VOC (µg/m³)', 'outdoor_voc_parts':'Maximum outdoor VOC (ppb)',
 'indoor_aqi':'Indoor AQI triggering ventilation', 'indoor_co2':'Indoor CO₂ triggering ventilation (ppm)',
 'indoor_pm25':'Indoor PM2.5 triggering ventilation (µg/m³)',
 'indoor_pm10':'Indoor PM10 triggering ventilation (µg/m³)',
 'indoor_voc':'Indoor VOC triggering ventilation (µg/m³)',
 'indoor_voc_parts':'Indoor VOC triggering ventilation (ppb)',
 'indoor_humidity':'Indoor humidity triggering ventilation (%)',
 'min_outdoor_temp':'Minimum outdoor temperature (°C)', 'max_outdoor_temp':'Maximum outdoor temperature (°C)',
 'max_outdoor_humidity':'Maximum outdoor humidity (%)', 'max_wind_kmh':'Maximum wind speed (km/h)',
 'max_age_minutes':'Maximum age of any outdoor reading (minutes)',
}
fields = ['areas','outdoor_sensors','weather_entities','language']
stepids = ['areas','outdoor','weather','delivery','thresholds']
for code,v in lang.items():
 steps = {}
 for i, sid in enumerate(stepids):
  name, desc, primary = v['steps'][i]
  stepdata = {fields[i]:primary} if i < 4 else threshold_labels
  if sid=='weather':stepdata['weather_warnings']=v['fields']['weather_warnings']
  if sid=='delivery':stepdata = {key:v['fields'][key] for key in ['language','automatic_tts','automatic_notifications','use_announcement_hub','notify_entities','tts_engine','media_players']}
  steps[sid] = {'title':name,'description':desc,'data':stepdata}
  if sid in ('areas','outdoor','weather','delivery'):
   helps = {
    'areas':'Window-class binary sensors only; covers are excluded. New setups preselect all detected areas; existing selections are preserved when reconfiguring. ⚠ marks a missing contact.',
    'outdoor_sensors':'Choose genuine outdoor sensors. Available readings above limits block opening; unknown, unavailable or stale readings are reported, not classified as unsafe.',
    'weather_entities':'At least one weather provider. Rain, storms and extreme wind/temperature block opening.',
    'weather_warnings':'Optional. Active and unavailable selected warnings block window opening.',
    'language':'Choose auto for Home Assistant’s language; the manual action can override it.',
    'automatic_tts':'Disabled by default. New open recommendations need 90 seconds of stable conditions.',
    'automatic_notifications':'Disabled by default. No repeated alerts on every sensor reading.',
    'use_announcement_hub':'Uses the existing room-aware routing when Announcement Hub is installed.',
    'notify_entities':'Direct outputs when Announcement Hub is not used.',
    'tts_engine':'Direct speech provider when Announcement Hub is not used.',
    'media_players':'Direct audio destinations; room assignment controls targeting.',
   }
   steps[sid]['data_description']={field:helps.get(field, stepdata[field]) for field in stepdata}
 errors = v['errors']
 section = {'step':steps,'error':errors, 'abort':{'already_configured':'Air Quality Advisor is already configured.'}}
 opts={
   'step':{
     'init':{
       'title':v['title'],
       'menu_options':{
         'areas':v['steps'][0][0]+' / '+v['steps'][1][0]+' / '+v['steps'][2][0],
         'delivery':v['steps'][3][0],
         'thresholds':v['steps'][4][0],
       },
     },
     **steps,
   },
   'error':errors,
 }
 data={
   'title':v['title'],
   'config':section,
   'options':opts,
   'entity':{'sensor':{'recommendation':{'name':v['entity'],'state':v['status']}}},
   'services':{'announce':{'name':v['service'],'description':v['service_description'],'fields':{
       key:{'name':label,'description':label} for key,label in v['service_fields'].items()
   }}},
 }
 name='strings.json' if code=='en' else f'translations/{code}.json'
 (root/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 # HA expects en.json alongside strings.json as well.
 if code=='en':(root/'translations/en.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
