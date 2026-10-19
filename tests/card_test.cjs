'use strict';
const assert = require('node:assert/strict');
const path = require('node:path');
const registered = new Map();
class FakeElement {
  attachShadow() { this.shadowRoot={innerHTML:'', addEventListener(){}};return this.shadowRoot; }
}
global.HTMLElement = FakeElement;
global.customElements = {
  get(name){return registered.get(name);},
  define(name,ctor){registered.set(name,ctor);}
};
global.window = {customCards:[]};
const cardPath = path.resolve(__dirname,'../custom_components/air_quality_advisor/frontend/air-quality-advisor-card.js');
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
