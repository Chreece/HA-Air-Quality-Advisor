'use strict';
const assert = require('node:assert/strict');
const path = require('node:path');
const registered = new Map();
class FakeElement {
  attachShadow() {
    const listeners = {};
    this.shadowRoot={innerHTML:'',listeners,
      addEventListener(type,handler){listeners[type]=handler;}};
    return this.shadowRoot;
  }
}
global.HTMLElement = FakeElement;
global.customElements = {
  get(name){return registered.get(name);},
  define(name,ctor){registered.set(name,ctor);}
};
global.window = {customCards:[]};
const cardPath = path.resolve(__dirname,'../custom_components/environment_manager/frontend/air-quality-advisor-card.js');
require(cardPath);
assert.equal(registered.has('air-quality-advisor-card'),true);
assert.equal(window.customCards.filter((c)=>c.type==='air-quality-advisor-card').length,1);
const Card=registered.get('air-quality-advisor-card');
const input={
  version:1,summary:{safe:1,attention:1,unknown:1,total:3},
  outdoor:{status:'partial',safe_to_ventilate:true,data_complete:false,
    readings:[{metric:'pm25',value:8,threshold:15,unit:'µg/m³',available:true,exceeded:false}],
    weather:[{condition:'sunny',temperature_c:22,humidity:40,wind_kmh:10}],warnings:[],blockers:[]},
  rooms:[
    {area_id:'kitchen',name:'Kitchen',status:'safe',readings:[{metric:'co2',value:600,threshold:1000,unit:'ppm',available:true,exceeded:false}],
      windows:[{name:'Kitchen window',entity_id:'binary_sensor.kitchen_window',opened:false}]},
    {area_id:'living',name:'<img src=x onerror=alert(1)>',status:'attention',action:'open',
      action_window_ids:['binary_sensor.living_window'],high_count:1,readings:[{metric:'co2',value:1370,threshold:1000,unit:'ppm',available:true,exceeded:true}],
      windows:[{name:'Living window',entity_id:'binary_sensor.living_window',opened:false}]},
    {area_id:'bedroom',name:'Bedroom',status:'unknown',readings:[],windows:[]}
  ]
};
const card=new Card();
card.setConfig({entity:'sensor.air_quality_advisor_recommendations'});
for(const [lang,needle] of [['el','Home Environment Manager'],['de','Home Environment Manager'],['fr','Home Environment Manager'],['es','Home Environment Manager'],['en','Home Environment Manager']]) {
  card.hass={language:lang,states:{'sensor.air_quality_advisor_recommendations':{state:'open',attributes:{dashboard:input}}}};
  assert.ok(card.shadowRoot.innerHTML.includes(needle), `missing language ${lang}`);
}

