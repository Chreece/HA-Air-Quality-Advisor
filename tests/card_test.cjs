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
console.log('Dashboard card frontend tests passed');
