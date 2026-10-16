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
      metric_voc:'TVOC', metric_voc_parts:'VOC', metric_humidity:'Humidity',
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
      metric_humidity:'Luftfeuchtigkeit',wx_sunny:'Sonnig',wx_clearNight:'Klare Nacht',
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
      metric_humidity:'Υγρασία',wx_sunny:'Ηλιοφάνεια',wx_clearNight:'Ξαστεριά',
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
      noAttention:'Tout semble bon',metric_humidity:'Humidité',wx_sunny:'Ensoleillé',
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
      noAttention:'Todo parece correcto',metric_humidity:'Humedad',wx_sunny:'Soleado',
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
    pm10:'mdi:blur', voc:'mdi:flask-outline', voc_parts:'mdi:flask-outline', humidity:'mdi:water-percent' };
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
      const requested = String(this._hass?.language || 'en').replace('_','-').toLowerCase();
      const root = requested.split('-')[0];
      return [requested, root].find((key) => LANGUAGE[key]) || 'en';
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

    _metricName(metric) { return this._t(`metric_${metric}`); }

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
      return `<div class="metric ${miniature ? 'tiny' : ''} metric-${level}">
        <div class="metric-line">
          <span class="metric-name">${this._icon(METRIC_ICON[item.metric] || 'mdi:gauge')} ${escape(metric)}</span>
          <span class="metric-number">${escape(display)} <small>${escape(unit)}</small></span>
        </div>
        ${hasLimit ? `<div class="meter" role="progressbar" aria-label="${escape(metric)}"
          aria-valuemin="0" aria-valuemax="${escape(limit)}" aria-valuenow="${available ? escape(item.value) : '0'}">
          <span class="meter-fill" style="width:${pct.toFixed(2)}%"></span><span class="meter-limit"></span>
        </div><div class="metric-limit">${threshold}</div>`
          : `<div class="metric-limit">${available ? '' : escape(this._t('missing'))}</div>`}
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
      const subheading = room.high_count > 0 ? this._t('indoorHigh')
        : status === 'unknown' ? this._t('missingIndoor')
          : this._t('allOkay');
      return `<article class="room room-${status}">
        <div class="room-heading">
          <div class="room-icon">${this._icon(status === 'safe' ? 'mdi:home-check-outline' : status === 'attention' ? 'mdi:home-alert-outline' : 'mdi:home-question-outline')}</div>
          <div class="room-main"><h3>${escape(room.name)}</h3><span>${escape(subheading)}</span></div>
          <span class="status-tag">${this._icon(ICON[status])}${escape(this._t(status))}</span>
        </div>
        ${this._config.show_metrics === false ? '' : readings.length ? `<div class="metric-grid">${shown.map((item) => this._metric(item)).join('')}</div>`
          : `<div class="empty-measurements">${this._icon('mdi:gauge-empty')} ${escape(this._t('missingIndoor'))}</div>`}
        ${button}
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
        this.shadowRoot.innerHTML = `${this._styles()}<ha-card class="shell"><div class="empty-state">
        ${this._icon('mdi:air-filter')}<h3>${escape(this._t('title'))}</h3><p>${escape(this._t('missingCard'))}</p></div></ha-card>`;
        return;
      }
      const rooms = safeArray(data.rooms).slice().sort((a,b) =>
        ({attention:0,unknown:1,safe:2}[a.status] ?? 3) - ({attention:0,unknown:1,safe:2}[b.status] ?? 3) ||
        String(a.name).localeCompare(String(b.name), this._hass.language));
      this.shadowRoot.innerHTML = `${this._styles()}<ha-card class="shell">
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
      const lang = String(this._hass.language || 'en').split(/[-_]/)[0];
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
        <label>Title<input data-setting="title" type="text" value="${escape(this._config.title || '')}" /></label>
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