for (const [lang, expected, rtl] of [
  ['it', 'Home Environment Manager', false],
  ['nl', 'Home Environment Manager', false],
  ['pt-BR', 'Home Environment Manager', false],
  ['zh-Hans', 'Home Environment Manager', false],
  ['zh-Hant', 'Home Environment Manager', false],
  ['zh_TW', 'Home Environment Manager', false],
  ['ja', 'Home Environment Manager', false],
  ['ko', 'Home Environment Manager', false],
  ['hi', 'Home Environment Manager', false],
  ['ar', 'Home Environment Manager', true],
  ['he', 'Home Environment Manager', true],
  ['ur', 'Home Environment Manager', true],
]) {
  card.hass={language:lang,states:{'sensor.air_quality_advisor_recommendations':{state:'open',attributes:{dashboard:input}}}};
  assert.ok(card.shadowRoot.innerHTML.includes(expected), `missing UI language: ${lang}`);
  assert.ok(card.shadowRoot.innerHTML.includes(`dir="${rtl ? 'rtl' : 'ltr'}"`), `wrong text direction: ${lang}`);
}
card.hass={language:'en',states:{'sensor.air_quality_advisor_recommendations':{state:'open',attributes:{dashboard:input}}}};
assert.ok(!card.shadowRoot.innerHTML.includes('<img src=x onerror='),'dynamic names must be escaped');
assert.ok(card.shadowRoot.innerHTML.includes('&lt;img src=x'));
assert.ok(card.shadowRoot.innerHTML.includes('out-chip'));
assert.ok(card.shadowRoot.innerHTML.includes('donut'));
assert.ok(card.shadowRoot.innerHTML.includes('metric-grid'));
assert.ok(!card.shadowRoot.innerHTML.includes('hass.callService'));
assert.equal(window.customCards[0].getEntitySuggestion(card._hass,'sensor.air_quality_advisor_recommendations').config.type,'custom:air-quality-advisor-card');
// Mold mode renders a derived surface estimate and valid-RH sensor average.
{
  const mold = JSON.parse(JSON.stringify(input));
  mold.rooms[0].readings = [{
    entity_id:'derived.mold_kitchen', metric:'mold', value:82.4,
    threshold:70, unit:'%', available:true, exceeded:true,
    details:{average_indoor_humidity:64.8,humidity_sensor_count:2,
             estimated_surface_c:13.2}
  }];
  card.hass={language:'el',states:{
    'sensor.air_quality_advisor_recommendations':{
      state:'open',attributes:{dashboard:mold}
    }
  }};
  assert.ok(card.shadowRoot.innerHTML.includes('Ένδειξη μούχλας'));
  assert.ok(card.shadowRoot.innerHTML.includes('Μέση υγρασία:'));
  assert.ok(card.shadowRoot.innerHTML.includes('2 αισθητήρες'));
  assert.ok(card.shadowRoot.innerHTML.includes('Εκτιμώμενη επιφάνεια:'));
  assert.match(card.shadowRoot.innerHTML, /13[,.]2°C/);
  assert.ok(!card.shadowRoot.innerHTML.includes('n=2'));
}
// A never-calibrated mold indicator must not erase perfectly valid air data.
{
  const partial = JSON.parse(JSON.stringify(input));
  partial.rooms = [{
    area_id:'living',name:'Wohnzimmer',status:'unknown',
    status_detail:'mold_not_calibrated',available_count:2,high_count:0,
    windows:[{name:'Living window',entity_id:'binary_sensor.living_window',opened:false}],
    readings:[
      {metric:'pm25',value:1,threshold:25,unit:'µg/m³',available:true,exceeded:false},
      {metric:'aqi',value:12.9,threshold:100,unit:'AQI',available:true,exceeded:false},
      {metric:'mold',value:null,threshold:70,unit:'%',available:false,exceeded:false,
        details:{status:'needs_calibration',average_indoor_humidity:53,
                 humidity_sensor_count:2}},
    ],
  }];
  card.hass={language:'el',states:{
    'sensor.air_quality_advisor_recommendations':{
      state:'idle',attributes:{dashboard:partial}
    }
  }};
  const html = card.shadowRoot.innerHTML;
  assert.ok(html.includes('Η ένδειξη μούχλας δεν έχει βαθμονομηθεί'),
    'uncalibrated mold should be explained in Greek');
  assert.ok(html.includes('Ελλιπή δεδομένα'),'valid PM/AQI means partial data');
  assert.ok(!html.includes('Δεν υπάρχουν εσωτερικές μετρήσεις'),
    'valid PM and AQI readings must never be called no indoor data');
  assert.ok(html.includes('PM2.5') && html.includes('AQI'));
  assert.ok(html.includes('2 αισθητήρες') && html.includes('53%'),
    'show valid RH average even before calibration');

  // Unavailable inputs *after* calibration are not the same as no calibration.
  partial.rooms[0].status_detail = 'mold_inputs_unavailable';
  partial.rooms[0].readings[2].details.status = 'inputs_unavailable';
  card.hass={language:'de',states:{
    'sensor.air_quality_advisor_recommendations':{
      state:'idle',attributes:{dashboard:partial}
    }
  }};
  assert.ok(card.shadowRoot.innerHTML.includes('Messdaten für Schimmelindikator fehlen'));
  assert.ok(!card.shadowRoot.innerHTML.includes('Schimmelindikator nicht kalibriert'));

  partial.rooms[0].readings = [{
    metric:'mold',value:null,threshold:70,unit:'%',available:false,exceeded:false,
    details:{status:'needs_calibration',humidity_sensor_count:0}
  }];
  partial.rooms[0].status_detail = 'mold_not_calibrated';
  card.hass={language:'en',states:{
    'sensor.air_quality_advisor_recommendations':{
      state:'idle',attributes:{dashboard:partial}
    }
  }};
  assert.ok(card.shadowRoot.innerHTML.includes('No data'),
    'a room with zero usable measurements remains unknown');
  assert.ok(card.shadowRoot.innerHTML.includes('Mold indicator not calibrated'));
}
// All unavailable mold inputs must produce explicit warnings without turning
// healthy particulate measurements into false "No data" or an alert action.
{
  const diagnostic = JSON.parse(JSON.stringify(input));
  diagnostic.rooms=[{
    area_id:'living',name:'Wohnzimmer',status:'unknown',
    status_detail:'mold_not_calibrated',available_count:2,
    windows:[{name:'Window',entity_id:'binary_sensor.window',opened:false}],
    readings:[
      {metric:'pm25',value:1,threshold:25,unit:'µg/m³',available:true,exceeded:false},
      {metric:'aqi',value:12.9,threshold:100,unit:'AQI',available:true,exceeded:false},
      {metric:'mold',value:null,threshold:70,unit:'%',available:false,exceeded:false,
       details:{status:'needs_calibration',
        missing_inputs:['calibration','indoor_temperature','outdoor_temperature','humidity'],
        outdoor_weather_entity:'weather.zuhause',
        indoor_temperature_entity:'sensor.wohnzimmer_temperature'}}
    ],
    mold_warnings:['calibration','indoor_temperature','outdoor_temperature','humidity'],
  }];
  card.hass={language:'el',states:{
    'sensor.air_quality_advisor_recommendations':{
      state:'idle',attributes:{dashboard:diagnostic}
    }
  }};
  let html=card.shadowRoot.innerHTML;
  assert.ok(html.includes('mold-warnings'));
  assert.equal((html.match(/class="mold-warning"/g)||[]).length,4);
  assert.ok(html.includes('Μέτρησε και αποθήκευσε'));
  assert.ok(html.includes('Δεν υπάρχει έγκυρη μέτρηση θερμοκρασίας'));
  assert.ok(html.includes('δεν δίνει έγκυρη εξωτερική'));
  assert.ok(html.includes('μετρήσεις υγρασίας'));
  assert.ok(html.includes('weather.zuhause'));
  assert.ok(html.includes('sensor.wohnzimmer_temperature'));
  assert.ok(html.includes('Ελλιπή δεδομένα'));
  assert.ok(html.includes('PM2.5') && html.includes('AQI'));
  diagnostic.rooms[0].readings[2].details.missing_inputs=[];
  diagnostic.rooms[0].mold_warnings=['outdoor_temperature'];
  card.hass={language:'de',states:{
    'sensor.air_quality_advisor_recommendations':{
      state:'idle',attributes:{dashboard:diagnostic}
    }
  }};
  html=card.shadowRoot.innerHTML;
  assert.equal((html.match(/class="mold-warning"/g)||[]).length,1);
  assert.ok(html.includes('Wetterentität'));
  diagnostic.rooms[0].readings[2].value=61;
  diagnostic.rooms[0].readings[2].available=true;
  diagnostic.rooms[0].mold_warnings=[];
  diagnostic.rooms[0].status='safe';
  diagnostic.rooms[0].status_detail=null;
  card.hass={language:'en',states:{
    'sensor.air_quality_advisor_recommendations':{
      state:'idle',attributes:{dashboard:diagnostic}
    }
  }};
  assert.ok(!card.shadowRoot.innerHTML.includes('class="mold-warning"'));
}
// When mold is unavailable, surface RH must not be implied: make the
// alternate averaged room humidity and its *own* 65% threshold explicit.
{
  const sample = JSON.parse(JSON.stringify(input));
  sample.rooms = [{
    area_id:'living',name:'Wohnzimmer',status:'unknown',
    status_detail:'mold_not_calibrated',available_count:3,high_count:0,
    rh_fallback:{active:true,value:55,threshold:65,humidity_sensor_count:2},
    mold_warnings:['calibration'],
    windows:[{name:'Window',entity_id:'binary_sensor.window',opened:false}],
    readings:[
      {metric:'humidity',value:55,threshold:65,unit:'%',available:true,exceeded:false,
       details:{fallback_for_mold:true,humidity_sensor_count:2}},
      {metric:'pm25',value:1,threshold:25,unit:'µg/m³',available:true,exceeded:false},
      {metric:'aqi',value:12.9,threshold:100,unit:'AQI',available:true,exceeded:false},
      {metric:'mold',value:null,threshold:70,unit:'%',available:false,exceeded:false,
       details:{status:'needs_calibration',missing_inputs:['calibration']}}
    ],
  }];
  card.hass={language:'el',states:{
    'sensor.air_quality_advisor_recommendations':{state:'idle',attributes:{dashboard:sample}}
  }};
  const gr = card.shadowRoot.innerHTML;
  assert.ok(gr.includes('Ενεργή εφεδρική χρήση σχετικής υγρασίας'));
  assert.ok(gr.includes('Υγρασία Ø (RH)'));
  assert.ok(gr.includes('55%'));
  assert.ok(gr.includes('65%'));
  // Compact layout shows actionable RH, PM2.5 and AQI; the missing mold
  // gauge is available through "More details", while its warning is visible.
  assert.ok(gr.includes('mold-warnings'));
  assert.ok(gr.includes('Μέτρησε και αποθήκευσε'));
  card._expanded.add('living');
  card._render(true);
  assert.ok(card.shadowRoot.innerHTML.includes('Ένδειξη μούχλας'));
  card._expanded.delete('living');
  card._render(true);
  assert.ok(gr.includes('PM2.5') && gr.includes('AQI'));
  assert.ok(!gr.includes('Δεν υπάρχουν εσωτερικές μετρήσεις'));

  card.hass={language:'de',states:{
    'sensor.air_quality_advisor_recommendations':{state:'idle',attributes:{dashboard:sample}}
  }};
  assert.ok(card.shadowRoot.innerHTML.includes('RH-Ersatzwert aktiv'));

  sample.rooms[0].rh_fallback = {active:false};
  sample.rooms[0].mold_warnings = [];
  sample.rooms[0].status = 'safe';
  sample.rooms[0].status_detail = null;
  sample.rooms[0].readings=[{
    metric:'mold',value:57,threshold:70,unit:'%',available:true,exceeded:false,
    details:{status:'ready',missing_inputs:[]}
  }];
  card.hass={language:'en',states:{
    'sensor.air_quality_advisor_recommendations':{state:'idle',attributes:{dashboard:sample}}
  }};
  assert.ok(!card.shadowRoot.innerHTML.includes('class="rh-fallback"'));
  assert.ok(!card.shadowRoot.innerHTML.includes('RH fallback active'));
  assert.ok(card.shadowRoot.innerHTML.includes('Mold indication'));
}
// Exactly three measurement tiles must still offer More details for calibration.
{
  const sample=JSON.parse(JSON.stringify(input));
  sample.rooms[0].readings=[
    {metric:'aqi',value:12.9,threshold:100,unit:'AQI',available:true,exceeded:false},
    {metric:'pm25',value:1,threshold:25,unit:'µg/m³',available:true,exceeded:false},
    {metric:'mold',value:71.9,threshold:70,unit:'%',available:true,exceeded:true,
      details:{status:'ready',average_indoor_humidity:55,humidity_sensor_count:2,
        estimated_surface_c:17.1,calibration_factor:2.370123456789,
        indoor_temperature_c:21.7,outdoor_temperature_c:8.5}}
  ];
  card.hass={language:'el',states:{
    'sensor.air_quality_advisor_recommendations':{
      state:'open',attributes:{dashboard:sample}
    }
  }};
  const compact=card.shadowRoot.innerHTML;
  assert.ok(compact.includes('Μέση υγρασία: 55%'));
  assert.ok(compact.includes('2 αισθητήρες'));
  assert.ok(compact.includes('Εκτιμώμενη επιφάνεια: 17,1°C'));
  assert.ok(!compact.includes('n=2'));
  assert.ok(compact.includes('data-expand="kitchen"'));
  assert.ok(!compact.includes('class="mold-calibration-details"'));
  card._expanded.add('kitchen');
  card._render(true);
  const open=card.shadowRoot.innerHTML;
  assert.ok(open.includes('aria-expanded="true"'));
  assert.ok(open.includes('class="mold-calibration-details"'));
  assert.ok(open.includes('Συντελεστής βαθμονόμησης'));
  assert.ok(open.includes('2,370123'));
  assert.ok(open.includes('title="2.370123456789"'));
  assert.ok(open.includes('Εσωτερική θερμοκρασία'));
  assert.ok(open.includes('21,7°C'));
  assert.ok(open.includes('Εξωτερική θερμοκρασία'));
  assert.ok(open.includes('8,5°C'));
  card._expanded.delete('kitchen');
  card._render(true);

  sample.rooms[0].readings[2].details.humidity_sensor_count=1;
  card.hass={language:'el',states:{
    'sensor.air_quality_advisor_recommendations':{
      state:'open',attributes:{dashboard:sample}
    }
  }};
  assert.ok(card.shadowRoot.innerHTML.includes('1 αισθητήρας'));
  assert.ok(!card.shadowRoot.innerHTML.includes('1 αισθητήρες'));

  card.hass={language:'de',states:{
    'sensor.air_quality_advisor_recommendations':{
      state:'open',attributes:{dashboard:sample}
    }
  }};
  assert.ok(card.shadowRoot.innerHTML.includes('Durchschnittliche Luftfeuchte'));
  assert.ok(card.shadowRoot.innerHTML.includes('Geschätzte Oberflächentemperatur'));

  sample.rooms[0].readings[2].details.calibration_factor=2;
  card.hass={language:'en',states:{
    'sensor.air_quality_advisor_recommendations':{
      state:'open',attributes:{dashboard:sample}
    }
  }};
  card._expanded.add('kitchen');
  card._render(true);
  assert.ok(card.shadowRoot.innerHTML.includes('Calibration factor'));
  assert.ok(card.shadowRoot.innerHTML.includes('2.00'));
  card._expanded.delete('kitchen');
  card._render(true);

  card.setConfig({entity:'sensor.air_quality_advisor_recommendations',show_metrics:false});
  assert.ok(!card.shadowRoot.innerHTML.includes('class="mold-calibration-details"'));
  assert.ok(!card.shadowRoot.innerHTML.includes('data-expand="kitchen"'));

  card.setConfig({entity:'sensor.air_quality_advisor_recommendations'});
  sample.rooms[0].readings[2].details.calibration_factor=null;
  card.hass={language:'en',states:{
    'sensor.air_quality_advisor_recommendations':{
      state:'open',attributes:{dashboard:sample}
    }
  }};
  assert.ok(!card.shadowRoot.innerHTML.includes('data-expand="kitchen"'));
}
console.log('Dashboard card frontend tests passed');

