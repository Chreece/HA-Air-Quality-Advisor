"""Localized rooms-first setup, applied after all existing translation passes."""
from __future__ import annotations
from copy import deepcopy
import json
from pathlib import Path

# Room selector title; windows; air/environment; pressure; room help; general help.
TEXT = {
'en': ('Rooms to monitor', 'Windows', 'Air quality and environmental sensors', 'Pressure sensors', 'Select inputs for this room. Each choice shows device name — entity name. Empty groups stay unused; they never enable automatic discovery or equipment control.', 'Select shared input sources and notification outputs. Save finishes setup. Operating settings remain on the Home and room devices.'),
'el': ('Χώροι για παρακολούθηση', 'Παράθυρα', 'Αισθητήρες ποιότητας αέρα και περιβάλλοντος', 'Αισθητήρες πίεσης', 'Επίλεξε τις εισόδους του χώρου. Κάθε επιλογή δείχνει όνομα συσκευής — όνομα οντότητας. Οι κενές ομάδες δεν χρησιμοποιούνται και δεν ενεργοποιούν αυτόματη ανακάλυψη ή έλεγχο εξοπλισμού.', 'Επίλεξε κοινές πηγές δεδομένων και εξόδους ειδοποιήσεων. Η αποθήκευση ολοκληρώνει τη ρύθμιση. Οι παράμετροι λειτουργίας βρίσκονται στις συσκευές του σπιτιού και των χώρων.'),
'de': ('Zu überwachende Räume', 'Fenster', 'Luftqualitäts- und Umgebungssensoren', 'Drucksensoren', 'Eingänge für diesen Raum auswählen. Jede Auswahl zeigt Gerätename — Entitätsname. Leere Gruppen bleiben ungenutzt; sie aktivieren weder automatische Erkennung noch Gerätesteuerung.', 'Gemeinsame Datenquellen und Benachrichtigungsausgänge auswählen. Speichern beendet die Einrichtung. Betriebsparameter bleiben auf den Haus- und Raumgeräten.'),
'fr': ('Pièces à surveiller', 'Fenêtres', 'Capteurs de qualité de l’air et d’environnement', 'Capteurs de pression', 'Sélectionnez les entrées de cette pièce : nom de l’appareil — nom de l’entité. Les groupes vides restent inutilisés et n’activent ni découverte automatique ni commande.', 'Sélectionnez les sources communes et les sorties de notification. Enregistrer termine la configuration. Les réglages de fonctionnement restent sur les appareils de la maison et des pièces.'),
'es': ('Estancias que supervisar', 'Ventanas', 'Sensores de calidad del aire y del entorno', 'Sensores de presión', 'Selecciona las entradas de esta estancia: nombre del dispositivo — nombre de la entidad. Los grupos vacíos no se usan ni activan descubrimiento o control automático.', 'Selecciona fuentes compartidas y salidas de notificación. Guardar termina la configuración. Los ajustes de funcionamiento quedan en los dispositivos de la casa y las estancias.'),
'it': ('Stanze da monitorare', 'Finestre', 'Sensori della qualità dell’aria e ambientali', 'Sensori di pressione', 'Seleziona gli ingressi della stanza: nome dispositivo — nome entità. I gruppi vuoti non vengono usati e non attivano rilevamento o controllo automatico.', 'Seleziona fonti condivise e uscite di notifica. Salva completa la configurazione. Le impostazioni operative restano sui dispositivi della casa e delle stanze.'),
'nl': ('Te bewaken kamers', 'Ramen', 'Luchtkwaliteits- en omgevingssensoren', 'Druksensoren', 'Selecteer ingangen voor deze kamer: apparaatnaam — entiteitsnaam. Lege groepen blijven ongebruikt en activeren geen automatische detectie of bediening.', 'Selecteer gedeelde bronnen en meldingsuitgangen. Opslaan voltooit de installatie. Bedrijfsinstellingen blijven op de huis- en kamerapparaten.'),
'pt': ('Divisões a monitorizar', 'Janelas', 'Sensores de qualidade do ar e do ambiente', 'Sensores de pressão', 'Selecione entradas da divisão: nome do dispositivo — nome da entidade. Grupos vazios não são usados e não ativam descoberta nem controlo automático.', 'Selecione fontes partilhadas e saídas de notificação. Guardar conclui a configuração. Os parâmetros de operação ficam nos dispositivos da casa e das divisões.'),
'pt-BR': ('Ambientes para monitorar', 'Janelas', 'Sensores de qualidade do ar e do ambiente', 'Sensores de pressão', 'Selecione entradas do ambiente: nome do dispositivo — nome da entidade. Grupos vazios não são usados e não ativam descoberta nem controle automático.', 'Selecione fontes compartilhadas e saídas de notificação. Salvar conclui a configuração. Os parâmetros de operação ficam nos dispositivos da casa e dos ambientes.'),
'pl': ('Pomieszczenia do monitorowania', 'Okna', 'Czujniki jakości powietrza i otoczenia', 'Czujniki ciśnienia', 'Wybierz wejścia pomieszczenia: nazwa urządzenia — nazwa encji. Puste grupy pozostają nieużywane i nie włączają automatycznego wykrywania ani sterowania.', 'Wybierz wspólne źródła i wyjścia powiadomień. Zapis kończy konfigurację. Ustawienia pracy pozostają na urządzeniach domu i pomieszczeń.'),
'cs': ('Sledované místnosti', 'Okna', 'Snímače kvality vzduchu a prostředí', 'Snímače tlaku', 'Vyberte vstupy místnosti: název zařízení — název entity. Prázdné skupiny se nepoužívají a nezapínají automatické vyhledávání ani řízení.', 'Vyberte společné zdroje a výstupy oznámení. Uložení dokončí nastavení. Provozní nastavení zůstává na zařízeních domu a místností.'),
'sk': ('Monitorované miestnosti', 'Okná', 'Snímače kvality vzduchu a prostredia', 'Snímače tlaku', 'Vyberte vstupy miestnosti: názov zariadenia — názov entity. Prázdne skupiny sa nepoužívajú a nezapínajú automatické vyhľadávanie ani riadenie.', 'Vyberte spoločné zdroje a výstupy oznámení. Uloženie dokončí nastavenie. Prevádzkové nastavenia zostávajú na zariadeniach domu a miestností.'),
'sv': ('Rum att övervaka', 'Fönster', 'Luftkvalitets- och miljösensorer', 'Trycksensorer', 'Välj rummets ingångar: enhetsnamn — entitetsnamn. Tomma grupper används inte och aktiverar varken automatisk upptäckt eller styrning.', 'Välj gemensamma källor och aviseringsutgångar. Spara slutför inställningen. Driftinställningarna finns kvar på husets och rummens enheter.'),
'da': ('Rum der skal overvåges', 'Vinduer', 'Luftkvalitets- og miljøsensorer', 'Tryksensorer', 'Vælg rummets indgange: enhedsnavn — entitetsnavn. Tomme grupper bruges ikke og aktiverer ikke automatisk registrering eller styring.', 'Vælg fælles kilder og notifikationsudgange. Gem afslutter opsætningen. Driftsindstillinger forbliver på husets og rummenes enheder.'),
'nb': ('Rom som skal overvåkes', 'Vinduer', 'Luftkvalitets- og miljøsensorer', 'Trykksensorer', 'Velg rommets innganger: enhetsnavn — entitetsnavn. Tomme grupper brukes ikke og aktiverer ikke automatisk oppdagelse eller styring.', 'Velg felles kilder og varslingsutganger. Lagre fullfører oppsettet. Driftsinnstillingene blir på husets og rommenes enheter.'),
'fi': ('Valvottavat huoneet', 'Ikkunat', 'Ilmanlaatu- ja ympäristöanturit', 'Paineanturit', 'Valitse huoneen tulot: laitteen nimi — entiteetin nimi. Tyhjät ryhmät jäävät käyttämättä eivätkä käynnistä automaattista tunnistusta tai ohjausta.', 'Valitse yhteiset lähteet ja ilmoitusten lähdöt. Tallennus päättää määrityksen. Käyttöasetukset jäävät kodin ja huoneiden laitteisiin.'),
'hu': ('Figyelendő helyiségek', 'Ablakok', 'Levegőminőség- és környezeti érzékelők', 'Nyomásérzékelők', 'Válaszd ki a helyiség bemeneteit: eszköznév — entitásnév. Az üres csoportok nem használtak, és nem indítanak automatikus felismerést vagy vezérlést.', 'Válassz közös forrásokat és értesítési kimeneteket. A mentés befejezi a beállítást. Az üzemi beállítások a ház és a helyiségek eszközein maradnak.'),
'ro': ('Camere de monitorizat', 'Ferestre', 'Senzori de calitate a aerului și de mediu', 'Senzori de presiune', 'Selectează intrările camerei: numele dispozitivului — numele entității. Grupurile goale rămân neutilizate și nu activează descoperirea sau controlul automat.', 'Selectează sursele comune și ieșirile de notificare. Salvarea încheie configurarea. Setările de funcționare rămân pe dispozitivele casei și camerelor.'),
'bg': ('Стаи за наблюдение', 'Прозорци', 'Датчици за качество на въздуха и средата', 'Датчици за налягане', 'Изберете входовете на стаята: име на устройство — име на обект. Празните групи не се използват и не включват автоматично откриване или управление.', 'Изберете общи източници и изходи за известия. Записването завършва настройката. Работните настройки остават на устройствата на дома и стаите.'),
'hr': ('Sobe za praćenje', 'Prozori', 'Senzori kvalitete zraka i okoliša', 'Senzori tlaka', 'Odaberite ulaze sobe: naziv uređaja — naziv entiteta. Prazne se grupe ne koriste i ne uključuju automatsko otkrivanje ni upravljanje.', 'Odaberite zajedničke izvore i izlaze obavijesti. Spremanje završava postavljanje. Radne postavke ostaju na uređajima doma i soba.'),
'sr': ('Собе за праћење', 'Прозори', 'Сензори квалитета ваздуха и околине', 'Сензори притиска', 'Изаберите улазе собе: назив уређаја — назив ентитета. Празне групе се не користе и не укључују аутоматско откривање ни управљање.', 'Изаберите заједничке изворе и излазе обавештења. Чување завршава подешавање. Радна подешавања остају на уређајима дома и соба.'),
'ru': ('Комнаты для наблюдения', 'Окна', 'Датчики качества воздуха и среды', 'Датчики давления', 'Выберите входы комнаты: имя устройства — имя сущности. Пустые группы не используются и не включают автоматическое обнаружение или управление.', 'Выберите общие источники и выходы уведомлений. Сохранение завершает настройку. Рабочие параметры остаются на устройствах дома и комнат.'),
'uk': ('Кімнати для спостереження', 'Вікна', 'Датчики якості повітря й середовища', 'Датчики тиску', 'Виберіть входи кімнати: назва пристрою — назва сутності. Порожні групи не використовуються і не вмикають автоматичне виявлення або керування.', 'Виберіть спільні джерела й виходи сповіщень. Збереження завершує налаштування. Робочі параметри залишаються на пристроях дому й кімнат.'),
 'tr': ('İzlenecek odalar', 'Pencereler', 'Hava kalitesi ve çevre sensörleri', 'Basınç sensörleri', 'Odanın girişlerini seçin: cihaz adı — varlık adı. Boş gruplar kullanılmaz ve otomatik keşif veya kontrolü etkinleştirmez.', 'Ortak kaynakları ve bildirim çıkışlarını seçin. Kaydet kurulumu tamamlar. Çalışma ayarları ev ve oda cihazlarında kalır.'),
'ar': ('الغرف المراد مراقبتها', 'النوافذ', 'مستشعرات جودة الهواء والبيئة', 'مستشعرات الضغط', 'اختر مدخلات الغرفة: اسم الجهاز — اسم الكيان. المجموعات الفارغة لا تستخدم ولا تفعّل الاكتشاف أو التحكم التلقائي.', 'اختر المصادر المشتركة ومخرجات الإشعارات. الحفظ ينهي الإعداد. تبقى إعدادات التشغيل على أجهزة المنزل والغرف.'),
'he': ('חדרים למעקב', 'חלונות', 'חיישני איכות אוויר וסביבה', 'חיישני לחץ', 'בחר את קלטי החדר: שם המכשיר — שם הישות. קבוצות ריקות אינן בשימוש ולא מפעילות גילוי או בקרה אוטומטיים.', 'בחר מקורות משותפים ופלטי התראות. שמירה מסיימת את ההגדרה. הגדרות התפעול נשארות במכשירי הבית והחדרים.'),
'fa': ('اتاق‌های مورد پایش', 'پنجره‌ها', 'حسگرهای کیفیت هوا و محیط', 'حسگرهای فشار', 'ورودی‌های اتاق را انتخاب کنید: نام دستگاه — نام موجودیت. گروه‌های خالی استفاده نمی‌شوند و کشف یا کنترل خودکار را فعال نمی‌کنند.', 'منابع مشترک و خروجی‌های اعلان را انتخاب کنید. ذخیره، راه‌اندازی را تمام می‌کند. تنظیمات کارکرد روی دستگاه‌های خانه و اتاق‌ها می‌مانند.'),
'hi': ('निगरानी के कमरे', 'खिड़कियाँ', 'वायु गुणवत्ता और पर्यावरण सेंसर', 'दबाव सेंसर', 'कमरे के इनपुट चुनें: उपकरण का नाम — एंटिटी का नाम। खाली समूह उपयोग नहीं होते और स्वचालित खोज या नियंत्रण चालू नहीं करते।', 'साझा स्रोत और सूचना आउटपुट चुनें। सहेजना सेटअप पूरा करता है। संचालन सेटिंग घर और कमरे के उपकरणों पर रहती हैं।'),
'bn': ('পর্যবেক্ষণের ঘর', 'জানালা', 'বায়ুর গুণমান ও পরিবেশের সেন্সর', 'চাপের সেন্সর', 'ঘরের ইনপুট বেছে নিন: ডিভাইসের নাম — এনটিটির নাম। খালি গোষ্ঠী ব্যবহার হয় না এবং স্বয়ংক্রিয় খোঁজ বা নিয়ন্ত্রণ চালু করে না।', 'যৌথ উৎস ও বিজ্ঞপ্তির আউটপুট বেছে নিন। সংরক্ষণ করলে সেটআপ শেষ হয়। চালনার সেটিং বাড়ি ও ঘরের ডিভাইসে থাকে।'),
 'ta': ('கண்காணிக்க வேண்டிய அறைகள்', 'சாளரங்கள்', 'காற்றுத் தரம் மற்றும் சுற்றுச்சூழல் உணரிகள்', 'அழுத்த உணரிகள்', 'அறையின் உள்ளீடுகளைத் தேர்ந்தெடுக்கவும்: சாதனப் பெயர் — உருப்படிப் பெயர். காலிக் குழுக்கள் பயன்படுத்தப்படாது; தானியங்கிக் கண்டறிதலையோ கட்டுப்பாட்டையோ இயக்காது.', 'பொதுவான மூலங்களையும் அறிவிப்பு வெளியீடுகளையும் தேர்ந்தெடுக்கவும். சேமித்தல் அமைப்பை முடிக்கிறது. இயக்க அமைப்புகள் வீடு மற்றும் அறைச் சாதனங்களில் இருக்கும்.'),
'ur': ('نگرانی کے کمرے', 'کھڑکیاں', 'ہوا کے معیار اور ماحول کے سینسر', 'دباؤ کے سینسر', 'کمرے کے ان پٹ منتخب کریں: آلے کا نام — اینٹیٹی کا نام۔ خالی گروپ استعمال نہیں ہوتے اور خودکار تلاش یا کنٹرول فعال نہیں کرتے۔', 'مشترکہ ذرائع اور اطلاع کے آؤٹ پٹ منتخب کریں۔ محفوظ کرنے سے سیٹ اپ مکمل ہوتا ہے۔ عملی ترتیبات گھر اور کمرے کے آلات پر رہتی ہیں۔'),
'id': ('Ruangan untuk dipantau', 'Jendela', 'Sensor kualitas udara dan lingkungan', 'Sensor tekanan', 'Pilih masukan ruangan: nama perangkat — nama entitas. Kelompok kosong tidak digunakan dan tidak mengaktifkan penemuan atau kendali otomatis.', 'Pilih sumber bersama dan keluaran notifikasi. Simpan menyelesaikan penyiapan. Pengaturan operasi tetap berada pada perangkat rumah dan ruangan.'),
'vi': ('Phòng cần giám sát', 'Cửa sổ', 'Cảm biến chất lượng không khí và môi trường', 'Cảm biến áp suất', 'Chọn đầu vào của phòng: tên thiết bị — tên thực thể. Nhóm trống không được dùng và không bật khám phá hoặc điều khiển tự động.', 'Chọn nguồn chung và đầu ra thông báo. Lưu hoàn tất thiết lập. Cài đặt vận hành nằm trên thiết bị của nhà và phòng.'),
'ko': ('모니터링할 방', '창문', '공기질 및 환경 센서', '압력 센서', '방의 입력을 선택하세요. 기기 이름 — 엔티티 이름으로 표시됩니다. 빈 그룹은 사용하지 않으며 자동 검색이나 제어를 켜지 않습니다.', '공유 소스와 알림 출력을 선택하세요. 저장하면 설정이 끝납니다. 운전 설정은 집과 방의 기기에 남습니다.'),
'ja': ('監視する部屋', '窓', '空気質・環境センサー', '気圧センサー', '部屋の入力を選択します。機器名 — エンティティ名で表示されます。空のグループは使用されず、自動検出や自動制御を有効にしません。', '共通の入力源と通知出力を選択します。保存すると設定が完了します。運転設定は家と部屋のデバイスに残ります。'),
'zh-Hans': ('要监测的房间', '窗户', '空气质量与环境传感器', '压力传感器', '选择房间的输入，显示为设备名称 — 实体名称。空组不使用，也不会启用自动发现或控制。', '选择共享输入源和通知输出。保存即完成设置。运行参数保留在家庭和房间设备上。'),
'zh-Hant': ('要監測的房間', '窗戶', '空氣品質與環境感測器', '壓力感測器', '選擇房間的輸入，顯示為裝置名稱 — 實體名稱。空群組不使用，也不會啟用自動探索或控制。', '選擇共用輸入源和通知輸出。儲存即完成設定。運作參數保留在家庭和房間裝置上。'),
 'th': ('ห้องที่จะตรวจสอบ', 'หน้าต่าง', 'เซ็นเซอร์คุณภาพอากาศและสิ่งแวดล้อม', 'เซ็นเซอร์ความดัน', 'เลือกอินพุตของห้อง โดยแสดงชื่ออุปกรณ์ — ชื่อเอนทิตี กลุ่มว่างจะไม่ใช้และไม่เปิดการค้นหาหรือควบคุมอัตโนมัติ', 'เลือกแหล่งข้อมูลร่วมและเอาต์พุตการแจ้งเตือน บันทึกเพื่อจบการตั้งค่า การตั้งค่าการทำงานยังอยู่บนอุปกรณ์ของบ้านและห้อง'),
}


