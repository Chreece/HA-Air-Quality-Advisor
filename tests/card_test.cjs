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
for(const [lang,needle] of [['el','Ποιότητα αέρα'],['de','Luftqualität'],['fr','Qualité de l’air'],['es','Calidad del aire'],['en','Air quality']]) {
  card.hass={language:lang,states:{'sensor.air_quality_advisor_recommendations':{state:'open',attributes:{dashboard:input}}}};
  assert.ok(card.shadowRoot.innerHTML.includes(needle), `missing language ${lang}`);
}

for (const [lang, expected, rtl] of [
  ['it', 'Qualità dell’aria', false],
  ['nl', 'Luchtkwaliteit', false],
  ['pt-BR', 'Qualidade do ar', false],
  ['zh-Hans', '空气质量', false],
  ['zh-Hant', '空氣品質', false],
  ['zh_TW', '空氣品質', false],
  ['ja', '空気質', false],
  ['ko', '공기질', false],
  ['hi', 'वायु गुणवत्ता', false],
  ['ar', 'جودة الهواء', true],
  ['he', 'איכות האוויר', true],
  ['ur', 'ہوا کا معیار', true],
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
  assert.ok(card.shadowRoot.innerHTML.includes('n=2'));
  assert.match(card.shadowRoot.innerHTML, /13[,.]2°C/);
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
  assert.ok(html.includes('n=2') && html.includes('53%'),
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
console.log('Dashboard card frontend tests passed');