assert.equal(registered.has('home-environment-manager-card'),true);
assert.equal(window.customCards.some((card)=>card.type==='home-environment-manager-card'),true);

const pidData = JSON.parse(JSON.stringify(input));
pidData.rooms[0].environment = {climate_pid:{
  status:'controlling',mode:'heat',target_c:21.5,
  demand_percent:40,desired_setpoint_c:22.1
}};
const pidCard = new Card();
pidCard.setConfig({entity:'sensor.pid_test'});
for (const [language,translation] of [['en','Climate PID'],['de','Klima-PID'],['el','Κλιματικός PID']]) {
  pidCard.hass={language,states:{'sensor.pid_test':{state:'idle',attributes:{dashboard:pidData}}}};
  assert.ok(pidCard.shadowRoot.innerHTML.includes(translation), 'PID title not localized: '+language);
  assert.ok(pidCard.shadowRoot.innerHTML.includes('data-pid-area="kitchen"'));
  assert.ok(pidCard.shadowRoot.innerHTML.includes('data-pid-action="pause"'));
}
pidData.rooms[0].environment.climate_pid={status:'paused',reason:'manual_hvac_mode_change'};
pidCard.hass={language:'en',states:{'sensor.pid_test':{state:'idle',attributes:{dashboard:pidData}}}};
assert.ok(pidCard.shadowRoot.innerHTML.includes('data-pid-action="resume"'));
pidData.rooms[0].environment.climate_pid={status:'disabled'};
pidCard.hass={language:'en',states:{'sensor.pid_test':{state:'idle',attributes:{dashboard:pidData}}}};
assert.ok(!pidCard.shadowRoot.innerHTML.includes('data-pid-action="pause"'));

const nativeRange=JSON.parse(JSON.stringify(input));
nativeRange.rooms[0].environment={climate_plan:{
  status:'ready',profile:'home',mode:'heat_cool',
  low_target_c:20,high_target_c:26,
  actuation:{status:'native_range_commanded'},
  reason:'device_internal_heat_cool',
}};
const rangeCard=new Card();
rangeCard.setConfig({entity:'sensor.range_demo'});
for(const [lang,title] of [['en','Climate'],['de','Klima'],['el','Κλίμα']]){
  rangeCard.hass={language:lang,states:{
    'sensor.range_demo':{state:'idle',attributes:{dashboard:nativeRange}},
  }};
  assert.ok(rangeCard.shadowRoot.innerHTML.includes(title));
  assert.ok(rangeCard.shadowRoot.innerHTML.includes('20–26 °C'));
  assert.ok(rangeCard.shadowRoot.innerHTML.includes('data-climate-area="kitchen"'));
}


// Show separate, explicitly opted-in HVAC and humidity status without
// conflating active secondary setpoints with the primary controller hold.
const multiDevice=JSON.parse(JSON.stringify(input));
multiDevice.rooms[0].environment={climate_plan:{
  status:'hold',reason:'secondary_thermal_driver_pending',mode:'cool',
  temperature_target_c:26,profile:'home',
  actuation:{status:'hold'},
  secondary_actuation:{status:'setpoint_commanded'},
  humidity_actuation:{status:'paused'},
  equipment_plan:{
    thermal:{status:'selected',entity_id:'climate.kitchen_ac',mode:'cool'},
    moisture:{status:'selected',entity_id:'humidifier.dryer',action:'dry'},
    humidity:{status:'advisory',action:'dry',measured_rh:67},
    humidity_evidence:'selected_sensor',
  },
}};
const multiCard=new Card();
multiCard.setConfig({entity:'sensor.multi_device'});
for (const [language, labels] of [
  ['en',['Secondary HVAC','Humidity control','Selected equipment']],
  ['de',['Zweites Klimagerät','Luftfeuchteregelung','Ausgewähltes Gerät']],
  ['el',['Δεύτερη συσκευή κλίματος','Ρύθμιση υγρασίας','Επιλεγμένη συσκευή']],
]) {
  multiCard.hass={language,states:{
    'sensor.multi_device':{state:'idle',attributes:{dashboard:multiDevice}},
  }};
  for(const label of labels)
    assert.ok(multiCard.shadowRoot.innerHTML.includes(label), language+': '+label);
  assert.ok(multiCard.shadowRoot.innerHTML.includes('climate.kitchen_ac'));
  assert.ok(multiCard.shadowRoot.innerHTML.includes('humidifier.dryer'));
  assert.ok(multiCard.shadowRoot.innerHTML.includes('data-climate-action="pause"'));
}
multiDevice.rooms[0].environment.climate_plan.actuation={status:'paused'};
multiDevice.rooms[0].environment.climate_plan.secondary_actuation={status:'paused'};
multiCard.hass={language:'en',states:{
  'sensor.multi_device':{state:'idle',attributes:{dashboard:multiDevice}},
}};
assert.ok(multiCard.shadowRoot.innerHTML.includes('data-climate-action="resume"'));


