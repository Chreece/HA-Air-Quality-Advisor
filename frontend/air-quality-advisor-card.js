/* Air Quality Advisor for Home Assistant — native Lovelace card, no dependencies.
 * Install with the integration; the integration registers this asset with HA.
 * The card ONLY displays information. It never controls windows or devices.
 */
(() => {
  'use strict';

  const BRAND_TITLE = "Home Environment Manager";
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
  const RH_FALLBACK_TEXT = {"en":"RH fallback active","de":"RH-Ersatzwert aktiv","el":"Ενεργή εφεδρική χρήση σχετικής υγρασίας","fr":"Repli sur l’humidité relative actif","es":"Respaldo de humedad relativa activo","ar":"الاعتماد الاحتياطي على الرطوبة النسبية نشط","bg":"Активно заместване с относителна влажност","bn":"আপেক্ষিক আর্দ্রতার বিকল্প সক্রিয়","cs":"Aktivní náhradní relativní vlhkost","da":"RH-reservemåling aktiv","fa":"جایگزین رطوبت نسبی فعال است","fi":"Suhteellisen kosteuden varatila käytössä","he":"גיבוי לחות יחסית פעיל","hi":"सापेक्ष आर्द्रता का बैकअप सक्रिय","hr":"Aktivna zamjena relativnom vlagom","hu":"Relatív páratartalom tartalékmód aktív","id":"Cadangan kelembapan relatif aktif","it":"Fallback umidità relativa attivo","ja":"相対湿度の代替値を使用中","ko":"상대습도 대체값 사용 중","nb":"RH-reservemåling aktiv","nl":"RH-terugval actief","pl":"Aktywna rezerwowa wilgotność względna","pt":"Alternativa por humidade relativa ativa","pt-br":"Fallback de umidade relativa ativo","ro":"Mod de rezervă cu umiditate relativă activ","ru":"Используется резервная относительная влажность","sk":"Aktívna náhradná relatívna vlhkosť","sr":"Активна резервна релативна влажност","sv":"Reservvärde för relativ luftfuktighet aktivt","ta":"ஒப்பீட்டு ஈரப்பத மாற்று செயலில் உள்ளது","th":"ใช้ค่าความชื้นสัมพัทธ์สำรอง","tr":"Bağıl nem yedek ölçümü etkin","uk":"Активна резервна відносна вологість","ur":"نسبتی نمی کی متبادل پیمائش فعال ہے","vi":"Đang dùng độ ẩm tương đối dự phòng","zh-hans":"已启用相对湿度回退","zh-hant":"已啟用相對濕度備援"};
  // Calibration and humidity summary labels in all 38 supported card locales.
  const MOLD_DETAIL_LABELS = {"en":["Average humidity","sensor","sensors","Estimated surface","Calibration factor","Indoor temperature","Outdoor temperature"],"de":["Durchschnittliche Luftfeuchte","Sensor","Sensoren","Geschätzte Oberflächentemperatur","Kalibrierfaktor","Raumtemperatur","Außentemperatur"],"el":["Μέση υγρασία","αισθητήρας","αισθητήρες","Εκτιμώμενη επιφάνεια","Συντελεστής βαθμονόμησης","Εσωτερική θερμοκρασία","Εξωτερική θερμοκρασία"],"fr":["Humidité moyenne","capteur","capteurs","Surface estimée","Facteur de calibration","Température intérieure","Température extérieure"],"es":["Humedad media","sensor","sensores","Superficie estimada","Factor de calibración","Temperatura interior","Temperatura exterior"],"ar":["متوسط الرطوبة","مستشعر","مستشعرات","السطح المقدّر","معامل المعايرة","درجة الحرارة الداخلية","درجة الحرارة الخارجية"],"bg":["Средна влажност","сензор","сензора","Оценена температура на повърхността","Калибрационен коефициент","Вътрешна температура","Външна температура"],"bn":["গড় আর্দ্রতা","সেন্সর","সেন্সর","আনুমানিক পৃষ্ঠের তাপমাত্রা","ক্রমাঙ্কন গুণক","ভেতরের তাপমাত্রা","বাইরের তাপমাত্রা"],"cs":["Průměrná vlhkost","senzor","senzory","Odhadovaná teplota povrchu","Kalibrační faktor","Vnitřní teplota","Venkovní teplota"],"da":["Gennemsnitlig luftfugtighed","sensor","sensorer","Estimeret overfladetemperatur","Kalibreringsfaktor","Indetemperatur","Udetemperatur"],"fa":["میانگین رطوبت","حسگر","حسگر","دمای تخمینی سطح","ضریب کالیبراسیون","دمای داخل","دمای بیرون"],"fi":["Keskimääräinen ilmankosteus","anturi","anturia","Arvioitu pintalämpötila","Kalibrointikerroin","Sisälämpötila","Ulkolämpötila"],"he":["לחות ממוצעת","חיישן","חיישנים","טמפרטורת משטח משוערת","מקדם כיול","טמפרטורה פנימית","טמפרטורה חיצונית"],"hi":["औसत आर्द्रता","सेंसर","सेंसर","अनुमानित सतह तापमान","अंशांकन गुणांक","अंदर का तापमान","बाहर का तापमान"],"hr":["Prosječna vlažnost","senzor","senzora","Procijenjena temperatura površine","Faktor kalibracije","Unutarnja temperatura","Vanjska temperatura"],"hu":["Átlagos páratartalom","érzékelő","érzékelő","Becsült felületi hőmérséklet","Kalibrációs tényező","Beltéri hőmérséklet","Kültéri hőmérséklet"],"id":["Kelembapan rata-rata","sensor","sensor","Perkiraan suhu permukaan","Faktor kalibrasi","Suhu dalam ruangan","Suhu luar ruangan"],"it":["Umidità media","sensore","sensori","Temperatura superficiale stimata","Fattore di calibrazione","Temperatura interna","Temperatura esterna"],"ja":["平均湿度","センサー","センサー","推定表面温度","校正係数","室内温度","屋外温度"],"ko":["평균 습도","센서","센서","예상 표면 온도","보정 계수","실내 온도","실외 온도"],"nb":["Gjennomsnittlig luftfuktighet","sensor","sensorer","Estimert overflatetemperatur","Kalibreringsfaktor","Innetemperatur","Utetemperatur"],"nl":["Gemiddelde luchtvochtigheid","sensor","sensoren","Geschatte oppervlaktetemperatuur","Kalibratiefactor","Binnentemperatuur","Buitentemperatuur"],"pl":["Średnia wilgotność","czujnik","czujniki","Szacowana temperatura powierzchni","Współczynnik kalibracji","Temperatura wewnętrzna","Temperatura zewnętrzna"],"pt":["Humidade média","sensor","sensores","Temperatura estimada da superfície","Fator de calibração","Temperatura interior","Temperatura exterior"],"pt-br":["Umidade média","sensor","sensores","Temperatura estimada da superfície","Fator de calibração","Temperatura interna","Temperatura externa"],"ro":["Umiditate medie","senzor","senzori","Temperatura estimată a suprafeței","Factor de calibrare","Temperatura interioară","Temperatura exterioară"],"ru":["Средняя влажность","датчик","датчика","Оценочная температура поверхности","Калибровочный коэффициент","Температура внутри","Температура снаружи"],"sk":["Priemerná vlhkosť","senzor","senzory","Odhadovaná teplota povrchu","Kalibračný faktor","Vnútorná teplota","Vonkajšia teplota"],"sr":["Просечна влажност","сензор","сензора","Процењена температура површине","Фактор калибрације","Унутрашња температура","Спољашња температура"],"sv":["Genomsnittlig luftfuktighet","sensor","sensorer","Uppskattad yttemperatur","Kalibreringsfaktor","Inomhustemperatur","Utomhustemperatur"],"ta":["சராசரி ஈரப்பதம்","சென்சார்","சென்சார்கள்","மதிப்பிடப்பட்ட மேற்பரப்பு வெப்பநிலை","அளவுத்திருத்த காரணி","உட்புற வெப்பநிலை","வெளிப்புற வெப்பநிலை"],"th":["ความชื้นเฉลี่ย","เซนเซอร์","เซนเซอร์","อุณหภูมิพื้นผิวโดยประมาณ","ค่าปรับเทียบ","อุณหภูมิภายใน","อุณหภูมิภายนอก"],"tr":["Ortalama nem","sensör","sensör","Tahmini yüzey sıcaklığı","Kalibrasyon katsayısı","İç sıcaklık","Dış sıcaklık"],"uk":["Середня вологість","датчик","датчики","Оцінена температура поверхні","Калібрувальний коефіцієнт","Температура всередині","Температура зовні"],"ur":["اوسط نمی","سینسر","سینسر","سطح کا اندازاً درجہ حرارت","کیلیبریشن عامل","اندرونی درجہ حرارت","بیرونی درجہ حرارت"],"vi":["Độ ẩm trung bình","cảm biến","cảm biến","Nhiệt độ bề mặt ước tính","Hệ số hiệu chuẩn","Nhiệt độ trong nhà","Nhiệt độ ngoài trời"],"zh-hans":["平均湿度","传感器","传感器","估算表面温度","校准系数","室内温度","室外温度"],"zh-hant":["平均濕度","感測器","感測器","估算表面溫度","校正係數","室內溫度","室外溫度"]};


  const CLIMATE_LABELS = {
    en:{title:'Climate',heat:'Heating target',cool:'Cooling target',occupied:'Occupied',
      unoccupied:'Unoccupied',away:'Away',sleep:'Sleep',home:'Home',
      holding:'Waiting for safe conditions',active:'Native thermostat control',
      advisory:'Planning only',pause:'Pause climate',resume:'Resume climate',
      mode:'Selected mode',target:'Active target',device:'Device',
      primary:'Primary HVAC',secondary:'Secondary HVAC',humidity:'Humidity control',humidityPower:'Humidity power',environmentActive:'Environment control active',
      selectedDevice:'Selected equipment',moistureAction:'Humidity decision',
      currentHumidity:'Measured RH',sourceStatus:'Sensor evidence',
      fan:'Fan-speed control',fanPower:'Fan power',dryFanAuto:'Commissioned DRY/FAN modes',extraction:'Ventilation/extraction',
      filtration:'Particle filtration',treatment:'Air treatment',
      manualDry:'Manual AC mode suggestion (no automatic switch)',
      windowHelp:'Open-window opportunity (advisory only)',
      priority:'Room priority',heldPurpose:'Held',
      co2Priority:'CO₂ ventilation',particlePriority:'Particle filtration',
      temperaturePriority:'Temperature comfort',humidityPriority:'Humidity',
      safetyPriority:'Safety interlock',noPriority:'No qualifying demand',
      environmentOnly:'Room monitoring; individual device controllers below',
      devices:'Managed climate devices',method:'Control method',
      manual:'Manual',automatic:'Automatic',pid:'PID',off:'Off',existing:'Native control',
      roomTemperature:'Room temperature',temperatureMissing:'No valid room temperature',
      manualTemperature:'Manual temperature target',manualHumidity:'Manual humidity target',
      save:'Save target',openEntity:'Open climate entity',
      invalidTarget:'Target invalid, unsupported or outside device limits.',
      editFailed:'Could not save the device settings.'},
    de:{title:'Klima',heat:'Heizsollwert',cool:'Kühlsollwert',occupied:'Belegt',
      unoccupied:'Unbelegt',away:'Abwesend',sleep:'Schlaf',home:'Zuhause',
      holding:'Wartet auf sichere Bedingungen',active:'Native Thermostatregelung',
      advisory:'Nur Planung',pause:'Klima pausieren',resume:'Klima fortsetzen',
      mode:'Aktueller Modus',target:'Aktives Ziel',device:'Gerät',
      primary:'Hauptthermostat',secondary:'Zweites Klimagerät',humidity:'Luftfeuchteregelung',humidityPower:'Be-/Entfeuchter schalten',environmentActive:'Umweltregelung aktiv',
      selectedDevice:'Ausgewähltes Gerät',moistureAction:'Feuchteentscheidung',
      currentHumidity:'Gemessene rF',sourceStatus:'Sensornachweis',
      fan:'Lüfter-Drehzahlregelung',fanPower:'Lüfter Ein/Aus',dryFanAuto:'Freigegebene DRY/FAN-Modi',extraction:'Lüftung / Abluft',
      filtration:'Partikelfiltration',treatment:'Luftbehandlung',
      manualDry:'Empfohlener Klimamodus (nur manuell, kein Umschalten)',
      windowHelp:'Fensterlüften als Alternative (nur Hinweis)',
      priority:'Raumpriorität',heldPurpose:'Gesperrt',
      co2Priority:'CO₂-Lüftung',particlePriority:'Partikelfiltration',
      temperaturePriority:'Temperaturkomfort',humidityPriority:'Luftfeuchtigkeit',
      safetyPriority:'Sicherheitssperre',noPriority:'Kein qualifizierter Bedarf',
      environmentOnly:'Raumüberwachung; einzelne Gerätesteuerungen unten',
      devices:'Verwaltete Klimageräte',method:'Regelungsart',
      manual:'Manuell',automatic:'Automatisch',pid:'PID',off:'Aus',existing:'Native Steuerung',
      roomTemperature:'Raumtemperatur',temperatureMissing:'Keine gültige Raumtemperatur',
      manualTemperature:'Manueller Temperatursollwert',manualHumidity:'Manueller Feuchtesollwert',
      save:'Ziel speichern',openEntity:'Klima-Entität öffnen',
      invalidTarget:'Sollwert ungültig, nicht unterstützt oder außerhalb der Gerätegrenzen.',
      editFailed:'Änderungen konnten nicht gespeichert werden.'},
    el:{title:'Κλίμα',heat:'Στόχος θέρμανσης',cool:'Στόχος ψύξης',occupied:'Παρουσία',
      unoccupied:'Κενό',away:'Απουσία',sleep:'Ύπνος',home:'Σπίτι',
      holding:'Αναμονή ασφαλών συνθηκών',active:'Έλεγχος θερμοστάτη',
      advisory:'Μόνο σχεδιασμός',pause:'Παύση κλίματος',resume:'Συνέχιση κλίματος',
      mode:'Λειτουργία',target:'Ενεργός στόχος',device:'Συσκευή',
      primary:'Κύριος θερμοστάτης',secondary:'Δεύτερη συσκευή κλίματος',humidity:'Ρύθμιση υγρασίας',humidityPower:'Έλεγχος ισχύος υγρασίας',environmentActive:'Ενεργή διαχείριση περιβάλλοντος',
      selectedDevice:'Επιλεγμένη συσκευή',moistureAction:'Απόφαση υγρασίας',
      currentHumidity:'Μετρημένη υγρασία',sourceStatus:'Ποιότητα μετρήσεων',
      fan:'Ρύθμιση ταχύτητας ανεμιστήρων',fanPower:'Ισχύς ανεμιστήρων',dryFanAuto:'Εγκεκριμένες λειτουργίες DRY/FAN',extraction:'Εξαερισμός / απαγωγή',
      filtration:'Φιλτράρισμα σωματιδίων',treatment:'Διαχείριση αέρα',
      manualDry:'Πρόταση χειροκίνητης λειτουργίας A/C (χωρίς αυτόματη αλλαγή)',
      windowHelp:'Πιθανή εξοικονόμηση με άνοιγμα παραθύρου (μόνο συμβουλή)',
      priority:'Προτεραιότητα δωματίου',heldPurpose:'Σε αναμονή',
      co2Priority:'Εξαερισμός CO₂',particlePriority:'Φιλτράρισμα σωματιδίων',
      temperaturePriority:'Θερμική άνεση',humidityPriority:'Υγρασία',
      safetyPriority:'Ασφάλεια',noPriority:'Καμία έγκυρη ανάγκη',
      environmentOnly:'Παρακολούθηση δωματίου· οι ελεγκτές συσκευών βρίσκονται παρακάτω',
      devices:'Ελεγκτές κλιματικών συσκευών',method:'Μέθοδος ελέγχου',
      manual:'Χειροκίνητος',automatic:'Αυτόματος',pid:'PID',off:'Κλειστό',existing:'Εγγενής έλεγχος',
      roomTemperature:'Θερμοκρασία δωματίου',temperatureMissing:'Δεν υπάρχει έγκυρη θερμοκρασία δωματίου',
      manualTemperature:'Χειροκίνητος στόχος θερμοκρασίας',manualHumidity:'Χειροκίνητος στόχος υγρασίας',
      save:'Αποθήκευση στόχου',openEntity:'Άνοιγμα οντότητας κλίματος',
      invalidTarget:'Μη έγκυρος ή μη υποστηριζόμενος στόχος ή εκτός ορίων συσκευής.',
      editFailed:'Αποτυχία αποθήκευσης ρυθμίσεων.'},
  };

  const PID_LABELS = {
    en:{title:'Climate PID',active:'Setpoint regulation active',paused:'Paused: manual action required',
        pending:'Waiting for safe conditions',effort:'PID effort',target:'Room target',requested:'Requested setpoint',
        pause:'Pause PID',resume:'Resume PID',caution:'Controls setpoint only; does not change HVAC mode.'},
    de:{title:'Klima-PID',active:'Sollwertregelung aktiv',paused:'Pausiert: manueller Eingriff nötig',
        pending:'Wartet auf sichere Bedingungen',effort:'PID-Ausgang',target:'Raumziel',requested:'Thermostat-Sollwert',
        pause:'PID pausieren',resume:'PID fortsetzen',caution:'Ändert nur den Sollwert, nicht den Heiz-/Kühlmodus.'},
    el:{title:'Κλιματικός PID',active:'Ενεργή ρύθμιση θερμοστάτη',paused:'Παύση: απαιτείται ενέργεια',
        pending:'Αναμονή ασφαλών συνθηκών',effort:'Έξοδος PID',target:'Στόχος δωματίου',requested:'Επιθυμητή θερμοκρασία',
        pause:'Παύση PID',resume:'Συνέχιση PID',caution:'Αλλάζει μόνο το setpoint, όχι τη λειτουργία HVAC.'},
    fr:{title:'PID climatique',active:'Réglage de consigne actif',paused:'En pause : action manuelle',
        pending:'En attente de conditions sûres',effort:'Effort PID',target:'Cible',requested:'Consigne demandée',
        pause:'Pause PID',resume:'Reprendre PID',caution:'Ne modifie que la consigne, jamais le mode HVAC.'},
    es:{title:'PID climático',active:'Regulación de consigna activa',paused:'Pausado: intervención manual',
        pending:'Esperando condiciones seguras',effort:'Esfuerzo PID',target:'Objetivo',requested:'Consigna solicitada',
        pause:'Pausar PID',resume:'Reanudar PID',caution:'Solo modifica la consigna; no cambia el modo HVAC.'},
  };

  const SCIENCE_LABELS = {
    en: {title:'Building physics · estimates',drying:'Outdoor air is drier',humidifying:'Outdoor air carries more moisture',
      neutral:'Similar moisture content',predicted:'Outside air, warmed to room temperature',
      band:'Adaptive comfort band',heat:'Above the comfort band',cool:'Below the comfort band',
      normal:'Within the comfort band',unknown:'Needs seven days of outdoor history',
      cooling:'Passive cooling opportunity',surface:'Surface condensation margin',
      exposure:'Surface humidity above 80% (24 h)',pm25:'PM2.5 mean (24 h)',
      pm10:'PM10 mean (24 h)',co2:'CO₂ trend',ach:'Estimated air changes',
      energy:'Heat per complete air exchange (per m³)',unverified:'CO₂ sensor technology must be verified separately',
      estimated:'Estimates depend on sensor accuracy and model assumptions.'},
    de: {title:'Bauphysik · Schätzwerte',drying:'Außenluft ist trockener',humidifying:'Außenluft enthält mehr Feuchtigkeit',
      neutral:'Ähnlicher Feuchtegehalt',predicted:'Außenluft auf Raumtemperatur erwärmt',
      band:'Adaptiver Komfortbereich',heat:'Oberhalb des Komfortbereichs',cool:'Unterhalb des Komfortbereichs',
      normal:'Im Komfortbereich',unknown:'Sieben Tage Außenverlauf erforderlich',
      cooling:'Passive Kühlung möglich',surface:'Abstand zur Kondensation an Oberfläche',
      exposure:'Oberflächenfeuchte über 80 % (24 h)',pm25:'PM2.5-Mittel (24 h)',
      pm10:'PM10-Mittel (24 h)',co2:'CO₂-Trend',ach:'Geschätzter Luftwechsel',
      energy:'Wärme pro vollständigem Luftaustausch (je m³)',unverified:'CO₂-Sensortechnik separat prüfen',
      estimated:'Schätzungen hängen von Sensoren und Modellannahmen ab.'},
    el: {title:'Φυσική κτιρίων · εκτιμήσεις',drying:'Ο εξωτερικός αέρας είναι ξηρότερος',humidifying:'Ο εξωτερικός αέρας έχει περισσότερη υγρασία',
      neutral:'Παρόμοια ποσότητα υγρασίας',predicted:'Εξωτερικός αέρας θερμασμένος στη θερμοκρασία δωματίου',
      band:'Προσαρμοστική ζώνη άνεσης',heat:'Πάνω από τη ζώνη άνεσης',cool:'Κάτω από τη ζώνη άνεσης',
      normal:'Εντός της ζώνης άνεσης',unknown:'Απαιτούνται 7 ημέρες εξωτερικών μετρήσεων',
      cooling:'Δυνατότητα παθητικής ψύξης',surface:'Περιθώριο συμπύκνωσης στην επιφάνεια',
      exposure:'Υγρασία επιφάνειας πάνω από 80% (24 ώρες)',pm25:'Μέσος όρος PM2.5 (24 ώρες)',
      pm10:'Μέσος όρος PM10 (24 ώρες)',co2:'Τάση CO₂',ach:'Εκτίμηση ανανεώσεων αέρα',
      energy:'Θερμότητα ανά πλήρη αλλαγή αέρα (ανά m³)',unverified:'Απαιτείται επαλήθευση του αισθητήρα CO₂',
      estimated:'Οι εκτιμήσεις εξαρτώνται από τους αισθητήρες και τις παραδοχές.'}
  };

  const EXTRA_LABELS = {
    en:{pollen:'Pollen forecast',pollenHigh:'High pollen',purification:'Purifier clean-air changes',
      measuredAch:'Measured ventilation trend',toTarget:'Estimated CO₂ target time',
      sourceMoisture:'Rapid humidity change',hcho:'Verified formaldehyde (30 min)',
      radon:'Radon annual average',noise:'Sound exposure (24 h)',nightNoise:'Nighttime sound',
      light:'Daylight above threshold',melanopic:'Sensor measured melanopic EDI',
      overheated:'Overheating degree-hours',pmv:'Thermal comfort PMV / PPD',
      particle:'Indoor / outdoor PM2.5 ratio',unknown:'History or validated hardware required',
      noActuation:'Informational only · PID climate control is planned, not active.'},
    de:{pollen:'Pollenprognose',pollenHigh:'Hohe Pollenbelastung',purification:'Partikel-Luftwechsel des Luftreinigers',
      measuredAch:'Beobachteter Lüftungstrend',toTarget:'Geschätzte CO₂-Zielzeit',
      sourceMoisture:'Schneller Feuchteanstieg',hcho:'Geprüftes Formaldehyd (30 min)',
      radon:'Radon-Jahresmittel',noise:'Schallbelastung (24 h)',nightNoise:'Schall im Schlafzimmer',
      light:'Tageslicht über Schwellenwert',melanopic:'Gemessene melanopische EDI',
      overheated:'Überhitzungsgradstunden',pmv:'Thermischer Komfort PMV / PPD',
      particle:'PM2.5-Verhältnis innen / außen',unknown:'Messhistorie oder Sensorprüfung fehlt',
      noActuation:'Nur Hinweise · PID-Klimaregelung ist geplant, noch nicht aktiv.'},
    el:{pollen:'Πρόγνωση γύρης',pollenHigh:'Υψηλή γύρη',purification:'Ανανεώσεις καθαρού αέρα φίλτρου',
      measuredAch:'Παρατηρούμενη τάση αερισμού',toTarget:'Εκτίμηση χρόνου στόχου CO₂',
      sourceMoisture:'Απότομη αύξηση υγρασίας',hcho:'Επαληθευμένη φορμαλδεΰδη (30 λεπτά)',
      radon:'Ετήσιος μέσος όρος ραδονίου',noise:'Θόρυβος (24 ώρες)',nightNoise:'Νυχτερινός θόρυβος',
      light:'Φως ημέρας πάνω από όριο',melanopic:'Μετρημένη μελανοπική EDI',
      overheated:'Βαθμοώρες υπερθέρμανσης',pmv:'Θερμική άνεση PMV / PPD',
      particle:'Αναλογία PM2.5 μέσα / έξω',unknown:'Απαιτείται ιστορικό ή επαλήθευση αισθητήρα',
      noActuation:'Μόνο πληροφορίες · Ο έλεγχος κλίματος PID είναι μελλοντική δυνατότητα.'}
  };

  const DEVICE_EDIT_LABELS = {
    en: {room:'Edit room',home:'Home settings'},
    el: {room:'Ρυθμίσεις χώρου',home:'Ρυθμίσεις σπιτιού'},
    de: {room:'Raum bearbeiten',home:'Hauseinstellungen'},
    fr: {room:'Modifier la pièce',home:'Paramètres du logement'},
    es: {room:'Editar habitación',home:'Ajustes de la vivienda'}
  };

  const ESC_MAP = {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'};
  const escape = (s) => String(s ?? '').replace(/[&<>"']/g, (ch) => ESC_MAP[ch]);
  const clamp = (num,min,max) => Math.max(min, Math.min(max,num));
  const safeArray = (x) => Array.isArray(x) ? x : [];

  function detected(hass) {
    return Object.entries(hass?.states || {})
      .filter(([id, state]) => id.startsWith('sensor.') &&
        (state?.attributes?.dashboard?.version === 1 ||
         state?.attributes?.dashboard_api === 'environment_manager/dashboard'))
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
      this._shownControllerSignature = null;
      this._dashboardData = null;
      this._dashboardEntity = null;
      this._dashboardLoadedRevision = null;
      this._dashboardFetching = null;
      this._dashboardFailureCount = 0;
      this._dashboardNextAttemptAt = 0;
      this._climateEditError = null;
      this._lastState = null;
      this._lastConfigKey = null;
      this._areaDeviceIds = new Map();
      this._homeDeviceId = null;
      this._deviceRegistryLoading = null;
      this._deviceRegistryUnavailable = false;
      this._deviceRegistryLoaded = false;
      this._deviceRegistryFailureCount = 0;
      this._deviceRegistryNextAttemptAt = 0;
      this._focusedEditor = null;
      this._pendingRender = false;
      this._pendingForceRender = false;
      this._editRenderTimer = null;
      this._lastRenderError = null;
      this._hasValidRender = false;
      // A focused native select/input belongs to the user until they commit
      // or leave it; replacing shadowRoot.innerHTML while it is open closes
      // the browser's picker and discards any unfinished manual edit.
      this.shadowRoot.addEventListener('focusin', (event) => {
        const editor = event.target.closest?.('[data-climate-method],[data-climate-input]');
        if (!editor) return;
        this._focusedEditor = editor;
        if (this._editRenderTimer !== null) {
          clearTimeout(this._editRenderTimer);
          this._editRenderTimer = null;
        }
      });
      this.shadowRoot.addEventListener('pointerdown', (event) => {
        const editor = event.target.closest?.('[data-climate-method],[data-climate-input]');
        if (editor) this._focusedEditor = editor;
      });
      this.shadowRoot.addEventListener('focusout', (event) => {
        if (event.target !== this._focusedEditor) return;
        this._focusedEditor = null;
        // A click on Save follows input focusout. Defer the DOM replacement
        // until after click dispatch so its target is not removed beforehand.
        this._flushDeferredRenderSoon();
      });
      this.shadowRoot.addEventListener('click', (event) => {
        const edit = event.target.closest?.('[data-edit-area],[data-edit-home]');
        if (edit) {
          const area = edit.getAttribute('data-edit-area');
          const id = area === null ? this._homeDeviceId : this._areaDeviceIds.get(area);
          if (!id) return;
          const path = '/config/devices/device/' + encodeURIComponent(id);
          // HA's SPA device route; never build a link from the area name.
          if (window.history?.pushState && window.dispatchEvent) {
            window.history.pushState(null, '', path);
            window.dispatchEvent(new Event('location-changed'));
          } else if (window.location) {
            window.location.assign(path);
          }
          return;
        }
        const moreInfo = event.target.closest?.('[data-open-climate]');
        if (moreInfo) {
          const entityId = moreInfo.getAttribute('data-open-climate');
          const area = moreInfo.getAttribute('data-controller-area');
          if (this._managedControllers(area).some((item)=>item.entityId===entityId)) {
            this.dispatchEvent(new CustomEvent('hass-more-info', {
              detail:{entityId}, bubbles:true, composed:true
            }));
          }
          return;
        }
        const targetSave = event.target.closest?.('[data-save-climate-target]');
        if (targetSave) {
          const area = targetSave.getAttribute('data-controller-area');
          const entityId = targetSave.getAttribute('data-save-climate-target');
          const metric = targetSave.getAttribute('data-target-metric');
          const controller = this._managedControllers(area).find(
            (entry)=>entry.entityId===entityId);
          const input = targetSave.closest('.climate-target-editor')
            ?.querySelector('input[data-climate-input]');
          const parsed = input ? Number(String(input.value).replace(',', '.')) : NaN;
          const boundaries = controller?.climate?.attributes || {};
          const nativeSupported = Number(boundaries.supported_features) || 0;
          const validMetric = metric==='temperature' ? Boolean(nativeSupported & 1)
            : metric==='humidity' && Boolean(nativeSupported & 4);
          const minimum = metric==='temperature'
            ? Number(boundaries.min_temp ?? 5) : Number(boundaries.min_humidity ?? 20);
          const maximum = metric==='temperature'
            ? Number(boundaries.max_temp ?? 35) : Number(boundaries.max_humidity ?? 80);
          if (!controller || controller.method?.state!=='manual' ||
              controller.climate?.state==='unavailable' || !validMetric ||
              !Number.isFinite(parsed) || !Number.isFinite(minimum) ||
              !Number.isFinite(maximum) || parsed<minimum || parsed>maximum) {
            this._climateEditError = (CLIMATE_LABELS[this._language()] ||
              CLIMATE_LABELS.en).invalidTarget;
            this._render(true);
            return;
          }
          const service = metric==='temperature' ? 'set_temperature' : 'set_humidity';
          this._climateEditError = null;
          Promise.resolve(this._hass.callService('climate',service,{
            entity_id:entityId,[metric]:parsed
          })).catch((error)=>{
            console.error('Home Environment Manager manual target failed',error);
            this._climateEditError = (CLIMATE_LABELS[this._language()] ||
              CLIMATE_LABELS.en).editFailed;
            this._render(true);
          });
          return;
        }
        const climate = event.target.closest?.('[data-climate-action]');
        if (climate) {
          const area = climate.getAttribute('data-climate-area');
          const action = climate.getAttribute('data-climate-action');
          if (area && ['pause','resume'].includes(action) && this._hass?.callService) {
            Promise.resolve(this._hass.callService('environment_manager','climate_control',{area,action}))
              .catch((error)=>console.error('Home Environment Manager climate action failed',error));
          }
          return;
        }
        const pid = event.target.closest?.('[data-pid-action]');
        if (pid) {
          const area = pid.getAttribute('data-pid-area');
          const action = pid.getAttribute('data-pid-action');
          if (area && ['pause','resume'].includes(action) && this._hass?.callService) {
            Promise.resolve(this._hass.callService('environment_manager','pid_control',{area,action}))
              .catch((error)=>console.error('Home Environment Manager PID action failed',error));
          }
          return;
        }
        const button = event.target.closest?.('[data-expand]');
        if (!button) return;
        const area = button.getAttribute('data-expand');
        if (this._expanded.has(area)) this._expanded.delete(area);
        else this._expanded.add(area);
        this._render(true);
      });
      this.shadowRoot.addEventListener('change', (event) => {
        const selector = event.target.closest?.('[data-climate-method]');
        if (!selector || !this._hass?.callService) return;
        const area = selector.getAttribute('data-controller-area');
        const entityId = selector.getAttribute('data-climate-method');
        const current = this._managedControllers(area).find(
          (item)=>item.methodId===entityId);
        const value = selector.value;
        const choices = current?.method?.attributes?.options;
        if (!current || current.climate?.state==='unavailable' ||
            !Array.isArray(choices) || !choices.includes(value)) return;
        this._climateEditError = null;
        Promise.resolve(this._hass.callService('select','select_option',{
          entity_id:entityId,option:value
        })).catch((error)=>{
          console.error('Home Environment Manager control method failed',error);
          this._climateEditError = (CLIMATE_LABELS[this._language()] ||
            CLIMATE_LABELS.en).editFailed;
          this._render(true);
        });
        // A native change event commits the user's selected option. This is
        // the earliest safe point to let the Manual target editor appear.
        if (this._focusedEditor === selector) {
          this._focusedEditor = null;
          this._pendingRender = true;
          this._flushDeferredRenderSoon();
        }
      });
    }

    _flushDeferredRenderSoon() {
      if (this._editRenderTimer !== null) clearTimeout(this._editRenderTimer);
      this._editRenderTimer = setTimeout(() => {
        this._editRenderTimer = null;
        if (this._focusedEditor || !this._pendingRender) return;
        const forced = this._pendingForceRender;
        this._pendingRender = false;
        this._pendingForceRender = false;
        this._render(forced);
      }, 80);
    }

    disconnectedCallback() {
      if (this._editRenderTimer !== null) {
        clearTimeout(this._editRenderTimer);
        this._editRenderTimer = null;
      }
      this._focusedEditor = null;
      this._pendingRender = false;
      this._pendingForceRender = false;
    }

    setConfig(config) {
      if (config.entity && !/^sensor\.[a-z0-9_]+$/.test(config.entity)) {
        throw new Error('Home Environment Manager: entity must be a sensor.* entity ID');
      }
      this._config = {show_outside:true, show_metrics:true, show_science:true, ...config};
      this._lastConfigKey = null;
      this._loadDashboard();
      this._render(true);
    }

    set hass(hass) {
      this._hass = hass;
      this._loadDashboard();
      this._loadDeviceIds();
      this._render();
    }

    _loadDashboard() {
      // Recorder attributes deliberately contain only an API marker/revision.
      // Fetch the complete scientific and device data over authenticated WS.
      // Old in-memory dashboards remain displayable during a rolling upgrade.
      if (!this._hass?.callWS) return;
      const [entityId, state] = this._state();
      const attrs = state?.attributes || {};
      if (!entityId || attrs.dashboard_api !== 'environment_manager/dashboard' ||
          attrs.dashboard?.version === 1) return;
      const revision = Number(attrs.dashboard_revision) || 0;
      if (this._dashboardEntity === entityId &&
          this._dashboardLoadedRevision === revision && this._dashboardData) return;
      if (this._dashboardFetching ||
          Date.now()<this._dashboardNextAttemptAt) return;
      const capturedEntity = entityId;
      const capturedRevision = revision;
      this._dashboardFetching = Promise.resolve().then(() =>
        this._hass.callWS({
          type:'environment_manager/dashboard', entity_id:capturedEntity
        })
      ).then((snapshot) => {
        if (!snapshot || snapshot.version !== 1 ||
            !Array.isArray(snapshot.rooms)) throw new Error('Invalid dashboard snapshot');
        // A response from a previously selected recommendation must never
        // appear on another entry's card after the user changes the source.
        if (this._state()[0] !== capturedEntity) return;
        this._dashboardData = snapshot;
        this._dashboardEntity = capturedEntity;
        this._dashboardLoadedRevision = capturedRevision;
        this._dashboardFailureCount = 0;
        this._dashboardNextAttemptAt = 0;
        this._render(true);
      }).catch((error) => {
        this._dashboardFailureCount = Math.min(6, this._dashboardFailureCount+1);
        this._dashboardNextAttemptAt = Date.now() +
          Math.min(60000, 1000 * (2 ** this._dashboardFailureCount));
        if (this._dashboardFailureCount<=2) {
          console.warn('Home Environment Manager dashboard will retry',error);
        }
      }).finally(() => {
        this._dashboardFetching = null;
        const [currentEntity, current] = this._state();
        const currentRevision = Number(current?.attributes?.dashboard_revision) || 0;
        if (current?.attributes?.dashboard_api === 'environment_manager/dashboard' &&
            (currentEntity !== capturedEntity ||
             currentRevision !== capturedRevision) &&
            Date.now()>=this._dashboardNextAttemptAt) {
          this._loadDashboard();
        }
      });
    }

    _loadDeviceIds() {
      // Loading/reconnect failures are transient. A permanent "unavailable"
      // latch previously required a browser hard refresh to recover links.
      if (this._deviceRegistryLoading || this._deviceRegistryLoaded ||
          !this._hass?.callWS || Date.now()<this._deviceRegistryNextAttemptAt) return;
      // Defer the call to catch both synchronous WebSocket failures and
      // rejected promises without escaping from Home Assistant's hass setter.
      this._deviceRegistryLoading = Promise.resolve().then(() =>
        this._hass.callWS({type:'config/device_registry/list'})
      ).then((entries) => {
        if (!Array.isArray(entries)) throw new Error('Invalid device registry');
        const belong = (d) => safeArray(d?.identifiers)
          .filter((pair) => Array.isArray(pair) && pair[0]==='environment_manager')
          .map((pair) => pair[1]);
        const home = entries.filter((device) => belong(device).some(
          (identifier) => typeof identifier === 'string' && !identifier.includes('_area_')
        ));
        const stateId = this._state()[0];
        const currentDevice = this._hass?.entities?.[stateId]?.device_id;
        const parent = home.find((device)=>device.id===currentDevice) ||
                       (home.length===1 ? home[0] : null);
        if (!parent) {
          // Multiple integrations or an incomplete HA registry are ambiguous.
          // Do not navigate to a guessed device; retry when HA reconnects.
          throw new Error('Home device registry not yet unambiguous');
        }
        const ids = belong(parent);
        const entryId = ids.find((id) => typeof id==='string' && !id.includes('_area_'));
        if (!entryId) throw new Error('Home device registry is incomplete');
        const roomDevices = new Map();
        for (const device of entries) {
          for (const identifier of belong(device)) {
            const prefix = entryId+'_area_';
            if (typeof identifier === 'string' && identifier.startsWith(prefix)) {
              roomDevices.set(identifier.slice(prefix.length),device.id);
            }
          }
        }
        this._homeDeviceId = parent.id;
        this._areaDeviceIds = roomDevices;
        this._deviceRegistryLoaded = true;
        this._deviceRegistryUnavailable = false;
        this._deviceRegistryFailureCount = 0;
        this._deviceRegistryNextAttemptAt = 0;
        this._render(true);
      }).catch((error) => {
        this._deviceRegistryLoaded = false;
        this._deviceRegistryFailureCount = Math.min(6, this._deviceRegistryFailureCount+1);
        this._deviceRegistryNextAttemptAt = Date.now()+
          Math.min(60000, 1000*(2**this._deviceRegistryFailureCount));
        // A temporary websocket/registry outage must not break card rendering
        // and must not generate a console warning on every hass state update.
        if (this._deviceRegistryFailureCount<=2) {
          console.warn('Home Environment Manager device links will retry', error);
        }
      }).finally(() => { this._deviceRegistryLoading = null; });
    }

    _deviceEditLabel(home = false) {
      const l = DEVICE_EDIT_LABELS[this._language()] || DEVICE_EDIT_LABELS.en;
      return home ? l.home : l.room;
    }

    _editButton(area) {
      const device = this._areaDeviceIds.get(String(area));
      return '<button class="edit-device" type="button" data-edit-area="'+escape(area)+
        '" aria-label="'+escape(this._deviceEditLabel())+'" title="'+escape(
          this._deviceEditLabel())+'" '+(device ? '' : 'disabled')+'>'+
        this._icon('mdi:cog-outline')+'</button>';
    }

    getCardSize() { return 5; }

    _language() {
      return cardLanguage(this._hass?.language);
    }

    _t(key) {
      const lang = this._language();
      return key === "title" ? BRAND_TITLE : (LANGUAGE[lang]?.[key] || LANGUAGE.en[key] || key);
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

    _managedControllers(area) {
      // Only match Manager-created native climate facades with provenance.
      // An unrelated physical entity must never acquire writable controls.
      const states = Object.entries(this._hass?.states || {});
      const physical = states.filter(([id, item])=>
        id.startsWith('climate.') && item?.attributes?.area_id===area &&
        Array.isArray(item.attributes.source_entity_ids) &&
        item.attributes.source_entity_ids.length>0 &&
        typeof item.attributes.control_mode==='string');
      const selectors = states.filter(([id, item])=> id.startsWith('select.') &&
        item?.attributes?.area_id===area &&
        Array.isArray(item.attributes.source_entity_ids) &&
        Array.isArray(item.attributes.options) &&
        ['automatic','manual','off'].every((mode)=>item.attributes.options.includes(mode)));
      const signature = (item) => JSON.stringify(
        safeArray(item.attributes.source_entity_ids).slice().sort());
      return physical.map(([entityId, climate])=>{
        const matched = selectors.filter(([,item])=>signature(item)===signature(climate));
        const [methodId, method] = matched.length===1 ? matched[0] : [null,null];
        return {entityId,climate,methodId,method};
      }).sort((a,b)=>a.entityId.localeCompare(b.entityId));
    }

    _controllerSignature() {
      // The main recommendation sensor may be unchanged while a physical
      // controller is switched to Manual/PID/Off in Home Assistant.
      const rows = Object.entries(this._hass?.states || {})
        .filter(([id, state]) =>
          (id.startsWith('select.') || id.startsWith('climate.')) &&
          Array.isArray(state?.attributes?.source_entity_ids) &&
          typeof state.attributes.area_id==='string')
        .map(([id,state])=>[
          id,state.state,state.attributes.control_mode,
          state.attributes.temperature,state.attributes.humidity,
          state.attributes.supported_features,
          state.attributes.options,
          state.attributes.source_entity_ids,
        ]);
      return JSON.stringify(rows);
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

    _moldLabels() {
      return MOLD_DETAIL_LABELS[this._language()] || MOLD_DETAIL_LABELS.en;
    }

    _formatCalibration(value) {
      if (typeof value !== 'number' || !Number.isFinite(value)) return '–';
      // Display precision only: this never changes the stored numeric factor.
      try {
        return new Intl.NumberFormat(this._hass?.language || 'en', {
          minimumFractionDigits: 2, maximumFractionDigits: 6, useGrouping: false
        }).format(value);
      } catch { return String(value); }
    }

    _moldCalibrationDetails(moldReading) {
      const details = moldReading?.details;
      if (typeof details?.calibration_factor !== 'number' ||
          !Number.isFinite(details.calibration_factor)) return '';
      const labels = this._moldLabels();
      const temperature = (value) => typeof value === 'number' && Number.isFinite(value)
        ? `${escape(this._format(value))}°C` : '–';
      return `<section class="mold-calibration-details" role="group"
          aria-label="${escape(labels[4])}">
        <div><span>${escape(labels[4])}</span>
          <strong title="${escape(String(details.calibration_factor))}">${escape(this._formatCalibration(details.calibration_factor))}</strong></div>
        <div><span>${escape(labels[5])}</span>
          <strong>${temperature(details.indoor_temperature_c)}</strong></div>
        <div><span>${escape(labels[6])}</span>
          <strong>${temperature(details.outdoor_temperature_c)}</strong></div>
      </section>`;
    }

    _metricHelp(item) {
      const lang = this._language();
      const gr = lang === 'el';
      const de = lang === 'de';
      const texts = {
        co2: ['CO₂ shows how much exhaled air accumulates indoors. Elevated levels suggest insufficient ventilation and may coincide with sleepiness and impaired concentration.', 'Το CO₂ δείχνει πόσος εκπνεόμενος αέρας συσσωρεύεται. Υψηλή συγκέντρωση υποδηλώνει ανεπαρκή αερισμό και μπορεί να συνδέεται με υπνηλία και μειωμένη συγκέντρωση.', 'CO₂ zeigt die Ansammlung ausgeatmeter Luft und kann auf unzureichende Lüftung hinweisen.'],
        pm25: ['PM2.5 particles can penetrate deeply into the lungs. Filtration and avoiding polluted outdoor air may reduce exposure.', 'Τα σωματίδια PM2.5 διεισδύουν βαθιά στους πνεύμονες. Ο καθαρισμός και η αποφυγή ρυπασμένου εξωτερικού αέρα μειώνουν την έκθεση.', 'PM2,5-Partikel können tief in die Lunge eindringen. Filtration kann die Belastung senken.'],
        pm10: ['PM10 is inhalable particulate matter. High exposure can irritate the airways.', 'Τα PM10 είναι εισπνεόμενα αιωρούμενα σωματίδια που μπορούν να ερεθίσουν τους αεραγωγούς.', 'PM10 ist einatembarer Feinstaub, der die Atemwege reizen kann.'],
        humidity: ['Relative humidity depends on temperature. Persistently high RH increases condensation and mold risk; low RH may cause dryness.', 'Η σχετική υγρασία εξαρτάται από τη θερμοκρασία. Η παρατεταμένα υψηλή υγρασία αυξάνει τον κίνδυνο συμπύκνωσης και μούχλας· η χαμηλή προκαλεί ξηρότητα.', 'Relative Luftfeuchte hängt von der Temperatur ab. Dauerhaft hohe Werte fördern Kondenswasser und Schimmel.'],
        mold: ['This is an estimated critical-surface moisture indicator, not a mold detector. Cold surfaces and persistent high RH can raise risk.', 'Πρόκειται για εκτίμηση υγρασίας κρίσιμης επιφάνειας, όχι ανιχνευτή μούχλας. Οι κρύες επιφάνειες και η επίμονη υγρασία αυξάνουν τον κίνδυνο.', 'Dies ist eine Schätzung der Oberflächenfeuchte, kein Schimmeldetektor.'],
        aqi: ['Air Quality Index summarizes pollution according to the selected provider scale. Different national scales are not interchangeable.', 'Ο δείκτης AQI συνοψίζει τη ρύπανση βάσει της κλίμακας του παρόχου. Οι εθνικές κλίμακες δεν είναι ισοδύναμες.', 'Der Luftqualitätsindex verwendet die Skala des Anbieters. Nationale Skalen sind nicht austauschbar.'],
        voc: ['Volatile organic compounds may originate from cleaning agents, paints and furnishings. Sensor accuracy and compound coverage vary.', 'Οι πτητικές οργανικές ενώσεις προέρχονται μεταξύ άλλων από καθαριστικά, βαφές και έπιπλα. Η ακρίβεια του αισθητήρα διαφέρει.', 'Flüchtige organische Stoffe stammen etwa aus Reinigern, Farben und Möbeln.'],
        voc_parts: ['VOC concentration in parts per billion depends on sensor calibration and reference gas; high readings merit source inspection.', 'Οι VOC σε ppb εξαρτώνται από τη βαθμονόμηση και το αέριο αναφοράς. Οι υψηλές τιμές απαιτούν έλεγχο της πηγής.', 'VOC in ppb sind stark von Kalibrierung und Referenzgas abhängig.'],
        no2: ['Nitrogen dioxide can aggravate respiratory symptoms; sources include traffic and combustion.', 'Το διοξείδιο του αζώτου μπορεί να επιδεινώσει αναπνευστικά συμπτώματα· προέρχεται από κυκλοφορία και καύση.', 'Stickstoffdioxid aus Verkehr oder Verbrennung belastet die Atemwege.'],
        o3: ['Ground-level ozone can irritate the lungs and worsen asthma symptoms.', 'Το όζον κοντά στο έδαφος μπορεί να ερεθίσει τους πνεύμονες και να επιδεινώσει το άσθμα.', 'Bodennahes Ozon kann die Atemwege reizen.'],
        so2: ['Sulfur dioxide from combustion can irritate breathing passages.', 'Το διοξείδιο του θείου από καύσεις μπορεί να ερεθίσει το αναπνευστικό.', 'Schwefeldioxid aus Verbrennung kann die Atemwege reizen.']
      };
      const base = texts[item.metric] || [
        'Measured environmental data from the selected Home Assistant sensor. Use the recorded source, units and freshness to interpret it.',
        'Περιβαλλοντική μέτρηση από αισθητήρα Home Assistant. Ελέγξτε την πηγή, τις μονάδες και την ενημέρωση.',
        'Umweltmessung des ausgewählten Home-Assistant-Sensors. Quelle, Einheit und Aktualität beachten.'
      ];
      const limit = typeof item.threshold === 'number' && Number.isFinite(item.threshold)
        ? (gr ? ' Όριο ρύθμισης: ' : de ? ' Konfiguriertes Limit: ' : ' Configured threshold: ') + item.threshold + (item.unit ? ' ' + item.unit : '') + '.'
        : '';
      return (gr ? base[1] : de ? base[2] : base[0]) + limit;
    }

    _metric(item, miniature = false) {
      const metric = item.details?.fallback_for_mold
        ? `${this._t('humidity')} Ø (RH)`
        : item.metric==='unknown' ? (item.name || item.entity_id || this._t('missing'))
          : this._metricName(item.metric);
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
      const moldLabels = this._moldLabels();
      const count = details?.humidity_sensor_count;
      const average = details && typeof details.average_indoor_humidity === 'number'
        && Number.isFinite(details.average_indoor_humidity)
        ? `<div>${escape(moldLabels[0])}: ${escape(this._format(details.average_indoor_humidity))}%
          ${Number.isInteger(count) && count > 0
            ? ` · ${escape(count)} ${escape(count === 1 ? moldLabels[1] : moldLabels[2])}`
            : ''}</div>`
        : '';
      const surface = details && typeof details.estimated_surface_c === 'number'
        && Number.isFinite(details.estimated_surface_c)
        ? `<div>${escape(moldLabels[3])}: ${escape(this._format(details.estimated_surface_c))}°C</div>`
        : '';
      const moldInfo = average || surface
        ? `<div class="mold-summary">${average}${surface}</div>` : '';
      return `<div class="metric ${miniature ? 'tiny' : ''} metric-${level}">
        <div class="metric-line">
          <span class="metric-name">${this._icon(METRIC_ICON[item.metric] || 'mdi:gauge')} ${escape(metric)} <details class="metric-help"><summary aria-label="${escape(metric)} information" title="${escape(this._metricHelp(item))}">${this._icon('mdi:information-outline')}</summary><div class="metric-help-content" role="note">${escape(this._metricHelp(item))}</div></details></span>
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


    _scienceHelp(topic) {
      const lang = this._language();
      const explanations = {
        moisture: ['Moisture-ratio difference estimates whether outside air can dry or humidify the room. Relative humidity alone does not show this.', 'Η διαφορά στην ποσότητα υδρατμών δείχνει αν ο εξωτερικός αέρας μπορεί να ξηράνει ή να υγράνει το δωμάτιο. Η σχετική υγρασία μόνη της δεν επαρκεί.'],
        predicted: ['Outdoor relative humidity projected after the air warms indoors; this is a physical estimate, not a humidity forecast.', 'Εκτίμηση σχετικής υγρασίας του εξωτερικού αέρα αφού θερμανθεί μέσα. Δεν αποτελεί πρόγνωση.'],
        band: ['Adaptive comfort band derived from outdoor temperature history. It describes expected comfort, not a mandatory medical limit.', 'Προσαρμοστική ζώνη θερμικής άνεσης βάσει ιστορικού εξωτερικής θερμοκρασίας, όχι ιατρικό όριο.'],
        cooling: ['Positive outdoor cooling advantage suggests a possible window-airing opportunity if outdoor air quality and weather are safe.', 'Πιθανή φυσική ψύξη από τον εξωτερικό αέρα, μόνο εφόσον επιτρέπουν η ρύπανση και ο καιρός.'],
        surface: ['Condensation margin estimates how near a cold surface is to its dew point. A small margin increases moisture risk.', 'Το περιθώριο συμπύκνωσης δείχνει πόσο πλησιάζει μια ψυχρή επιφάνεια στο σημείο δρόσου. Μικρή διαφορά αυξάνει τον κίνδυνο υγρασίας.'],
        exposure: ['Hours with estimated surface RH above the displayed exposure threshold. Persistent moisture raises mold risk; it is not proof of mold.', 'Ώρες με εκτιμώμενη υγρασία επιφάνειας πάνω από το εμφανιζόμενο όριο. Η παρατεταμένη υγρασία ευνοεί τη μούχλα, δεν την αποδεικνύει.'],
        pm: ['Measured 24-hour particulate mean, only shown when history coverage is sufficient. Exposure duration matters, not just one reading.', 'Μέσος όρος σωματιδίων 24 ωρών μόνο με επαρκές ιστορικό. Η διάρκεια έκθεσης έχει σημασία.'],
        co2: ['CO₂ rate of change can help evaluate ventilation or occupancy but does not independently measure air changes.', 'Ο ρυθμός μεταβολής CO₂ βοηθά στην αξιολόγηση αερισμού ή παρουσίας αλλά δεν μετρά απευθείας τις εναλλαγές αέρα.'],
        ach: ['Conditional air-change estimate from a qualified CO₂ decay sequence. It is not a certified ventilation airflow measurement.', 'Εκτίμηση εναλλαγών αέρα από αξιόπιστη πτώση CO₂· δεν αποτελεί πιστοποιημένη μέτρηση παροχής αέρα.'],
        energy: ['Approximate heat required per cubic meter of exchanged air. Mechanical efficiency and actual device power are not included.', 'Εκτιμώμενη θερμική ενέργεια ανά κυβικό μέτρο ανανέωσης αέρα· δεν περιλαμβάνει πραγματική κατανάλωση συσκευών.'],
        purification: ['Nominal clean-air changes from entered room volume and purifier CADR; real performance varies with filters and airflow.', 'Ονομαστικές εναλλαγές καθαρού αέρα από όγκο χώρου και CADR. Η πραγματική απόδοση εξαρτάται από φίλτρα και ροή.'],
        ventilation: ['Indicative minutes to a selected target based on observed improvement. Changes in occupancy or windows can invalidate the estimate.', 'Ενδεικτικά λεπτά μέχρι τον στόχο βάσει μετρήσεων. Αλλαγές παρουσίας και παραθύρων επηρεάζουν την εκτίμηση.'],
        humidity_event: ['Recent relative-humidity increase can indicate moisture generation (showering, cooking or drying), but source attribution is uncertain.', 'Πρόσφατη άνοδος σχετικής υγρασίας μπορεί να οφείλεται σε ντους, μαγείρεμα ή στέγνωμα· η πηγή δεν αποδεικνύεται.'],
        formaldehyde: ['Formaldehyde can irritate the eyes and airways. The short measurement period is not a long-term exposure assessment.', 'Η φορμαλδεΰδη μπορεί να ερεθίσει μάτια και αεραγωγούς. Η σύντομη μέτρηση δεν εκτιμά τη μακροχρόνια έκθεση.'],
        radon: ['Radon is a radioactive gas associated with increased lung cancer risk from long-term exposure. Meaningful assessment requires an adequately long calibrated measurement.', 'Το ραδόνιο είναι ραδιενεργό αέριο και η μακροχρόνια έκθεση αυξάνει τον κίνδυνο καρκίνου πνεύμονα. Χρειάζεται αξιόπιστη μακρά μέτρηση.'],
        noise: ['Sound levels in dB(A) depend on measurement period and calibration. Sustained or nighttime noise may disrupt sleep.', 'Η στάθμη dB(A) εξαρτάται από τη διάρκεια και τη βαθμονόμηση. Επίμονος ή νυχτερινός θόρυβος μπορεί να επηρεάσει τον ύπνο.'],
        light: ['Observed daylight availability can help assess light exposure, but ordinary lux does not determine circadian stimulus.', 'Η διάρκεια φυσικού φωτισμού περιγράφει την έκθεση στο φως, αλλά τα κοινά lux δεν προσδιορίζουν τον κιρκάδιο ερεθισμό.'],
        melanopic: ['Melanopic equivalent daylight illuminance approximates biological light stimulation only from a verified spectral measurement.', 'Τα μελανοπικά lux εκτιμούν τη βιολογική επίδραση φωτός μόνο με κατάλληλη φασματική μέτρηση.'],
        overheating: ['Cumulative degrees above an overheating reference reflect both intensity and duration of indoor heat.', 'Σωρευτικοί βαθμοώρες πάνω από όριο υπερθέρμανσης δείχνουν ένταση και διάρκεια ζέστης.'],
        pmv: ['PMV predicts average thermal sensation and PPD the predicted percentage dissatisfied under declared clothing, activity, airflow and radiation assumptions.', 'Το PMV εκτιμά θερμική αίσθηση και το PPD το ποσοστό δυσαρέσκειας, με υποθέσεις ένδυσης, δραστηριότητας και ροής αέρα.'],
        particle: ['Indoor/outdoor particle ratio compares measured concentrations; differences do not by themselves prove filtration efficiency.', 'Ο λόγος εσωτερικών/εξωτερικών σωματιδίων συγκρίνει μετρήσεις, αλλά δεν αποδεικνύει μόνος του απόδοση φίλτρων.'],
      };
      const record = explanations[topic] || ['Measured environmental estimate; interpret only with its source and units.', 'Περιβαλλοντική εκτίμηση: ελέγξτε πηγή και μονάδες.'];
      return record[lang === 'el' ? 1 : 0];
    }

    _environmentReport(room) {
      const e = room.environment || {};
      const m = e.moisture || {};
      const t = e.thermal_comfort || {};
      const p = e.passive_cooling || {};
      const s = e.condensation || {};
      const h = e.surface_rh_exposure_24h || {};
      const labels = SCIENCE_LABELS[this._language()] || SCIENCE_LABELS.en;
      const fmt = (v, digits = 1) => this._format(v, digits);
      const lines = [];
      const add = (label, value, topic = '') => {
        const help = this._scienceHelp(topic);
        lines.push('<div class="science-line"><span>' + escape(label) +
          ' <details class="metric-help"><summary aria-label="' + escape(label) +
          ' information" title="' + escape(help) + '">' +
          this._icon('mdi:information-outline') +
          '</summary><div class="metric-help-content" role="note">' +
          escape(help) + '</div></details></span><strong>' + escape(value) + '</strong></div>');
      };
      if (m.status === 'drying' || m.status === 'humidifying' || m.status === 'neutral') {
        add(m.status === 'drying' ? labels.drying :
            m.status === 'humidifying' ? labels.humidifying : labels.neutral,
          fmt(m.drying_potential_g_kg, 2) + ' g/kg','moisture');
        if (typeof m.outside_air_rh_when_warmed_percent === 'number')
          add(labels.predicted, fmt(m.outside_air_rh_when_warmed_percent) + '% RH','predicted');
      }
      if (t.status === 'within_band' || t.status === 'above_band' || t.status === 'below_band') {
        add(labels.band + ' · ' +
            (t.status === 'above_band' ? labels.heat :
             t.status === 'below_band' ? labels.cool : labels.normal),
          fmt(t.lower_80_c) + '–' + fmt(t.upper_80_c) + ' °C','band');
      }
      if (p.status === 'cooling_opportunity')
        add(labels.cooling, fmt(p.cooling_delta_c) + ' °C','cooling');
      if (s.status && s.status !== 'unavailable')
        add(labels.surface, fmt(s.condensation_margin_c) + ' °C','surface');
      if (h.status === 'ready')
        add(labels.exposure, fmt(h.above_threshold_hours) + ' h','exposure');
      for (const [key, label] of [['pm25_24h', labels.pm25], ['pm10_24h', labels.pm10]]) {
        const value = e[key] || {};
        if (value.status === 'ready') add(label, fmt(value.mean) + ' µg/m³','pm');
      }
      if (e.co2_trend?.status === 'ready')
        add(labels.co2, fmt(e.co2_trend.trend_ppm_per_hour) + ' ppm/h','co2');
      if (e.co2_decay_ach?.status === 'estimate')
        add(labels.ach, fmt(e.co2_decay_ach.ach_per_hour, 2) + ' h⁻¹','ach');
      if (typeof e.heat_per_full_air_exchange_wh_m3 === 'number')
        add(labels.energy, fmt(e.heat_per_full_air_exchange_wh_m3) + ' Wh/m³','energy');
      const extra = e.international || {};
      const eLabels = EXTRA_LABELS[this._language()] || EXTRA_LABELS.en;
      if (extra.air_purification?.nominal_particle_clean_air_changes_h !== undefined)
        add(eLabels.purification,fmt(extra.air_purification.nominal_particle_clean_air_changes_h,2)+' h⁻¹','purification');
      if (extra.ventilation_learning?.status === 'indicative')
        add(eLabels.toTarget,'~'+fmt(extra.ventilation_learning.estimated_minutes_to_target)+' min','ventilation');
      if (extra.moisture_event?.status === 'relative_humidity_rise')
        add(eLabels.sourceMoisture,'+'+fmt(extra.moisture_event.rh_change_percent_points)+' %','humidity_event');
      if (extra.formaldehyde_30min?.status === 'ready')
        add(eLabels.hcho,fmt(extra.formaldehyde_30min.mean)+' µg/m³','formaldehyde');
      if (extra.radon?.status === 'annual_screening')
        add(eLabels.radon,fmt(extra.radon.mean_bq_m3)+' Bq/m³','radon');
      if (extra.sound_24h?.status === 'indicative_laeq')
        add(eLabels.noise,fmt(extra.sound_24h.db_a)+' dB(A)','noise');
      if (extra.sound_last_night?.status === 'indicative_night_laeq')
        add(eLabels.nightNoise,fmt(extra.sound_last_night.db_a)+' dB(A)','noise');
      if (extra.daylight?.status === 'descriptive')
        add(eLabels.light,fmt(extra.daylight.observed_hours_above_threshold)+' h','light');
      if (extra.daylight?.melanopic_edi_status === 'sensor_reported_not_from_photopic_lux')
        add(eLabels.melanopic,fmt(extra.daylight.melanopic_edi_lux)+' lx','melanopic');
      if (extra.overheating_degree_hours?.status === 'ready')
        add(eLabels.overheated,fmt(extra.overheating_degree_hours.degree_hours_over_reference)+' °C·h','overheating');
      if (extra.pmv_ppd?.status === 'estimate')
        add(eLabels.pmv,fmt(extra.pmv_ppd.pmv,2)+' / '+fmt(extra.pmv_ppd.ppd_percent)+'%','pmv');
      if (extra.particle_indoor_outdoor_ratio?.status === 'descriptive_only')
        add(eLabels.particle,fmt(extra.particle_indoor_outdoor_ratio.ratio,2),'particle');
      if (!lines.length) return '';
      return '<section class="science-section" aria-label="' + escape(labels.title) + '">' +
        '<div class="field-label">' + this._icon('mdi:flask-outline') +
        escape(labels.title) + '</div><div class="science-grid">' + lines.join('') + '</div>' +
        '<div class="science-caveat">' + escape(labels.estimated) + '</div></section>';
    }

    _pollenIndicator(outdoor) {
      const p = outdoor?.pollen || {};
      if (p.status !== 'provider_defined') return '';
      const title = (EXTRA_LABELS[this._language()] || EXTRA_LABELS.en);
      return '<div class="pollen-indicator" role="status">' +
        this._icon('mdi:flower-pollen') +
        escape(title.pollen) + ': <strong>' + escape(this._format(p.value)) + ' / ' +
        escape(this._format(p.max_scale)) + (p.high ? ' · ' + escape(title.pollenHigh) : '') +
        '</strong></div>';
    }

    _controllerPanel(room) {
      const devices=this._managedControllers(room.area_id);
      if (!devices.length) return '';
      const l=CLIMATE_LABELS[this._language()] || CLIMATE_LABELS.en;
      const methods={existing:l.existing,automatic:l.automatic,manual:l.manual,
        pid:l.pid,off:l.off};
      const sections=devices.map((entry)=>{
        const state=entry.climate;
        const attrs=state.attributes || {};
        const available=state.state!=='unavailable' && state.state!=='unknown';
        const selection=entry.method;
        const options=Array.isArray(selection?.attributes?.options)
          ? selection.attributes.options : [];
        const control=selection?.state || attrs.control_mode || 'existing';
        const name=attrs.friendly_name || entry.entityId;
        const method=entry.methodId && options.length
          ? '<label class="managed-method-label"><span>'+escape(l.method)+'</span>'+
          '<select data-climate-method="'+escape(entry.methodId)+
          '" data-controller-area="'+escape(room.area_id)+
          '" aria-label="'+escape(l.method)+' · '+escape(name)+'" '+
          (available ? '' : 'disabled')+'>'+
          options.map((option)=>'<option value="'+escape(option)+'" '+
            (option===control ? 'selected' : '')+'>'+
            escape(methods[option] || option)+'</option>').join('')+
          '</select></label>' : '';
        const features=Number(attrs.supported_features) || 0;
        const editable=available && control==='manual';
        const editors=[];
        for(const [kind,bit,label,minKey,maxKey,fallbackLow,fallbackHigh,step] of [
          ['temperature',1,l.manualTemperature,'min_temp','max_temp',5,35,0.5],
          ['humidity',4,l.manualHumidity,'min_humidity','max_humidity',20,80,1],
        ]) {
          if (!(features & bit) || !editable) continue;
          const minimum=Number(attrs[minKey] ?? fallbackLow);
          const maximum=Number(attrs[maxKey] ?? fallbackHigh);
          const value=attrs[kind];
          if (!Number.isFinite(minimum) || !Number.isFinite(maximum) ||
              !(maximum > minimum)) continue;
          editors.push('<div class="climate-target-editor">'+
            '<label><span>'+escape(label)+'</span>'+
            '<input type="number" data-climate-input="'+escape(kind)+
            '" min="'+escape(minimum)+'" max="'+escape(maximum)+
            '" step="'+escape(step)+'" value="'+
            (Number.isFinite(value) ? escape(value) : '')+'"></label>'+
            '<button type="button" data-save-climate-target="'+escape(entry.entityId)+
            '" data-target-metric="'+escape(kind)+'" data-controller-area="'+
            escape(room.area_id)+'">'+escape(l.save)+'</button></div>');
        }
        const status=attrs.controller_status?.status || '';
        return '<section class="managed-controller">'+
          '<button type="button" class="climate-entity-link" '+
          'data-open-climate="'+escape(entry.entityId)+
          '" data-controller-area="'+escape(room.area_id)+
          '" title="'+escape(l.openEntity)+'">'+
          this._icon('mdi:thermostat')+' <strong>'+escape(name)+
          '</strong> '+this._icon('mdi:open-in-new')+'</button>'+
          '<div class="managed-status">'+escape(entry.entityId)+
          ' · '+escape(state.state)+
          (status ? ' · '+escape(status.replaceAll('_',' ')) : '')+'</div>'+
          method+editors.join('')+'</section>';
      }).join('');
      return '<div class="managed-controllers">'+
        '<strong>'+escape(l.devices)+'</strong>'+
        (this._climateEditError ? '<small role="alert" class="climate-edit-error">'+
          escape(this._climateEditError)+'</small>' : '')+
        sections+'</div>';
    }

    _climatePanel(room) {
      const p=room?.environment?.climate_plan || {};
      const managed=this._managedControllers(room.area_id);
      if ((!p.status || p.status==='disabled') && !managed.length) return '';
      const l=CLIMATE_LABELS[this._language()] || CLIMATE_LABELS.en;
      const primary=p.actuation || {};
      const secondary=p.secondary_actuation || {};
      const moisture=p.humidity_actuation || {};
      const power=p.humidity_power_actuation || {};
      const fan=p.fan_actuation || {};
      const fanPower=p.fan_power_actuation || {};
      const dryFan=p.native_air_mode_actuation || {};
      const controllers=[
        {label:l.primary, status:primary.status || 'advisory_only'},
        {label:l.secondary, status:secondary.status || 'advisory_only'},
        {label:l.humidity, status:moisture.status || 'advisory_only'},
        {label:l.humidityPower, status:power.status || 'advisory_only'},
        {label:l.fan, status:fan.status || 'advisory_only'},
        {label:l.fanPower, status:fanPower.status || 'advisory_only'},
        {label:l.dryFanAuto, status:dryFan.status || 'advisory_only'},
      ];
      const working=['setpoint_commanded','native_range_commanded',
        'at_setpoint','native_range_at_setpoint','holding','commanded',
        'modulating','mode_commanded','target_commanded',
        'fan_speed_increased','at_target_speed',
        'native_mode_commanded',
        'power_command_sent','owned_running','power_off_acknowledged',
        'fan_power_commanded','owned_fan_running','fan_power_off_acknowledged',
        'minimum_fan_on_hold',
        'minimum_on_hold_before_safe_off'];
      const active=controllers.some((part)=>working.includes(part.status));
      const enabled=controllers.filter((part)=>part.status!=='advisory_only' &&
        part.status!=='disabled');
      const allPaused=enabled.length>0 && enabled.every((part)=>part.status==='paused');
      const blocked=!active && ['hold','unavailable','unsupported_mode',
        'unsupported_device'].includes(p.status);
      const target=(typeof p.low_target_c==='number' &&
                    typeof p.high_target_c==='number') ?
        this._format(p.low_target_c)+'–'+this._format(p.high_target_c)+' °C' :
        typeof p.temperature_target_c==='number' ?
        this._format(p.temperature_target_c)+' °C' : '—';
      const title=active ? (p.controller==='environment' ? l.environmentActive : l.active)
        : enabled.length ? l.holding : l.advisory;
      const command=allPaused?'resume':'pause';
      const controls=enabled.length===0 ? '' :
        '<button type="button" class="pid-button" data-climate-area="'+escape(room.area_id)+
        '" data-climate-action="'+command+'">'+escape(command==='pause'?l.pause:l.resume)+'</button>';
      const equipment=p.equipment_plan || {};
      const thermal=equipment.thermal || {};
      const wet=equipment.moisture || {};
      const humidity=equipment.humidity || {};
      const sources=[
        thermal.entity_id ? '<span>'+escape(l.selectedDevice)+': <b>'+
          escape(thermal.entity_id)+'</b></span>' : '',
        wet.entity_id ? '<span>'+escape(l.humidity)+': <b>'+
          escape(wet.entity_id)+'</b></span>' : '',
      ].filter(Boolean).join('');
      const controllerDetails=controllers.filter((part)=>
        part.status!=='advisory_only' && part.status!=='disabled').map((part)=>
        '<small>'+escape(part.label)+': '+escape(String(part.status).replaceAll('_',' '))+
        '</small>').join('');
      const humidityDetails=humidity.status==='advisory' ?
        '<small>'+escape(l.moistureAction)+': '+escape(humidity.action||'idle')+
        (typeof humidity.measured_rh==='number' ?
          ' · '+escape(l.currentHumidity)+': '+escape(this._format(humidity.measured_rh))+'%' : '')+
        ' · '+escape(l.sourceStatus)+': '+escape(equipment.humidity_evidence||'unknown')+
        '</small>' : '';
      const air=p.air_actions || {};
      const extract=air.extraction || {};
      const filter=air.filtration || {};
      const airDetails=[
        extract.status==='recommended' ? l.extraction+': '+
          (extract.entity_id || l.advisory) : '',
        filter.status==='recommended' ? l.filtration+': '+
          (filter.entity_id || l.advisory) : '',
      ].filter(Boolean).map((v)=>'<small>'+escape(v)+'</small>').join('');
      const nativeAir=p.native_air_mode_advice || {};
      const dryAdvice=['manual_mode_transition_suggested',
        'manual_stop_dry_suggested'].includes(nativeAir.status) ?
        '<small>'+escape(l.manualDry)+': '+escape(nativeAir.recommended_mode||'')+
        ' · '+escape(nativeAir.climate_entity||'')+'</small>' : '';
      const windowPlan=p.window_efficiency || {};
      const windowAdvice=windowPlan.status==='opportunity' ?
        '<small>'+escape(l.windowHelp)+': '+
        escape(String(windowPlan.effect||''))+' · '+
        escape(String(windowPlan.active_device||''))+
        '</small>' : '';
      const coordinator=p.coordination || {};
      const purposes=coordinator.channels || {};
      const priorities={
        measured_co2_ventilation:l.co2Priority,
        measured_particle_filtration:l.particlePriority,
        temperature_comfort:l.temperaturePriority,
        humidity_management:l.humidityPriority,
        safety:l.safetyPriority,
        hold_or_no_demand:l.noPriority,
      };
      const priorityDetail=coordinator.priority ?
        '<small>'+escape(l.priority)+': '+
        escape(priorities[coordinator.priority] || l.noPriority)+'</small>' : '';
      const heldDetails=Object.entries(purposes)
        .filter(([,data])=>data?.status==='held').slice(0,3)
        .map(([kind,data])=>'<small>'+escape(l.heldPurpose)+' · '+
          escape(kind)+': '+escape(String(data.reason||'unverified').replaceAll('_',' '))+
          '</small>').join('');
      const reason=(p.reason==='secondary_thermal_driver_pending' && active)
        ? '' : p.reason==='environment_only_no_hvac' ? l.environmentOnly
          : (p.reason || '');
      const measuredTemp=typeof p.temperature_c==='number'
        ? '<span>'+escape(l.roomTemperature)+': <b>'+
          escape(this._format(p.temperature_c))+' °C</b></span>'
        : '<span>'+escape(l.temperatureMissing)+'</span>';
      const selected=p.temperature_evidence || {};
      const sourceDiagnostic=p.temperature_c==null && selected.status &&
        selected.status!=='ready' ? '<small>'+escape(selected.status.replaceAll('_',' '))+
          (selected.entity_ids?.length ? ' · '+
            escape(selected.entity_ids.slice(0,3).join(', ')) : '')+
          '</small>' : '';
      return '<section class="pid-panel" aria-label="'+escape(l.title)+'">'+
        '<div class="pid-title">'+this._icon('mdi:thermostat')+
        '<strong>'+escape(l.title)+'</strong><span>'+escape(title)+'</span></div>'+
        '<div class="pid-metrics">'+
        (p.controller==='environment' ? '' :
          '<span>'+escape(l.target)+': <b>'+escape(target)+'</b></span>'+
          '<span>'+escape(l.mode)+': <b>'+escape(p.mode||'—')+'</b></span>')+
        '<span>'+escape(l[p.profile] || p.profile || 'home')+'</span>'+sources+'</div>'+
        measuredTemp+sourceDiagnostic+
        controllerDetails+priorityDetail+heldDetails+
        humidityDetails+airDetails+dryAdvice+windowAdvice+
        (blocked?'<small>'+escape(l.holding)+'</small>':'')+
        (reason?'<small>'+escape(reason)+'</small>':'')+
        controls+this._controllerPanel(room)+'</section>';
    }

    _pidPanel(room) {
      const pid = room?.environment?.climate_pid || {};
      if (!pid.status || pid.status === 'disabled') return '';
      const l = PID_LABELS[this._language()] || PID_LABELS.en;
      const active = ['controlling','at_device_setpoint'].includes(pid.status);
      const paused = pid.status === 'paused';
      const title = paused ? l.paused : active ? l.active : l.pending;
      const metrics = [];
      const show = (title,value)=> metrics.push('<span class="pid-metric">'+escape(title)+
                                              ': <strong>'+escape(value)+'</strong></span>');
      if (typeof pid.target_c === 'number') show(l.target,this._format(pid.target_c)+' °C');
      if (typeof pid.demand_percent === 'number') show(l.effort,this._format(pid.demand_percent)+'%');
      if (typeof pid.desired_setpoint_c === 'number') show(l.requested,this._format(pid.desired_setpoint_c)+' °C');
      const action = paused ? 'resume' : 'pause';
      const button = paused || active ? '<button type="button" class="pid-button" data-pid-area="' +
        escape(room.area_id) + '" data-pid-action="'+action+'">'+escape(paused ? l.resume : l.pause)+'</button>' : '';
      return '<section class="pid-panel"><div class="pid-title">' +
        this._icon('mdi:thermostat')+'<strong>'+escape(l.title)+'</strong><span>'+escape(title)+
        '</span></div><div class="pid-metrics">'+metrics.join('')+'</div>'+
        '<small>'+escape(l.caution)+'</small>'+button+'</section>';
    }

    _room(room) {
      if (room?.climate_only === true) {
        const labels=CLIMATE_LABELS[this._language()] || CLIMATE_LABELS.en;
        return `<article class="room room-climate-only">
          <div class="room-heading">
            <div class="room-icon">${this._icon('mdi:thermostat')}</div>
            <div class="room-main"><h3>${escape(room.name)}</h3>
              <span>${escape(labels.title)}</span></div>
            ${this._editButton(room.area_id)}
          </div>
          ${this._climatePanel(room)}
        </article>`;
      }
      const status = ['safe','attention','unknown'].includes(room.status) ? room.status : 'unknown';
      const readings = safeArray(room.readings);
      const windows = safeArray(room.windows);
      const moldReading = readings.find((item) => item.metric === 'mold' && !item.available);
      const moldCalibration = readings.find((item) => item.metric === 'mold' &&
        typeof item.details?.calibration_factor === 'number' &&
        Number.isFinite(item.details.calibration_factor));
      const rhFallback = room.rh_fallback?.active === true
        ? `<div class="rh-fallback" role="note">
          ${this._icon('mdi:water-percent')}
          <span><b>${escape(RH_FALLBACK_TEXT[this._language()] || RH_FALLBACK_TEXT.en)}</b>
          · ${escape(this._format(room.rh_fallback.value))}%
          · ${escape(this._t('limits'))} ${escape(this._format(room.rh_fallback.threshold))}%</span>
        </div>` : '';
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
      const button = (readings.length > 3 || moldCalibration) &&
        this._config.show_metrics !== false ? `<button type="button" class="expand" data-expand="${escape(room.area_id)}"
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
          ${this._editButton(room.area_id)}
          <span class="status-tag">${this._icon(ICON[status])}${escape(roomStatusLabel)}</span>
        </div>
        ${this._config.show_metrics === false ? '' : readings.length ? `<div class="metric-grid">${shown.map((item) => this._metric(item)).join('')}</div>`
          : `<div class="empty-measurements">${this._icon('mdi:gauge-empty')} ${escape(this._t('missingIndoor'))}</div>`}
        ${button}
        ${expanded && this._config.show_metrics !== false
          ? this._moldCalibrationDetails(moldCalibration) : ''}
        ${this._climatePanel(room)}
        ${this._pidPanel(room)}
        ${this._config.show_science === false ? '' : this._environmentReport(room)}
        ${rhFallback}
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
      if (this._focusedEditor) {
        this._pendingRender = true;
        this._pendingForceRender = this._pendingForceRender || force;
        return; // Never replace an open native select / unfinished input.
      }
      try {
        this._renderContent(force);
        this._lastRenderError = null;
      } catch (error) {
        // A transient malformed/partial HA snapshot must not cause Lovelace's
        // generic broken-card error or poison the cache until a hard refresh.
        const message = String(error?.message || error);
        if (message !== this._lastRenderError) {
          console.warn('Home Environment Manager card update will retry', error);
        }
        this._lastRenderError = message;
        this._lastState = null;
        this._shownControllerSignature = null;
        this._lastConfigKey = null;
        const notice = this._language()==='el'
          ? 'Προσωρινό πρόβλημα δεδομένων. Αυτόματη επαναφορά.'
          : this._language()==='de'
            ? 'Daten vorübergehend nicht verfügbar. Automatischer neuer Versuch.'
            : 'Data temporarily unavailable. Retrying automatically.';
        const card = this._hasValidRender && this.shadowRoot.querySelector?.('ha-card');
        if (card) {
          card.setAttribute('aria-busy','true');
          if (!card.querySelector?.('[data-card-recovery]')) {
            card.insertAdjacentHTML?.('afterbegin',
              '<div data-card-recovery role="status" style="padding:12px">'+
              escape(notice)+'</div>');
          }
        } else {
          this.shadowRoot.innerHTML = '<ha-card><div role="status" style="padding:20px">'+
            escape(notice)+'</div></ha-card>';
        }
      }
    }

    _renderContent(force = false) {
      const [entity, state] = this._state();
      const lang = this._language();
      const key = JSON.stringify(this._config);
      const controllerSignature = this._controllerSignature();
      if (!force && this._lastState === state && this._shownEntity === entity &&
          this._shownLanguage === lang && this._lastConfigKey === key &&
          this._shownControllerSignature === controllerSignature) return;
      const inline = state?.attributes?.dashboard;
      const data = inline?.version === 1 ? inline :
        this._dashboardEntity === entity ? this._dashboardData : null;
      if (!data || data.version !== 1) {
        this.shadowRoot.innerHTML = `${this._styles()}<ha-card class="shell" dir="${RTL_LANGUAGES.has(lang) ? 'rtl' : 'ltr'}"><div class="empty-state">
        ${this._icon('mdi:air-filter')}<h3>${escape(this._t('title'))}</h3><p>${escape(
          state?.attributes?.dashboard_api==='environment_manager/dashboard'
            ? (lang==='el' ? 'Φόρτωση δεδομένων δωματίων…'
               : lang==='de' ? 'Raumdaten werden geladen…'
               : 'Loading room data…')
            : this._t('missingCard'))}</p></div></ha-card>`;
        // Keep retrying when the recommended sensor is still starting:
        // HA may later supply the dashboard on the same card instance.
        this._lastState = null;
        this._hasValidRender = false;
        return;
      }
      const rooms = safeArray(data.rooms).filter((room)=>room &&
        typeof room==='object' && typeof room.area_id==='string').slice().sort((a,b) =>
        ({attention:0,unknown:1,safe:2}[a.status] ?? 3) - ({attention:0,unknown:1,safe:2}[b.status] ?? 3) ||
        String(a.name).localeCompare(String(b.name), this._hass.language));
      this.shadowRoot.innerHTML = `${this._styles()}<ha-card class="shell" dir="${RTL_LANGUAGES.has(lang) ? 'rtl' : 'ltr'}">
        <header class="card-heading"><div><div class="overline">HOME ASSISTANT</div>
        <h2>${escape(this._config.title || this._t('title'))}</h2><span>${escape(this._t('subtitle'))}</span></div>
        <div class="header-actions"><button class="edit-device" type="button" data-edit-home
          aria-label="${escape(this._deviceEditLabel(true))}" title="${escape(this._deviceEditLabel(true))}"
          ${this._homeDeviceId ? '' : 'disabled'}>${this._icon('mdi:cog-outline')}</button>
        <div class="card-logo">${this._icon('mdi:air-filter')}</div></div></header>
        <div class="content">
          ${this._outside(data.outdoor || {})}
          ${this._pollenIndicator(data.outdoor || {})}
          ${this._summary(data.summary || {})}
          <div class="rooms-list">${rooms.length ? rooms.map((room) => this._room(room)).join('')
            : `<div class="empty-rooms">${this._icon('mdi:home-outline')}${escape(this._t('noRooms'))}</div>`}</div>
          <footer>${this._icon('mdi:shield-check-outline')} ${escape(this._t('sourceData'))}</footer>
        </div>
      </ha-card>`;
      // Commit the cache only after the complete template was constructed
      // and applied. A failed render must be retried on the next HA update.
      this._shownControllerSignature = controllerSignature;
      this._lastState = state;
      this._shownEntity = entity;
      this._shownLanguage = lang;
      this._lastConfigKey = key;
      this._hasValidRender = true;
    }

    _styles() { return `<style>
      :host{display:block;--aqa-green:#1f9d77;--aqa-amber:#df9143;--aqa-red:#df6d55;--aqa-blue:#499bb9;
        --aqa-muted:var(--secondary-text-color,#78848f);--aqa-text:var(--primary-text-color,#1a313d);
        --aqa-surface:var(--card-background-color,#fff);--aqa-edge:var(--divider-color,rgba(110,135,145,.17));
        font-family:var(--paper-font-body1_-_font-family,Roboto,Arial,sans-serif);color:var(--aqa-text)}
      .shell{overflow:hidden;border-radius:22px;background:var(--aqa-surface);box-shadow:var(--ha-card-box-shadow,0 2px 16px rgba(0,0,0,.06))}
      .card-heading{display:flex;align-items:center;justify-content:space-between;gap:16px;padding:24px 26px 20px}
      .header-actions{display:flex;gap:8px;align-items:center}
      .edit-device{display:inline-grid;place-items:center;flex:0 0 auto;min-width:32px;height:32px;
        padding:5px;border:1px solid var(--aqa-edge);border-radius:10px;cursor:pointer;
        background:var(--aqa-surface);color:var(--aqa-blue)}
      .edit-device ha-icon{--mdc-icon-size:19px}
      .edit-device:disabled{opacity:.35;cursor:not-allowed}
      .edit-device:focus-visible{outline:2px solid var(--aqa-blue);outline-offset:2px}
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
      .rh-fallback{display:flex;align-items:flex-start;gap:7px;margin:10px 0;
        padding:9px 10px;border-radius:10px;font-size:11px;line-height:1.4;
        border:1px solid color-mix(in srgb,var(--aqa-blue),transparent 70%);
        background:color-mix(in srgb,var(--aqa-blue),transparent 93%)}
      .rh-fallback ha-icon{flex:0 0 auto;--mdc-icon-size:16px;color:var(--aqa-blue)}
      .rh-fallback b{font-weight:700}
      .mold-warnings{display:grid;gap:6px;margin:11px 0;padding:10px;border-radius:10px;
        background:color-mix(in srgb,var(--aqa-amber),transparent 91%);
        border:1px solid color-mix(in srgb,var(--aqa-amber),transparent 72%)}
      .mold-warning{display:flex;align-items:flex-start;gap:7px;color:var(--aqa-text);font-size:11px;line-height:1.4}
      .mold-warning ha-icon{flex:0 0 auto;--mdc-icon-size:15px;color:var(--aqa-amber)}
      .mold-warning small{color:var(--aqa-muted)}
      .metric-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,125px),1fr));gap:9px}
      .pollen-indicator{display:flex;align-items:center;gap:7px;margin:12px 0;color:var(--aqa-text);padding:8px 12px;border:1px solid var(--aqa-edge);border-radius:11px;font-size:11px;background:color-mix(in srgb,var(--aqa-amber),transparent 96%)}
      .pollen-indicator ha-icon{color:var(--aqa-amber);--mdc-icon-size:18px}
      .pid-panel{border:1px solid var(--aqa-edge);border-radius:12px;padding:11px;margin:10px 0;background:color-mix(in srgb,var(--aqa-blue),transparent 94%)}
      .pid-title{display:flex;flex-wrap:wrap;align-items:center;gap:7px;font-size:12px}
      .pid-title span{margin-inline-start:auto;color:var(--aqa-muted);font-size:11px}
      .pid-metrics{display:flex;flex-wrap:wrap;gap:7px 14px;margin:8px 0;font-size:11px}
      .pid-panel small{font-size:10px;line-height:1.4;color:var(--aqa-muted);display:block}
      .pid-button{padding:6px 10px;border:1px solid var(--aqa-edge);background:var(--aqa-surface);color:var(--aqa-text);border-radius:8px;cursor:pointer;margin-top:9px}
      .pid-button:focus-visible{outline:2px solid var(--aqa-blue)}
      .managed-controllers{display:grid;gap:9px;margin-top:12px;border-top:1px solid var(--aqa-edge);padding-top:10px}
      .managed-controllers>strong{font-size:11px}
      .managed-controller{padding:9px;border:1px solid var(--aqa-edge);border-radius:11px;
        background:var(--aqa-surface);min-width:0}
      .climate-entity-link{display:flex;align-items:center;gap:6px;max-width:100%;cursor:pointer;
        border:0;background:transparent;color:var(--aqa-text);padding:3px;font-size:11px;text-align:start}
      .climate-entity-link strong{overflow-wrap:anywhere}
      .climate-entity-link ha-icon{--mdc-icon-size:16px;color:var(--aqa-blue);flex:0 0 auto}
      .managed-status{font-size:10px;color:var(--aqa-muted);margin:5px 0 9px;overflow-wrap:anywhere}
      .managed-method-label,.climate-target-editor label{display:grid;gap:5px;font-size:10px}
      .managed-method-label select,.climate-target-editor input{border:1px solid var(--aqa-edge);
        border-radius:8px;background:var(--aqa-surface);color:var(--aqa-text);padding:7px;
        font:inherit;max-width:100%;min-width:0}
      .climate-target-editor{display:flex;align-items:end;gap:8px;flex-wrap:wrap;margin-top:9px}
      .climate-target-editor label{flex:1 1 120px}
      .climate-target-editor button{padding:7px 9px;border:1px solid var(--aqa-blue);border-radius:8px;
        background:var(--aqa-surface);color:var(--aqa-blue);cursor:pointer;font-size:10px}
      .climate-edit-error{color:var(--aqa-red)!important}
      .science-section{margin:10px 0 12px;padding:11px 12px;border:1px solid var(--aqa-edge);border-radius:12px;background:color-mix(in srgb,var(--aqa-blue),transparent 97%)}
      .science-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:6px 12px;margin-top:8px}
      .science-line{display:flex;align-items:center;justify-content:space-between;gap:8px;font-size:11px;border-bottom:1px solid var(--aqa-edge);padding:5px 0}
      .science-line span{color:var(--aqa-muted);line-height:1.3}.science-line strong{font-size:12px;text-align:end;white-space:nowrap}
      .science-caveat{color:var(--aqa-muted);font-size:10px;line-height:1.3;margin-top:8px}
      .metric{border-radius:11px;background:color-mix(in srgb,var(--aqa-muted),transparent 96%);border:1px solid var(--aqa-edge);padding:10px;min-width:0}
      .metric-attention{border-color:color-mix(in srgb,var(--aqa-amber),transparent 66%)}
      .metric-line{display:flex;align-items:flex-start;gap:7px;justify-content:space-between;flex-wrap:wrap}
      .metric-name{font-size:10px;color:var(--aqa-muted);display:inline-flex;align-items:center;gap:3px;font-weight:700}
      .metric-name ha-icon{--mdc-icon-size:15px}
      .metric-help{display:inline-flex;position:relative;align-items:center}
      .metric-help summary{display:flex;align-items:center;cursor:pointer;list-style:none;color:var(--primary-color,#03a9f4);padding:2px}
      .metric-help summary::-webkit-details-marker{display:none}
      .metric-help-content{position:absolute;z-index:25;top:100%;left:-30px;width:min(280px,72vw);padding:12px;border-radius:12px;box-shadow:0 6px 24px #0006;background:var(--card-background-color,#20252b);color:var(--primary-text-color,#fff);font-size:12px;line-height:1.5;font-weight:400;white-space:normal}
      .metric-help[open] summary{color:var(--accent-color,#00bcd4)}

      .metric-number{font-size:15px;font-weight:760;white-space:nowrap;line-height:1.2}
      .metric-number small{font-size:9px;color:var(--aqa-muted);font-weight:500}
      .meter{position:relative;display:block;height:6px;border-radius:99px;margin-top:11px;background:color-mix(in srgb,var(--aqa-muted),transparent 80%);overflow:hidden}
      .meter-fill{height:100%;display:block;background:var(--aqa-green);border-radius:99px;transition:width .35s ease}
      .metric-attention .meter-fill{background:var(--aqa-amber)}
      .meter-limit{position:absolute;right:1px;top:0;height:100%;width:1px;background:var(--aqa-text);opacity:.24}
      .metric-limit{color:var(--aqa-muted);font-size:9px;line-height:1.3;margin-top:5px}
      .mold-summary{display:grid;gap:3px;margin-top:7px;color:var(--aqa-muted);
        font-size:9px;line-height:1.4;overflow-wrap:anywhere}
      .mold-calibration-details{display:grid;gap:7px;margin-top:9px;padding:10px;
        border:1px solid var(--aqa-edge);border-radius:10px;
        background:color-mix(in srgb,var(--aqa-muted),transparent 96%);font-size:11px}
      .mold-calibration-details>div{display:flex;align-items:baseline;
        justify-content:space-between;gap:10px;flex-wrap:wrap}
      .mold-calibration-details span{color:var(--aqa-muted)}
      .mold-calibration-details strong{font-weight:700;color:var(--aqa-text);
        overflow-wrap:anywhere;word-break:break-word}
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
      const t = (key) => key === "title" ? BRAND_TITLE : (texts[key] || LANGUAGE.en[key]);
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
        <label class="tick"><input type="checkbox" data-setting="show_metrics" ${this._config.show_metrics!==false?'checked':''}>${escape(t('readings'))}</label>
        <label class="tick"><input type="checkbox" data-setting="show_science" ${this._config.show_science!==false?'checked':''}>${escape(SCIENCE_LABELS[lang]?.title || SCIENCE_LABELS.en.title)}</label>`;
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
  // New brand alias; old Lovelace YAML configurations keep working unmodified.
  if (!customElements.get('home-environment-manager-card')) {
    customElements.define('home-environment-manager-card', class extends AirQualityAdvisorCard {});
  }
  if (!customElements.get('home-environment-manager-card-editor')) {
    customElements.define('home-environment-manager-card-editor', class extends AirQualityAdvisorCardEditor {});
  }
  customElements.get('home-environment-manager-card').getConfigElement =
    () => document.createElement('home-environment-manager-card-editor');
  AirQualityAdvisorCard.getConfigElement = () => document.createElement('air-quality-advisor-card-editor');
  window.customCards = window.customCards || [];
  if (!window.customCards.some((card) => card.type === 'air-quality-advisor-card')) {
    window.customCards.push({
      type:'air-quality-advisor-card',
      name:BRAND_TITLE,
      description:'Evidence-grounded room environment, air quality, thermal comfort, ventilation and climate advice. PID control is planned.',
      preview:true,
      documentationURL:'https://github.com/Chreece/HA-Air-Quality-Advisor',
      getEntitySuggestion: (hass,entityId) =>
        (hass.states[entityId]?.attributes?.dashboard?.version === 1 ||
         hass.states[entityId]?.attributes?.dashboard_api === 'environment_manager/dashboard')
          ? {config:{type:'custom:air-quality-advisor-card',entity:entityId}}
          : null
    });
  }
  if (!window.customCards.some((card) => card.type === 'home-environment-manager-card')) {
    window.customCards.push({
      type:'home-environment-manager-card',
      name:BRAND_TITLE,
      description:'Indoor air, moisture, thermal comfort, exposure and climate guidance.',
      preview:true,
      documentationURL:'https://github.com/Chreece/HA-Air-Quality-Advisor',
      getEntitySuggestion:(hass,entityId) =>
        (hass.states[entityId]?.attributes?.dashboard?.version === 1 ||
         hass.states[entityId]?.attributes?.dashboard_api === 'environment_manager/dashboard')
          ? {config:{type:'custom:home-environment-manager-card',entity:entityId}}
          : null
    });
  }
})();
