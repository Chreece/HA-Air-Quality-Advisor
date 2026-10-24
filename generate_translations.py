"""Build HA's canonical strings.json and shipped UI translations."""
from __future__ import annotations
import json
from pathlib import Path

root = Path(__file__).parent / 'custom_components' / 'environment_manager'
lang = {
'en': {
 'title':'Home Environment Manager',
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
# Dedicated window-contact review precedes area discovery. The picker includes
# every Window-class binary sensor, while only likely virtual/auxiliary signals
# are suggested for exclusion. Users remain authoritative.
window_exclusion_text = {
 'en': (
  'Window sensor exclusions',
  'Review window-class binary sensors. ⚠ marks likely virtual or auxiliary signals (for example window-open detection on a radiator thermostat); those are preselected for exclusion. Uncheck any real window contact. Your choices are saved and take priority over future suggestions.',
  'Window entities to exclude',
  'The menu lists every Window-class binary sensor with its room and entity ID. Selected entities will not count as windows for room selection, recommendations or the dashboard. An empty selection includes them all.',
  'One or more excluded entities are no longer in the list.'
 ),
 'de': (
  'Fenstersensoren ausschließen',
  'Prüfe die Binärsensoren der Klasse Fenster. ⚠ markiert vermutlich virtuelle oder zusätzliche Signale (z. B. Fenster-offen-Erkennung eines Heizkörperthermostats), die zum Ausschließen vorausgewählt sind. Echte Fensterkontakte einfach abwählen. Deine Auswahl bleibt gespeichert.',
  'Auszuschließende Fenster-Entitäten',
  'Alle Fenster-Binärsensoren mit Raum und Entitäts-ID. Markierte Sensoren werden bei Bereichen, Empfehlungen und Dashboard nicht als Fenster gezählt. Ohne Auswahl werden alle berücksichtigt.',
  'Mindestens eine ausgeschlossene Entität ist nicht mehr auswählbar.'
 ),
 'el': (
  'Εξαίρεση αισθητήρων παραθύρων',
  'Έλεγξε όλους τους δυαδικούς αισθητήρες κατηγορίας «Παράθυρο». Το ⚠ δείχνει πιθανές εικονικές ή βοηθητικές ενδείξεις (π.χ. ανίχνευση ανοιχτού παραθύρου θερμοστάτη), προεπιλεγμένες για εξαίρεση. Αποεπίλεξε οποιαδήποτε πραγματική επαφή παραθύρου. Οι επιλογές σου διατηρούνται.',
  'Οντότητες παραθύρων προς εξαίρεση',
  'Εμφανίζονται όλοι οι αισθητήρες με χώρο και αναγνωριστικό οντότητας. Οι επιλεγμένοι αγνοούνται στους χώρους, στις συστάσεις και στον πίνακα. Κενή επιλογή σημαίνει καμία εξαίρεση.',
  'Μία ή περισσότερες εξαιρούμενες οντότητες δεν είναι διαθέσιμες στη λίστα.'
 ),
 'fr': (
  'Exclure des capteurs de fenêtre',
  'Vérifiez les capteurs binaires de classe Fenêtre. ⚠ signale les indicateurs probablement virtuels ou auxiliaires (p. ex. détection de fenêtre ouverte d’un thermostat), présélectionnés pour exclusion. Décochez les véritables contacts. Vos choix sont conservés.',
  'Entités de fenêtre à exclure',
  'Tous les capteurs de fenêtre, avec leur pièce et leur identifiant. Les entités sélectionnées sont ignorées dans les pièces, recommandations et le tableau de bord. Une sélection vide conserve tous les capteurs.',
  'Une ou plusieurs entités exclues ne figurent plus dans la liste.'
 ),
 'es': (
  'Excluir sensores de ventana',
  'Revisa los sensores binarios de clase Ventana. ⚠ indica señales probablemente virtuales o auxiliares (como detección de ventana abierta de un termostato), preseleccionadas para excluir. Desmarca cualquier contacto real. Tus elecciones se guardan.',
  'Entidades de ventana que se excluyen',
  'Se muestran todos los sensores con su área e ID. Los seleccionados no cuentan en áreas, recomendaciones ni panel. Sin selección se incluyen todos.',
  'Una o más entidades excluidas ya no aparecen entre las opciones.'
 ),
}
for language, copy in window_exclusion_text.items():
 lang[language]['steps'].insert(0, copy[:3])
 lang[language]['fields']['excluded_window_entities'] = copy[2]
 lang[language]['errors']['invalid_window_exclusions'] = copy[4]


# One room-specific picker per monitored area; options always follow the same wizard.
# Each locale supplies its own instructions and field descriptions.
indoor_step_text = json.loads("{\"en\":[\"Indoor air quality exclusions\",\"Room: {area_name} ({position}/{total}). Choose the air-quality and humidity sensors to EXCLUDE from this room. Each choice identifies its device, entity name and ID. Leave everything unselected to monitor all supported sensors.\",\"Sensors to exclude in this room\",\"Selected sensors are ignored in recommendations and the dashboard for this room only. Humidity, CO₂, AQI, PM2.5, PM10 and VOC sensors are supported. An empty selection keeps them all.\",\"A selected indoor sensor is not in this room’s supported list.\",\"Edit advanced thresholds after announcements (optional)\",\"If enabled, an extra page lets you edit measurement and weather thresholds. Otherwise finish with your saved thresholds unchanged.\"],\"de\":[\"Raumluftsensoren ausschließen\",\"Raum: {area_name} ({position}/{total}). Wähle Luftqualitäts- und Feuchtesensoren, die in diesem Raum AUSGESCHLOSSEN werden sollen. Angezeigt werden Gerätename, Entitätsname und ID. Ohne Auswahl bleiben alle unterstützten Sensoren aktiv.\",\"In diesem Raum auszuschließende Sensoren\",\"Ausgewählte Sensoren werden nur für diesen Raum bei Empfehlungen und im Dashboard ignoriert. Unterstützt: Luftfeuchtigkeit, CO₂, AQI, PM2.5, PM10 und VOC.\",\"Ein ausgewählter Sensor ist für diesen Raum nicht verfügbar.\",\"Erweiterte Grenzwerte danach bearbeiten (optional)\",\"Aktivieren, um nach den Ansagen die Grenzwerte anzupassen. Andernfalls bleiben die gespeicherten Werte erhalten.\"],\"el\":[\"Εξαίρεση αισθητήρων εσωτερικού αέρα\",\"Χώρος: {area_name} ({position}/{total}). Επίλεξε τους αισθητήρες ποιότητας αέρα και υγρασίας που θέλεις να ΕΞΑΙΡΕΘΟΥΝ από αυτόν τον χώρο. Εμφανίζονται όνομα συσκευής, όνομα οντότητας και ID. Χωρίς επιλογή χρησιμοποιούνται όλοι οι υποστηριζόμενοι αισθητήρες.\",\"Αισθητήρες προς εξαίρεση σε αυτόν τον χώρο\",\"Οι επιλεγμένοι αισθητήρες αγνοούνται στις συστάσεις και στον πίνακα μόνο για αυτόν τον χώρο. Υποστηρίζονται υγρασία, CO₂, AQI, PM2.5, PM10 και VOC.\",\"Ένας επιλεγμένος αισθητήρας δεν υποστηρίζεται σε αυτόν τον χώρο.\",\"Επεξεργασία προχωρημένων ορίων στη συνέχεια (προαιρετικά)\",\"Ενεργοποίησέ το για να τροποποιήσεις τα όρια μετά τις ανακοινώσεις. Διαφορετικά διατηρούνται τα αποθηκευμένα όρια.\"],\"fr\":[\"Exclure des capteurs d’air intérieur\",\"Pièce : {area_name} ({position}/{total}). Sélectionnez les capteurs de qualité de l’air ou d’humidité à EXCLURE de cette pièce. Chaque entrée affiche le nom de l’appareil, le nom de l’entité et son ID. Laissez vide pour surveiller tous les capteurs compatibles.\",\"Capteurs à exclure pour cette pièce\",\"Ces capteurs seront ignorés pour cette pièce dans les recommandations et le tableau de bord. Humidité, CO₂, AQI, PM2.5, PM10 et COV sont pris en charge.\",\"Un capteur sélectionné n’est pas compatible avec cette pièce.\",\"Modifier ensuite les seuils avancés (facultatif)\",\"Activez cette option pour modifier les seuils après les annonces ; sinon les valeurs actuelles sont conservées.\"],\"es\":[\"Excluir sensores de aire interior\",\"Habitación: {area_name} ({position}/{total}). Selecciona los sensores de calidad del aire y humedad que deseas EXCLUIR de esta habitación. Se muestran dispositivo, nombre de entidad e ID. Deja la selección vacía para usar todos los sensores compatibles.\",\"Sensores que se excluyen en esta habitación\",\"Se ignorarán únicamente en esta habitación al calcular recomendaciones y mostrar el panel. Son compatibles humedad, CO₂, AQI, PM2.5, PM10 y COV.\",\"Un sensor seleccionado no es compatible con esta habitación.\",\"Editar límites avanzados después (opcional)\",\"Actívalo para editar los límites después de anuncios. Si no, se conservarán los actuales.\"]}")
for language, item in indoor_step_text.items():
    lang[language]['steps'].insert(2, tuple(item[:3]))
    lang[language]['fields']['excluded_indoor_entities'] = item[2]
    lang[language]['errors']['invalid_indoor_exclusions'] = item[4]

threshold_labels = {
 'outdoor_aqi':'Maximum outdoor AQI', 'outdoor_co2':'Maximum outdoor CO₂ (ppm)',
 'outdoor_pm25':'Maximum outdoor PM2.5 (µg/m³)', 'outdoor_pm10':'Maximum outdoor PM10 (µg/m³)',
 'outdoor_voc':'Maximum outdoor VOC (µg/m³)', 'outdoor_voc_parts':'Maximum outdoor VOC (ppb)',
 'outdoor_no2':'Outdoor NO₂ operational screening (µg/m³)',
 'outdoor_o3':'Outdoor O₃ operational screening (µg/m³)',
 'outdoor_so2':'Outdoor SO₂ operational screening (µg/m³)',
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
fields = ['excluded_window_entities','areas','excluded_indoor_entities','outdoor_sensors','weather_entities','language']
stepids = ['window_sensors','areas','indoor_sensors','outdoor','weather','delivery','thresholds']
menu_stepids = ['areas','window_sensors','indoor_sensors','outdoor','weather','delivery','thresholds']
initial_stepids = menu_stepids  # Form navigation begins with Rooms too.

area_descriptions = {
 'en':'First select the rooms to monitor. Rooms with Window-class binary sensors are preselected; covers do not count. Next, review window-sensor exclusions. If these remove all usable contacts from a selected room, you can review your rooms again.',
 'de':'Wähle zuerst die zu überwachenden Räume. Räume mit Fenstersensoren (Binärsensor, Geräteklasse Fenster) sind vorausgewählt; Cover zählen nicht. Danach prüfst du die Sensorausschlüsse. Räume ohne verbleibenden Kontakt kannst du erneut auswählen.',
 'el':'Πρώτα επίλεξε τους χώρους παρακολούθησης. Προεπιλέγονται όσοι έχουν δυαδικό αισθητήρα κατηγορίας «Παράθυρο» (όχι cover). Έπειτα έλεγξε τις εξαιρέσεις. Αν ένας χώρος μείνει χωρίς ενεργή επαφή παραθύρου, θα επανεξετάσεις την επιλογή χώρων.',
 'fr':'Choisissez d’abord les pièces à surveiller. Celles avec un capteur binaire de classe Fenêtre sont présélectionnées ; les volets ne comptent pas. Examinez ensuite les exclusions. Si une pièce n’a plus de contact utilisable, révisez la sélection.',
 'es':'Primero selecciona las habitaciones. Se preseleccionan las que tienen sensores binarios de clase Ventana; las cubiertas no cuentan. Después revisa las exclusiones. Si una habitación se queda sin contactos útiles, vuelve a revisar la selección.',
}
area_hints = {
 'en':'Rooms first. Window-class binary sensors only; covers do not count. Exclusions are reviewed next, with a room review if needed.',
 'de':'Räume zuerst. Nur binäre Fenstersensoren, keine Cover. Danach folgen Sensorausschlüsse und bei Bedarf eine erneute Raumauswahl.',
 'el':'Πρώτα οι χώροι. Μόνο δυαδικοί αισθητήρες «Παράθυρο», όχι cover. Ακολουθούν οι εξαιρέσεις και, αν χρειαστεί, επανεξέταση χώρων.',
 'fr':'Les pièces d’abord. Seuls les capteurs binaires Fenêtre sont pris en compte, pas les volets. Exclusions et éventuelle révision ensuite.',
 'es':'Primero las habitaciones. Solo sensores binarios de clase Ventana, no cubiertas. Después exclusiones y, si es necesario, nueva selección.',
}
area_validation = {
 'en':{
  'no_windows_after_exclusions':'These exclusions would leave no usable window contacts. Keep at least one contact included.',
  'review_areas_after_exclusions':'Some selected rooms lost their last window contact after exclusions. Please review your rooms.',
 },
 'de':{
  'no_windows_after_exclusions':'Diese Ausschlüsse würden alle nutzbaren Fensterkontakte entfernen. Lass mindestens einen Kontakt aktiviert.',
  'review_areas_after_exclusions':'Einige ausgewählte Räume haben nach den Ausschlüssen keinen Fensterkontakt mehr. Prüfe die Raumauswahl.',
 },
 'el':{
  'no_windows_after_exclusions':'Με αυτές τις εξαιρέσεις δεν απομένει κανένας διαθέσιμος αισθητήρας παραθύρου. Διατήρησε τουλάχιστον μία επαφή.',
  'review_areas_after_exclusions':'Κάποιοι επιλεγμένοι χώροι έμειναν χωρίς επαφή παραθύρου μετά τις εξαιρέσεις. Έλεγξε ξανά τους χώρους.',
 },
 'fr':{
  'no_windows_after_exclusions':'Ces exclusions supprimeraient tous les contacts de fenêtre utilisables. Conservez au moins un contact.',
  'review_areas_after_exclusions':'Certaines pièces sélectionnées n’ont plus de contact de fenêtre après les exclusions. Revoyez les pièces.',
 },
 'es':{
  'no_windows_after_exclusions':'Estas exclusiones dejarían todas las habitaciones sin contactos de ventana utilizables. Conserva al menos uno.',
  'review_areas_after_exclusions':'Algunas habitaciones seleccionadas ya no tienen contactos de ventana tras las exclusiones. Revisa la selección.',
 },
}

REPEAT_TEXT = {
 "en": [
  "Repeat announcements (minutes)",
  "Default 10 minutes. Set to 0 to never repeat. The same window recommendation and reason must still apply. Each room has its own timer; sensor fluctuations above the same limit do not reset it. Requires automatic notifications or TTS.",
  "Enter a whole number from 0 to 1440 minutes (0 disables repeats)."
 ],
 "de": [
  "Ansagen wiederholen (Minuten)",
  "Standard: 10 Minuten. 0 = niemals wiederholen. Eine Erinnerung erfolgt nur, solange dieselbe Fensterempfehlung und Ursache bestehen. Jeder Raum hat einen eigenen Timer. Automatische Benachrichtigungen oder TTS müssen aktiv sein.",
  "Eine ganze Zahl zwischen 0 und 1440 Minuten eingeben; 0 deaktiviert die Wiederholung."
 ],
 "el": [
  "Επανάληψη ανακοινώσεων (λεπτά)",
  "Προεπιλογή: 10 λεπτά. Με 0 δεν επαναλαμβάνονται ποτέ. Η υπενθύμιση γίνεται μόνο όσο ισχύει η ίδια σύσταση και αιτία για το παράθυρο. Κάθε δωμάτιο έχει ανεξάρτητο χρονόμετρο. Απαιτούνται αυτόματες ειδοποιήσεις ή TTS.",
  "Δώσε ακέραιο από 0 έως 1440 λεπτά. Το 0 απενεργοποιεί τις επαναλήψεις."
 ],
 "fr": [
  "Répéter les annonces (minutes)",
  "Par défaut : 10 minutes. 0 = ne jamais répéter. Une annonce n'est répétée que si la même recommandation et la même cause persistent. Minuterie indépendante par pièce. Les notifications automatiques ou la synthèse vocale doivent être activées.",
  "Saisissez un nombre entier entre 0 et 1440 minutes ; 0 désactive les répétitions."
 ],
 "es": [
  "Repetir anuncios (minutos)",
  "Predeterminado: 10 minutos. 0 = no repetir nunca. Solo se repite cuando persisten la misma recomendación y su causa. Cada habitación usa un temporizador independiente. Requiere notificaciones automáticas o TTS.",
  "Introduce un número entero entre 0 y 1440 minutos; 0 desactiva las repeticiones."
 ]
}

AI_REWRITE_TEXT = {
 "en": {
  "enable": "Use AI for announcements",
  "agent": "Conversation agent",
  "explain": "One option for both paths. When Announcement Hub is selected, send use_ai: true/false to its action; otherwise rewrite direct Home Assistant notifications/TTS. The recommendation itself stays deterministic.",
  "help": "Home Assistant default is preselected. A custom agent overrides the Hub agent or is used for direct rewriting; default inherits Hub's own agent when Hub is selected.",
  "hub_help": "Only shown when Announcement Hub is configured. When stopped, unavailable or rejecting a job, the advisor falls back to Home Assistant notification/TTS and a persistent notification if needed.",
  "missing": "The Home Assistant conversation.process action is unavailable.",
  "invalid": "Select a supported Home Assistant conversation agent."
 },
 "de": {
  "enable": "KI für Ansagen verwenden",
  "agent": "Konversationsagent",
  "explain": "Eine KI-Option für beide Wege. Mit Announcement Hub wird use_ai: true/false übergeben; andernfalls werden direkte Home-Assistant-Meldungen und TTS umformuliert. Die Fensterentscheidung bleibt unverändert.",
  "help": "Home Assistant Standard ist vorausgewählt. Ein eigener Agent wird an den Hub weitergereicht oder für direkte Ansagen verwendet; Standard übernimmt beim Hub dessen eigenen Agenten.",
  "hub_help": "Nur bei eingerichteten Announcement Hub sichtbar. Falls der Hub nicht läuft oder Nachrichten ablehnt, werden direkte Home-Assistant-Ausgaben bzw. eine dauerhafte Benachrichtigung verwendet.",
  "missing": "Die Home-Assistant-Aktion conversation.process ist nicht verfügbar.",
  "invalid": "Wähle einen unterstützten Home-Assistant-Konversationsagenten."
 },
 "el": {
  "enable": "Χρήση AI στις ανακοινώσεις",
  "agent": "Πράκτορας συνομιλίας",
  "explain": "Μία επιλογή AI και για τις δύο μεθόδους. Με Announcement Hub αποστέλλεται use_ai: true/false· διαφορετικά το AI αναδιατυπώνει τις άμεσες ειδοποιήσεις και το TTS. Οι συστάσεις παραθύρων δεν αλλάζουν.",
  "help": "Προεπιλέγεται το Home Assistant default. Άλλος πράκτορας αποστέλλεται στο Hub ή χρησιμοποιείται απευθείας· η προεπιλογή διατηρεί τον πράκτορα που έχει οριστεί στο Hub.",
  "hub_help": "Εμφανίζεται μόνο όταν το Announcement Hub έχει ρυθμιστεί. Αν δεν λειτουργεί ή απορρίψει μήνυμα, γίνεται μετάβαση στις εξόδους του Home Assistant ή σε μόνιμη ειδοποίηση.",
  "missing": "Η ενέργεια conversation.process του Home Assistant δεν είναι διαθέσιμη.",
  "invalid": "Επίλεξε έναν υποστηριζόμενο πράκτορα συνομιλίας του Home Assistant."
 },
 "fr": {
  "enable": "Utiliser l’IA pour les annonces",
  "agent": "Agent conversationnel",
  "explain": "Une seule option IA pour les deux circuits. Avec Announcement Hub, use_ai: true/false est transmis; sinon l’IA reformule les notifications et la synthèse vocale directes. La décision concernant les fenêtres ne change pas.",
  "help": "Home Assistant par défaut est présélectionné. Un agent personnalisé remplace celui du Hub ou reformule directement; par défaut, le Hub conserve son propre agent.",
  "hub_help": "Affiché uniquement lorsque Announcement Hub est configuré. Si le Hub est arrêté ou refuse une annonce, retour vers les sorties Home Assistant ou une notification persistante.",
  "missing": "L’action Home Assistant conversation.process est indisponible.",
  "invalid": "Sélectionnez un agent conversationnel Home Assistant pris en charge."
 },
 "es": {
  "enable": "Usar IA para los anuncios",
  "agent": "Agente de conversación",
  "explain": "Una sola opción de IA para ambos métodos. Con Announcement Hub se envía use_ai: true/false; si no, la IA reformula las notificaciones y el TTS directos. Las recomendaciones sobre ventanas no cambian.",
  "help": "Home Assistant predeterminado está preseleccionado. Un agente personalizado se envía al Hub o se usa directamente; la opción predeterminada respeta el agente propio del Hub.",
  "hub_help": "Aparece solo cuando Announcement Hub está configurado. Si no funciona o rechaza el mensaje, se usan las salidas directas de Home Assistant o una notificación persistente.",
  "missing": "La acción conversation.process de Home Assistant no está disponible.",
  "invalid": "Selecciona un agente de conversación compatible de Home Assistant."
 }
}
for code,v in lang.items():
 steps = {}
 for i, sid in enumerate(stepids):
  name, desc, primary = v['steps'][i]
  stepdata = {fields[i]:primary} if i < 5 else threshold_labels
  if sid=='weather':stepdata['weather_warnings']=v['fields']['weather_warnings']
  if sid=='delivery':stepdata = {key:v['fields'][key] for key in ['language','automatic_tts','automatic_notifications','use_announcement_hub','notify_entities','tts_engine','media_players']}
  steps[sid] = {'title':name,'description':desc,'data':stepdata}
  if sid in ('window_sensors','areas','indoor_sensors','outdoor','weather','delivery'):
   helps = {
    'excluded_window_entities':window_exclusion_text[code][3],
    'areas':'Window-class binary sensors only; covers and selected exclusions are ignored. New setups preselect qualifying areas; existing selections are preserved when reconfiguring. ⚠ marks a missing contact.',
    'excluded_indoor_entities':indoor_step_text[code][3],
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
 ai = AI_REWRITE_TEXT[code]
 steps['delivery']['data']['announcement_repeat_minutes'] = REPEAT_TEXT[code][0]
 steps['delivery']['data_description']['announcement_repeat_minutes'] = REPEAT_TEXT[code][1]
 steps['delivery']['data']['ai_rewrite_announcements'] = ai['enable']
 steps['delivery']['data']['ai_conversation_agent'] = ai['agent']
 steps['delivery']['data_description']['ai_rewrite_announcements'] = ai['explain']
 steps['delivery']['data_description']['ai_conversation_agent'] = ai['help']
 steps['delivery']['data_description']['use_announcement_hub'] = ai['hub_help']
 steps['areas']['description'] = area_descriptions[code]
 steps['areas']['data_description']['areas'] = area_hints[code]
 errors = {**v['errors'], **area_validation[code],
           'invalid_repeat_minutes': REPEAT_TEXT[code][2],
           'missing_ai_service': ai['missing'], 'invalid_ai_agent': ai['invalid']}
 section = {'step':{sid:steps[sid] for sid in initial_stepids},'error':errors, 'abort':{'already_configured':'Home Environment Manager is already configured.'}}
 # Configure selects a single section from a localized options menu.
 menu_titles = {
  'en':'Choose settings to edit', 'el':'Επιλογή ρυθμίσεων',
  'de':'Einstellungen auswählen', 'fr':'Choisir les paramètres à modifier',
  'es':'Elegir ajustes para editar',
 }
 menu_descriptions = {
  'en':'Choose one section. All other settings stay unchanged.',
  'el':'Επίλεξε μία ενότητα. Όλες οι υπόλοιπες ρυθμίσεις παραμένουν ως έχουν.',
  'de':'Wähle einen Bereich aus. Alle anderen Einstellungen bleiben unverändert.',
  'fr':'Choisissez une rubrique. Tous les autres paramètres restent inchangés.',
  'es':'Elige una sección. El resto de ajustes no cambiará.',
 }
 opts={
   'step':{
     'init':{
       'title':menu_titles[code],
       'description':menu_descriptions[code],
       'menu_options':{sid:steps[sid]['title'] for sid in menu_stepids},
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

# Extend the standard five translations without changing their existing text.
from generate_extra_translations import generate_extended
generate_extended(root)

# Final, language-specific help text/error messages and selector labels.
# This is the single reviewed source: regenerating must never restore English
# descriptions to Greek or other localized configuration forms.
from apply_config_i18n import apply_config_overrides
apply_config_overrides(root)

# Optional mold indication and per-room calibration in all 38 languages.
from apply_mold_i18n import apply_mold_i18n
apply_mold_i18n(root)

# Brand and international optional-science configuration, after legacy overrides.
from apply_environment_i18n import apply_environment_i18n
apply_environment_i18n(root)

# Explicitly opt-in supervisory PID climate control, after all legacy overrides.
from apply_pid_i18n import apply_pid_i18n
apply_pid_i18n(root)

# Opt-in climate profiles and international occupancy/away configuration.
from apply_climate_i18n import apply_climate_i18n
apply_climate_i18n(root)

# Compact grouped options, per-device configuration and 38-language labels.
from apply_compact_i18n import apply_compact_i18n
apply_compact_i18n(root)

# Final pass: translate every visible field and supply specific help in
# all 38 languages after legacy/compact generators have completed.
from apply_full_config_i18n import apply_full_config_i18n
apply_full_config_i18n(root)

# Minimal per-area entities, translated only after every other generator pass.
from apply_area_entities_i18n import apply_area_entities_i18n
apply_area_entities_i18n(root)

# Native Home and Area entity labels after all options-flow localization passes.
from apply_device_controls_i18n import apply_device_controls_i18n
apply_device_controls_i18n(root)

# Per-physical-device controllers must be translated after all previous labels.
from apply_equipment_i18n import apply_equipment_i18n
apply_equipment_i18n(root)

# Integration-page room groups; no device/control identities are changed.
from apply_room_hub_i18n import apply_room_hub_i18n
apply_room_hub_i18n(root)

# Ordered rooms, explicit inputs and final general-source setup.
from apply_room_setup_i18n import apply_room_setup_i18n
apply_room_setup_i18n(root)

# General-source defaults, Task AI/TTS provider labels and Home away cooldown.
from apply_beta16_i18n import apply_beta16_i18n
apply_beta16_i18n(root)

from apply_beta19_i18n import apply_beta19_i18n
apply_beta19_i18n(root)

# Final presentation-only pass. All PID parameter names must start with PID
# in every locale, even after downstream generators change room/device labels.
# The channel name, if present, follows PID so sorting is consistent.
from apply_pid_sort_i18n import apply_pid_sort_i18n
apply_pid_sort_i18n(root)