// Fan speed regulation is a distinct service with independently qualified
// extraction/filtration evidence; the dashboard never claims it turns fans on.
const airPanel=JSON.parse(JSON.stringify(input));
airPanel.rooms[0].environment={climate_plan:{
  status:'hold',mode:'heat',profile:'home',temperature_target_c:20,
  actuation:{status:'hold'},
  secondary_actuation:{status:'advisory_only'},
  humidity_actuation:{status:'advisory_only'},
  fan_actuation:{status:'fan_speed_increased',entity_id:'fan.kitchen_filter',
                 new_percent:50},
  air_actions:{status:'advisory',filtration:{
    status:'recommended',entity_id:'fan.kitchen_filter',
  },extraction:{status:'blocked_outdoor_evidence'}},
}};
const airCard=new Card();
airCard.setConfig({entity:'sensor.air_panel'});
for(const [lang,label] of [
  ['en','Particle filtration'],
  ['de','Partikelfiltration'],
  ['el','Φιλτράρισμα σωματιδίων'],
]) {
  airCard.hass={language:lang,states:{
    'sensor.air_panel':{state:'idle',attributes:{dashboard:airPanel}},
  }};
  assert.ok(airCard.shadowRoot.innerHTML.includes(label));
  assert.ok(airCard.shadowRoot.innerHTML.includes('fan.kitchen_filter'));
  assert.ok(airCard.shadowRoot.innerHTML.includes('data-climate-action="pause"'));
}


// Windowless HVAC-only rooms appear without a fake missing air or window warning.
const onlyClimate=JSON.parse(JSON.stringify(input));
onlyClimate.rooms=[{
  area_id:'bedroom',name:'Bedroom',status:'unknown',climate_only:true,
  environment:{climate_plan:{
    status:'ready',mode:'heat',temperature_target_c:21,profile:'home',
    actuation:{status:'setpoint_commanded'},
  }},
  readings:[],windows:[],high_count:0,available_count:0,
}];
const onlyCard=new Card();
onlyCard.setConfig({entity:'sensor.climate_only'});
onlyCard.hass={language:'en',states:{
  'sensor.climate_only':{state:'idle',attributes:{dashboard:onlyClimate}},
}};
assert.ok(onlyCard.shadowRoot.innerHTML.includes('room-climate-only'));
assert.ok(onlyCard.shadowRoot.innerHTML.includes('Bedroom'));
assert.ok(onlyCard.shadowRoot.innerHTML.includes('21 °C'));
const onlyRoomMarkup=onlyCard.shadowRoot.innerHTML.slice(
  onlyCard.shadowRoot.innerHTML.indexOf('<article class="room room-climate-only">')
);
assert.ok(!onlyRoomMarkup.includes('class="empty-measurements"'));
assert.ok(!onlyRoomMarkup.includes('class="window-section"'));


// Native AC DRY/FAN_ONLY is manual advice only; never a mode-control button.
const dryManual=JSON.parse(JSON.stringify(input));
dryManual.rooms[0].environment={climate_plan:{
  status:'ready',profile:'home',mode:'off',
  actuation:{status:'advisory_only'},secondary_actuation:{status:'advisory_only'},
  humidity_actuation:{status:'advisory_only'},fan_actuation:{status:'advisory_only'},
  native_air_mode_advice:{
    status:'manual_mode_transition_suggested',
    recommended_mode:'dry',climate_entity:'climate.kitchen_ac',
    automatic_control:false,
  },
}};
const dryCard=new Card();
dryCard.setConfig({entity:'sensor.manual_dry'});
for(const [lang,word] of [
  ['en','Manual AC mode suggestion'],
  ['de','Empfohlener Klimamodus'],
  ['el','Πρόταση χειροκίνητης λειτουργίας'],
]){
  dryCard.hass={language:lang,states:{
    'sensor.manual_dry':{state:'idle',attributes:{dashboard:dryManual}},
  }};
  assert.ok(dryCard.shadowRoot.innerHTML.includes(word));
  assert.ok(dryCard.shadowRoot.innerHTML.includes('climate.kitchen_ac'));
  assert.ok(!dryCard.shadowRoot.innerHTML.includes('data-climate-action="pause"'));
}


// Environmental-only climate rooms show actual humidity power status without
// invented thermostat targets, preserve localized names and pause/resume.
const humidityOnly=JSON.parse(JSON.stringify(input));
humidityOnly.rooms=[{
  area_id:'bathroom',name:'Bathroom',climate_only:true,
  status:'unknown',readings:[],windows:[],high_count:0,available_count:0,
  environment:{climate_plan:{
    status:'advisory',controller:'environment',profile:'home',
    mode:null,actuation:{status:'advisory_only'},
    secondary_actuation:{status:'advisory_only'},
    humidity_actuation:{status:'advisory_only'},
    humidity_power_actuation:{status:'owned_running',
                               entity_id:'humidifier.bathroom_dryer'},
    fan_actuation:{status:'advisory_only'},
    equipment_plan:{moisture:{status:'selected',
                              entity_id:'humidifier.bathroom_dryer',
                              action:'dry'},
                    humidity:{status:'advisory',action:'dry',
                              measured_rh:68}},
  }},
}];
const humidityCard=new Card();
humidityCard.setConfig({entity:'sensor.humidity_only'});
for(const [language,label] of [
  ['en','Humidity power'],
  ['de','Be-/Entfeuchter schalten'],
  ['el','Έλεγχος ισχύος υγρασίας'],
]){
  humidityCard.hass={language,states:{
    'sensor.humidity_only':{state:'idle',attributes:{dashboard:humidityOnly}},
  }};
  const html=humidityCard.shadowRoot.innerHTML;
  assert.ok(html.includes(label),language+': '+label);
  assert.ok(html.includes('humidifier.bathroom_dryer'));
  assert.ok(html.includes('data-climate-action="pause"'));
  assert.ok(!html.includes('NaN °C'));
}
humidityOnly.rooms[0].environment.climate_plan.humidity_power_actuation={
  status:'paused',reason:'restart_requires_manual_output_reconciliation',
};
humidityCard.hass={language:'en',states:{
  'sensor.humidity_only':{state:'idle',attributes:{dashboard:humidityOnly}},
}};
assert.ok(humidityCard.shadowRoot.innerHTML.includes('data-climate-action="resume"'));


