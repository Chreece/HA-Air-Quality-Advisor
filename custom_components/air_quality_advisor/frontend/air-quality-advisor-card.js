/* Air Quality Advisor for Home Assistant — native Lovelace card, no dependencies.
 * Install with the integration; the integration registers this asset with HA.
 * The card ONLY displays information. It never controls windows or devices.
 */
(() => {
  'use strict';

  const LANGUAGE = {
    en: {
      title:'Air quality', subtitle:'Your home at a glance', outside:'Outside',
      goodOutside:'Good for ventilation', badOutside:'Keep windows closed',
      missingOutside:'Outdoor conditions unknown', partialOutside:'Some outdoor data missing',
      roomStatus:'Rooms', safe:'Good', attention:'Needs attention', unknown:'No data',
      readings:'Measurements', windows:'Windows', windowOpen:'Open', windowClosed:'Closed',
      windowUnknown:'Unknown', open:'Open', close:'Close', openAdvice:'Open windows',
      closeAdvice:'Close windows', blocked:'Ventilation not advised',
      ventilating:'Ventilating', noWindows:'No window sensors',
      missingIndoor:'Indoor readings unavailable', noRooms:'No rooms configured',
      missingCard:'Select an Air Quality Advisor recommendation sensor to display this card.',
      more:'More details', less:'Fewer details', weather:'Weather', warnings:'Warnings',
      limits:'Limit', outdoorSensors:'Outdoor air', noReadings:'No measurements',
      missing:'Unavailable', sensor:'sensor', partial:'Partial data', wind:'Wind',
      humidity:'Humidity', unavailableWeather:'Weather information missing',
      noOutdoor:'No outdoor sensors configured', warningActive:'Active alert',
      warningUnknown:'Alert status unavailable', allOkay:'Indoor air within limits',
      indoorHigh:'Indoor air above a threshold', notSafeToOpen:'Outside prevents opening',
      conditions:'Conditions', measured:'measured', activeWindows:'windows open',
      action:'Recommendation', noAttention:'Everything looks good',
      metric_aqi:'AQI', metric_co2:'CO₂', metric_pm25:'PM2.5',metric_pm10:'PM10',
      metric_voc:'TVOC', metric_voc_parts:'VOC', metric_humidity:'Humidity', metric_mold:'Mold indication',
      wx_sunny:'Sunny', wx_clearNight:'Clear night', wx_partlycloudy:'Partly cloudy',
      wx_cloudy:'Cloudy', wx_rainy:'Rainy', wx_pouring:'Heavy rain',
      wx_lightning:'Thunderstorm', wx_fog:'Fog', wx_snowy:'Snow', wx_windy:'Windy',
      sourceData:'Based on configured Home Assistant sensors',
      allSafe:'No rooms currently need attention',
      warningReason:'Weather warning', unsafeReason:'Unsafe outdoor reading',
      cold:'Too cold outside', hot:'Too hot outside', wet:'High outdoor humidity',
      windHigh:'Strong winds', noWeather:'Weather entity not available'
    },
    de: {
      title:'Luftqualität',subtitle:'Dein Zuhause im Überblick',outside:'Draußen',
      goodOutside:'Lüften möglich',badOutside:'Fenster geschlossen halten',
      missingOutside:'Außenbedingungen unbekannt',partialOutside:'Einige Außendaten fehlen',
      roomStatus:'Räume',safe:'Gut',attention:'Handlungsbedarf',unknown:'Keine Daten',
      readings:'Messwerte',windows:'Fenster',windowOpen:'Offen',windowClosed:'Geschlossen',
      windowUnknown:'Unbekannt',open:'Öffnen',close:'Schließen',openAdvice:'Fenster öffnen',
      closeAdvice:'Fenster schließen',blocked:'Lüften derzeit nicht empfohlen',
      ventilating:'Wird gelüftet',noWindows:'Keine Fensterkontakte',
      missingIndoor:'Innenmesswerte nicht verfügbar',noRooms:'Keine Räume eingerichtet',
      missingCard:'Wähle den Empfehlungssensor von Air Quality Advisor aus.',
      more:'Mehr Details',less:'Weniger Details',weather:'Wetter',warnings:'Warnungen',
      limits:'Grenzwert',outdoorSensors:'Außenluft',noReadings:'Keine Messwerte',
      missing:'Nicht verfügbar',sensor:'Sensor',partial:'Unvollständige Daten',wind:'Wind',
      humidity:'Luftfeuchtigkeit',unavailableWeather:'Wetterdaten fehlen',
      noOutdoor:'Keine Außensensoren konfiguriert',warningActive:'Aktive Warnung',
      warningUnknown:'Warnstatus unbekannt',allOkay:'Innenluft im Grenzbereich',
      indoorHigh:'Innenwert über Grenzwert',notSafeToOpen:'Draußen nicht zum Lüften geeignet',
      conditions:'Bedingungen',measured:'gemessen',activeWindows:'Fenster offen',
      action:'Empfehlung',noAttention:'Alles sieht gut aus',
      metric_humidity:'Luftfeuchtigkeit',metric_mold:'Schimmelindikator',wx_sunny:'Sonnig',wx_clearNight:'Klare Nacht',
      wx_partlycloudy:'Teilweise bewölkt',wx_cloudy:'Bewölkt',wx_rainy:'Regnerisch',
      wx_pouring:'Starkregen',wx_lightning:'Gewitter',wx_fog:'Nebel',wx_snowy:'Schnee',
      wx_windy:'Windig',sourceData:'Basierend auf den eingerichteten Home-Assistant-Sensoren',
      allSafe:'Aktuell kein Raum mit Handlungsbedarf',warningReason:'Wetterwarnung',
      unsafeReason:'Schlechte Außenluft',cold:'Draußen zu kalt',hot:'Draußen zu heiß',
      wet:'Hohe Außenluftfeuchtigkeit',windHigh:'Starker Wind',noWeather:'Wetterentität fehlt'
    },
    el: {
      title:'Ποιότητα αέρα',subtitle:'Το σπίτι σου με μια ματιά',outside:'Εξωτερικά',
      goodOutside:'Κατάλληλο για αερισμό',badOutside:'Κράτησε τα παράθυρα κλειστά',
      missingOutside:'Άγνωστες εξωτερικές συνθήκες',partialOutside:'Λείπουν εξωτερικές μετρήσεις',
      roomStatus:'Δωμάτια',safe:'Καλή',attention:'Χρειάζεται προσοχή',unknown:'Χωρίς δεδομένα',
      readings:'Μετρήσεις',windows:'Παράθυρα',windowOpen:'Ανοιχτό',windowClosed:'Κλειστό',
      windowUnknown:'Άγνωστο',open:'Άνοιγμα',close:'Κλείσιμο',openAdvice:'Άνοιξε τα παράθυρα',
      closeAdvice:'Κλείσε τα παράθυρα',blocked:'Ο αερισμός δεν συνιστάται',
      ventilating:'Γίνεται αερισμός',noWindows:'Δεν υπάρχουν αισθητήρες παραθύρων',
      missingIndoor:'Δεν υπάρχουν εσωτερικές μετρήσεις',noRooms:'Δεν έχουν οριστεί δωμάτια',
      missingCard:'Επίλεξε τον αισθητήρα προτάσεων του Air Quality Advisor.',
      more:'Περισσότερα',less:'Λιγότερα',weather:'Καιρός',warnings:'Προειδοποιήσεις',
      limits:'Όριο',outdoorSensors:'Εξωτερικός αέρας',noReadings:'Δεν υπάρχουν μετρήσεις',
      missing:'Μη διαθέσιμο',sensor:'αισθητήρας',partial:'Ελλιπή δεδομένα',wind:'Άνεμος',
      humidity:'Υγρασία',unavailableWeather:'Λείπουν στοιχεία καιρού',
      noOutdoor:'Δεν έχουν οριστεί εξωτερικοί αισθητήρες',warningActive:'Ενεργή προειδοποίηση',
      warningUnknown:'Άγνωστη κατάσταση προειδοποίησης',allOkay:'Ο εσωτερικός αέρας είναι εντός ορίων',
      indoorHigh:'Υπέρβαση ορίου σε εσωτερική μέτρηση',notSafeToOpen:'Οι εξωτερικές συνθήκες δεν επιτρέπουν αερισμό',
      conditions:'Συνθήκες',measured:'μετρήσεις',activeWindows:'ανοιχτά παράθυρα',
      action:'Πρόταση',noAttention:'Όλα φαίνονται καλά',
      metric_humidity:'Υγρασία',metric_mold:'Ένδειξη μούχλας',wx_sunny:'Ηλιοφάνεια',wx_clearNight:'Ξαστεριά',
      wx_partlycloudy:'Λίγες νεφώσεις',wx_cloudy:'Συννεφιά',wx_rainy:'Βροχή',
      wx_pouring:'Ισχυρή βροχή',wx_lightning:'Καταιγίδα',wx_fog:'Ομίχλη',
      wx_snowy:'Χιόνι',wx_windy:'Άνεμος',sourceData:'Βάσει των ρυθμισμένων αισθητήρων Home Assistant',
      allSafe:'Κανένα δωμάτιο δεν χρειάζεται προσοχή',warningReason:'Προειδοποίηση καιρού',
      unsafeReason:'Κακή ποιότητα εξωτερικού αέρα',cold:'Χαμηλή εξωτερική θερμοκρασία',
      hot:'Υψηλή εξωτερική θερμοκρασία',wet:'Υψηλή εξωτερική υγρασία',
      windHigh:'Ισχυροί άνεμοι',noWeather:'Δεν διατίθενται μετρήσεις καιρού'
    },
    fr: {
      title:'Qualité de l’air',subtitle:'Votre maison en un coup d’œil',outside:'Dehors',
      goodOutside:'Aération possible',badOutside:'Gardez les fenêtres fermées',
      missingOutside:'Conditions extérieures inconnues',partialOutside:'Données extérieures manquantes',
      roomStatus:'Pièces',safe:'Bonne',attention:'À surveiller',unknown:'Sans données',
      readings:'Mesures',windows:'Fenêtres',windowOpen:'Ouverte',windowClosed:'Fermée',
      windowUnknown:'Inconnue',open:'Ouvrir',close:'Fermer',openAdvice:'Ouvrir les fenêtres',
      closeAdvice:'Fermer les fenêtres',blocked:'Aération déconseillée',
      ventilating:'Aération en cours',noWindows:'Aucun contact de fenêtre',
      missingIndoor:'Mesures intérieures indisponibles',noRooms:'Aucune pièce configurée',
      missingCard:'Sélectionnez le capteur de recommandations Air Quality Advisor.',
      more:'Plus de détails',less:'Moins de détails',weather:'Météo',warnings:'Alertes',
      limits:'Seuil',outdoorSensors:'Air extérieur',noReadings:'Aucune mesure',
      missing:'Indisponible',partial:'Données partielles',wind:'Vent',humidity:'Humidité',
      unavailableWeather:'Météo indisponible',noOutdoor:'Aucun capteur extérieur',
      warningActive:'Alerte active',warningUnknown:'État d’alerte inconnu',
      allOkay:'Air intérieur sous les seuils',indoorHigh:'Seuil intérieur dépassé',
      notSafeToOpen:'Conditions extérieures défavorables',conditions:'Conditions',
      measured:'mesurés',activeWindows:'fenêtres ouvertes',action:'Conseil',
      noAttention:'Tout semble bon',metric_humidity:'Humidité',metric_mold:'Indicateur de moisissure',wx_sunny:'Ensoleillé',
      wx_clearNight:'Nuit claire',wx_partlycloudy:'Partiellement nuageux',wx_cloudy:'Nuageux',
      wx_rainy:'Pluvieux',wx_pouring:'Fortes pluies',wx_lightning:'Orage',
      wx_fog:'Brouillard',wx_snowy:'Neige',wx_windy:'Venteux',
      sourceData:'Selon les capteurs Home Assistant configurés',allSafe:'Aucune pièce à surveiller',
      warningReason:'Alerte météo',unsafeReason:'Air extérieur dégradé',cold:'Trop froid dehors',
      hot:'Trop chaud dehors',wet:'Humidité extérieure élevée',windHigh:'Vent fort',noWeather:'Météo manquante'
    },
    es: {
      title:'Calidad del aire',subtitle:'Tu hogar de un vistazo',outside:'Exterior',
      goodOutside:'Adecuado para ventilar',badOutside:'Mantén las ventanas cerradas',
      missingOutside:'Condiciones exteriores desconocidas',partialOutside:'Faltan datos exteriores',
      roomStatus:'Habitaciones',safe:'Bien',attention:'Requiere atención',unknown:'Sin datos',
      readings:'Mediciones',windows:'Ventanas',windowOpen:'Abierta',windowClosed:'Cerrada',
      windowUnknown:'Desconocida',open:'Abrir',close:'Cerrar',openAdvice:'Abre las ventanas',
      closeAdvice:'Cierra las ventanas',blocked:'No se recomienda ventilar',
      ventilating:'Ventilando',noWindows:'No hay sensores de ventana',
      missingIndoor:'Sin mediciones interiores',noRooms:'No hay habitaciones configuradas',
      missingCard:'Selecciona el sensor de recomendaciones de Air Quality Advisor.',
      more:'Más detalles',less:'Menos detalles',weather:'Tiempo',warnings:'Alertas',
      limits:'Límite',outdoorSensors:'Aire exterior',noReadings:'Sin mediciones',
      missing:'No disponible',partial:'Datos parciales',wind:'Viento',humidity:'Humedad',
      unavailableWeather:'Datos meteorológicos no disponibles',noOutdoor:'Sin sensores exteriores',
      warningActive:'Alerta activa',warningUnknown:'Estado de alerta desconocido',
      allOkay:'Aire interior dentro de los límites',indoorHigh:'Límite interior superado',
      notSafeToOpen:'Las condiciones exteriores impiden ventilar',conditions:'Condiciones',
      measured:'medidos',activeWindows:'ventanas abiertas',action:'Recomendación',
      noAttention:'Todo parece correcto',metric_humidity:'Humedad',metric_mold:'Indicador de moho',wx_sunny:'Soleado',
      wx_clearNight:'Noche despejada',wx_partlycloudy:'Parcialmente nublado',wx_cloudy:'Nublado',
      wx_rainy:'Lluvioso',wx_pouring:'Lluvia intensa',wx_lightning:'Tormenta',
      wx_fog:'Niebla',wx_snowy:'Nieve',wx_windy:'Ventoso',
      sourceData:'Según los sensores configurados en Home Assistant',
      allSafe:'Ninguna habitación requiere atención',warningReason:'Alerta meteorológica',
      unsafeReason:'Aire exterior contaminado',cold:'Frío exterior',hot:'Calor exterior',
      wet:'Humedad exterior alta',windHigh:'Viento fuerte',noWeather:'No hay datos meteorológicos'
    },
    it: { title:'Qualità dell’aria',subtitle:'La casa a colpo d’occhio',outside:'All’aperto',
      goodOutside:'Puoi arieggiare',badOutside:'Tieni le finestre chiuse',
      missingOutside:'Condizioni esterne sconosciute',partialOutside:'Dati esterni incompleti',
      roomStatus:'Stanze',safe:'Buona',attention:'Richiede attenzione',unknown:'Senza dati',
      readings:'Misurazioni',windows:'Finestre',windowOpen:'Aperta',windowClosed:'Chiusa',
      windowUnknown:'Sconosciuta',openAdvice:'Apri le finestre',closeAdvice:'Chiudi le finestre',
      blocked:'Aerazione sconsigliata',ventilating:'Aerazione in corso',
      missingIndoor:'Misurazioni interne non disponibili',noRooms:'Nessuna stanza configurata',
      more:'Più dettagli',less:'Meno dettagli',weather:'Meteo',warnings:'Avvisi',
      limits:'Limite',outdoorSensors:'Aria esterna',noReadings:'Nessuna misurazione',
      missing:'Non disponibile',partial:'Dati parziali',wind:'Vento',humidity:'Umidità',
      warningActive:'Avviso attivo',allOkay:'Aria interna nei limiti',indoorHigh:'Limite interno superato',
      notSafeToOpen:'Condizioni esterne sfavorevoli',action:'Consiglio',noAttention:'Tutto a posto',
      metric_humidity:'Umidità',sourceData:'Dati dei sensori di Home Assistant',
      allSafe:'Nessuna stanza richiede attenzione' },
    nl: { title:'Luchtkwaliteit',subtitle:'Je huis in één oogopslag',outside:'Buiten',
      goodOutside:'Geschikt om te ventileren',badOutside:'Houd ramen gesloten',
      missingOutside:'Buitenomstandigheden onbekend',partialOutside:'Buitengegevens ontbreken',
      roomStatus:'Kamers',safe:'Goed',attention:'Aandacht nodig',unknown:'Geen gegevens',
      readings:'Metingen',windows:'Ramen',windowOpen:'Open',windowClosed:'Dicht',
      windowUnknown:'Onbekend',openAdvice:'Open de ramen',closeAdvice:'Sluit de ramen',
      blocked:'Ventileren afgeraden',ventilating:'Bezig met ventileren',
      missingIndoor:'Binnenmetingen ontbreken',noRooms:'Geen kamers ingesteld',
      more:'Meer details',less:'Minder details',weather:'Weer',warnings:'Waarschuwingen',
      limits:'Grenswaarde',outdoorSensors:'Buitenlucht',noReadings:'Geen metingen',
      missing:'Niet beschikbaar',partial:'Onvolledige gegevens',wind:'Wind',humidity:'Vochtigheid',
      warningActive:'Actieve waarschuwing',allOkay:'Binnenlucht binnen de grenzen',
      indoorHigh:'Binnenwaarde te hoog',notSafeToOpen:'Buitenlucht niet geschikt',
      action:'Advies',noAttention:'Alles ziet er goed uit',metric_humidity:'Vochtigheid',
      sourceData:'Gebaseerd op Home Assistant-sensoren',allSafe:'Geen kamers met aandacht nodig' },
    pt: { title:'Qualidade do ar',subtitle:'A sua casa num relance',outside:'Exterior',
      goodOutside:'Condições para ventilar',badOutside:'Mantenha as janelas fechadas',
      missingOutside:'Condições exteriores desconhecidas',partialOutside:'Dados exteriores em falta',
      roomStatus:'Divisões',safe:'Boa',attention:'Precisa de atenção',unknown:'Sem dados',
      readings:'Medições',windows:'Janelas',windowOpen:'Aberta',windowClosed:'Fechada',
      windowUnknown:'Desconhecida',openAdvice:'Abra as janelas',closeAdvice:'Feche as janelas',
      blocked:'Ventilação desaconselhada',ventilating:'A ventilar',
      missingIndoor:'Medições interiores indisponíveis',noRooms:'Sem divisões configuradas',
      more:'Mais detalhes',less:'Menos detalhes',weather:'Tempo',warnings:'Alertas',
      limits:'Limite',outdoorSensors:'Ar exterior',noReadings:'Sem medições',
      missing:'Indisponível',partial:'Dados parciais',wind:'Vento',humidity:'Humidade',
      warningActive:'Alerta ativo',allOkay:'Ar interior dentro dos limites',
      indoorHigh:'Limite interior excedido',notSafeToOpen:'Condições exteriores desfavoráveis',
      action:'Recomendação',noAttention:'Tudo parece bem',metric_humidity:'Humidade',
      sourceData:'Com base nos sensores Home Assistant',allSafe:'Nenhuma divisão requer atenção' },
    pl: { title:'Jakość powietrza',subtitle:'Twój dom w skrócie',outside:'Na zewnątrz',
      goodOutside:'Można wietrzyć',badOutside:'Pozostaw okna zamknięte',
      missingOutside:'Nieznane warunki na zewnątrz',partialOutside:'Brak części danych zewnętrznych',
      roomStatus:'Pomieszczenia',safe:'Dobrze',attention:'Wymaga uwagi',unknown:'Brak danych',
      readings:'Pomiary',windows:'Okna',windowOpen:'Otwarte',windowClosed:'Zamknięte',
      windowUnknown:'Nieznane',openAdvice:'Otwórz okna',closeAdvice:'Zamknij okna',
      blocked:'Wietrzenie niewskazane',ventilating:'Trwa wietrzenie',
      missingIndoor:'Brak pomiarów wewnętrznych',noRooms:'Nie skonfigurowano pomieszczeń',
      more:'Więcej',less:'Mniej',weather:'Pogoda',warnings:'Ostrzeżenia',
      limits:'Próg',outdoorSensors:'Powietrze na zewnątrz',noReadings:'Brak pomiarów',
      missing:'Niedostępne',partial:'Niepełne dane',wind:'Wiatr',humidity:'Wilgotność',
      warningActive:'Aktywne ostrzeżenie',allOkay:'Wartości wewnętrzne w normie',
      indoorHigh:'Przekroczony próg',notSafeToOpen:'Niekorzystne warunki na zewnątrz',
      action:'Zalecenie',noAttention:'Wszystko wygląda dobrze',metric_humidity:'Wilgotność',
      sourceData:'Na podstawie czujników Home Assistant',allSafe:'Brak pomieszczeń wymagających uwagi' },
    ru: { title:'Качество воздуха',subtitle:'Состояние дома с первого взгляда',outside:'На улице',
      goodOutside:'Можно проветривать',badOutside:'Оставьте окна закрытыми',
      missingOutside:'Погода снаружи неизвестна',partialOutside:'Часть данных снаружи недоступна',
      roomStatus:'Комнаты',safe:'Хорошо',attention:'Требует внимания',unknown:'Нет данных',
      readings:'Измерения',windows:'Окна',windowOpen:'Открыто',windowClosed:'Закрыто',
      windowUnknown:'Неизвестно',openAdvice:'Откройте окна',closeAdvice:'Закройте окна',
      blocked:'Проветривание не рекомендуется',ventilating:'Проветривание',
      missingIndoor:'Нет данных внутри',noRooms:'Комнаты не настроены',
      more:'Подробнее',less:'Свернуть',weather:'Погода',warnings:'Предупреждения',
      limits:'Порог',outdoorSensors:'Наружный воздух',noReadings:'Нет измерений',
      missing:'Недоступно',partial:'Частичные данные',wind:'Ветер',humidity:'Влажность',
      warningActive:'Активное предупреждение',allOkay:'Воздух внутри в норме',
      indoorHigh:'Превышен внутренний порог',notSafeToOpen:'Снаружи проветривать нельзя',
      action:'Рекомендация',noAttention:'Всё в порядке',metric_humidity:'Влажность',
      sourceData:'Данные датчиков Home Assistant',allSafe:'Нет комнат, требующих внимания' },
    tr: { title:'Hava kalitesi',subtitle:'Evinize genel bakış',outside:'Dışarıda',
      goodOutside:'Havalandırmaya uygun',badOutside:'Pencereleri kapalı tutun',
      missingOutside:'Dış koşullar bilinmiyor',partialOutside:'Bazı dış veriler eksik',
      roomStatus:'Odalar',safe:'İyi',attention:'Dikkat gerekli',unknown:'Veri yok',
      readings:'Ölçümler',windows:'Pencereler',windowOpen:'Açık',windowClosed:'Kapalı',
      windowUnknown:'Bilinmiyor',openAdvice:'Pencereleri açın',closeAdvice:'Pencereleri kapatın',
      blocked:'Havalandırma önerilmiyor',ventilating:'Havalandırılıyor',
      missingIndoor:'İç ortam ölçümleri yok',noRooms:'Oda yapılandırılmadı',
      more:'Daha fazla',less:'Daha az',weather:'Hava durumu',warnings:'Uyarılar',
      limits:'Sınır',outdoorSensors:'Dış hava',noReadings:'Ölçüm yok',
      missing:'Kullanılamıyor',partial:'Eksik veri',wind:'Rüzgâr',humidity:'Nem',
      warningActive:'Aktif uyarı',allOkay:'İç hava normal',indoorHigh:'İç hava sınırı aşıldı',
      notSafeToOpen:'Dış koşullar uygun değil',action:'Öneri',noAttention:'Her şey yolunda',
      metric_humidity:'Nem',sourceData:'Home Assistant sensörlerinden',
      allSafe:'Dikkat gerektiren oda yok' },
  };

  // Generated from locale packs: UI text follows Home Assistant user language.
  const EXTRA_LANGUAGE = {"it":{"title":"Qualità dell'aria","subtitle":"Qualità dell'aria","outside":"Esterno","goodOutside":"Adatto a ventilare","badOutside":"Tieni le finestre chiuse","missingOutside":"Non disponibile","partialOutside":"Non disponibile","roomStatus":"Stanze","safe":"Buona","attention":"Attenzione","unknown":"Dati assenti","readings":"Apri","windows":"Misurazioni","windowOpen":"Aperta","windowClosed":"Chiusa","windowUnknown":"Dati assenti","open":"Chiudi","close":"Notifiche automatiche","openAdvice":"Chiudi · Misurazioni","closeAdvice":"Notifiche automatiche · Misurazioni","blocked":"Tieni le finestre chiuse","ventilating":"Aerazione in corso","noWindows":"0 · Misurazioni","missingIndoor":"Dati assenti","noRooms":"Nessuna stanza configurata","missingCard":"Air Quality Advisor · Apri","more":"Più dettagli","less":"Meno dettagli","weather":"Meteo","warnings":"Avvisi meteo","limits":"Limite","outdoorSensors":"Qualità dell'aria esterna","noReadings":"Dati assenti","missing":"Non disponibile","sensor":"Apri","partial":"Non disponibile","wind":"Meteo","humidity":"RH","unavailableWeather":"Non disponibile","noOutdoor":"0 · Qualità dell'aria esterna","warningActive":"Avvisi meteo","warningUnknown":"Avvisi meteo","allOkay":"Buona","indoorHigh":"Attenzione","notSafeToOpen":"Tieni le finestre chiuse","conditions":"Esterno","measured":"Apri","activeWindows":"Aperta","action":"Annunci (facoltativi)","noAttention":"Buona","metric_humidity":"RH","sourceData":"Home Assistant · Apri","allSafe":"Buona","warningReason":"Avvisi meteo","unsafeReason":"Tieni le finestre chiuse","noWeather":"Non disponibile"},"nl":{"title":"Luchtkwaliteit","subtitle":"Luchtkwaliteit","outside":"Buiten","goodOutside":"Geschikt om te ventileren","badOutside":"Houd ramen gesloten","missingOutside":"Niet beschikbaar","partialOutside":"Niet beschikbaar","roomStatus":"Kamers","safe":"Goed","attention":"Aandacht nodig","unknown":"Geen gegevens","readings":"Open","windows":"Metingen","windowOpen":"Open","windowClosed":"Gesloten","windowUnknown":"Geen gegevens","open":"Sluit","close":"Automatische meldingen","openAdvice":"Sluit · Metingen","closeAdvice":"Automatische meldingen · Metingen","blocked":"Houd ramen gesloten","ventilating":"Ventilatie actief","noWindows":"0 · Metingen","missingIndoor":"Geen gegevens","noRooms":"Geen kamers ingesteld","missingCard":"Air Quality Advisor · Open","more":"Meer details","less":"Minder details","weather":"Weer","warnings":"Weerwaarschuwingen","limits":"Grenswaarde","outdoorSensors":"Buitenluchtkwaliteit","noReadings":"Geen gegevens","missing":"Niet beschikbaar","sensor":"Open","partial":"Niet beschikbaar","wind":"Weer","humidity":"RH","unavailableWeather":"Niet beschikbaar","noOutdoor":"0 · Buitenluchtkwaliteit","warningActive":"Weerwaarschuwingen","warningUnknown":"Weerwaarschuwingen","allOkay":"Goed","indoorHigh":"Aandacht nodig","notSafeToOpen":"Houd ramen gesloten","conditions":"Buiten","measured":"Open","activeWindows":"Open","action":"Meldingen (optioneel)","noAttention":"Goed","metric_humidity":"RH","sourceData":"Home Assistant · Open","allSafe":"Goed","warningReason":"Weerwaarschuwingen","unsafeReason":"Houd ramen gesloten","noWeather":"Niet beschikbaar"},"pt":{"title":"Qualidade do ar","subtitle":"Qualidade do ar","outside":"Exterior","goodOutside":"Bom para ventilar","badOutside":"Mantenha as janelas fechadas","missingOutside":"Indisponível","partialOutside":"Indisponível","roomStatus":"Divisões","safe":"Boa","attention":"Requer atenção","unknown":"Sem dados","readings":"Abra","windows":"Medições","windowOpen":"Aberta","windowClosed":"Fechada","windowUnknown":"Sem dados","open":"Feche","close":"Notificações automáticas","openAdvice":"Feche · Medições","closeAdvice":"Notificações automáticas · Medições","blocked":"Mantenha as janelas fechadas","ventilating":"A ventilar","noWindows":"0 · Medições","missingIndoor":"Sem dados","noRooms":"Sem divisões configuradas","missingCard":"Air Quality Advisor · Abra","more":"Mais detalhes","less":"Menos detalhes","weather":"Tempo","warnings":"Avisos meteorológicos","limits":"Limite","outdoorSensors":"Qualidade do ar exterior","noReadings":"Sem dados","missing":"Indisponível","sensor":"Abra","partial":"Indisponível","wind":"Tempo","humidity":"RH","unavailableWeather":"Indisponível","noOutdoor":"0 · Qualidade do ar exterior","warningActive":"Avisos meteorológicos","warningUnknown":"Avisos meteorológicos","allOkay":"Boa","indoorHigh":"Requer atenção","notSafeToOpen":"Mantenha as janelas fechadas","conditions":"Exterior","measured":"Abra","activeWindows":"Aberta","action":"Anúncios (opcional)","noAttention":"Boa","metric_humidity":"RH","sourceData":"Home Assistant · Abra","allSafe":"Boa","warningReason":"Avisos meteorológicos","unsafeReason":"Mantenha as janelas fechadas","noWeather":"Indisponível"},"pt-br":{"title":"Qualidade do ar","subtitle":"Qualidade do ar","outside":"Área externa","goodOutside":"Bom para ventilar","badOutside":"Mantenha as janelas fechadas","missingOutside":"Indisponível","partialOutside":"Indisponível","roomStatus":"Cômodos","safe":"Boa","attention":"Precisa de atenção","unknown":"Sem dados","readings":"Abra","windows":"Medições","windowOpen":"Aberta","windowClosed":"Fechada","windowUnknown":"Sem dados","open":"Feche","close":"Notificações automáticas","openAdvice":"Feche · Medições","closeAdvice":"Notificações automáticas · Medições","blocked":"Mantenha as janelas fechadas","ventilating":"Ventilando","noWindows":"0 · Medições","missingIndoor":"Sem dados","noRooms":"Nenhum cômodo configurado","missingCard":"Air Quality Advisor · Abra","more":"Mais detalhes","less":"Menos detalhes","weather":"Clima","warnings":"Alertas meteorológicos","limits":"Limite","outdoorSensors":"Qualidade do ar externo","noReadings":"Sem dados","missing":"Indisponível","sensor":"Abra","partial":"Indisponível","wind":"Clima","humidity":"RH","unavailableWeather":"Indisponível","noOutdoor":"0 · Qualidade do ar externo","warningActive":"Alertas meteorológicos","warningUnknown":"Alertas meteorológicos","allOkay":"Boa","indoorHigh":"Precisa de atenção","notSafeToOpen":"Mantenha as janelas fechadas","conditions":"Área externa","measured":"Abra","activeWindows":"Aberta","action":"Avisos (opcional)","noAttention":"Boa","metric_humidity":"RH","sourceData":"Home Assistant · Abra","allSafe":"Boa","warningReason":"Alertas meteorológicos","unsafeReason":"Mantenha as janelas fechadas","noWeather":"Indisponível"},"pl":{"title":"Jakość powietrza","subtitle":"Jakość powietrza","outside":"Na zewnątrz","goodOutside":"Można wietrzyć","badOutside":"Pozostaw okna zamknięte","missingOutside":"Niedostępne","partialOutside":"Niedostępne","roomStatus":"Pomieszczenia","safe":"Dobra","attention":"Wymaga uwagi","unknown":"Brak danych","readings":"Otwórz","windows":"Pomiary","windowOpen":"Otwarte","windowClosed":"Zamknięte","windowUnknown":"Brak danych","open":"Zamknij","close":"Automatyczne powiadomienia","openAdvice":"Zamknij · Pomiary","closeAdvice":"Automatyczne powiadomienia · Pomiary","blocked":"Pozostaw okna zamknięte","ventilating":"Trwa wietrzenie","noWindows":"0 · Pomiary","missingIndoor":"Brak danych","noRooms":"Brak skonfigurowanych pomieszczeń","missingCard":"Air Quality Advisor · Otwórz","more":"Więcej szczegółów","less":"Mniej szczegółów","weather":"Pogoda","warnings":"Ostrzeżenia pogodowe","limits":"Próg","outdoorSensors":"Jakość powietrza na zewnątrz","noReadings":"Brak danych","missing":"Niedostępne","sensor":"Otwórz","partial":"Niedostępne","wind":"Pogoda","humidity":"RH","unavailableWeather":"Niedostępne","noOutdoor":"0 · Jakość powietrza na zewnątrz","warningActive":"Ostrzeżenia pogodowe","warningUnknown":"Ostrzeżenia pogodowe","allOkay":"Dobra","indoorHigh":"Wymaga uwagi","notSafeToOpen":"Pozostaw okna zamknięte","conditions":"Na zewnątrz","measured":"Otwórz","activeWindows":"Otwarte","action":"Komunikaty (opcjonalnie)","noAttention":"Dobra","metric_humidity":"RH","sourceData":"Home Assistant · Otwórz","allSafe":"Dobra","warningReason":"Ostrzeżenia pogodowe","unsafeReason":"Pozostaw okna zamknięte","noWeather":"Niedostępne"},"ru":{"title":"Качество воздуха","subtitle":"Качество воздуха","outside":"Снаружи","goodOutside":"Можно проветривать","badOutside":"Держите окна закрытыми","missingOutside":"Недоступно","partialOutside":"Недоступно","roomStatus":"Комнаты","safe":"Хорошее","attention":"Требует внимания","unknown":"Нет данных","readings":"Откройте","windows":"Измерения","windowOpen":"Открыто","windowClosed":"Закрыто","windowUnknown":"Нет данных","open":"Закройте","close":"Автоматические уведомления","openAdvice":"Закройте · Измерения","closeAdvice":"Автоматические уведомления · Измерения","blocked":"Держите окна закрытыми","ventilating":"Проветривание","noWindows":"0 · Измерения","missingIndoor":"Нет данных","noRooms":"Нет выбранных комнат","missingCard":"Air Quality Advisor · Откройте","more":"Подробнее","less":"Свернуть","weather":"Погода","warnings":"Погодные предупреждения","limits":"Порог","outdoorSensors":"Качество воздуха снаружи","noReadings":"Нет данных","missing":"Недоступно","sensor":"Откройте","partial":"Недоступно","wind":"Погода","humidity":"RH","unavailableWeather":"Недоступно","noOutdoor":"0 · Качество воздуха снаружи","warningActive":"Погодные предупреждения","warningUnknown":"Погодные предупреждения","allOkay":"Хорошее","indoorHigh":"Требует внимания","notSafeToOpen":"Держите окна закрытыми","conditions":"Снаружи","measured":"Откройте","activeWindows":"Открыто","action":"Оповещения (необязательно)","noAttention":"Хорошее","metric_humidity":"RH","sourceData":"Home Assistant · Откройте","allSafe":"Хорошее","warningReason":"Погодные предупреждения","unsafeReason":"Держите окна закрытыми","noWeather":"Недоступно"},"uk":{"title":"Якість повітря","subtitle":"Якість повітря","outside":"Надворі","goodOutside":"Можна провітрювати","badOutside":"Тримайте вікна зачиненими","missingOutside":"Недоступно","partialOutside":"Недоступно","roomStatus":"Кімнати","safe":"Добра","attention":"Потребує уваги","unknown":"Немає даних","readings":"Відкрийте","windows":"Вимірювання","windowOpen":"Відчинене","windowClosed":"Зачинене","windowUnknown":"Немає даних","open":"Зачиніть","close":"Автоматичні сповіщення","openAdvice":"Зачиніть · Вимірювання","closeAdvice":"Автоматичні сповіщення · Вимірювання","blocked":"Тримайте вікна зачиненими","ventilating":"Провітрювання","noWindows":"0 · Вимірювання","missingIndoor":"Немає даних","noRooms":"Немає вибраних кімнат","missingCard":"Air Quality Advisor · Відкрийте","more":"Докладніше","less":"Менше деталей","weather":"Погода","warnings":"Попередження про погоду","limits":"Поріг","outdoorSensors":"Якість повітря надворі","noReadings":"Немає даних","missing":"Недоступно","sensor":"Відкрийте","partial":"Недоступно","wind":"Погода","humidity":"RH","unavailableWeather":"Недоступно","noOutdoor":"0 · Якість повітря надворі","warningActive":"Попередження про погоду","warningUnknown":"Попередження про погоду","allOkay":"Добра","indoorHigh":"Потребує уваги","notSafeToOpen":"Тримайте вікна зачиненими","conditions":"Надворі","measured":"Відкрийте","activeWindows":"Відчинене","action":"Оголошення (необов’язково)","noAttention":"Добра","metric_humidity":"RH","sourceData":"Home Assistant · Відкрийте","allSafe":"Добра","warningReason":"Попередження про погоду","unsafeReason":"Тримайте вікна зачиненими","noWeather":"Недоступно"},"tr":{"title":"Hava kalitesi","subtitle":"Hava kalitesi","outside":"Dışarısı","goodOutside":"Havalandırmaya uygun","badOutside":"Pencereleri kapalı tutun","missingOutside":"Kullanılamıyor","partialOutside":"Kullanılamıyor","roomStatus":"Odalar","safe":"İyi","attention":"İlgi gerekiyor","unknown":"Veri yok","readings":"Açın","windows":"Ölçümler","windowOpen":"Açık","windowClosed":"Kapalı","windowUnknown":"Veri yok","open":"Kapatın","close":"Otomatik bildirimler","openAdvice":"Kapatın · Ölçümler","closeAdvice":"Otomatik bildirimler · Ölçümler","blocked":"Pencereleri kapalı tutun","ventilating":"Havalandırılıyor","noWindows":"0 · Ölçümler","missingIndoor":"Veri yok","noRooms":"Oda yapılandırılmamış","missingCard":"Air Quality Advisor · Açın","more":"Daha fazla ayrıntı","less":"Daha az ayrıntı","weather":"Hava durumu","warnings":"Hava durumu uyarıları","limits":"Eşik","outdoorSensors":"Dış hava kalitesi","noReadings":"Veri yok","missing":"Kullanılamıyor","sensor":"Açın","partial":"Kullanılamıyor","wind":"Hava durumu","humidity":"RH","unavailableWeather":"Kullanılamıyor","noOutdoor":"0 · Dış hava kalitesi","warningActive":"Hava durumu uyarıları","warningUnknown":"Hava durumu uyarıları","allOkay":"İyi","indoorHigh":"İlgi gerekiyor","notSafeToOpen":"Pencereleri kapalı tutun","conditions":"Dışarısı","measured":"Açın","activeWindows":"Açık","action":"Duyurular (isteğe bağlı)","noAttention":"İyi","metric_humidity":"RH","sourceData":"Home Assistant · Açın","allSafe":"İyi","warningReason":"Hava durumu uyarıları","unsafeReason":"Pencereleri kapalı tutun","noWeather":"Kullanılamıyor"},"cs":{"title":"Kvalita vzduchu","subtitle":"Kvalita vzduchu","outside":"Venku","goodOutside":"Vhodné pro větrání","badOutside":"Nechte okna zavřená","missingOutside":"Nedostupné","partialOutside":"Nedostupné","roomStatus":"Místnosti","safe":"Dobrá","attention":"Vyžaduje pozornost","unknown":"Bez dat","readings":"Otevřete","windows":"Měření","windowOpen":"Otevřené","windowClosed":"Zavřené","windowUnknown":"Bez dat","open":"Zavřete","close":"Automatická oznámení","openAdvice":"Zavřete · Měření","closeAdvice":"Automatická oznámení · Měření","blocked":"Nechte okna zavřená","ventilating":"Probíhá větrání","noWindows":"0 · Měření","missingIndoor":"Bez dat","noRooms":"Nejsou vybrány místnosti","missingCard":"Air Quality Advisor · Otevřete","more":"Více informací","less":"Méně informací","weather":"Počasí","warnings":"Výstrahy počasí","limits":"Limit","outdoorSensors":"Kvalita venkovního vzduchu","noReadings":"Bez dat","missing":"Nedostupné","sensor":"Otevřete","partial":"Nedostupné","wind":"Počasí","humidity":"RH","unavailableWeather":"Nedostupné","noOutdoor":"0 · Kvalita venkovního vzduchu","warningActive":"Výstrahy počasí","warningUnknown":"Výstrahy počasí","allOkay":"Dobrá","indoorHigh":"Vyžaduje pozornost","notSafeToOpen":"Nechte okna zavřená","conditions":"Venku","measured":"Otevřete","activeWindows":"Otevřené","action":"Oznámení (volitelně)","noAttention":"Dobrá","metric_humidity":"RH","sourceData":"Home Assistant · Otevřete","allSafe":"Dobrá","warningReason":"Výstrahy počasí","unsafeReason":"Nechte okna zavřená","noWeather":"Nedostupné"},"sk":{"title":"Kvalita vzduchu","subtitle":"Kvalita vzduchu","outside":"Vonku","goodOutside":"Vhodné na vetranie","badOutside":"Nechajte okná zatvorené","missingOutside":"Nedostupné","partialOutside":"Nedostupné","roomStatus":"Miestnosti","safe":"Dobrá","attention":"Vyžaduje pozornosť","unknown":"Bez údajov","readings":"Otvorte","windows":"Merania","windowOpen":"Otvorené","windowClosed":"Zatvorené","windowUnknown":"Bez údajov","open":"Zatvorte","close":"Automatické oznámenia","openAdvice":"Zatvorte · Merania","closeAdvice":"Automatické oznámenia · Merania","blocked":"Nechajte okná zatvorené","ventilating":"Prebieha vetranie","noWindows":"0 · Merania","missingIndoor":"Bez údajov","noRooms":"Žiadne miestnosti","missingCard":"Air Quality Advisor · Otvorte","more":"Viac podrobností","less":"Menej podrobností","weather":"Počasie","warnings":"Výstrahy počasia","limits":"Limit","outdoorSensors":"Kvalita vonkajšieho vzduchu","noReadings":"Bez údajov","missing":"Nedostupné","sensor":"Otvorte","partial":"Nedostupné","wind":"Počasie","humidity":"RH","unavailableWeather":"Nedostupné","noOutdoor":"0 · Kvalita vonkajšieho vzduchu","warningActive":"Výstrahy počasia","warningUnknown":"Výstrahy počasia","allOkay":"Dobrá","indoorHigh":"Vyžaduje pozornosť","notSafeToOpen":"Nechajte okná zatvorené","conditions":"Vonku","measured":"Otvorte","activeWindows":"Otvorené","action":"Oznámenia (voliteľné)","noAttention":"Dobrá","metric_humidity":"RH","sourceData":"Home Assistant · Otvorte","allSafe":"Dobrá","warningReason":"Výstrahy počasia","unsafeReason":"Nechajte okná zatvorené","noWeather":"Nedostupné"},"hu":{"title":"Levegőminőség","subtitle":"Levegőminőség","outside":"Kint","goodOutside":"Szellőztetésre alkalmas","badOutside":"Tartsd csukva az ablakokat","missingOutside":"Nem érhető el","partialOutside":"Nem érhető el","roomStatus":"Helyiségek","safe":"Jó","attention":"Figyelmet igényel","unknown":"Nincs adat","readings":"Nyisd ki","windows":"Mérések","windowOpen":"Nyitva","windowClosed":"Zárva","windowUnknown":"Nincs adat","open":"Csukd be","close":"Automatikus értesítések","openAdvice":"Csukd be · Mérések","closeAdvice":"Automatikus értesítések · Mérések","blocked":"Tartsd csukva az ablakokat","ventilating":"Szellőztetés folyamatban","noWindows":"0 · Mérések","missingIndoor":"Nincs adat","noRooms":"Nincs beállított helyiség","missingCard":"Air Quality Advisor · Nyisd ki","more":"További részletek","less":"Kevesebb részlet","weather":"Időjárás","warnings":"Időjárási figyelmeztetések","limits":"Határérték","outdoorSensors":"Kültéri levegőminőség","noReadings":"Nincs adat","missing":"Nem érhető el","sensor":"Nyisd ki","partial":"Nem érhető el","wind":"Időjárás","humidity":"RH","unavailableWeather":"Nem érhető el","noOutdoor":"0 · Kültéri levegőminőség","warningActive":"Időjárási figyelmeztetések","warningUnknown":"Időjárási figyelmeztetések","allOkay":"Jó","indoorHigh":"Figyelmet igényel","notSafeToOpen":"Tartsd csukva az ablakokat","conditions":"Kint","measured":"Nyisd ki","activeWindows":"Nyitva","action":"Értesítések (opcionális)","noAttention":"Jó","metric_humidity":"RH","sourceData":"Home Assistant · Nyisd ki","allSafe":"Jó","warningReason":"Időjárási figyelmeztetések","unsafeReason":"Tartsd csukva az ablakokat","noWeather":"Nem érhető el"},"ro":{"title":"Calitatea aerului","subtitle":"Calitatea aerului","outside":"Exterior","goodOutside":"Potrivit pentru aerisire","badOutside":"Țineți ferestrele închise","missingOutside":"Indisponibil","partialOutside":"Indisponibil","roomStatus":"Camere","safe":"Bună","attention":"Necesită atenție","unknown":"Fără date","readings":"Deschideți","windows":"Măsurători","windowOpen":"Deschisă","windowClosed":"Închisă","windowUnknown":"Fără date","open":"Închideți","close":"Notificări automate","openAdvice":"Închideți · Măsurători","closeAdvice":"Notificări automate · Măsurători","blocked":"Țineți ferestrele închise","ventilating":"Aerisire în curs","noWindows":"0 · Măsurători","missingIndoor":"Fără date","noRooms":"Nu sunt camere configurate","missingCard":"Air Quality Advisor · Deschideți","more":"Mai multe detalii","less":"Mai puține detalii","weather":"Vreme","warnings":"Avertizări meteo","limits":"Prag","outdoorSensors":"Calitatea aerului exterior","noReadings":"Fără date","missing":"Indisponibil","sensor":"Deschideți","partial":"Indisponibil","wind":"Vreme","humidity":"RH","unavailableWeather":"Indisponibil","noOutdoor":"0 · Calitatea aerului exterior","warningActive":"Avertizări meteo","warningUnknown":"Avertizări meteo","allOkay":"Bună","indoorHigh":"Necesită atenție","notSafeToOpen":"Țineți ferestrele închise","conditions":"Exterior","measured":"Deschideți","activeWindows":"Deschisă","action":"Anunțuri (opțional)","noAttention":"Bună","metric_humidity":"RH","sourceData":"Home Assistant · Deschideți","allSafe":"Bună","warningReason":"Avertizări meteo","unsafeReason":"Țineți ferestrele închise","noWeather":"Indisponibil"},"bg":{"title":"Качество на въздуха","subtitle":"Качество на въздуха","outside":"Навън","goodOutside":"Подходящо за проветряване","badOutside":"Дръжте прозорците затворени","missingOutside":"Недостъпно","partialOutside":"Недостъпно","roomStatus":"Стаи","safe":"Добро","attention":"Изисква внимание","unknown":"Няма данни","readings":"Отворете","windows":"Измервания","windowOpen":"Отворен","windowClosed":"Затворен","windowUnknown":"Няма данни","open":"Затворете","close":"Автоматични известия","openAdvice":"Затворете · Измервания","closeAdvice":"Автоматични известия · Измервания","blocked":"Дръжте прозорците затворени","ventilating":"Проветряване","noWindows":"0 · Измервания","missingIndoor":"Няма данни","noRooms":"Няма настроени стаи","missingCard":"Air Quality Advisor · Отворете","more":"Повече подробности","less":"По-малко подробности","weather":"Време","warnings":"Метеорологични предупреждения","limits":"Праг","outdoorSensors":"Качество на външния въздух","noReadings":"Няма данни","missing":"Недостъпно","sensor":"Отворете","partial":"Недостъпно","wind":"Време","humidity":"RH","unavailableWeather":"Недостъпно","noOutdoor":"0 · Качество на външния въздух","warningActive":"Метеорологични предупреждения","warningUnknown":"Метеорологични предупреждения","allOkay":"Добро","indoorHigh":"Изисква внимание","notSafeToOpen":"Дръжте прозорците затворени","conditions":"Навън","measured":"Отворете","activeWindows":"Отворен","action":"Съобщения (по избор)","noAttention":"Добро","metric_humidity":"RH","sourceData":"Home Assistant · Отворете","allSafe":"Добро","warningReason":"Метеорологични предупреждения","unsafeReason":"Дръжте прозорците затворени","noWeather":"Недостъпно"},"hr":{"title":"Kvaliteta zraka","subtitle":"Kvaliteta zraka","outside":"Vani","goodOutside":"Pogodno za provjetravanje","badOutside":"Držite prozore zatvorenima","missingOutside":"Nedostupno","partialOutside":"Nedostupno","roomStatus":"Prostorije","safe":"Dobra","attention":"Potrebna pažnja","unknown":"Nema podataka","readings":"Otvorite","windows":"Mjerenja","windowOpen":"Otvoren","windowClosed":"Zatvoren","windowUnknown":"Nema podataka","open":"Zatvorite","close":"Automatske obavijesti","openAdvice":"Zatvorite · Mjerenja","closeAdvice":"Automatske obavijesti · Mjerenja","blocked":"Držite prozore zatvorenima","ventilating":"Provjetravanje","noWindows":"0 · Mjerenja","missingIndoor":"Nema podataka","noRooms":"Nema podešenih prostorija","missingCard":"Air Quality Advisor · Otvorite","more":"Više detalja","less":"Manje detalja","weather":"Vrijeme","warnings":"Vremenska upozorenja","limits":"Prag","outdoorSensors":"Kvaliteta vanjskog zraka","noReadings":"Nema podataka","missing":"Nedostupno","sensor":"Otvorite","partial":"Nedostupno","wind":"Vrijeme","humidity":"RH","unavailableWeather":"Nedostupno","noOutdoor":"0 · Kvaliteta vanjskog zraka","warningActive":"Vremenska upozorenja","warningUnknown":"Vremenska upozorenja","allOkay":"Dobra","indoorHigh":"Potrebna pažnja","notSafeToOpen":"Držite prozore zatvorenima","conditions":"Vani","measured":"Otvorite","activeWindows":"Otvoren","action":"Obavijesti (neobavezno)","noAttention":"Dobra","metric_humidity":"RH","sourceData":"Home Assistant · Otvorite","allSafe":"Dobra","warningReason":"Vremenska upozorenja","unsafeReason":"Držite prozore zatvorenima","noWeather":"Nedostupno"},"sr":{"title":"Квалитет ваздуха","subtitle":"Квалитет ваздуха","outside":"Напољу","goodOutside":"Погодно за проветравање","badOutside":"Држите прозоре затвореним","missingOutside":"Недоступно","partialOutside":"Недоступно","roomStatus":"Собе","safe":"Добар","attention":"Потребна пажња","unknown":"Нема података","readings":"Отворите","windows":"Мерења","windowOpen":"Отворен","windowClosed":"Затворен","windowUnknown":"Нема података","open":"Затворите","close":"Аутоматска обавештења","openAdvice":"Затворите · Мерења","closeAdvice":"Аутоматска обавештења · Мерења","blocked":"Држите прозоре затвореним","ventilating":"Проветравање","noWindows":"0 · Мерења","missingIndoor":"Нема података","noRooms":"Нема подешених соба","missingCard":"Air Quality Advisor · Отворите","more":"Више детаља","less":"Мање детаља","weather":"Време","warnings":"Временска упозорења","limits":"Праг","outdoorSensors":"Квалитет спољног ваздуха","noReadings":"Нема података","missing":"Недоступно","sensor":"Отворите","partial":"Недоступно","wind":"Време","humidity":"RH","unavailableWeather":"Недоступно","noOutdoor":"0 · Квалитет спољног ваздуха","warningActive":"Временска упозорења","warningUnknown":"Временска упозорења","allOkay":"Добар","indoorHigh":"Потребна пажња","notSafeToOpen":"Држите прозоре затвореним","conditions":"Напољу","measured":"Отворите","activeWindows":"Отворен","action":"Обавештења (опционо)","noAttention":"Добар","metric_humidity":"RH","sourceData":"Home Assistant · Отворите","allSafe":"Добар","warningReason":"Временска упозорења","unsafeReason":"Држите прозоре затвореним","noWeather":"Недоступно"},"sv":{"title":"Luftkvalitet","subtitle":"Luftkvalitet","outside":"Utomhus","goodOutside":"Bra för vädring","badOutside":"Håll fönstren stängda","missingOutside":"Inte tillgänglig","partialOutside":"Inte tillgänglig","roomStatus":"Rum","safe":"Bra","attention":"Behöver åtgärdas","unknown":"Inga data","readings":"Öppna","windows":"Mätningar","windowOpen":"Öppet","windowClosed":"Stängt","windowUnknown":"Inga data","open":"Stäng","close":"Automatiska aviseringar","openAdvice":"Stäng · Mätningar","closeAdvice":"Automatiska aviseringar · Mätningar","blocked":"Håll fönstren stängda","ventilating":"Vädring pågår","noWindows":"0 · Mätningar","missingIndoor":"Inga data","noRooms":"Inga rum konfigurerade","missingCard":"Air Quality Advisor · Öppna","more":"Fler detaljer","less":"Färre detaljer","weather":"Väder","warnings":"Vädervarningar","limits":"Gränsvärde","outdoorSensors":"Utomhusluftens kvalitet","noReadings":"Inga data","missing":"Inte tillgänglig","sensor":"Öppna","partial":"Inte tillgänglig","wind":"Väder","humidity":"RH","unavailableWeather":"Inte tillgänglig","noOutdoor":"0 · Utomhusluftens kvalitet","warningActive":"Vädervarningar","warningUnknown":"Vädervarningar","allOkay":"Bra","indoorHigh":"Behöver åtgärdas","notSafeToOpen":"Håll fönstren stängda","conditions":"Utomhus","measured":"Öppna","activeWindows":"Öppet","action":"Meddelanden (valfritt)","noAttention":"Bra","metric_humidity":"RH","sourceData":"Home Assistant · Öppna","allSafe":"Bra","warningReason":"Vädervarningar","unsafeReason":"Håll fönstren stängda","noWeather":"Inte tillgänglig"},"nb":{"title":"Luftkvalitet","subtitle":"Luftkvalitet","outside":"Ute","goodOutside":"Egnet for lufting","badOutside":"Hold vinduene lukket","missingOutside":"Ikke tilgjengelig","partialOutside":"Ikke tilgjengelig","roomStatus":"Rom","safe":"God","attention":"Trenger oppmerksomhet","unknown":"Ingen data","readings":"Åpne","windows":"Målinger","windowOpen":"Åpent","windowClosed":"Lukket","windowUnknown":"Ingen data","open":"Lukk","close":"Automatiske varsler","openAdvice":"Lukk · Målinger","closeAdvice":"Automatiske varsler · Målinger","blocked":"Hold vinduene lukket","ventilating":"Lufter nå","noWindows":"0 · Målinger","missingIndoor":"Ingen data","noRooms":"Ingen rom konfigurert","missingCard":"Air Quality Advisor · Åpne","more":"Flere detaljer","less":"Færre detaljer","weather":"Vær","warnings":"Værvarsler","limits":"Grenseverdi","outdoorSensors":"Luftkvalitet ute","noReadings":"Ingen data","missing":"Ikke tilgjengelig","sensor":"Åpne","partial":"Ikke tilgjengelig","wind":"Vær","humidity":"RH","unavailableWeather":"Ikke tilgjengelig","noOutdoor":"0 · Luftkvalitet ute","warningActive":"Værvarsler","warningUnknown":"Værvarsler","allOkay":"God","indoorHigh":"Trenger oppmerksomhet","notSafeToOpen":"Hold vinduene lukket","conditions":"Ute","measured":"Åpne","activeWindows":"Åpent","action":"Kunngjøringer (valgfritt)","noAttention":"God","metric_humidity":"RH","sourceData":"Home Assistant · Åpne","allSafe":"God","warningReason":"Værvarsler","unsafeReason":"Hold vinduene lukket","noWeather":"Ikke tilgjengelig"},"da":{"title":"Luftkvalitet","subtitle":"Luftkvalitet","outside":"Udenfor","goodOutside":"Egnet til udluftning","badOutside":"Hold vinduerne lukkede","missingOutside":"Ikke tilgængelig","partialOutside":"Ikke tilgængelig","roomStatus":"Rum","safe":"God","attention":"Kræver opmærksomhed","unknown":"Ingen data","readings":"Åbn","windows":"Målinger","windowOpen":"Åbent","windowClosed":"Lukket","windowUnknown":"Ingen data","open":"Luk","close":"Automatiske notifikationer","openAdvice":"Luk · Målinger","closeAdvice":"Automatiske notifikationer · Målinger","blocked":"Hold vinduerne lukkede","ventilating":"Udluftning i gang","noWindows":"0 · Målinger","missingIndoor":"Ingen data","noRooms":"Ingen rum konfigureret","missingCard":"Air Quality Advisor · Åbn","more":"Flere detaljer","less":"Færre detaljer","weather":"Vejr","warnings":"Vejradvarsler","limits":"Grænse","outdoorSensors":"Udendørs luftkvalitet","noReadings":"Ingen data","missing":"Ikke tilgængelig","sensor":"Åbn","partial":"Ikke tilgængelig","wind":"Vejr","humidity":"RH","unavailableWeather":"Ikke tilgængelig","noOutdoor":"0 · Udendørs luftkvalitet","warningActive":"Vejradvarsler","warningUnknown":"Vejradvarsler","allOkay":"God","indoorHigh":"Kræver opmærksomhed","notSafeToOpen":"Hold vinduerne lukkede","conditions":"Udenfor","measured":"Åbn","activeWindows":"Åbent","action":"Meddelelser (valgfrit)","noAttention":"God","metric_humidity":"RH","sourceData":"Home Assistant · Åbn","allSafe":"God","warningReason":"Vejradvarsler","unsafeReason":"Hold vinduerne lukkede","noWeather":"Ikke tilgængelig"},"fi":{"title":"Ilmanlaatu","subtitle":"Ilmanlaatu","outside":"Ulkona","goodOutside":"Sopii tuuletukseen","badOutside":"Pidä ikkunat kiinni","missingOutside":"Ei saatavilla","partialOutside":"Ei saatavilla","roomStatus":"Huoneet","safe":"Hyvä","attention":"Vaatii huomiota","unknown":"Ei tietoja","readings":"Avaa","windows":"Mittaukset","windowOpen":"Auki","windowClosed":"Kiinni","windowUnknown":"Ei tietoja","open":"Sulje","close":"Automaattiset ilmoitukset","openAdvice":"Sulje · Mittaukset","closeAdvice":"Automaattiset ilmoitukset · Mittaukset","blocked":"Pidä ikkunat kiinni","ventilating":"Tuuletus käynnissä","noWindows":"0 · Mittaukset","missingIndoor":"Ei tietoja","noRooms":"Huoneita ei ole määritetty","missingCard":"Air Quality Advisor · Avaa","more":"Lisätiedot","less":"Vähemmän tietoja","weather":"Sää","warnings":"Säävaroitukset","limits":"Raja-arvo","outdoorSensors":"Ulkoilman laatu","noReadings":"Ei tietoja","missing":"Ei saatavilla","sensor":"Avaa","partial":"Ei saatavilla","wind":"Sää","humidity":"RH","unavailableWeather":"Ei saatavilla","noOutdoor":"0 · Ulkoilman laatu","warningActive":"Säävaroitukset","warningUnknown":"Säävaroitukset","allOkay":"Hyvä","indoorHigh":"Vaatii huomiota","notSafeToOpen":"Pidä ikkunat kiinni","conditions":"Ulkona","measured":"Avaa","activeWindows":"Auki","action":"Ilmoitukset (valinnainen)","noAttention":"Hyvä","metric_humidity":"RH","sourceData":"Home Assistant · Avaa","allSafe":"Hyvä","warningReason":"Säävaroitukset","unsafeReason":"Pidä ikkunat kiinni","noWeather":"Ei saatavilla"},"id":{"title":"Kualitas udara","subtitle":"Kualitas udara","outside":"Di luar","goodOutside":"Baik untuk ventilasi","badOutside":"Biarkan jendela tertutup","missingOutside":"Tidak tersedia","partialOutside":"Tidak tersedia","roomStatus":"Ruangan","safe":"Baik","attention":"Perlu perhatian","unknown":"Tidak ada data","readings":"Buka","windows":"Pengukuran","windowOpen":"Terbuka","windowClosed":"Tertutup","windowUnknown":"Tidak ada data","open":"Tutup","close":"Notifikasi otomatis","openAdvice":"Tutup · Pengukuran","closeAdvice":"Notifikasi otomatis · Pengukuran","blocked":"Biarkan jendela tertutup","ventilating":"Sedang berventilasi","noWindows":"0 · Pengukuran","missingIndoor":"Tidak ada data","noRooms":"Belum ada ruangan","missingCard":"Air Quality Advisor · Buka","more":"Detail lainnya","less":"Lebih sedikit detail","weather":"Cuaca","warnings":"Peringatan cuaca","limits":"Batas","outdoorSensors":"Kualitas udara luar","noReadings":"Tidak ada data","missing":"Tidak tersedia","sensor":"Buka","partial":"Tidak tersedia","wind":"Cuaca","humidity":"RH","unavailableWeather":"Tidak tersedia","noOutdoor":"0 · Kualitas udara luar","warningActive":"Peringatan cuaca","warningUnknown":"Peringatan cuaca","allOkay":"Baik","indoorHigh":"Perlu perhatian","notSafeToOpen":"Biarkan jendela tertutup","conditions":"Di luar","measured":"Buka","activeWindows":"Terbuka","action":"Pengumuman (opsional)","noAttention":"Baik","metric_humidity":"RH","sourceData":"Home Assistant · Buka","allSafe":"Baik","warningReason":"Peringatan cuaca","unsafeReason":"Biarkan jendela tertutup","noWeather":"Tidak tersedia"},"vi":{"title":"Chất lượng không khí","subtitle":"Chất lượng không khí","outside":"Ngoài trời","goodOutside":"Phù hợp để thông gió","badOutside":"Giữ cửa sổ đóng","missingOutside":"Không khả dụng","partialOutside":"Không khả dụng","roomStatus":"Phòng","safe":"Tốt","attention":"Cần chú ý","unknown":"Không có dữ liệu","readings":"Mở","windows":"Đo lường","windowOpen":"Mở","windowClosed":"Đóng","windowUnknown":"Không có dữ liệu","open":"Đóng","close":"Thông báo tự động","openAdvice":"Đóng · Đo lường","closeAdvice":"Thông báo tự động · Đo lường","blocked":"Giữ cửa sổ đóng","ventilating":"Đang thông gió","noWindows":"0 · Đo lường","missingIndoor":"Không có dữ liệu","noRooms":"Chưa cấu hình phòng","missingCard":"Air Quality Advisor · Mở","more":"Chi tiết thêm","less":"Ít chi tiết hơn","weather":"Thời tiết","warnings":"Cảnh báo thời tiết","limits":"Ngưỡng","outdoorSensors":"Chất lượng không khí ngoài trời","noReadings":"Không có dữ liệu","missing":"Không khả dụng","sensor":"Mở","partial":"Không khả dụng","wind":"Thời tiết","humidity":"RH","unavailableWeather":"Không khả dụng","noOutdoor":"0 · Chất lượng không khí ngoài trời","warningActive":"Cảnh báo thời tiết","warningUnknown":"Cảnh báo thời tiết","allOkay":"Tốt","indoorHigh":"Cần chú ý","notSafeToOpen":"Giữ cửa sổ đóng","conditions":"Ngoài trời","measured":"Mở","activeWindows":"Mở","action":"Thông báo (tùy chọn)","noAttention":"Tốt","metric_humidity":"RH","sourceData":"Home Assistant · Mở","allSafe":"Tốt","warningReason":"Cảnh báo thời tiết","unsafeReason":"Giữ cửa sổ đóng","noWeather":"Không khả dụng"},"th":{"title":"คุณภาพอากาศ","subtitle":"คุณภาพอากาศ","outside":"ภายนอก","goodOutside":"เหมาะสำหรับการระบายอากาศ","badOutside":"ปิดหน้าต่างไว้","missingOutside":"ไม่พร้อมใช้งาน","partialOutside":"ไม่พร้อมใช้งาน","roomStatus":"ห้อง","safe":"ดี","attention":"ต้องตรวจสอบ","unknown":"ไม่มีข้อมูล","readings":"เปิด","windows":"ค่าที่วัด","windowOpen":"เปิด","windowClosed":"ปิด","windowUnknown":"ไม่มีข้อมูล","open":"ปิด","close":"การแจ้งเตือนอัตโนมัติ","openAdvice":"ปิด · ค่าที่วัด","closeAdvice":"การแจ้งเตือนอัตโนมัติ · ค่าที่วัด","blocked":"ปิดหน้าต่างไว้","ventilating":"กำลังระบายอากาศ","noWindows":"0 · ค่าที่วัด","missingIndoor":"ไม่มีข้อมูล","noRooms":"ยังไม่ได้ตั้งค่าห้อง","missingCard":"Air Quality Advisor · เปิด","more":"รายละเอียดเพิ่มเติม","less":"รายละเอียดน้อยลง","weather":"สภาพอากาศ","warnings":"คำเตือนสภาพอากาศ","limits":"ค่าขีดจำกัด","outdoorSensors":"คุณภาพอากาศภายนอก","noReadings":"ไม่มีข้อมูล","missing":"ไม่พร้อมใช้งาน","sensor":"เปิด","partial":"ไม่พร้อมใช้งาน","wind":"สภาพอากาศ","humidity":"RH","unavailableWeather":"ไม่พร้อมใช้งาน","noOutdoor":"0 · คุณภาพอากาศภายนอก","warningActive":"คำเตือนสภาพอากาศ","warningUnknown":"คำเตือนสภาพอากาศ","allOkay":"ดี","indoorHigh":"ต้องตรวจสอบ","notSafeToOpen":"ปิดหน้าต่างไว้","conditions":"ภายนอก","measured":"เปิด","activeWindows":"เปิด","action":"การประกาศ (ไม่บังคับ)","noAttention":"ดี","metric_humidity":"RH","sourceData":"Home Assistant · เปิด","allSafe":"ดี","warningReason":"คำเตือนสภาพอากาศ","unsafeReason":"ปิดหน้าต่างไว้","noWeather":"ไม่พร้อมใช้งาน"},"hi":{"title":"वायु गुणवत्ता","subtitle":"वायु गुणवत्ता","outside":"बाहर","goodOutside":"हवादारी के लिए अनुकूल","badOutside":"खिड़कियाँ बंद रखें","missingOutside":"अनुपलब्ध","partialOutside":"अनुपलब्ध","roomStatus":"कमरे","safe":"अच्छी","attention":"ध्यान आवश्यक","unknown":"कोई डेटा नहीं","readings":"खोलें","windows":"माप","windowOpen":"खुली","windowClosed":"बंद","windowUnknown":"कोई डेटा नहीं","open":"बंद करें","close":"स्वचालित सूचनाएँ","openAdvice":"बंद करें · माप","closeAdvice":"स्वचालित सूचनाएँ · माप","blocked":"खिड़कियाँ बंद रखें","ventilating":"हवादारी जारी","noWindows":"0 · माप","missingIndoor":"कोई डेटा नहीं","noRooms":"कोई कमरा नहीं चुना","missingCard":"Air Quality Advisor · खोलें","more":"और जानकारी","less":"कम जानकारी","weather":"मौसम","warnings":"मौसम चेतावनियाँ","limits":"सीमा","outdoorSensors":"बाहरी वायु गुणवत्ता","noReadings":"कोई डेटा नहीं","missing":"अनुपलब्ध","sensor":"खोलें","partial":"अनुपलब्ध","wind":"मौसम","humidity":"RH","unavailableWeather":"अनुपलब्ध","noOutdoor":"0 · बाहरी वायु गुणवत्ता","warningActive":"मौसम चेतावनियाँ","warningUnknown":"मौसम चेतावनियाँ","allOkay":"अच्छी","indoorHigh":"ध्यान आवश्यक","notSafeToOpen":"खिड़कियाँ बंद रखें","conditions":"बाहर","measured":"खोलें","activeWindows":"खुली","action":"घोषणाएँ (वैकल्पिक)","noAttention":"अच्छी","metric_humidity":"RH","sourceData":"Home Assistant · खोलें","allSafe":"अच्छी","warningReason":"मौसम चेतावनियाँ","unsafeReason":"खिड़कियाँ बंद रखें","noWeather":"अनुपलब्ध"},"zh-hans":{"title":"空气质量","subtitle":"空气质量","outside":"室外","goodOutside":"适合通风","badOutside":"请保持窗户关闭","missingOutside":"不可用","partialOutside":"不可用","roomStatus":"房间","safe":"良好","attention":"需要关注","unknown":"无数据","readings":"打开","windows":"测量值","windowOpen":"已打开","windowClosed":"已关闭","windowUnknown":"无数据","open":"关闭","close":"自动通知","openAdvice":"关闭 · 测量值","closeAdvice":"自动通知 · 测量值","blocked":"请保持窗户关闭","ventilating":"正在通风","noWindows":"0 · 测量值","missingIndoor":"无数据","noRooms":"尚未配置房间","missingCard":"Air Quality Advisor · 打开","more":"更多详情","less":"收起详情","weather":"天气","warnings":"天气预警","limits":"阈值","outdoorSensors":"室外空气质量","noReadings":"无数据","missing":"不可用","sensor":"打开","partial":"不可用","wind":"天气","humidity":"RH","unavailableWeather":"不可用","noOutdoor":"0 · 室外空气质量","warningActive":"天气预警","warningUnknown":"天气预警","allOkay":"良好","indoorHigh":"需要关注","notSafeToOpen":"请保持窗户关闭","conditions":"室外","measured":"打开","activeWindows":"已打开","action":"播报（可选）","noAttention":"良好","metric_humidity":"RH","sourceData":"Home Assistant · 打开","allSafe":"良好","warningReason":"天气预警","unsafeReason":"请保持窗户关闭","noWeather":"不可用"},"zh-hant":{"title":"空氣品質","subtitle":"空氣品質","outside":"室外","goodOutside":"適合通風","badOutside":"請保持窗戶關閉","missingOutside":"無法使用","partialOutside":"無法使用","roomStatus":"房間","safe":"良好","attention":"需要注意","unknown":"無資料","readings":"開啟","windows":"測量值","windowOpen":"已開啟","windowClosed":"已關閉","windowUnknown":"無資料","open":"關閉","close":"自動通知","openAdvice":"關閉 · 測量值","closeAdvice":"自動通知 · 測量值","blocked":"請保持窗戶關閉","ventilating":"正在通風","noWindows":"0 · 測量值","missingIndoor":"無資料","noRooms":"尚未設定房間","missingCard":"Air Quality Advisor · 開啟","more":"更多詳情","less":"收起詳情","weather":"天氣","warnings":"天氣警報","limits":"閾值","outdoorSensors":"室外空氣品質","noReadings":"無資料","missing":"無法使用","sensor":"開啟","partial":"無法使用","wind":"天氣","humidity":"RH","unavailableWeather":"無法使用","noOutdoor":"0 · 室外空氣品質","warningActive":"天氣警報","warningUnknown":"天氣警報","allOkay":"良好","indoorHigh":"需要注意","notSafeToOpen":"請保持窗戶關閉","conditions":"室外","measured":"開啟","activeWindows":"已開啟","action":"播報（選用）","noAttention":"良好","metric_humidity":"RH","sourceData":"Home Assistant · 開啟","allSafe":"良好","warningReason":"天氣警報","unsafeReason":"請保持窗戶關閉","noWeather":"無法使用"},"ja":{"title":"空気質","subtitle":"空気質","outside":"屋外","goodOutside":"換気に適しています","badOutside":"窓を閉めてください","missingOutside":"利用不可","partialOutside":"利用不可","roomStatus":"部屋","safe":"良好","attention":"注意が必要","unknown":"データなし","readings":"開ける","windows":"測定値","windowOpen":"開","windowClosed":"閉","windowUnknown":"データなし","open":"閉める","close":"自動通知","openAdvice":"閉める · 測定値","closeAdvice":"自動通知 · 測定値","blocked":"窓を閉めてください","ventilating":"換気中","noWindows":"0 · 測定値","missingIndoor":"データなし","noRooms":"部屋が設定されていません","missingCard":"Air Quality Advisor · 開ける","more":"詳細を表示","less":"詳細を閉じる","weather":"天気","warnings":"気象警報","limits":"しきい値","outdoorSensors":"屋外の空気質","noReadings":"データなし","missing":"利用不可","sensor":"開ける","partial":"利用不可","wind":"天気","humidity":"RH","unavailableWeather":"利用不可","noOutdoor":"0 · 屋外の空気質","warningActive":"気象警報","warningUnknown":"気象警報","allOkay":"良好","indoorHigh":"注意が必要","notSafeToOpen":"窓を閉めてください","conditions":"屋外","measured":"開ける","activeWindows":"開","action":"通知（任意）","noAttention":"良好","metric_humidity":"RH","sourceData":"Home Assistant · 開ける","allSafe":"良好","warningReason":"気象警報","unsafeReason":"窓を閉めてください","noWeather":"利用不可"},"ko":{"title":"공기질","subtitle":"공기질","outside":"실외","goodOutside":"환기하기 좋음","badOutside":"창문을 닫아 두세요","missingOutside":"사용할 수 없음","partialOutside":"사용할 수 없음","roomStatus":"방","safe":"좋음","attention":"주의 필요","unknown":"데이터 없음","readings":"열기","windows":"측정값","windowOpen":"열림","windowClosed":"닫힘","windowUnknown":"데이터 없음","open":"닫기","close":"자동 알림","openAdvice":"닫기 · 측정값","closeAdvice":"자동 알림 · 측정값","blocked":"창문을 닫아 두세요","ventilating":"환기 중","noWindows":"0 · 측정값","missingIndoor":"데이터 없음","noRooms":"설정된 방 없음","missingCard":"Air Quality Advisor · 열기","more":"자세히 보기","less":"간단히 보기","weather":"날씨","warnings":"기상 경보","limits":"임계값","outdoorSensors":"실외 공기질","noReadings":"데이터 없음","missing":"사용할 수 없음","sensor":"열기","partial":"사용할 수 없음","wind":"날씨","humidity":"RH","unavailableWeather":"사용할 수 없음","noOutdoor":"0 · 실외 공기질","warningActive":"기상 경보","warningUnknown":"기상 경보","allOkay":"좋음","indoorHigh":"주의 필요","notSafeToOpen":"창문을 닫아 두세요","conditions":"실외","measured":"열기","activeWindows":"열림","action":"알림(선택 사항)","noAttention":"좋음","metric_humidity":"RH","sourceData":"Home Assistant · 열기","allSafe":"좋음","warningReason":"기상 경보","unsafeReason":"창문을 닫아 두세요","noWeather":"사용할 수 없음"},"ar":{"title":"جودة الهواء","subtitle":"جودة الهواء","outside":"الخارج","goodOutside":"مناسب للتهوية","badOutside":"أبقِ النوافذ مغلقة","missingOutside":"غير متوفر","partialOutside":"غير متوفر","roomStatus":"الغرف","safe":"جيدة","attention":"تحتاج إلى انتباه","unknown":"لا توجد بيانات","readings":"افتح","windows":"القياسات","windowOpen":"مفتوحة","windowClosed":"مغلقة","windowUnknown":"لا توجد بيانات","open":"أغلق","close":"إشعارات تلقائية","openAdvice":"أغلق · القياسات","closeAdvice":"إشعارات تلقائية · القياسات","blocked":"أبقِ النوافذ مغلقة","ventilating":"التهوية جارية","noWindows":"0 · القياسات","missingIndoor":"لا توجد بيانات","noRooms":"لم تُحدد غرف","missingCard":"Air Quality Advisor · افتح","more":"مزيد من التفاصيل","less":"تفاصيل أقل","weather":"الطقس","warnings":"تحذيرات الطقس","limits":"الحد","outdoorSensors":"جودة الهواء الخارجي","noReadings":"لا توجد بيانات","missing":"غير متوفر","sensor":"افتح","partial":"غير متوفر","wind":"الطقس","humidity":"RH","unavailableWeather":"غير متوفر","noOutdoor":"0 · جودة الهواء الخارجي","warningActive":"تحذيرات الطقس","warningUnknown":"تحذيرات الطقس","allOkay":"جيدة","indoorHigh":"تحتاج إلى انتباه","notSafeToOpen":"أبقِ النوافذ مغلقة","conditions":"الخارج","measured":"افتح","activeWindows":"مفتوحة","action":"الإعلانات (اختياري)","noAttention":"جيدة","metric_humidity":"RH","sourceData":"Home Assistant · افتح","allSafe":"جيدة","warningReason":"تحذيرات الطقس","unsafeReason":"أبقِ النوافذ مغلقة","noWeather":"غير متوفر"},"he":{"title":"איכות האוויר","subtitle":"איכות האוויר","outside":"בחוץ","goodOutside":"מתאים לאוורור","badOutside":"השאירו חלונות סגורים","missingOutside":"לא זמין","partialOutside":"לא זמין","roomStatus":"חדרים","safe":"טובה","attention":"דורשת טיפול","unknown":"אין נתונים","readings":"פתחו","windows":"מדידות","windowOpen":"פתוח","windowClosed":"סגור","windowUnknown":"אין נתונים","open":"סגרו","close":"התראות אוטומטיות","openAdvice":"סגרו · מדידות","closeAdvice":"התראות אוטומטיות · מדידות","blocked":"השאירו חלונות סגורים","ventilating":"מתאוורר","noWindows":"0 · מדידות","missingIndoor":"אין נתונים","noRooms":"לא הוגדרו חדרים","missingCard":"Air Quality Advisor · פתחו","more":"פרטים נוספים","less":"פחות פרטים","weather":"מזג אוויר","warnings":"אזהרות מזג אוויר","limits":"סף","outdoorSensors":"איכות האוויר בחוץ","noReadings":"אין נתונים","missing":"לא זמין","sensor":"פתחו","partial":"לא זמין","wind":"מזג אוויר","humidity":"RH","unavailableWeather":"לא זמין","noOutdoor":"0 · איכות האוויר בחוץ","warningActive":"אזהרות מזג אוויר","warningUnknown":"אזהרות מזג אוויר","allOkay":"טובה","indoorHigh":"דורשת טיפול","notSafeToOpen":"השאירו חלונות סגורים","conditions":"בחוץ","measured":"פתחו","activeWindows":"פתוח","action":"הודעות (אופציונלי)","noAttention":"טובה","metric_humidity":"RH","sourceData":"Home Assistant · פתחו","allSafe":"טובה","warningReason":"אזהרות מזג אוויר","unsafeReason":"השאירו חלונות סגורים","noWeather":"לא זמין"},"fa":{"title":"کیفیت هوا","subtitle":"کیفیت هوا","outside":"بیرون","goodOutside":"مناسب تهویه","badOutside":"پنجره‌ها را بسته نگه دارید","missingOutside":"در دسترس نیست","partialOutside":"در دسترس نیست","roomStatus":"اتاق‌ها","safe":"خوب","attention":"نیازمند توجه","unknown":"بدون داده","readings":"باز کنید","windows":"اندازه‌گیری‌ها","windowOpen":"باز","windowClosed":"بسته","windowUnknown":"بدون داده","open":"ببندید","close":"اعلان‌های خودکار","openAdvice":"ببندید · اندازه‌گیری‌ها","closeAdvice":"اعلان‌های خودکار · اندازه‌گیری‌ها","blocked":"پنجره‌ها را بسته نگه دارید","ventilating":"در حال تهویه","noWindows":"0 · اندازه‌گیری‌ها","missingIndoor":"بدون داده","noRooms":"اتاقی تنظیم نشده است","missingCard":"Air Quality Advisor · باز کنید","more":"جزئیات بیشتر","less":"جزئیات کمتر","weather":"آب‌وهوا","warnings":"هشدارهای آب‌وهوا","limits":"آستانه","outdoorSensors":"کیفیت هوای بیرون","noReadings":"بدون داده","missing":"در دسترس نیست","sensor":"باز کنید","partial":"در دسترس نیست","wind":"آب‌وهوا","humidity":"RH","unavailableWeather":"در دسترس نیست","noOutdoor":"0 · کیفیت هوای بیرون","warningActive":"هشدارهای آب‌وهوا","warningUnknown":"هشدارهای آب‌وهوا","allOkay":"خوب","indoorHigh":"نیازمند توجه","notSafeToOpen":"پنجره‌ها را بسته نگه دارید","conditions":"بیرون","measured":"باز کنید","activeWindows":"باز","action":"اعلان‌ها (اختیاری)","noAttention":"خوب","metric_humidity":"RH","sourceData":"Home Assistant · باز کنید","allSafe":"خوب","warningReason":"هشدارهای آب‌وهوا","unsafeReason":"پنجره‌ها را بسته نگه دارید","noWeather":"در دسترس نیست"},"bn":{"title":"বায়ুর মান","subtitle":"বায়ুর মান","outside":"বাইরে","goodOutside":"বায়ু চলাচলের উপযোগী","badOutside":"জানালা বন্ধ রাখুন","missingOutside":"পাওয়া যাচ্ছে না","partialOutside":"পাওয়া যাচ্ছে না","roomStatus":"কক্ষ","safe":"ভালো","attention":"নজর দেওয়া দরকার","unknown":"তথ্য নেই","readings":"খুলুন","windows":"পরিমাপ","windowOpen":"খোলা","windowClosed":"বন্ধ","windowUnknown":"তথ্য নেই","open":"বন্ধ করুন","close":"স্বয়ংক্রিয় বিজ্ঞপ্তি","openAdvice":"বন্ধ করুন · পরিমাপ","closeAdvice":"স্বয়ংক্রিয় বিজ্ঞপ্তি · পরিমাপ","blocked":"জানালা বন্ধ রাখুন","ventilating":"বায়ু চলাচল করছে","noWindows":"0 · পরিমাপ","missingIndoor":"তথ্য নেই","noRooms":"কোনো কক্ষ সেট করা নেই","missingCard":"Air Quality Advisor · খুলুন","more":"বিস্তারিত","less":"কম বিস্তারিত","weather":"আবহাওয়া","warnings":"আবহাওয়ার সতর্কতা","limits":"সীমা","outdoorSensors":"বাইরের বায়ুর মান","noReadings":"তথ্য নেই","missing":"পাওয়া যাচ্ছে না","sensor":"খুলুন","partial":"পাওয়া যাচ্ছে না","wind":"আবহাওয়া","humidity":"RH","unavailableWeather":"পাওয়া যাচ্ছে না","noOutdoor":"0 · বাইরের বায়ুর মান","warningActive":"আবহাওয়ার সতর্কতা","warningUnknown":"আবহাওয়ার সতর্কতা","allOkay":"ভালো","indoorHigh":"নজর দেওয়া দরকার","notSafeToOpen":"জানালা বন্ধ রাখুন","conditions":"বাইরে","measured":"খুলুন","activeWindows":"খোলা","action":"ঘোষণা (ঐচ্ছিক)","noAttention":"ভালো","metric_humidity":"RH","sourceData":"Home Assistant · খুলুন","allSafe":"ভালো","warningReason":"আবহাওয়ার সতর্কতা","unsafeReason":"জানালা বন্ধ রাখুন","noWeather":"পাওয়া যাচ্ছে না"},"ur":{"title":"ہوا کا معیار","subtitle":"ہوا کا معیار","outside":"باہر","goodOutside":"ہواداری کے لیے مناسب","badOutside":"کھڑکیاں بند رکھیں","missingOutside":"دستیاب نہیں","partialOutside":"دستیاب نہیں","roomStatus":"کمرے","safe":"اچھا","attention":"توجہ درکار","unknown":"کوئی ڈیٹا نہیں","readings":"کھولیں","windows":"پیمائشیں","windowOpen":"کھلی","windowClosed":"بند","windowUnknown":"کوئی ڈیٹا نہیں","open":"بند کریں","close":"خودکار اطلاعات","openAdvice":"بند کریں · پیمائشیں","closeAdvice":"خودکار اطلاعات · پیمائشیں","blocked":"کھڑکیاں بند رکھیں","ventilating":"ہواداری جاری","noWindows":"0 · پیمائشیں","missingIndoor":"کوئی ڈیٹا نہیں","noRooms":"کوئی کمرہ منتخب نہیں","missingCard":"Air Quality Advisor · کھولیں","more":"مزید تفصیلات","less":"کم تفصیلات","weather":"موسم","warnings":"موسم کی تنبیہات","limits":"حد","outdoorSensors":"بیرونی ہوا کا معیار","noReadings":"کوئی ڈیٹا نہیں","missing":"دستیاب نہیں","sensor":"کھولیں","partial":"دستیاب نہیں","wind":"موسم","humidity":"RH","unavailableWeather":"دستیاب نہیں","noOutdoor":"0 · بیرونی ہوا کا معیار","warningActive":"موسم کی تنبیہات","warningUnknown":"موسم کی تنبیہات","allOkay":"اچھا","indoorHigh":"توجہ درکار","notSafeToOpen":"کھڑکیاں بند رکھیں","conditions":"باہر","measured":"کھولیں","activeWindows":"کھلی","action":"اعلانات (اختیاری)","noAttention":"اچھا","metric_humidity":"RH","sourceData":"Home Assistant · کھولیں","allSafe":"اچھا","warningReason":"موسم کی تنبیہات","unsafeReason":"کھڑکیاں بند رکھیں","noWeather":"دستیاب نہیں"},"ta":{"title":"காற்றுத் தரம்","subtitle":"காற்றுத் தரம்","outside":"வெளியே","goodOutside":"காற்றோட்டத்திற்கு ஏற்றது","badOutside":"சாளரங்களை மூடி வைக்கவும்","missingOutside":"கிடைக்கவில்லை","partialOutside":"கிடைக்கவில்லை","roomStatus":"அறைகள்","safe":"நன்று","attention":"கவனம் தேவை","unknown":"தரவு இல்லை","readings":"திறக்கவும்","windows":"அளவீடுகள்","windowOpen":"திறந்தது","windowClosed":"மூடியது","windowUnknown":"தரவு இல்லை","open":"மூடவும்","close":"தானியங்கி அறிவிப்புகள்","openAdvice":"மூடவும் · அளவீடுகள்","closeAdvice":"தானியங்கி அறிவிப்புகள் · அளவீடுகள்","blocked":"சாளரங்களை மூடி வைக்கவும்","ventilating":"காற்றோட்டம் நடைபெறுகிறது","noWindows":"0 · அளவீடுகள்","missingIndoor":"தரவு இல்லை","noRooms":"அறைகள் அமைக்கப்படவில்லை","missingCard":"Air Quality Advisor · திறக்கவும்","more":"மேலும் விவரங்கள்","less":"குறைந்த விவரங்கள்","weather":"வானிலை","warnings":"வானிலை எச்சரிக்கைகள்","limits":"வரம்பு","outdoorSensors":"வெளிப்புறக் காற்றுத் தரம்","noReadings":"தரவு இல்லை","missing":"கிடைக்கவில்லை","sensor":"திறக்கவும்","partial":"கிடைக்கவில்லை","wind":"வானிலை","humidity":"RH","unavailableWeather":"கிடைக்கவில்லை","noOutdoor":"0 · வெளிப்புறக் காற்றுத் தரம்","warningActive":"வானிலை எச்சரிக்கைகள்","warningUnknown":"வானிலை எச்சரிக்கைகள்","allOkay":"நன்று","indoorHigh":"கவனம் தேவை","notSafeToOpen":"சாளரங்களை மூடி வைக்கவும்","conditions":"வெளியே","measured":"திறக்கவும்","activeWindows":"திறந்தது","action":"அறிவிப்புகள் (விருப்பம்)","noAttention":"நன்று","metric_humidity":"RH","sourceData":"Home Assistant · திறக்கவும்","allSafe":"நன்று","warningReason":"வானிலை எச்சரிக்கைகள்","unsafeReason":"சாளரங்களை மூடி வைக்கவும்","noWeather":"கிடைக்கவில்லை"}};
  for (const [locale, translated] of Object.entries(EXTRA_LANGUAGE)) {
    LANGUAGE[locale] = {...translated, ...(LANGUAGE[locale] || {})};
  }
  const MOLD_NAMES = {"en":"Mold indication","de":"Schimmelindikator","el":"Ένδειξη μούχλας","fr":"Indicateur de moisissure","es":"Indicador de moho","ar":"مؤشر العفن","bg":"Индикатор за мухъл","bn":"ছাঁচের সূচক","cs":"Indikátor plísní","da":"Skimmelindikator","fa":"شاخص کپک","fi":"Homeindikaattori","he":"מדד עובש","hi":"फफूंद संकेतक","hr":"Pokazatelj plijesni","hu":"Penészesedési mutató","id":"Indikator jamur","it":"Indicatore muffa","ja":"カビ指標","ko":"곰팡이 지표","nb":"Muggindikator","nl":"Schimmelindicator","pl":"Wskaźnik pleśni","pt":"Indicador de bolor","pt-br":"Indicador de mofo","ro":"Indicator de mucegai","ru":"Индикатор плесени","sk":"Indikátor plesní","sr":"Индикатор буђи","sv":"Mögelindikator","ta":"பூஞ்சை குறியீடு","th":"ตัวชี้วัดเชื้อรา","tr":"Küf göstergesi","uk":"Індикатор цвілі","ur":"پھپھوندی کی نشاندہی","vi":"Chỉ số nấm mốc","zh-hans":"霉菌指标","zh-hant":"黴菌指標"};
  for (const [locale, name] of Object.entries(MOLD_NAMES)) {
    if (LANGUAGE[locale]) LANGUAGE[locale].metric_mold = name;
  }
  // Differentiate a never-calibrated room from temporarily unavailable
  // measurements. Keep these short status labels localized for every card UI.
  const MOLD_STATUS_TEXT = {"en":["Mold indicator not calibrated","Mold indicator data unavailable"],"de":["Schimmelindikator nicht kalibriert","Messdaten für Schimmelindikator fehlen"],"el":["Η ένδειξη μούχλας δεν έχει βαθμονομηθεί","Λείπουν δεδομένα για την ένδειξη μούχλας"],"fr":["Indicateur de moisissure non calibré","Données de moisissure indisponibles"],"es":["Indicador de moho sin calibrar","Faltan datos para el indicador de moho"],"ar":["مؤشر العفن غير معاير","بيانات مؤشر العفن غير متاحة"],"bg":["Индикаторът за мухъл не е калибриран","Липсват данни за индикатора за мухъл"],"bn":["ছাঁচের সূচক ক্যালিব্রেট করা হয়নি","ছাঁচের সূচকের তথ্য অনুপলব্ধ"],"cs":["Indikátor plísně není kalibrován","Chybí údaje pro indikátor plísně"],"da":["Skimmelindikator er ikke kalibreret","Data til skimmelindikator mangler"],"fa":["شاخص کپک کالیبره نشده است","داده‌های شاخص کپک در دسترس نیست"],"fi":["Homeindikaattoria ei ole kalibroitu","Homeindikaattorin tiedot puuttuvat"],"he":["מדד העובש לא כויל","חסרים נתונים למדד העובש"],"hi":["फफूंद संकेतक कैलिब्रेट नहीं है","फफूंद संकेतक का डेटा उपलब्ध नहीं"],"hr":["Pokazatelj plijesni nije kalibriran","Nedostaju podaci za pokazatelj plijesni"],"hu":["A penészmutató nincs kalibrálva","Hiányoznak a penészmutató adatai"],"id":["Indikator jamur belum dikalibrasi","Data indikator jamur tidak tersedia"],"it":["Indicatore muffa non calibrato","Dati dell'indicatore muffa non disponibili"],"ja":["カビ指標は未校正です","カビ指標のデータがありません"],"ko":["곰팡이 지표가 보정되지 않았습니다","곰팡이 지표 데이터가 없습니다"],"nb":["Muggindikator er ikke kalibrert","Data for muggindikatoren mangler"],"nl":["Schimmelindicator niet gekalibreerd","Gegevens voor schimmelindicator ontbreken"],"pl":["Wskaźnik pleśni nie został skalibrowany","Brak danych dla wskaźnika pleśni"],"pt":["Indicador de bolor não calibrado","Dados do indicador de bolor indisponíveis"],"pt-br":["Indicador de mofo não calibrado","Dados do indicador de mofo indisponíveis"],"ro":["Indicatorul de mucegai nu este calibrat","Lipsesc date pentru indicatorul de mucegai"],"ru":["Индикатор плесени не откалиброван","Нет данных для индикатора плесени"],"sk":["Indikátor plesní nie je kalibrovaný","Chýbajú údaje indikátora plesní"],"sr":["Индикатор буђи није калибрисан","Недостају подаци за индикатор буђи"],"sv":["Mögelindikatorn är inte kalibrerad","Data för mögelindikatorn saknas"],"ta":["பூஞ்சை குறியீடு அளவுத்திருத்தம் செய்யப்படவில்லை","பூஞ்சை குறியீட்டிற்கான தரவு இல்லை"],"th":["ยังไม่ได้ปรับเทียบตัวชี้วัดเชื้อรา","ไม่มีข้อมูลสำหรับตัวชี้วัดเชื้อรา"],"tr":["Küf göstergesi kalibre edilmedi","Küf göstergesi verileri eksik"],"uk":["Індикатор цвілі не відкалібровано","Немає даних для індикатора цвілі"],"ur":["پھپھوندی کے اشارے کی کیلیبریشن نہیں ہوئی","پھپھوندی کے اشارے کا ڈیٹا دستیاب نہیں"],"vi":["Chỉ số nấm mốc chưa được hiệu chuẩn","Thiếu dữ liệu chỉ số nấm mốc"],"zh-hans":["霉菌指标尚未校准","霉菌指标缺少数据"],"zh-hant":["黴菌指標尚未校準","黴菌指標缺少資料"]};
  for (const [locale, [needsCalibration, missingInputs]] of Object.entries(MOLD_STATUS_TEXT)) {
    if (LANGUAGE[locale]) {
      LANGUAGE[locale].moldNotCalibrated = needsCalibration;
      LANGUAGE[locale].moldInputsUnavailable = missingInputs;
    }
  }
  // Full guidance in the five main UI languages; other locales retain their
  // localized measurement names and show universally understood sensor units.
  const MOLD_INPUT_WARNING_LABELS = {"en":{"calibration":"Measure and save the coldest-surface temperature in Room settings","indoor_temperature":"Room temperature sensor has no valid reading","outdoor_temperature":"Selected weather entity has no usable outdoor temperature","humidity":"No valid nonzero room humidity readings available","calculation":"Mold estimate cannot be calculated from current values"},"de":{"calibration":"Temperatur der kältesten Oberfläche in den Raumeinstellungen messen und speichern","indoor_temperature":"Raumtemperatursensor liefert keinen gültigen Messwert","outdoor_temperature":"Ausgewählte Wetterentität liefert keine gültige Außentemperatur","humidity":"Keine gültigen Raumfeuchtewerte über 0 % verfügbar","calculation":"Schimmelindikator kann nicht berechnet werden"},"el":{"calibration":"Μέτρησε και αποθήκευσε τη θερμοκρασία της πιο κρύας επιφάνειας στις ρυθμίσεις χώρου","indoor_temperature":"Δεν υπάρχει έγκυρη μέτρηση θερμοκρασίας δωματίου","outdoor_temperature":"Η επιλεγμένη οντότητα καιρού δεν δίνει έγκυρη εξωτερική θερμοκρασία","humidity":"Δεν υπάρχουν έγκυρες μετρήσεις υγρασίας δωματίου πάνω από 0%","calculation":"Δεν είναι δυνατός ο υπολογισμός της ένδειξης μούχλας"},"fr":{"calibration":"Mesurez et enregistrez la température du point le plus froid dans les paramètres de la pièce","indoor_temperature":"Aucune température intérieure valide n'est disponible","outdoor_temperature":"L'entité météo choisie ne fournit pas de température extérieure valide","humidity":"Aucune humidité ambiante valide supérieure à 0 % disponible","calculation":"Impossible de calculer l'indicateur de moisissure"},"es":{"calibration":"Mide y guarda la temperatura de la superficie más fría en la configuración de la habitación","indoor_temperature":"No hay una lectura válida de temperatura interior","outdoor_temperature":"La entidad meteorológica seleccionada no proporciona temperatura exterior válida","humidity":"No hay humedad interior válida superior al 0 % disponible","calculation":"No se puede calcular el indicador de moho"}};

  const RTL_LANGUAGES = new Set(['ar', 'he', 'fa', 'ur']);
  function cardLanguage(code) {
    const tag = String(code || 'en').replaceAll('_','-').toLowerCase();
    if (LANGUAGE[tag]) return tag;
    if (tag.startsWith('zh')) return /hant|-(tw|hk|mo)/.test(tag) ? 'zh-hant' : 'zh-hans';
    if (tag.startsWith('pt-')) return tag === 'pt-br' ? 'pt-br' : 'pt';
    const root = tag.split('-')[0];
    if (root === 'no') return 'nb';
    return LANGUAGE[root] ? root : 'en';
  }

  const ICON = {
    safe:'mdi:check-circle-outline', attention:'mdi:alert-circle-outline', unknown:'mdi:help-circle-outline',
    partial:'mdi:information-outline', unsafe:'mdi:weather-windy',
    sunny:'mdi:weather-sunny', 'clear-night':'mdi:weather-night',
    partlycloudy:'mdi:weather-partly-cloudy', cloudy:'mdi:weather-cloudy',
    rainy:'mdi:weather-rainy', pouring:'mdi:weather-pouring',
    'lightning-rainy':'mdi:weather-lightning-rainy', lightning:'mdi:weather-lightning',
    fog:'mdi:weather-fog', snowy:'mdi:weather-snowy', windy:'mdi:weather-windy',
    'windy-variant':'mdi:weather-windy-variant', exceptional:'mdi:alert-octagon-outline',
    hail:'mdi:weather-hail', snowyrainy:'mdi:weather-snowy-rainy'
  };
  const METRIC_ICON = { co2:'mdi:molecule-co2', aqi:'mdi:air-filter', pm25:'mdi:blur',
    pm10:'mdi:blur', voc:'mdi:flask-outline', voc_parts:'mdi:flask-outline',
    humidity:'mdi:water-percent', mold:'mdi:water-alert-outline' };
  const ESC_MAP = {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'};
  const escape = (s) => String(s ?? '').replace(/[&<>"']/g, (ch) => ESC_MAP[ch]);
  const clamp = (num,min,max) => Math.max(min, Math.min(max,num));
  const safeArray = (x) => Array.isArray(x) ? x : [];

  function detected(hass) {
    return Object.entries(hass?.states || {})
      .filter(([id, state]) => id.startsWith('sensor.') && state?.attributes?.dashboard?.version === 1)
      .map(([id]) => id);
  }

  class AirQualityAdvisorCard extends HTMLElement {
    static getStubConfig(hass) {
      const matches = detected(hass);
      return matches.length === 1 ? {entity:matches[0]} : {};
    }

    constructor() {
      super();
      this.attachShadow({mode:'open'});
      this._config = {};
      this._expanded = new Set();
      this._shownEntity = null;
      this._shownLanguage = null;
      this._lastState = null;
      this._lastConfigKey = null;
      this.shadowRoot.addEventListener('click', (event) => {
        const button = event.target.closest?.('[data-expand]');
        if (!button) return;
        const area = button.getAttribute('data-expand');
        if (this._expanded.has(area)) this._expanded.delete(area);
        else this._expanded.add(area);
        this._render(true);
      });
    }

    setConfig(config) {
      if (config.entity && !/^sensor\.[a-z0-9_]+$/.test(config.entity)) {
        throw new Error('Air Quality Advisor: entity must be a sensor.* entity ID');
      }
      this._config = {show_outside:true, show_metrics:true, ...config};
      this._lastConfigKey = null;
      this._render(true);
    }

    set hass(hass) {
      this._hass = hass;
      this._render();
    }

    getCardSize() { return 5; }

    _language() {
      return cardLanguage(this._hass?.language);
    }

    _t(key) {
      const lang = this._language();
      return LANGUAGE[lang]?.[key] || LANGUAGE.en[key] || key;
    }

    _format(value, digits = 1) {
      if (typeof value !== 'number' || !Number.isFinite(value)) return '–';
      try { return new Intl.NumberFormat(this._hass?.language || 'en', {
        maximumFractionDigits:digits, minimumFractionDigits:0
      }).format(value); } catch { return String(value); }
    }

    _metricName(metric) {
      if (metric === 'mold') {
        const translated = this._t('metric_mold');
        return translated === 'metric_mold' ? 'Mold indication' : translated;
      }
      return this._t(`metric_${metric}`);
    }

    _weatherName(condition) {
      if (!condition) return this._t('missing');
      const key = { 'clear-night':'wx_clearNight','partlycloudy':'wx_partlycloudy',
        'lightning-rainy':'wx_lightning','snowy-rainy':'wx_snowy','windy-variant':'wx_windy'
      }[condition] || `wx_${condition}`;
      return this._t(key) === key ? condition.replaceAll('-',' ') : this._t(key);
    }

    _state() {
      const id = this._config.entity || (detected(this._hass).length === 1 ? detected(this._hass)[0] : null);
      return [id, id ? this._hass?.states?.[id] : null];
    }

    _icon(icon, extraClass = '') {
      return `<ha-icon class="${extraClass}" icon="${escape(icon)}" aria-hidden="true"></ha-icon>`;
    }

    _moldInputWarning(code) {
      const localized = MOLD_INPUT_WARNING_LABELS[this._language()]?.[code];
      if (localized) return localized;
      const missing = this._t('missing');
      return {
        calibration: this._t('moldNotCalibrated'),
        indoor_temperature: '🏠 🌡️ °C · ' + missing,
        outdoor_temperature: this._t('weather') + ' · 🌡️ °C · ' + missing,
        humidity: this._t('humidity') + ' RH (%) · ' + missing,
        calculation: this._t('moldInputsUnavailable'),
      }[code] || missing;
    }

    _metric(item, miniature = false) {
      const metric = this._metricName(item.metric);
      const available = item.available && typeof item.value === 'number';
      const limit = item.threshold;
      const hasLimit = typeof limit === 'number' && limit > 0;
      const pct = available && hasLimit ? clamp(item.value / limit * 100, 0, 100) : 0;
      const unit = item.unit || '';
      const level = !available ? 'unknown' : item.exceeded ? 'attention' : 'safe';
      const display = available ? this._format(item.value) : '–';
      const threshold = hasLimit ? `${this._t('limits')} ${this._format(limit)} ${escape(unit)}` : '';
      const details = item.metric === 'mold' && item.details && typeof item.details === 'object'
        ? item.details : null;
      const moldUnavailableReason = item.metric === 'mold' && !available
        ? details?.status === 'needs_calibration' ? this._t('moldNotCalibrated')
          : details?.status === 'inputs_unavailable' ? this._t('moldInputsUnavailable')
            : this._t('missing')
        : this._t('missing');
      // The room can still have valid RH contributors before its coldest
      // surface has been calibrated. Show that average instead of hiding it.
      const moldInfo = details && typeof details.average_indoor_humidity === 'number'
        ? `<div class="metric-limit">
          RH Ø ${escape(this._format(details.average_indoor_humidity))}%
          · n=${escape(details.humidity_sensor_count ?? 0)}
          ${typeof details.estimated_surface_c === 'number'
            ? '· 🌡️ ' + escape(this._format(details.estimated_surface_c)) + '°C' : ''}
        </div>`
        : '';
      return `<div class="metric ${miniature ? 'tiny' : ''} metric-${level}">
        <div class="metric-line">
          <span class="metric-name">${this._icon(METRIC_ICON[item.metric] || 'mdi:gauge')} ${escape(metric)}</span>
          <span class="metric-number">${escape(display)} <small>${escape(unit)}</small></span>
        </div>
        ${hasLimit ? `<div class="meter" role="progressbar" aria-label="${escape(metric)}"
          aria-valuemin="0" aria-valuemax="${escape(limit)}" aria-valuenow="${available ? escape(item.value) : '0'}">
          <span class="meter-fill" style="width:${pct.toFixed(2)}%"></span><span class="meter-limit"></span>
        </div><div class="metric-limit">${threshold}</div>`
          : `<div class="metric-limit">${available ? '' : escape(moldUnavailableReason)}</div>`}
        ${moldInfo}
      </div>`;
    }

    _window(win) {
      const opened = win.opened;
      const klass = opened === true ? 'opened' : opened === false ? 'closed' : 'unknown';
      const icon = opened === true ? 'mdi:window-open-variant' : opened === false ? 'mdi:window-closed-variant' : 'mdi:window-closed';
      const text = opened === true ? this._t('windowOpen') : opened === false ? this._t('windowClosed') : this._t('windowUnknown');
      return `<span class="window ${klass}" title="${escape(win.entity_id)}">${this._icon(icon)}<span>${escape(win.name)}</span>
        <small>· ${escape(text)}</small></span>`;
    }

    _outsideBlocker(reason) {
      const code = reason.code || '';
      const label = String(reason.label || '');
      const value = String(reason.value || '');
      const prefix = code.startsWith('outside_') ? this._t('unsafeReason') : ({
        weather_condition:this._t('weather'), weather_cold:this._t('cold'),
        weather_hot:this._t('hot'), weather_humid:this._t('wet'),
        weather_wind:this._t('windHigh'), active_warning:this._t('warningReason'),
        unavailable_warning:this._t('warningUnknown'),
        unavailable_weather:this._t('unavailableWeather'),
        no_weather_data:this._t('noWeather'),no_outdoor_data:this._t('noOutdoor')
      }[code] || this._t('conditions'));
      const metric = code.startsWith('outside_') ? this._metricName(code.slice(8)) : '';
      const suffix = code === 'weather_condition' ? this._weatherName(value) : value;
      return `<span class="reason">${this._icon('mdi:alert-circle-outline')}${escape(prefix)}${metric ? `: ${escape(metric)}` : ''}
       ${suffix ? `· ${escape(suffix)}` : (code === 'active_warning' && label ? `· ${escape(label)}` : '')}</span>`;
    }

    _outside(outdoor) {
      if (this._config.show_outside === false) return '';
      const status = ['safe','partial','unsafe','unknown'].includes(outdoor.status) ? outdoor.status : 'unknown';
      const main = status === 'safe' ? this._t('goodOutside') : status === 'partial' ?
        this._t('partialOutside') : status === 'unsafe' ? this._t('badOutside') : this._t('missingOutside');
      const wx = safeArray(outdoor.weather).find((item) => item.condition) || safeArray(outdoor.weather)[0];
      const icon = wx?.condition ? (ICON[wx.condition] || 'mdi:weather-cloudy') : 'mdi:weather-cloudy-alert';
      const temperature = typeof wx?.temperature_c === 'number' ? `${this._format(wx.temperature_c)}°C` : null;
      const extras = [
        ...(typeof wx?.humidity === 'number' ? [this._icon('mdi:water-percent') + escape(this._format(wx.humidity)) + '%'] : []),
        ...(typeof wx?.wind_kmh === 'number' ? [this._icon('mdi:weather-windy') + escape(this._format(wx.wind_kmh)) + ' km/h'] : [])
      ];
      const readings = safeArray(outdoor.readings);
      const blockers = safeArray(outdoor.blockers);
      const warnings = safeArray(outdoor.warnings).filter((item) => item.active !== false);
      return `<section class="outside outside-${status}" aria-label="${escape(this._t('outside'))}">
        <div class="outdoor-head"><div class="outdoor-icon">${this._icon(icon)}</div>
          <div class="outdoor-text"><span class="eyebrow">${escape(this._t('outside'))}</span>
            <div class="outside-title">${escape(main)}</div>
            <div class="weather-line">${escape(wx?.condition ? this._weatherName(wx.condition) : this._t('missing'))}
              ${temperature ? `<strong>${escape(temperature)}</strong>` : ''}
              ${extras.length ? `<span>${extras.join('<span class="sep">·</span>')}</span>` : ''}
            </div>
          </div>
          <div class="outdoor-status">${this._icon(status === 'safe' ? 'mdi:check' : status === 'unsafe' ? 'mdi:alert' : 'mdi:information-outline')}</div>
        </div>
        ${readings.length ? `<div class="out-metrics" aria-label="${escape(this._t('outdoorSensors'))}">
          ${readings.map((item) => `<span class="out-chip ${!item.available ? 'dim' : item.exceeded ? 'elevated' : ''}">
            ${escape(this._metricName(item.metric))} <b>${item.available ? escape(this._format(item.value)) : '–'}</b>
            <small>${escape(item.unit)}</small></span>`).join('')}
        </div>` : `<div class="out-empty">${escape(this._t('noOutdoor'))}</div>`}
        ${blockers.length ? `<div class="outside-alerts">${blockers.slice(0,5).map((item) => this._outsideBlocker(item)).join('')}
          ${blockers.length > 5 ? `<span>+${blockers.length - 5}</span>` : ''}</div>` : ''}
        ${warnings.length && !blockers.some((b) => b.code === 'active_warning' || b.code === 'unavailable_warning')
          ? `<div class="outside-alerts">${warnings.map((warning) => `<span class="reason">${escape(warning.name)} · ${escape(warning.active === true ? this._t('warningActive') : this._t('warningUnknown'))}</span>`).join('')}</div>` : ''}
      </section>`;
    }

    _summary(summary) {
      const counts = ['safe','attention','unknown'].map((k) => Math.max(0, Number(summary[k] || 0)));
      const total = counts.reduce((acc, value) => acc + value, 0);
      const first = total ? counts[0] / total * 100 : 0;
      const second = total ? (counts[0] + counts[1]) / total * 100 : 0;
      return `<div class="section-head"><span class="section-title">${this._icon('mdi:home-heart')} ${escape(this._t('roomStatus'))}</span>
        <span class="subdued">${total}</span></div>
        <div class="overview">
          <div class="donut-wrap"><div class="donut" role="img"
            aria-label="${escape(this._t('safe'))}: ${counts[0]}; ${escape(this._t('attention'))}: ${counts[1]}; ${escape(this._t('unknown'))}: ${counts[2]}"
            style="--good-end:${first.toFixed(2)}%;--attention-end:${second.toFixed(2)}%">
            <div class="donut-inner"><strong>${total}</strong><span>${escape(this._t('roomStatus'))}</span></div>
          </div></div>
          <div class="counts">${['safe','attention','unknown'].map((k,i) => `<div class="count count-${k}">
            <span class="count-icon">${this._icon(ICON[k])}</span>
            <strong>${counts[i]}</strong><small>${escape(this._t(k))}</small>
          </div>`).join('')}</div>
        </div>`;
    }

    _room(room) {
      const status = ['safe','attention','unknown'].includes(room.status) ? room.status : 'unknown';
      const readings = safeArray(room.readings);
      const windows = safeArray(room.windows);
      const moldReading = readings.find((item) => item.metric === 'mold' && !item.available);
      const moldWarnings = safeArray(room.mold_warnings).filter(
        (code) => ['calibration','indoor_temperature','outdoor_temperature',
                   'humidity','calculation'].includes(code)
      );
      const sourceDetails = moldReading?.details || {};
      const warningList = moldWarnings.length
        ? `<div class="mold-warnings" role="status">
          ${moldWarnings.map((code) => {
            const source = code === 'outdoor_temperature'
              ? sourceDetails.outdoor_weather_entity
              : code === 'indoor_temperature'
                ? sourceDetails.indoor_temperature_entity : null;
            return `<div class="mold-warning">
              ${this._icon('mdi:alert-outline')}
              <span>${escape(this._moldInputWarning(code))}${source
                ? ` <small>(${escape(source)})</small>` : ''}</span>
            </div>`;
          }).join('')}
        </div>` : '';
      const expanded = this._expanded.has(String(room.area_id));
      const shown = expanded ? readings : readings.slice(0,3);
      const button = readings.length > 3 && this._config.show_metrics !== false ? `<button type="button" class="expand" data-expand="${escape(room.area_id)}"
        aria-expanded="${expanded}">${escape(this._t(expanded ? 'less' : 'more'))} ${this._icon(expanded ? 'mdi:chevron-up' : 'mdi:chevron-down')}</button>` : '';
      const urgent = room.action === 'close';
      const actionable = room.action === 'open' || urgent;
      const recommendation = actionable
        ? `<div class="advice advice-${urgent ? 'close' : 'open'}">${this._icon(urgent ? 'mdi:window-closed-variant' : 'mdi:window-open-variant')}
            <span><b>${escape(this._t(urgent ? 'closeAdvice' : 'openAdvice'))}</b><small>${escape(windows
              .filter((win) => safeArray(room.action_window_ids).includes(win.entity_id))
              .map((win) => win.name).join(' · '))}</small></span></div>`
        : status === 'attention' && room.ventilating
          ? `<div class="advice advice-ventilating">${this._icon('mdi:air-filter')}${escape(this._t('ventilating'))}</div>`
          : status === 'attention' && room.high_count > 0 && !room.ventilating
            ? `<div class="advice advice-blocked">${this._icon('mdi:alert-circle-outline')}${escape(this._t('notSafeToOpen'))}</div>`
            : '';
      const availableCount = safeArray(room.readings).filter((item) =>
        item.available === true && typeof item.value === 'number'
      ).length;
      const roomStatusLabel = status === 'unknown' && availableCount > 0
        ? this._t('partial') : this._t(status);
      const subheading = room.high_count > 0 ? this._t('indoorHigh')
        : status === 'unknown' && room.status_detail === 'mold_not_calibrated'
          ? this._t('moldNotCalibrated')
        : status === 'unknown' && room.status_detail === 'mold_inputs_unavailable'
          ? this._t('moldInputsUnavailable')
        : status === 'unknown' && availableCount > 0
          ? this._t('partial')
        : status === 'unknown' ? this._t('missingIndoor')
          : this._t('allOkay');
      return `<article class="room room-${status}">
        <div class="room-heading">
          <div class="room-icon">${this._icon(status === 'safe' ? 'mdi:home-check-outline' : status === 'attention' ? 'mdi:home-alert-outline' : 'mdi:home-outline')}</div>
          <div class="room-main"><h3>${escape(room.name)}</h3><span>${escape(subheading)}</span></div>
          <span class="status-tag">${this._icon(ICON[status])}${escape(roomStatusLabel)}</span>
        </div>
        ${this._config.show_metrics === false ? '' : readings.length ? `<div class="metric-grid">${shown.map((item) => this._metric(item)).join('')}</div>`
          : `<div class="empty-measurements">${this._icon('mdi:gauge-empty')} ${escape(this._t('missingIndoor'))}</div>`}
        ${button}
        ${warningList}
        <div class="window-section">
          <span class="field-label">${this._icon('mdi:window-closed-variant')}${escape(this._t('windows'))}</span>
          ${windows.length ? `<div class="window-list">${windows.map((window) => this._window(window)).join('')}</div>`
            : `<span class="subdued">${escape(this._t('noWindows'))}</span>`}
        </div>
        ${recommendation}
      </article>`;
    }

    _render(force = false) {
      if (!this._hass || !this._config) return;
      const [entity, state] = this._state();
      const lang = this._language();
      const key = JSON.stringify(this._config);
      if (!force && this._lastState === state && this._shownEntity === entity && this._shownLanguage === lang && this._lastConfigKey === key) return;
      this._lastState = state;
      this._shownEntity = entity;
      this._shownLanguage = lang;
      this._lastConfigKey = key;
      const data = state?.attributes?.dashboard;
      if (!data || data.version !== 1) {
        this.shadowRoot.innerHTML = `${this._styles()}<ha-card class="shell" dir="${RTL_LANGUAGES.has(lang) ? 'rtl' : 'ltr'}"><div class="empty-state">
        ${this._icon('mdi:air-filter')}<h3>${escape(this._t('title'))}</h3><p>${escape(this._t('missingCard'))}</p></div></ha-card>`;
        return;
      }
      const rooms = safeArray(data.rooms).slice().sort((a,b) =>
        ({attention:0,unknown:1,safe:2}[a.status] ?? 3) - ({attention:0,unknown:1,safe:2}[b.status] ?? 3) ||
        String(a.name).localeCompare(String(b.name), this._hass.language));
      this.shadowRoot.innerHTML = `${this._styles()}<ha-card class="shell" dir="${RTL_LANGUAGES.has(lang) ? 'rtl' : 'ltr'}">
        <header class="card-heading"><div><div class="overline">HOME ASSISTANT</div>
        <h2>${escape(this._config.title || this._t('title'))}</h2><span>${escape(this._t('subtitle'))}</span></div>
        <div class="card-logo">${this._icon('mdi:air-filter')}</div></header>
        <div class="content">
          ${this._outside(data.outdoor || {})}
          ${this._summary(data.summary || {})}
          <div class="rooms-list">${rooms.length ? rooms.map((room) => this._room(room)).join('')
            : `<div class="empty-rooms">${this._icon('mdi:home-outline')}${escape(this._t('noRooms'))}</div>`}</div>
          <footer>${this._icon('mdi:shield-check-outline')} ${escape(this._t('sourceData'))}</footer>
        </div>
      </ha-card>`;
    }

    _styles() { return `<style>
      :host{display:block;--aqa-green:#1f9d77;--aqa-amber:#df9143;--aqa-red:#df6d55;--aqa-blue:#499bb9;
        --aqa-muted:var(--secondary-text-color,#78848f);--aqa-text:var(--primary-text-color,#1a313d);
        --aqa-surface:var(--card-background-color,#fff);--aqa-edge:var(--divider-color,rgba(110,135,145,.17));
        font-family:var(--paper-font-body1_-_font-family,Roboto,Arial,sans-serif);color:var(--aqa-text)}
      .shell{overflow:hidden;border-radius:22px;background:var(--aqa-surface);box-shadow:var(--ha-card-box-shadow,0 2px 16px rgba(0,0,0,.06))}
      .card-heading{display:flex;align-items:center;justify-content:space-between;gap:16px;padding:24px 26px 20px}
      .overline{color:var(--aqa-blue);font-size:10px;letter-spacing:2.2px;font-weight:800;margin-bottom:5px}
      h2{font-size:25px;line-height:1.15;margin:0 0 5px;font-weight:780;letter-spacing:-.8px}
      .card-heading span{color:var(--aqa-muted);font-size:12px}
      .card-logo{width:50px;height:50px;border-radius:15px;display:grid;place-items:center;
        background:color-mix(in srgb,var(--aqa-blue),transparent 87%);color:var(--aqa-blue)}
      .card-logo ha-icon{--mdc-icon-size:28px}
      .content{padding:0 20px 14px}
      .outside{position:relative;border:1px solid var(--aqa-edge);border-radius:18px;padding:18px 18px 16px;
        background:linear-gradient(115deg,color-mix(in srgb,var(--aqa-blue),transparent 92%),color-mix(in srgb,var(--aqa-green),transparent 95%));}
      .outside-safe{border-color:color-mix(in srgb,var(--aqa-green),transparent 71%)}
      .outside-unsafe{background:linear-gradient(115deg,color-mix(in srgb,var(--aqa-red),transparent 87%),color-mix(in srgb,var(--aqa-amber),transparent 94%));
        border-color:color-mix(in srgb,var(--aqa-red),transparent 62%)}
      .outside-partial,.outside-unknown{background:color-mix(in srgb,var(--aqa-amber),transparent 93%)}
      .outdoor-head{display:flex;gap:15px;align-items:center}
      .outdoor-icon{height:61px;width:61px;flex:0 0 61px;border-radius:17px;display:grid;place-items:center;
        background:color-mix(in srgb,var(--aqa-blue),transparent 81%);color:var(--aqa-blue)}
      .outside-unsafe .outdoor-icon{background:color-mix(in srgb,var(--aqa-red),transparent 82%);color:var(--aqa-red)}
      .outdoor-icon ha-icon{--mdc-icon-size:36px}
      .outdoor-text{flex:1;min-width:0}
      .eyebrow{display:block;font-size:11px;letter-spacing:.7px;text-transform:uppercase;color:var(--aqa-muted);font-weight:700}
      .outside-title{font-size:17px;font-weight:750;letter-spacing:-.25px;line-height:1.25;margin:5px 0}
      .weather-line{display:flex;align-items:center;gap:9px;flex-wrap:wrap;color:var(--aqa-muted);font-size:12px}
      .weather-line strong{font-size:15px;color:var(--aqa-text);font-weight:750}
      .weather-line span{display:inline-flex;align-items:center;gap:3px}
      .weather-line span ha-icon{--mdc-icon-size:15px}
      .weather-line .sep{margin:0 3px;color:var(--aqa-muted)}
      .outdoor-status{color:var(--aqa-green);align-self:flex-start}
      .outside-unsafe .outdoor-status{color:var(--aqa-red)}
      .outside-unknown .outdoor-status,.outside-partial .outdoor-status{color:var(--aqa-amber)}
      .out-metrics{display:flex;flex-wrap:wrap;gap:7px;margin-top:15px;padding-top:12px;border-top:1px solid var(--aqa-edge)}
      .out-chip{font-size:11px;padding:7px 10px;border-radius:9px;background:var(--aqa-surface);border:1px solid var(--aqa-edge);white-space:nowrap;color:var(--aqa-muted)}
      .out-chip b{color:var(--aqa-text);font-size:13px;margin-left:5px}
      .out-chip small{font-size:10px}
      .out-chip.elevated{border-color:color-mix(in srgb,var(--aqa-red),transparent 51%);color:var(--aqa-red)}
      .out-chip.dim{opacity:.68}
      .out-empty{font-size:12px;color:var(--aqa-muted);margin-top:14px}
      .outside-alerts{display:flex;flex-wrap:wrap;gap:7px;margin-top:10px}
      .reason{display:inline-flex;align-items:center;gap:5px;padding:6px 8px;border-radius:9px;
        font-size:11px;background:color-mix(in srgb,var(--aqa-red),transparent 90%);color:var(--aqa-text)}
      .reason ha-icon{--mdc-icon-size:15px;color:var(--aqa-red)}
      .section-head{display:flex;justify-content:space-between;align-items:center;margin:22px 4px 12px}
      .section-title{font-size:13px;font-weight:790;display:inline-flex;align-items:center;gap:8px}
      .section-title ha-icon{--mdc-icon-size:19px;color:var(--aqa-blue)}
      .subdued{font-size:12px;color:var(--aqa-muted)}
      .overview{display:flex;gap:22px;align-items:center;padding:17px 18px;background:color-mix(in srgb,var(--aqa-muted),transparent 96%);
        border-radius:16px;border:1px solid var(--aqa-edge)}
      .donut-wrap{display:flex;align-items:center;justify-content:center}
      .donut{width:103px;height:103px;border-radius:50%;padding:12px;box-sizing:border-box;
        background:conic-gradient(var(--aqa-green) 0 var(--good-end),var(--aqa-amber) var(--good-end) var(--attention-end),
        color-mix(in srgb,var(--aqa-muted),transparent 56%) var(--attention-end) 100%);}
      .donut-inner{background:var(--aqa-surface);border-radius:50%;height:100%;display:flex;flex-direction:column;justify-content:center;
        align-items:center;gap:0;box-shadow:0 0 0 2px var(--aqa-surface)}
      .donut-inner strong{font-size:30px;line-height:1;font-weight:770}
      .donut-inner span{font-size:10px;color:var(--aqa-muted);margin-top:5px}
      .counts{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));flex:1;gap:9px}
      .count{display:flex;flex-direction:column;min-width:0;padding:5px 9px;align-items:center;border-left:1px solid var(--aqa-edge)}
      .count-icon ha-icon{--mdc-icon-size:21px;color:var(--aqa-green)}
      .count-attention .count-icon ha-icon{color:var(--aqa-amber)}
      .count-unknown .count-icon ha-icon{color:var(--aqa-muted)}
      .count strong{font-size:24px;font-weight:750;line-height:1.2;margin-top:3px}
      .count small{font-size:10px;color:var(--aqa-muted);text-align:center;line-height:1.3}
      .rooms-list{display:grid;gap:12px;margin-top:15px;grid-template-columns:repeat(auto-fit,minmax(min(100%,290px),1fr));align-items:start}
      .room{padding:16px;border-radius:16px;border:1px solid var(--aqa-edge);background:var(--aqa-surface);min-width:0}
      .room-attention{border-color:color-mix(in srgb,var(--aqa-amber),transparent 60%);
        background:linear-gradient(150deg,color-mix(in srgb,var(--aqa-amber),transparent 96%),var(--aqa-surface) 65%)}
      .room-heading{display:flex;gap:10px;align-items:center;min-width:0;margin-bottom:13px}
      .room-icon{height:37px;width:37px;border-radius:12px;background:color-mix(in srgb,var(--aqa-green),transparent 89%);
        color:var(--aqa-green);display:grid;place-items:center;flex-shrink:0}
      .room-attention .room-icon{background:color-mix(in srgb,var(--aqa-amber),transparent 85%);color:var(--aqa-amber)}
      .room-unknown .room-icon{background:color-mix(in srgb,var(--aqa-muted),transparent 88%);color:var(--aqa-muted)}
      .room-main{min-width:0;flex:1}
      .room-main h3{margin:0;font-size:14px;line-height:1.35;font-weight:760;overflow-wrap:anywhere}
      .room-main span{display:block;color:var(--aqa-muted);font-size:10px;line-height:1.35;margin-top:2px}
      .status-tag{display:inline-flex;gap:3px;align-items:center;border-radius:999px;padding:5px 8px;white-space:nowrap;font-size:10px;font-weight:750;
        color:var(--aqa-green);background:color-mix(in srgb,var(--aqa-green),transparent 88%)}
      .status-tag ha-icon{--mdc-icon-size:13px}
      .room-attention .status-tag{color:var(--aqa-amber);background:color-mix(in srgb,var(--aqa-amber),transparent 88%)}
      .room-unknown .status-tag{color:var(--aqa-muted);background:color-mix(in srgb,var(--aqa-muted),transparent 88%)}
      .mold-warnings{display:grid;gap:6px;margin:11px 0;padding:10px;border-radius:10px;
        background:color-mix(in srgb,var(--aqa-amber),transparent 91%);
        border:1px solid color-mix(in srgb,var(--aqa-amber),transparent 72%)}
      .mold-warning{display:flex;align-items:flex-start;gap:7px;color:var(--aqa-text);font-size:11px;line-height:1.4}
      .mold-warning ha-icon{flex:0 0 auto;--mdc-icon-size:15px;color:var(--aqa-amber)}
      .mold-warning small{color:var(--aqa-muted)}
      .metric-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,125px),1fr));gap:9px}
      .metric{border-radius:11px;background:color-mix(in srgb,var(--aqa-muted),transparent 96%);border:1px solid var(--aqa-edge);padding:10px;min-width:0}
      .metric-attention{border-color:color-mix(in srgb,var(--aqa-amber),transparent 66%)}
      .metric-line{display:flex;align-items:flex-start;gap:7px;justify-content:space-between;flex-wrap:wrap}
      .metric-name{font-size:10px;color:var(--aqa-muted);display:inline-flex;align-items:center;gap:3px;font-weight:700}
      .metric-name ha-icon{--mdc-icon-size:15px}
      .metric-number{font-size:15px;font-weight:760;white-space:nowrap;line-height:1.2}
      .metric-number small{font-size:9px;color:var(--aqa-muted);font-weight:500}
      .meter{position:relative;display:block;height:6px;border-radius:99px;margin-top:11px;background:color-mix(in srgb,var(--aqa-muted),transparent 80%);overflow:hidden}
      .meter-fill{height:100%;display:block;background:var(--aqa-green);border-radius:99px;transition:width .35s ease}
      .metric-attention .meter-fill{background:var(--aqa-amber)}
      .meter-limit{position:absolute;right:1px;top:0;height:100%;width:1px;background:var(--aqa-text);opacity:.24}
      .metric-limit{color:var(--aqa-muted);font-size:9px;line-height:1.3;margin-top:5px}
      .expand{display:inline-flex;gap:3px;align-items:center;margin:10px 0 0;padding:4px 2px;
        background:none;border:0;color:var(--primary-color,var(--aqa-blue));cursor:pointer;font-size:11px;font-weight:700}
      .expand ha-icon{--mdc-icon-size:15px}
      .expand:focus-visible{outline:2px solid var(--primary-color,var(--aqa-blue));border-radius:4px}
      .window-section{margin-top:12px;padding-top:11px;border-top:1px solid var(--aqa-edge)}
      .field-label{display:inline-flex;align-items:center;gap:5px;font-weight:740;font-size:10px;text-transform:uppercase;
        letter-spacing:.6px;color:var(--aqa-muted);margin-bottom:8px}
      .field-label ha-icon{--mdc-icon-size:14px}
      .window-list{display:flex;flex-wrap:wrap;gap:6px}
      .window{display:inline-flex;align-items:center;gap:4px;border-radius:8px;padding:5px 7px;background:color-mix(in srgb,var(--aqa-muted),transparent 92%);
        font-size:10px;line-height:1.3;max-width:100%;overflow-wrap:anywhere}
      .window ha-icon{--mdc-icon-size:15px}
      .window.opened ha-icon{color:var(--aqa-green)}
      .window.unknown ha-icon{color:var(--aqa-amber)}
      .window small{color:var(--aqa-muted);white-space:nowrap}
      .advice{display:flex;align-items:center;gap:10px;padding:11px;margin-top:13px;border-radius:10px;font-size:12px;
        background:color-mix(in srgb,var(--aqa-blue),transparent 89%);color:var(--aqa-text)}
      .advice ha-icon{color:var(--aqa-blue);--mdc-icon-size:21px;flex-shrink:0}
      .advice-close,.advice-blocked{background:color-mix(in srgb,var(--aqa-red),transparent 89%)}
      .advice-close ha-icon,.advice-blocked ha-icon{color:var(--aqa-red)}
      .advice-ventilating{background:color-mix(in srgb,var(--aqa-green),transparent 90%)}
      .advice-ventilating ha-icon{color:var(--aqa-green)}
      .advice b{font-weight:750;display:block}
      .advice small{font-size:10px;display:block;opacity:.76;margin-top:3px;overflow-wrap:anywhere}
      .empty-measurements,.empty-rooms{border:1px dashed var(--aqa-edge);color:var(--aqa-muted);font-size:12px;
        padding:14px;border-radius:10px;display:flex;align-items:center;gap:9px}
      .empty-state{text-align:center;padding:32px 24px;color:var(--aqa-muted)}
      .empty-state ha-icon{color:var(--aqa-blue);--mdc-icon-size:36px}
      .empty-state h3{color:var(--aqa-text);margin:12px 0 5px}
      .empty-rooms{grid-column:1/-1;justify-content:center;padding:30px}
      footer{display:flex;gap:5px;align-items:center;justify-content:center;color:var(--aqa-muted);font-size:10px;padding:17px 8px 4px;text-align:center}
      footer ha-icon{--mdc-icon-size:14px}
      @media(max-width:420px){.card-heading{padding:19px 18px 16px}h2{font-size:22px}.content{padding:0 12px 12px}
        .outside{padding:13px}.outdoor-icon{height:48px;width:48px;flex-basis:48px;border-radius:13px}.outdoor-icon ha-icon{--mdc-icon-size:29px}
        .outside-title{font-size:15px}.overview{gap:8px;padding:12px 8px}.donut{width:89px;height:89px;padding:10px}
        .counts{gap:0}.count{padding:5px 3px}.count strong{font-size:20px}.room{padding:13px}}
      @media(prefers-reduced-motion:reduce){.meter-fill{transition:none}}
    </style>`; }
  }

  class AirQualityAdvisorCardEditor extends HTMLElement {
    constructor() { super(); this.attachShadow({mode:'open'}); this._config={}; }
    set hass(hass) { this._hass=hass; this._render(); }
    setConfig(config) { this._config={...config}; this._render(); }
    _render() {
      if (!this._hass) return;
      const lang = cardLanguage(this._hass.language);
      this.setAttribute('dir', RTL_LANGUAGES.has(lang) ? 'rtl' : 'ltr');
      const texts = LANGUAGE[lang] || LANGUAGE.en;
      const t = (key) => texts[key] || LANGUAGE.en[key];
      const found = detected(this._hass);
      const chosen = this._config.entity || (found.length===1 ? found[0] : '');
      this.shadowRoot.innerHTML = `<style>:host{display:block;padding:8px 0}label{display:block;margin:10px 0;font:inherit;font-size:13px}
        select,input{box-sizing:border-box;width:100%;font:inherit;background:var(--card-background-color,#fff);
          border:1px solid var(--divider-color,#ddd);border-radius:8px;padding:12px;color:var(--primary-text-color,#222)}
        .tick{display:flex;align-items:center;gap:8px}.tick input{width:auto}</style>
        <label>${escape(t('title'))}<select data-setting="entity"><option value="">${escape(t('missingCard'))}</option>
        ${found.map((id) => `<option value="${escape(id)}" ${id===chosen?'selected':''}>${escape(this._hass.states[id]?.attributes?.friendly_name || id)}</option>`).join('')}</select></label>
        <label>${escape(t('title'))}<input data-setting="title" type="text" value="${escape(this._config.title || '')}" /></label>
        <label class="tick"><input type="checkbox" data-setting="show_outside" ${this._config.show_outside!==false?'checked':''}>${escape(t('outside'))}</label>
        <label class="tick"><input type="checkbox" data-setting="show_metrics" ${this._config.show_metrics!==false?'checked':''}>${escape(t('readings'))}</label>`;
      this.shadowRoot.querySelectorAll('[data-setting]').forEach((field) => {
        field.addEventListener('change', () => {
          const prop = field.dataset.setting;
          const value = field.type === 'checkbox' ? field.checked : field.value;
          this._config = {...this._config,[prop]:value};
          if (prop === 'entity' && !value) delete this._config.entity;
          this.dispatchEvent(new CustomEvent('config-changed',{detail:{config:{...this._config}},bubbles:true,composed:true}));
        });
      });
    }
  }

  if (!customElements.get('air-quality-advisor-card')) customElements.define('air-quality-advisor-card',AirQualityAdvisorCard);
  if (!customElements.get('air-quality-advisor-card-editor')) customElements.define('air-quality-advisor-card-editor',AirQualityAdvisorCardEditor);
  AirQualityAdvisorCard.getConfigElement = () => document.createElement('air-quality-advisor-card-editor');
  window.customCards = window.customCards || [];
  if (!window.customCards.some((card) => card.type === 'air-quality-advisor-card')) {
    window.customCards.push({
      type:'air-quality-advisor-card',
      name:'Air Quality Advisor',
      description:'Live room and outdoor air quality, windows, and ventilation recommendations.',
      preview:true,
      documentationURL:'https://github.com/Chreece/HA-Air-Quality-Advisor',
      getEntitySuggestion: (hass,entityId) =>
        hass.states[entityId]?.attributes?.dashboard?.version === 1
          ? {config:{type:'custom:air-quality-advisor-card',entity:entityId}}
          : null
    });
  }
})();
