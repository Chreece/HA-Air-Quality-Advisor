"""Native room-subentry labels; the room group's devices own its settings."""
from __future__ import annotations

import json
from pathlib import Path

# Heading and actionable help for every supported frontend locale.
ROOM_TEXT = {
    "en": ("Room hub", "Select a Home Assistant area. Its group contains general room settings and one controller device per selected physical device. Adding a room does not enable automatic equipment control."),
    "el": ("Κόμβος δωματίου", "Επίλεξε έναν χώρο του Home Assistant. Η ομάδα του περιέχει τις γενικές ρυθμίσεις χώρου και μία συσκευή ελεγκτή ανά επιλεγμένη φυσική συσκευή. Η προσθήκη δωματίου δεν ενεργοποιεί τον αυτόματο έλεγχο εξοπλισμού."),
    "de": ("Raum-Hub", "Wähle einen Home-Assistant-Bereich. Seine Gruppe enthält allgemeine Raumeinstellungen und ein Steuergerät pro ausgewähltem physischem Gerät. Das Hinzufügen eines Raums aktiviert keine automatische Gerätesteuerung."),
    "fr": ("Concentrateur de pièce", "Sélectionnez une zone Home Assistant. Son groupe contient les réglages généraux de la pièce et un contrôleur par appareil physique sélectionné. Ajouter une pièce n'active pas la commande automatique des appareils."),
    "es": ("Centro de habitación", "Selecciona un área de Home Assistant. Su grupo contiene los ajustes generales de la habitación y un controlador por dispositivo físico seleccionado. Añadir una habitación no activa el control automático de equipos."),
    "it": ("Hub della stanza", "Seleziona un'area di Home Assistant. Il gruppo contiene le impostazioni generali della stanza e un controllore per ogni dispositivo fisico selezionato. Aggiungere una stanza non attiva il controllo automatico degli apparecchi."),
    "nl": ("Ruimtehub", "Selecteer een Home Assistant-ruimte. De groep bevat algemene ruimte-instellingen en één regelaar per geselecteerd fysiek apparaat. Een ruimte toevoegen schakelt geen automatische apparaatbesturing in."),
    "pt": ("Central da divisão", "Selecione uma área do Home Assistant. O grupo contém as definições gerais da divisão e um controlador por dispositivo físico selecionado. Adicionar uma divisão não ativa o controlo automático dos equipamentos."),
    "pt-BR": ("Central do ambiente", "Selecione uma área do Home Assistant. O grupo contém as configurações gerais do ambiente e um controlador por dispositivo físico selecionado. Adicionar um ambiente não ativa o controle automático dos equipamentos."),
    "pl": ("Centrala pomieszczenia", "Wybierz obszar Home Assistant. Grupa zawiera ogólne ustawienia pomieszczenia i jeden sterownik na wybrane urządzenie fizyczne. Dodanie pomieszczenia nie włącza automatycznego sterowania urządzeniami."),
    "cs": ("Centrála místnosti", "Vyberte oblast Home Assistant. Její skupina obsahuje obecná nastavení místnosti a jeden ovladač pro každé vybrané fyzické zařízení. Přidání místnosti nezapíná automatické řízení zařízení."),
    "sk": ("Centrála miestnosti", "Vyberte oblasť Home Assistant. Jej skupina obsahuje všeobecné nastavenia miestnosti a jeden ovládač pre každé vybrané fyzické zariadenie. Pridanie miestnosti nezapína automatické riadenie zariadení."),
    "sv": ("Rumshubb", "Välj ett område i Home Assistant. Gruppen innehåller allmänna rumsinställningar och en styrenhet per vald fysisk enhet. Att lägga till ett rum aktiverar inte automatisk styrning av utrustning."),
    "da": ("Rumhub", "Vælg et område i Home Assistant. Gruppen indeholder generelle rumindstillinger og én styreenhed pr. valgt fysisk enhed. Tilføjelse af et rum aktiverer ikke automatisk styring af udstyr."),
    "nb": ("Rom-hub", "Velg et område i Home Assistant. Gruppen inneholder generelle rominnstillinger og én kontroller per valgt fysisk enhet. Å legge til et rom aktiverer ikke automatisk styring av utstyr."),
    "fi": ("Huoneen keskitin", "Valitse Home Assistantin alue. Ryhmä sisältää huoneen yleiset asetukset ja yhden ohjaimen kutakin valittua fyysistä laitetta kohti. Huoneen lisääminen ei ota käyttöön laitteiden automaattista ohjausta."),
    "hu": ("Helyiségközpont", "Válassz egy Home Assistant-területet. A csoport az általános helyiségbeállításokat és minden kiválasztott fizikai eszközhöz egy vezérlőt tartalmaz. A helyiség hozzáadása nem kapcsolja be az eszközök automatikus vezérlését."),
    "ro": ("Centru de cameră", "Selectați o zonă Home Assistant. Grupul conține setările generale ale camerei și un controler pentru fiecare dispozitiv fizic selectat. Adăugarea unei camere nu activează controlul automat al echipamentelor."),
    "bg": ("Център на стаята", "Изберете зона в Home Assistant. Групата съдържа общите настройки на стаята и един контролер за всяко избрано физическо устройство. Добавянето на стая не включва автоматично управление на оборудването."),
    "hr": ("Središte prostorije", "Odaberite područje u Home Assistantu. Grupa sadrži opće postavke prostorije i jedan regulator po odabranom fizičkom uređaju. Dodavanje prostorije ne uključuje automatsko upravljanje opremom."),
    "sr": ("Центар просторије", "Изаберите област у Home Assistant-у. Група садржи општа подешавања просторије и један контролер по изабраном физичком уређају. Додавање просторије не укључује аутоматско управљање опремом."),
    "ru": ("Центр комнаты", "Выберите зону Home Assistant. Группа содержит общие настройки комнаты и один контроллер для каждого выбранного физического устройства. Добавление комнаты не включает автоматическое управление оборудованием."),
    "uk": ("Центр кімнати", "Виберіть зону Home Assistant. Група містить загальні налаштування кімнати та один контролер для кожного вибраного фізичного пристрою. Додавання кімнати не вмикає автоматичне керування обладнанням."),
    "tr": ("Oda merkezi", "Bir Home Assistant alanı seçin. Grup, genel oda ayarlarını ve seçilen her fiziksel cihaz için bir denetleyiciyi içerir. Oda eklemek, ekipmanın otomatik kontrolünü etkinleştirmez."),
    "ar": ("مركز الغرفة", "اختر منطقة في Home Assistant. تحتوي مجموعتها على إعدادات الغرفة العامة ومتحكم واحد لكل جهاز فعلي محدد. إضافة غرفة لا تفعّل التحكم التلقائي بالمعدات."),
    "he": ("מרכז החדר", "בחרו אזור ב-Home Assistant. הקבוצה מכילה את הגדרות החדר הכלליות ובקר אחד לכל מכשיר פיזי שנבחר. הוספת חדר אינה מפעילה שליטה אוטומטית בציוד."),
    "fa": ("مرکز اتاق", "یک ناحیه در Home Assistant انتخاب کنید. گروه آن شامل تنظیمات عمومی اتاق و یک کنترل‌کننده برای هر دستگاه فیزیکی انتخاب‌شده است. افزودن اتاق کنترل خودکار تجهیزات را فعال نمی‌کند."),
    "hi": ("कमरे का केंद्र", "Home Assistant का एक क्षेत्र चुनें। इसके समूह में कमरे की सामान्य सेटिंग और हर चुने गए भौतिक उपकरण का एक नियंत्रक होता है। कमरा जोड़ने से उपकरणों का स्वचालित नियंत्रण चालू नहीं होता।"),
    "bn": ("ঘরের কেন্দ্র", "Home Assistant-এর একটি এলাকা বেছে নিন। এর গ্রুপে ঘরের সাধারণ সেটিংস এবং প্রতিটি নির্বাচিত ভৌত ডিভাইসের জন্য একটি নিয়ন্ত্রক থাকে। ঘর যোগ করলে সরঞ্জামের স্বয়ংক্রিয় নিয়ন্ত্রণ চালু হয় না।"),
    "ta": ("அறை மையம்", "Home Assistant பகுதியில் ஒன்றைத் தேர்ந்தெடுக்கவும். அதன் குழுவில் பொதுவான அறை அமைப்புகளும் தேர்ந்தெடுக்கப்பட்ட ஒவ்வொரு சாதனத்திற்கும் ஒரு கட்டுப்படுத்தியும் இருக்கும். அறையைச் சேர்ப்பது சாதனங்களின் தானியங்கிக் கட்டுப்பாட்டை இயக்காது."),
    "ur": ("کمرے کا مرکز", "Home Assistant کا ایک علاقہ منتخب کریں۔ اس کے گروپ میں کمرے کی عمومی ترتیبات اور ہر منتخب جسمانی آلے کے لیے ایک کنٹرولر ہوتا ہے۔ کمرہ شامل کرنے سے آلات کا خودکار کنٹرول فعال نہیں ہوتا۔"),
    "id": ("Pusat ruangan", "Pilih area Home Assistant. Grupnya berisi pengaturan umum ruangan dan satu pengendali untuk setiap perangkat fisik yang dipilih. Menambahkan ruangan tidak mengaktifkan kendali peralatan otomatis."),
    "vi": ("Trung tâm phòng", "Chọn một khu vực Home Assistant. Nhóm chứa cài đặt chung của phòng và một bộ điều khiển cho mỗi thiết bị vật lý được chọn. Thêm phòng không bật điều khiển thiết bị tự động."),
    "ko": ("방 허브", "Home Assistant 영역을 선택하세요. 그룹에는 방의 일반 설정과 선택한 각 물리적 기기의 제어기 하나가 포함됩니다. 방을 추가해도 기기의 자동 제어가 활성화되지는 않습니다."),
    "ja": ("部屋のハブ", "Home Assistantのエリアを選択してください。グループには部屋の共通設定と、選択した物理機器ごとに1つのコントローラーが含まれます。部屋を追加しても機器の自動制御は有効になりません。"),
    "zh-Hans": ("房间中枢", "选择一个 Home Assistant 区域。其分组包含房间通用设置，以及每个已选物理设备对应的一个控制器设备。添加房间不会启用设备的自动控制。"),
    "zh-Hant": ("房間中樞", "選擇一個 Home Assistant 區域。其群組包含房間的一般設定，以及每個已選實體裝置對應的一個控制器裝置。新增房間不會啟用裝置的自動控制。"),
    "th": ("ศูนย์กลางห้อง", "เลือกพื้นที่ใน Home Assistant กลุ่มนี้มีการตั้งค่าทั่วไปของห้องและตัวควบคุมหนึ่งรายการต่ออุปกรณ์จริงที่เลือก การเพิ่มห้องจะไม่เปิดใช้งานการควบคุมอุปกรณ์อัตโนมัติ"),
}


def apply_room_hub_i18n(root: Path) -> None:
    """Room groups are translated separately from the pre-existing options UI."""
    vocab = json.loads((root / "compact_locales.json").read_text(encoding="utf-8"))
    files = sorted((root / "translations").glob("*.json"))
    if set(ROOM_TEXT) != set(vocab) or set(ROOM_TEXT) != {p.stem for p in files}:
        raise ValueError("All supported room-hub locales must be supplied")
    for path in (root / "strings.json", *files):
        lang = "en" if path.name == "strings.json" else path.stem
        title, help_text = ROOM_TEXT[lang]
        words = vocab[lang]
        doc = json.loads(path.read_text(encoding="utf-8"))
        doc.setdefault("config_subentries", {})["room"] = {
            "entry_type": title,
            "initiate_flow": {"user": title},
            "step": {"user": {"title": title, "description": help_text,
                "data": {"area_id": words["room"]},
                "data_description": {"area_id": help_text}}},
            "error": {"invalid_area": f"{words['invalid']}: {words['area']}."},
            "abort": {"already_configured": "[%key:common::config_flow::abort::already_configured%]"},
        }
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