// Window-based savings advice is visible but NEVER presented as a command.
// Climates exposing only DRY are rendered without a fabricated FAN_ONLY mode.
const windowAid=JSON.parse(JSON.stringify(input));
windowAid.rooms=[{
  area_id:'bathroom',name:'Bathroom',climate_only:true,status:'unknown',
  readings:[],windows:[],high_count:0,available_count:0,
  environment:{climate_plan:{
    status:'advisory',controller:'device',mode:'dry',profile:'home',
    actuation:{status:'advisory_only'},
    window_efficiency:{status:'opportunity',effect:'dry',
      active_device:'climate.dry_only',notify_enabled:true,
      automatic_control:false,
      evidence:{humidity_ratio_advantage_g_kg:3.4}},
    native_air_mode_advice:{status:'manual_stop_dry_suggested',
      recommended_mode:'off',automatic_control:false},
  }},
}];
const windowAidCard=new Card();
windowAidCard.setConfig({entity:'sensor.window_aid'});
for(const [language,word] of [
  ['en','Open-window opportunity'],
  ['de','Fensterlüften als Alternative'],
  ['el','Πιθανή εξοικονόμηση'],
]){
  windowAidCard.hass={language,states:{
    'sensor.window_aid':{state:'idle',attributes:{dashboard:windowAid}},
  }};
  const html=windowAidCard.shadowRoot.innerHTML;
  assert.ok(html.includes(word), language + ': missing window alternative');
  assert.ok(html.includes('climate.dry_only'));
  assert.ok(!html.includes('data-hvac-mode='));
}


// Automatic native fan power belongs to a separately authorized driver,
// including single-room IDs and runtime pause/resume.
const poweredFan=JSON.parse(JSON.stringify(input));
poweredFan.rooms=[{
  area_id:'kitchen',name:'Kitchen',climate_only:true,status:'unknown',
  readings:[],windows:[],high_count:0,available_count:0,
  environment:{climate_plan:{
    status:'advisory',controller:'environment',profile:'home',
    actuation:{status:'advisory_only'},fan_actuation:{status:'advisory_only'},
    fan_power_actuation:{status:'owned_fan_running',
                         entity_id:'fan.kitchen_extraction'},
    air_actions:{status:'advisory',extraction:{
      status:'recommended',entity_id:'fan.kitchen_extraction'}},
  }},
}];
const fanPowerCard=new Card();
fanPowerCard.setConfig({entity:'sensor.powered_fan'});
for(const [language,label] of [
  ['en','Fan power'],['de','Lüfter Ein/Aus'],
  ['el','Ισχύς ανεμιστήρων'],
]){
  fanPowerCard.hass={language,states:{
    'sensor.powered_fan':{state:'idle',attributes:{dashboard:poweredFan}},
  }};
  assert.ok(fanPowerCard.shadowRoot.innerHTML.includes(label),language+': '+label);
  assert.ok(fanPowerCard.shadowRoot.innerHTML.includes('data-climate-action="pause"'));
}
poweredFan.rooms[0].environment.climate_plan.fan_power_actuation={
  status:'paused',reason:'restart_requires_manual_fan_off_reconciliation'};
fanPowerCard.hass={language:'en',states:{
  'sensor.powered_fan':{state:'idle',attributes:{dashboard:poweredFan}},
}};
assert.ok(fanPowerCard.shadowRoot.innerHTML.includes('data-climate-action="resume"'));


// One centralized room arbiter explains priorities and inhibits unsupported
// simultaneous effects without inventing extra HVAC service controls.
const coordinated=JSON.parse(JSON.stringify(input));
coordinated.rooms=[{
  area_id:'bedroom',name:'Bedroom',climate_only:true,
  status:'unknown',readings:[],windows:[],
  environment:{climate_plan:{
    status:'advisory',controller:'environment',profile:'home',
    coordination:{
      status:'ready',priority:'measured_co2_ventilation',
      channels:{
        thermal:{status:'held',reason:'opposing_native_mode_armed'},
        humidity:{status:'eligible',entity_id:'humidifier.bedroom'},
        extraction:{status:'eligible',entity_id:'fan.bedroom'},
        filtration:{status:'idle'},
      },
    },
    actuation:{status:'advisory_only'},
  }},
}];
const arbCard=new Card();
arbCard.setConfig({entity:'sensor.room_priority'});
for(const [language,rank,hold] of [
  ['en','CO₂ ventilation','Held'],
  ['de','CO₂-Lüftung','Gesperrt'],
  ['el','Εξαερισμός CO₂','Σε αναμονή'],
]){
  arbCard.hass={language,states:{
    'sensor.room_priority':{state:'idle',attributes:{dashboard:coordinated}},
  }};
  const html=arbCard.shadowRoot.innerHTML;
  assert.ok(html.includes(rank),language+': priority');
  assert.ok(html.includes(hold),language+': blocked purpose');
  assert.ok(html.includes('opposing native mode armed'));
  assert.ok(!html.includes('data-hvac-mode='));
}


// Native DRY/FAN_ONLY controller status is visible independently of
// the existing manual mode advice and can be paused without HVAC broadcasts.
const nativeDry=JSON.parse(JSON.stringify(input));
nativeDry.rooms=[{
  area_id:'bathroom',name:'Bathroom',climate_only:true,status:'unknown',
  readings:[],windows:[],high_count:0,available_count:0,
  environment:{climate_plan:{
    status:'advisory',controller:'environment',profile:'home',
    actuation:{status:'advisory_only'},
    native_air_mode_advice:{status:'manual_mode_transition_suggested',
      recommended_mode:'dry',current_mode:'fan_only',
      climate_entity:'climate.bathroom_ac',automatic_control:false},
    native_air_mode_actuation:{
      status:'native_mode_commanded',entity_id:'climate.bathroom_ac',mode:'dry'},
  }},
}];
const nativeDryCard=new Card();
nativeDryCard.setConfig({entity:'sensor.native_dry'});
for(const [language,label] of [
  ['en','Commissioned DRY/FAN modes'],
  ['de','Freigegebene DRY/FAN-Modi'],
  ['el','Εγκεκριμένες λειτουργίες DRY/FAN'],
]){
  nativeDryCard.hass={language,states:{
    'sensor.native_dry':{state:'idle',attributes:{dashboard:nativeDry}},
  }};
  const html=nativeDryCard.shadowRoot.innerHTML;
  assert.ok(html.includes(label),language+': no mode controller');
  assert.ok(html.includes('native mode commanded'),language+': no mode status');
  assert.ok(html.includes('data-climate-action="pause"'));
  assert.ok(!html.includes('data-hvac-mode='));
}
nativeDry.rooms[0].environment.climate_plan.native_air_mode_actuation={
  status:'paused',reason:'manual_mode_or_unacknowledged_write',
};
nativeDryCard.hass={language:'en',states:{
  'sensor.native_dry':{state:'idle',attributes:{dashboard:nativeDry}},
}};
assert.ok(nativeDryCard.shadowRoot.innerHTML.includes('data-climate-action="resume"'));