def apply_document(doc: dict, lang: str, words: dict) -> None:
    rooms, windows, air, pressure, help_text, general_help = TEXT[lang]
    labels = {"windows": windows, "air_quality": air, "temperature": words['temperature'],
              "humidity": words['humidity'], "pressure": pressure, "climate_devices": words['devices']}
    for scope in ('config', 'options'):
        target = doc.setdefault(scope, {})
        steps = target.setdefault('step', {})
        # All general source labels/help already have independently maintained
        # native translations. Reuse them without a second divergent vocabulary.
        general_data, general_details = {}, {}
        for name in ('weather', 'outdoor', 'general_settings', 'pollen', 'delivery', 'areas'):
            block = doc.get('options', {}).get('step', {}).get(name, {})
            block = {**block, **steps.get(name, {})}
            general_data.update(block.get('data', {}))
            general_details.update(block.get('data_description', {}))
        keys = ('weather_entities', 'outdoor_sensors', 'weather_warnings', 'general_room_occupancy_sensors',
                'general_home_trackers', 'general_occupied_rooms_entity', 'general_occupied_rooms_attribute',
                'general_sleep_rooms_entity', 'general_sleep_rooms_attribute', 'pollen_entity', 'notify_entities',
                'media_players', 'tts_engine', 'ai_conversation_agent', 'language', 'use_mold_indicator')
        steps['setup_rooms'] = {'title': rooms, 'description': f"{rooms} → {words['source']} → {words['general']} {words['settings']}",
            'data': {'areas': rooms}, 'data_description': {'areas': rooms + '. ' + help_text}}
        steps['setup_room_sources'] = {'title': words['room'] + ' · {area_name} · {room_index}/{room_count}',
            'description': help_text, 'data': labels,
            'data_description': {k: f"{v}. {help_text}" for k, v in labels.items()}}
        steps['setup_general'] = {'title': f"{words['general']} {words['settings']}", 'description': general_help,
            'data': {k: general_data[k] for k in keys},
            'data_description': {k: general_details.get(k, general_help) for k in keys}}
        target.setdefault('error', {}).update(
            invalid_setup_rooms=f"{words['invalid']}: {rooms}",
            invalid_room_source=f"{words['invalid']}: {words['room']} · {words['source']}")
        target.setdefault('abort', {}).update(
            setup_area_removed=f"{words['invalid']}: {rooms}",
            setup_changed=f"{words['settings']} ↻ {rooms}")


def apply_room_setup_i18n(root: Path) -> None:
    vocab = json.loads((root / 'compact_locales.json').read_text(encoding='utf-8'))
    files = sorted((root / 'translations').glob('*.json'))
    if set(TEXT) != set(vocab) or set(TEXT) != {p.stem for p in files}:
        raise ValueError('Every supported setup language must be supplied')
    for path in [root / 'strings.json', *files]:
        lang = 'en' if path.name == 'strings.json' else path.stem
        doc = json.loads(path.read_text(encoding='utf-8'))
        apply_document(doc, lang, vocab[lang])
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