// Home and Area edit controls must use real device registry IDs rather than
// guess them from HA area names. This uses the actual SPA navigation route.
(async () => {
  const navigate=[];
  window.history={pushState(_state,_title,path){navigate.push(path);}};
  window.dispatchEvent=()=>true;
  const devices=[
    {id:'home-registered-id', identifiers:[['environment_manager','entry-42']]},
    {id:'kitchen-registered-id', identifiers:[['environment_manager','entry-42_area_kitchen']]},
    {id:'living-registered-id', identifiers:[['environment_manager','entry-42_area_living']]},
    {id:'bedroom-registered-id', identifiers:[['environment_manager','entry-42_area_bedroom']]},
  ];
  const editor=new Card();
  editor.setConfig({entity:'sensor.air_quality_advisor_recommendations'});
  let reads=0;
  const hass={
    language:'el',
    states:{'sensor.air_quality_advisor_recommendations':{
      state:'open',attributes:{dashboard:input}
    }},
    entities:{'sensor.air_quality_advisor_recommendations':{
      device_id:'home-registered-id'
    }},
    callWS:async request=>{
      assert.equal(request.type,'config/device_registry/list');
      reads++;
      return devices;
    },
  };
  editor.hass=hass;
  await new Promise((resolve)=>setImmediate(resolve));
  const html=editor.shadowRoot.innerHTML;
  assert.ok(html.includes('data-edit-home'),'missing home device edit button');
  assert.ok(html.includes('data-edit-area="kitchen"'),'missing kitchen edit button');
  assert.ok(html.includes('data-edit-area="living"'),'missing living edit button');
  assert.ok(html.includes('Ρυθμίσεις χώρου'),'room edit action needs Greek text');
  editor.hass=hass;
  assert.equal(reads,1,'device registry must not be repeatedly fetched on state updates');

  const element=(attrs)=>({getAttribute(name){return attrs[name]??null;}});
  editor.shadowRoot.listeners.click({target:{closest(query){
    return query.includes('data-edit-area') ? element({'data-edit-area':'kitchen'}) : null;
  }}});
  assert.equal(navigate.pop(),'/config/devices/device/kitchen-registered-id');
  editor.shadowRoot.listeners.click({target:{closest(query){
    return query.includes('data-edit-home') ? element({}) : null;
  }}});
  assert.equal(navigate.pop(),'/config/devices/device/home-registered-id');
})().catch((err)=>{console.error(err);process.exitCode=1;});


// Beta34: room-level Environment means observation, not missing managed
// devices. Each managed controller offers its own real HA entity and selector.
{
  const dashboard=JSON.parse(JSON.stringify(input));
  dashboard.rooms=[{
    area_id:'bath',name:'Bathroom',status:'unknown',readings:[
      {entity_id:'sensor.unclassified_input',name:'sensor.unclassified_input',
       metric:'unknown',value:null,unit:'',available:false}
    ],windows:[],
    environment:{climate_plan:{
      status:'advisory',controller:'environment',profile:'home',
      reason:'environment_only_no_hvac',temperature_c:21.5,
      temperature_evidence:{status:'ready',entity_ids:['sensor.bath_temperature']},
    }},
  }];
  const climateId='climate.bath_controller_climate_controller';
  const methodId='select.bath_controller_control_method';
  const climate={state:'off',attributes:{
    area_id:'bath',source_entity_ids:['humidifier.native'],
    control_mode:'manual',friendly_name:'Bath manager',
    supported_features:4+16+128+256,humidity:55,
    min_humidity:20,max_humidity:80,
    controller_status:{status:'within_target_band'},
  }};
  const method={state:'manual',attributes:{
    area_id:'bath',source_entity_ids:['humidifier.native'],
    options:['existing','automatic','manual','pid','off'],
  }};
  const calls=[],popups=[];
  const widget=new Card();
  widget.setConfig({entity:'sensor.beta34'});
  widget.dispatchEvent=(event)=>{popups.push(event);return true;};
  const base={state:'idle',attributes:{dashboard}};
  const snapshots={
    'sensor.beta34':base,[climateId]:climate,[methodId]:method,
    'climate.native':{state:'off',attributes:{fan_modes:['low','high']}},
  };
  widget.hass={language:'el',states:snapshots,
    callService:(domain,service,payload)=>{
      calls.push([domain,service,payload]);return Promise.resolve();
    }};
  let html=widget.shadowRoot.innerHTML;
  assert.ok(html.includes('Παρακολούθηση δωματίου'),'room-only message not translated');
  assert.ok(!html.includes('environment_only_no_hvac'),'raw internal reason must be hidden');
  assert.ok(html.includes('Θερμοκρασία δωματίου'),'verified room temperature shown');
  assert.ok(html.includes('21,5') || html.includes('21.5'));
  assert.ok(html.includes('data-open-climate="'+climateId+'"'));
  assert.ok(html.includes('data-climate-method="'+methodId+'"'));
  assert.ok(html.includes('data-save-climate-target="'+climateId+'"'));
  assert.ok(html.includes('data-target-metric="humidity"'));
  assert.ok(html.includes('data-climate-input="humidity"'));
  assert.ok(!html.includes('metric_unknown'),'unsupported metric must show identity');
  assert.ok(html.includes('sensor.unclassified_input'),'unsupported input not hidden');

  const elt=(attrs, editor=null)=>({
    getAttribute:(key)=>attrs[key]??null,
    closest:(selector)=>selector==='.climate-target-editor' ? editor : null,
  });
  const eventTarget=(match, attrs, editor=null)=>({
    closest:(selector)=>selector.includes(match) ? elt(attrs,editor) : null,
  });
  const previous=global.CustomEvent;
  global.CustomEvent=class {
    constructor(type,opts){this.type=type;this.detail=opts.detail;this.bubbles=opts.bubbles;this.composed=opts.composed;}
  };
  widget.shadowRoot.listeners.click({target:eventTarget('[data-open-climate]',{
    'data-open-climate':climateId,'data-controller-area':'bath',
  })});
  assert.equal(popups.length,1);
  assert.equal(popups[0].type,'hass-more-info');
  assert.deepEqual(popups[0].detail,{entityId:climateId});
  assert.equal(popups[0].composed,true);
  global.CustomEvent=previous;

  const chosenMethod=elt({
    'data-controller-area':'bath','data-climate-method':methodId,
  });
  chosenMethod.value='automatic';
  widget.shadowRoot.listeners.change({target:{
    closest:(selector)=>selector==='[data-climate-method]'
      ? chosenMethod : null,
  }});
  assert.deepEqual(calls[0],['select','select_option',
    {entity_id:methodId,option:'automatic'}]);

  widget.shadowRoot.listeners.click({target:eventTarget(
    '[data-save-climate-target]',{
      'data-controller-area':'bath','data-save-climate-target':climateId,
      'data-target-metric':'humidity',
    },{querySelector:()=>({value:'58'})})});
  assert.deepEqual(calls[1],['climate','set_humidity',
    {entity_id:climateId,humidity:58}]);

  // Wrong area and unsupported numeric targets cannot trigger physical calls.
  widget.shadowRoot.listeners.click({target:eventTarget(
    '[data-save-climate-target]',{
      'data-controller-area':'kitchen','data-save-climate-target':climateId,
      'data-target-metric':'humidity',
    },{querySelector:()=>({value:'57'})})});
  assert.equal(calls.length,2,'reject cross-room entity commands');

  // Independent method changes are reflected even when the room sensor
  // object itself stays unchanged; no hidden all-entity refresh is needed.
  method.state='automatic';
  widget.hass={language:'el',states:snapshots,callService:()=>Promise.resolve()};
  html=widget.shadowRoot.innerHTML;
  assert.ok(!html.includes('data-save-climate-target="'+climateId+'"'));
  assert.ok(html.includes('option value="automatic" selected'));
}

// A temperature-supporting native controller gets a °C manual editor rather
// than a fake humidity control; missing device control entities stay read-only.
{
  const dashboard=JSON.parse(JSON.stringify(input));
  dashboard.rooms=[{area_id:'living',name:'Living',status:'safe',
    readings:[],windows:[],environment:{climate_plan:{
      status:'advisory',controller:'environment',reason:'environment_only_no_hvac',
    }}}];
  const card=new Card();
  card.setConfig({entity:'sensor.beta34_temp'});
  card.hass={language:'en',states:{
    'sensor.beta34_temp':{state:'idle',attributes:{dashboard}},
    'climate.living_manager':{state:'off',attributes:{
      area_id:'living',source_entity_ids:['climate.living_native'],
      control_mode:'manual',friendly_name:'<img src=x onerror=alert(1)>',
      supported_features:1+16+128+256,temperature:20,
      min_temp:5,max_temp:35,
    }},
    'select.living_manager_control_method':{state:'manual',attributes:{
      area_id:'living',source_entity_ids:['climate.living_native'],
      options:['existing','automatic','manual','pid','off'],
    }},
  }};
  assert.ok(card.shadowRoot.innerHTML.includes('data-target-metric="temperature"'));
  assert.ok(!card.shadowRoot.innerHTML.includes('data-target-metric="humidity"'));
  assert.ok(card.shadowRoot.innerHTML.includes('&lt;img src=x'));
  assert.ok(!card.shadowRoot.innerHTML.includes('<img src=x onerror='));
}


// Beta35: an open native method menu must never be replaced by HA's next
// sensor/controller state update. A committed selection then refreshes, and
// typing an unfinished manual target is also preserved until focus leaves it.
(async () => {
  const live = JSON.parse(JSON.stringify(input));
  live.rooms=[{area_id:'bath',name:'Bathroom',status:'unknown',
    readings:[],windows:[],environment:{climate_plan:{
      status:'advisory',controller:'environment',temperature_c:20,
      reason:'environment_only_no_hvac',
    }}}];
  const climateId='climate.beta35_managed';
  const methodId='select.beta35_method';
  const attrs={area_id:'bath',source_entity_ids:['climate.physical_source'],
    control_mode:'manual',supported_features:1,temperature:20,
    min_temp:5,max_temp:35};
  const physical={state:'off',attributes:attrs};
  const selected={state:'manual',attributes:{
    area_id:'bath',source_entity_ids:['climate.physical_source'],
    options:['existing','automatic','manual','pid','off'],
  }};
  const first={state:'idle',attributes:{dashboard:live}};
  const calls=[];
  const card=new Card();
  card.setConfig({entity:'sensor.beta35'});
  const state={language:'en',states:{
    'sensor.beta35':first,[climateId]:physical,[methodId]:selected,
  },callService:(domain,service,data)=>{
    calls.push([domain,service,data]);
    if(domain==='select' && service==='select_option') selected.state=data.option;
    return Promise.resolve();
  }};
  card.hass=state;
  assert.ok(card.shadowRoot.innerHTML.includes('data-climate-method="'+methodId+'"'));
  const originalMarkup=card.shadowRoot.innerHTML;
  const dropdown={
    value:'manual',
    closest(query){return query.includes('data-climate-method') || query.includes('data-climate-input')
      ? this : null;},
    getAttribute(name){
      return {'data-controller-area':'bath','data-climate-method':methodId}[name]??null;
    },
  };
  card.shadowRoot.listeners.focusin({target:dropdown});
  const next={...state,states:{...state.states,
    'sensor.beta35':{state:'idle',attributes:{dashboard:{
      ...live,rooms:[{...live.rooms[0],environment:{
        climate_plan:{...live.rooms[0].environment.climate_plan,temperature_c:22},
      }}],
    }}},
  }};
  card.hass=next;
  assert.equal(card.shadowRoot.innerHTML,originalMarkup,
    'HA state updates must not destroy an open method select');
  assert.equal(card._pendingRender,true,'render must be queued until committed');
  dropdown.value='automatic';
  card.shadowRoot.listeners.change({target:{
    closest(query){return query==='[data-climate-method]' ? dropdown : null;},
  }});
  assert.deepEqual(calls[0],['select','select_option',{
    entity_id:methodId,option:'automatic',
  }]);
  assert.equal(card.shadowRoot.innerHTML,originalMarkup,
    'method picker must remain mounted until the change event is complete');
  await new Promise((resolve)=>setTimeout(resolve,130));
  assert.ok(card.shadowRoot.innerHTML.includes('22 °C') ||
            card.shadowRoot.innerHTML.includes('22°C'));
  assert.ok(card.shadowRoot.innerHTML.includes('option value="automatic" selected'));

  selected.state='manual';
  card.hass={...next,states:{...next.states,
    'sensor.beta35':{state:'idle',attributes:{dashboard:live}},
  }};
  assert.ok(card.shadowRoot.innerHTML.includes('data-climate-input="temperature"'));
  const editingMarkup=card.shadowRoot.innerHTML;
  const pendingTargetInput={value:'25',closest(selector){
    return selector.includes('data-climate-input') || selector.includes('data-climate-method')
      ? this : null;
  }};
  card.shadowRoot.listeners.focusin({target:pendingTargetInput});
  physical.attributes={...physical.attributes,temperature:21};
  card.hass={...next};
  assert.equal(card.shadowRoot.innerHTML,editingMarkup,
    'manual setpoint input must preserve unsaved value while focused');
  card.shadowRoot.listeners.focusout({target:pendingTargetInput});
  await new Promise((resolve)=>setTimeout(resolve,130));
  assert.notEqual(card.shadowRoot.innerHTML,editingMarkup,
    'queued state changes must be applied after editing ends');
})().catch((error)=>{console.error(error);process.exitCode=1;});


// Beta35: a temporary bad dashboard snapshot must not raise a Lovelace card
// exception or poison the update cache. A valid update repairs the same card
// instance without a page refresh.
{
  const card=new Card();
  card.setConfig({entity:'sensor.recover'});
  const bad={version:1,get rooms(){throw new Error('simulated malformed snapshot');}};
  assert.doesNotThrow(()=>{card.hass={language:'en',states:{
    'sensor.recover':{state:'unavailable',attributes:{dashboard:bad}},
  }};});
  assert.equal(card._lastState,null,'failed render must never be cached');
  assert.ok(card.shadowRoot.innerHTML.includes('Retrying automatically'));
  const healthy=JSON.parse(JSON.stringify(input));
  healthy.rooms=[null,healthy.rooms[0]];
  assert.doesNotThrow(()=>{card.hass={language:'en',states:{
    'sensor.recover':{state:'idle',attributes:{dashboard:healthy}},
  }};});
  assert.ok(card.shadowRoot.innerHTML.includes('Kitchen'),
    'the original card instance must recover when valid data returns');
  assert.equal(card._lastRenderError,null);
  assert.equal(card._hasValidRender,true);
}


// Beta35: transient WebSocket exceptions must not permanently block registry
// lookups. The card can recover on the next normal HA update.
(async ()=>{
  const card=new Card();
  card.setConfig({entity:'sensor.device_recovery'});
  const data={version:1,summary:{},rooms:[],outdoor:{}};
  const states={'sensor.device_recovery':{
    state:'idle',attributes:{dashboard:data},
  }};
  let attempts=0;
  const hass={
    language:'en',states,
    entities:{'sensor.device_recovery':{device_id:'real-home-device'}},
    callWS(){
      attempts++;
      if(attempts===1) throw new Error('transient HA websocket disconnect');
      return Promise.resolve([
        {id:'real-home-device',identifiers:[['environment_manager','entry-101']]},
        {id:'real-room-device',identifiers:[['environment_manager','entry-101_area_bath']]},
      ]);
    },
  };
  card.hass=hass;
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(attempts,1);
  assert.equal(card._deviceRegistryLoaded,false);
  assert.ok(card._deviceRegistryNextAttemptAt>Date.now());
  assert.ok(card.shadowRoot.innerHTML.includes('Home Environment Manager'),
    'registry failure must not prevent dashboard rendering');
  // Clock expiration is emulated; production waits for HA's next hass update.
  card._deviceRegistryNextAttemptAt=0;
  card.hass={...hass};
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(attempts,2);
  assert.equal(card._deviceRegistryLoaded,true);
  assert.equal(card._homeDeviceId,'real-home-device');
  assert.equal(card._areaDeviceIds.get('bath'),'real-room-device');
})().catch((error)=>{console.error(error);process.exitCode=1;});


// Beta37: the recommendation sensor contains no full dashboard attributes.
// The card retrieves the complete multi-room snapshot over the authenticated
// read-only Home Assistant WS command, keyed to its small revision marker.
(async ()=>{
  const recommendation='sensor.b37_window_recommendations';
  const meta=(revision)=>({
    dashboard_api:'environment_manager/dashboard',
    dashboard_version:1,dashboard_revision:revision,
    outdoor_safe:true,recommendation_count:0,
  });
  const snapshots=[
    {...input,rooms:[{...input.rooms[0],name:'Kitchen revision 0'}]},
    {...input,rooms:[{...input.rooms[0],name:'Kitchen revision 1'}]},
  ];
  let getCount=0,deviceCount=0;
  const hass={
    language:'en',
    states:{[recommendation]:{state:'idle',attributes:meta(0)}},
    entities:{[recommendation]:{device_id:'home-b37'}},
    callWS:async(request)=>{
      if(request.type==='environment_manager/dashboard'){
        assert.equal(request.entity_id,recommendation);
        return snapshots[getCount++];
      }
      if(request.type==='config/device_registry/list'){
        deviceCount++;
        return [{id:'home-b37',identifiers:[['environment_manager','entry-b37']]}];
      }
      throw new Error('Unexpected dashboard call '+request.type);
    },
  };
  const Card=registered.get('home-environment-manager-card');
  assert.equal(window.customCards.find(c=>c.type==='home-environment-manager-card')
    .getEntitySuggestion(hass,recommendation).config.entity,recommendation);
  const card=new Card();
  card.setConfig({entity:recommendation});
  card.hass=hass;
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(getCount,1);
  assert.ok(card.shadowRoot.innerHTML.includes('Kitchen revision 0'));
  assert.ok(!card._hass.states[recommendation].attributes.dashboard);
  card.hass={...hass};
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(getCount,1,'unchanged recorder token must not re-download dashboard');

  const newer={...hass,states:{
    ...hass.states,[recommendation]:{state:'idle',attributes:meta(1)},
  }};
  card.hass=newer;
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(getCount,2,'new revision must refresh only one WS snapshot');
  assert.ok(card.shadowRoot.innerHTML.includes('Kitchen revision 1'));
  assert.equal(deviceCount,1,'entity registry should not be repeatedly fetched');
})().catch(error=>{console.error(error);process.exitCode=1;});


// Beta37: a transient failed full-dashboard WS request is retryable on the
// same card. An old in-flight reply never overwrites a newly configured sensor.
(async ()=>{
  const eid='sensor.b37_retry';
  let calls=0;
  const meta=(rev)=>({
    dashboard_api:'environment_manager/dashboard',
    dashboard_version:1,dashboard_revision:rev,
  });
  const card=new Card();
  card.setConfig({entity:eid});
  const states={[eid]:{state:'idle',attributes:meta(1)}};
  const hass={language:'el',states,callWS:async request=>{
    if(request.type==='environment_manager/dashboard'){
      calls++;
      if(calls===1) throw new Error('temporary websocket disconnect');
      return {...input,rooms:[{...input.rooms[0],name:'Recovered kitchen'}]};
    }
    if(request.type==='config/device_registry/list')return [];
    throw new Error('Unexpected request');
  }};
  card.hass=hass;
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(calls,1);
  assert.ok(card._dashboardNextAttemptAt>Date.now());
  card._dashboardNextAttemptAt=0; // simulate elapsed retry time
  card.hass={...hass};
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(calls,2);
  assert.ok(card.shadowRoot.innerHTML.includes('Recovered kitchen'));
  assert.equal(card._dashboardData.version,1);
  assert.ok(card._dashboardEntity===eid);
})().catch(error=>{console.error(error);process.exitCode=1;});


// Beta38: unsupported/temporarily unavailable sensors keep source identity,
// but the tile heading must be a short, readable label rather than a huge
// raw sensor.* identifier spilling into neighboring tiles.
{
  const demo=JSON.parse(JSON.stringify(input));
  demo.rooms=[{
    area_id:'badezimmer',name:'Badezimmer',status:'unknown',
    status_detail:'partial_indoor_data',readings:[
      {metric:'humidity',entity_id:'sensor.badezimmer_humidity',
       value:60.9,unit:'%',available:true,exceeded:false,threshold:65},
      {metric:'unknown',entity_id:'sensor.badezimmer_fp300_presence',
       name:'sensor.badezimmer_fp300_presence',
       value:null,unit:'',available:false,exceeded:false},
      {metric:'unknown',entity_id:'sensor.badezimmer_illumination',
       name:'sensor.badezimmer_illumination',
       value:null,unit:'',available:false,exceeded:false},
    ],windows:[],
  }];
  const labelsFrom=(markup)=>[...markup.matchAll(
    /<span class="metric-title" title="[^"]*">([^<]*)<\/span>/g
  )].map(match=>match[1]);
  const demoCard=new Card();
  demoCard.setConfig({entity:'sensor.beta38'});
  demoCard.hass={language:'el',states:{
    'sensor.beta38':{state:'idle',attributes:{dashboard:demo}},
  }};
  const greek=demoCard.shadowRoot.innerHTML;
  const greekTitles=labelsFrom(greek);
  assert.ok(greekTitles.includes('Παρουσία'),JSON.stringify(greekTitles));
  assert.ok(greekTitles.includes('Φωτισμός'),JSON.stringify(greekTitles));
  assert.ok(greekTitles.includes('Υγρασία'),JSON.stringify(greekTitles));
  assert.ok(!greekTitles.some(title=>title.startsWith('sensor.')),
    'unknown source IDs must never be tile headings');
  assert.ok(greek.includes('title="sensor.badezimmer_illumination"'),
    'the exact sensor ID must still be discoverable in title');
  assert.ok(greek.includes('Μη διαθέσιμο'),
    'naming an unsupported metric must never fabricate a value');
  assert.ok(greek.includes('.metric-title{min-width:0;flex:1 1 auto;'),
    'names need a confined, wrapping flex column');
  assert.ok(greek.includes('-webkit-line-clamp:2'),
    'tile titles must not exceed two readable lines');

  demoCard.hass={language:'en',states:{
    'sensor.beta38':{state:'idle',attributes:{dashboard:demo}},
  }};
  const english=labelsFrom(demoCard.shadowRoot.innerHTML);
  assert.ok(english.includes('Illumination'),JSON.stringify(english));
  assert.ok(english.includes('Presence'),JSON.stringify(english));
  demoCard.hass={language:'de',states:{
    'sensor.beta38':{state:'idle',attributes:{dashboard:demo}},
  }};
  assert.ok(labelsFrom(demoCard.shadowRoot.innerHTML).includes('Beleuchtung'));

  // Keep a custom short HA friendly name when present; use a generic compact
  // suffix for unrecognized long identifiers, never reveal full ID as title.
  demo.rooms[0].readings=[{
    metric:'unknown',name:'sensor.long_device_coordinator_super_long_custom_reading',
    entity_id:'sensor.long_device_coordinator_super_long_custom_reading',
    value:null,unit:'',available:false,
  },{
    metric:'unknown',name:'Flow rate',
    entity_id:'sensor.badezimmer_fp300_custom_flow',
    value:null,unit:'',available:false,
  },{
    metric:'unknown',name:'<img src=x onerror=alert(1)>',
    entity_id:'sensor.badezimmer_weird_measurement',
    value:null,unit:'',available:false,
  }];
  demoCard.hass={language:'en',states:{
    'sensor.beta38':{state:'idle',attributes:{dashboard:demo}},
  }};
  const fallbackTitles=labelsFrom(demoCard.shadowRoot.innerHTML);
  assert.ok(fallbackTitles.includes('Custom Reading'));
  assert.ok(fallbackTitles.includes('Flow rate'));
  assert.ok(!demoCard.shadowRoot.innerHTML.includes('<img src=x onerror='),
    'user-supplied malicious or long names must not become executable markup');
}
