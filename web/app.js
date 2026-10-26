'use strict';
const $ = (id) => document.getElementById(id);
const form = $('config-form');
let defaults, catalog, lastPreview, timer, previousName = 'mi-app';
const fragment = new URLSearchParams(location.hash.slice(1));
if (fragment.get('token')) {
  sessionStorage.setItem('createapp-token', fragment.get('token'));
  history.replaceState(null, '', location.pathname);
}
const token = sessionStorage.getItem('createapp-token') || '';

async function api(path, body) {
  const response = await fetch(path, {
    method: body === undefined ? 'GET' : 'POST',
    headers: {'X-CreateApp-Token': token, ...(body === undefined ? {} : {'Content-Type': 'application/json'})},
    ...(body === undefined ? {} : {body: JSON.stringify(body)})
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'No se pudo completar la solicitud.');
  return data;
}

function values() {
  const data = new FormData(form);
  const config = {...defaults};
  for (const key of Object.keys(defaults)) {
    if (key === 'packs') config.packs = data.getAll('pack');
    else if (key === 'agents') config.agents = data.getAll('extra_agent');
    else if (key === 'skills') config.skills = data.has('custom_skills') ? data.getAll('skill') : null;
    else if (typeof defaults[key] === 'boolean') config[key] = data.has(key);
    else config[key] = data.get(key) ?? defaults[key];
  }
  config.agents = [...new Set([config.agent, ...config.agents])];
  return config;
}

function setField(name, value) {
  const field = form.elements.namedItem(name);
  if (typeof value === 'boolean') field.checked = value;
  else field.value = value;
}

function updateSummary() {
  const c = values();
  syncIndividualSkills(c);
  $('summary-name').textContent = c.name || 'Tu proyecto';
  $('summary-stack').textContent = form.elements.stack.selectedOptions[0].textContent;
  $('summary-agent').textContent = catalog.agents[c.agent];
  $('summary-coordinator').textContent = {superpowers:'Superpowers', matt:'Matt Pocock', simple:'Proceso simple'}[c.coordinator];
  $('owner-process').textContent = $('summary-coordinator').textContent;
  $('summary-packs').textContent = `${c.packs.length} seleccionados`;
  $('summary-tests').textContent = c.testing === 'strict' ? 'TDD estricto' : 'Proporcionales';
  const labels = {ponytail:'Ponytail', uiux:'UI UX Pro Max', anthropic:'Anthropic', addy:'Addy Osmani'};
  const rows = document.querySelectorAll('.responsibilities p');
  Object.entries(labels).forEach(([id, name], i) => rows[i + 1].lastElementChild.textContent = c.packs.includes(id) ? name : 'Desactivado');
  lastPreview = null;
}

function notice(parent, message, error = false) {
  const el = document.createElement('div');
  el.className = 'alert' + (error ? ' error' : '');
  el.textContent = message;
  parent.append(el);
}

function showError(message) {
  $('fatal').textContent = message;
  $('fatal').hidden = false;
  $('fatal').scrollIntoView({block:'center'});
}

function reveal(id) {
  for (const name of ['layout','review','progress']) $(name).hidden = name !== id;
  $('fatal').hidden = true;
  $(id).focus?.();
  if (id !== 'layout') $(id).scrollIntoView({block:'start'});
}

async function preview() {
  if (!form.reportValidity()) return;
  const button = $('preview-button');
  button.disabled = true;
  try {
    const p = await api('/api/preview', values());
    lastPreview = p;
    $('review-target').textContent = p.target;
    $('review-notices').replaceChildren();
    for (const warning of p.warnings) notice($('review-notices'), warning);
    if (p.conflicts.length) notice($('review-notices'), 'Se conservaron los archivos existentes. Revisá los archivos de configuración en conflicto: ' + p.conflicts.join(', '), true);
    $('review-roles').replaceChildren();
    for (const role of p.roles) {const chip = document.createElement('span');chip.textContent = 'ca-' + role;$('review-roles').append(chip);}
    $('review-files').replaceChildren();
    for (const file of p.files.filter(x => !x.includes('/skills/'))) {const li = document.createElement('li');li.textContent = file;$('review-files').append(li);}
    $('review-sources').replaceChildren();
    for (const source of p.sources) {
      const li = document.createElement('li'), title = document.createElement('strong'), sha = document.createElement('small');
      title.textContent = source.repo;
      sha.textContent = source.commit.slice(0,12) + ` · ${source.files} archivos`;
      li.append(title,sha);$('review-sources').append(li);
    }
    const size = p.sources.reduce((n,s)=>n+s.bytes,0);
    $('review-total').textContent = `${p.roles.length} perfiles · ${(size/1024/1024).toFixed(1)} MB de fuentes`;
    $('create-button').disabled = p.conflicts.length > 0;
    $('create-button').textContent = 'Aplicar configuración';
    reveal('review');
  } catch (e) {showError(e.message);} finally {button.disabled = false;}
}

async function poll() {
  try {
    const s = await api('/api/status');
    $('progress-log').textContent = s.messages.join('\n');
    $('progress-message').textContent = s.messages.at(-1) || 'Preparando…';
    if (s.state === 'running') timer = setTimeout(poll, 700);
    else if (s.state === 'done') {
      $('progress-title').textContent = 'Tu proyecto está preparado.';
      $('progress-message').textContent = s.result.target;
      $('success-next').hidden = false;
      $('another-button').textContent = 'Configurar otro proyecto';
    } else if (s.state === 'error') {
      $('progress-title').textContent = 'No se pudo completar.';
      $('progress-message').textContent = s.error;
      $('success-next').hidden = false;
      $('success-next').querySelector('p').textContent = 'Revisá el error. Las descargas se guardan en caché para reintentar. La preparación evita dejar un proyecto parcial si falla una descarga.';
      $('another-button').textContent = 'Volver a la configuración';
    }
  } catch (e) {
    $('progress-title').textContent = 'Se perdió la conexión local.';
    $('progress-message').textContent = 'Comprobá que la terminal de CreateApp siga abierta y recargá esta página para consultar el estado.';
  }
}

async function create() {
  if (!lastPreview) return;
  $('create-button').disabled = true;
  try {
    await api('/api/initialize', {config:lastPreview.config, config_hash:lastPreview.config_hash});
    $('success-next').hidden = true;
    $('success-next').querySelector('p').innerHTML = 'Leé <strong>.createapp/START_HERE.md</strong> en la carpeta del proyecto. Ahí tenés los comandos y el mensaje para empezar con tu asistente.';
    $('progress-title').textContent = 'Las piezas, en su lugar.';
    $('progress-log').textContent = '';
    reveal('progress');
    await poll();
  } catch (e) {showError(e.message);$('create-button').disabled=false;}
}


function buildIndividualOptions() {
  for (const [value,text] of Object.entries(catalog.agents)) {
    const label=document.createElement('label');label.className='check-line';
    const input=document.createElement('input');input.type='checkbox';input.name='extra_agent';input.value=value;input.checked=defaults.agents.includes(value);
    const span=document.createElement('span');span.textContent=text;
    label.append(input,span);$('extra-agents').append(label);
  }
  for (const [name,skill] of Object.entries(catalog.skills)) {
    const label=document.createElement('label');label.className='check-line';
    const input=document.createElement('input');input.type='checkbox';input.name='skill';input.value=name;input.checked=true;
    const span=document.createElement('span'),strong=document.createElement('strong'),small=document.createElement('small');strong.textContent='ca-'+name;small.textContent=skill.description;span.append(strong,small);
    label.append(input,span);$('individual-skills').append(label);
  }
}
function syncIndividualSkills(c) {
  const stack=c.stack==='auto'?catalog.detected_stack:c.stack;
  const enabled=new Set(c.packs);
  if(c.vercel_react&&['react-vite','nextjs'].includes(stack))enabled.add('vercel_react');
  if(c.vercel_web&&['react-vite','nextjs','web'].includes(stack))enabled.add('vercel_web');
  if(c.vercel_composition&&['react-vite','nextjs'].includes(stack))enabled.add('vercel_composition');
  if(c.database==='postgres')enabled.add('postgres');
  if(stack==='nextjs')enabled.add('next');
  for(const input of form.querySelectorAll('[name=skill]')) {
    let applies=enabled.has(catalog.skills[input.value].pack);
    if(['workflow','debug'].includes(input.value)&&c.coordinator!=='superpowers')applies=false;
    if(input.value==='matt-workflow'&&c.coordinator!=='matt')applies=false;
    input.disabled=!applies;input.closest('label').hidden=!applies;
  }
  for(const input of form.querySelectorAll('[name=extra_agent]')) {
    input.disabled=input.value===c.agent;
    if(input.disabled)input.checked=true;
  }
}

async function boot() {
  try {
    catalog = await api('/api/catalog');defaults = catalog.defaults;
    for (const [value, text] of Object.entries(catalog.agents)) {
      const option = document.createElement('option');option.value=value;option.textContent=text;form.elements.agent.append(option);
    }
    buildIndividualOptions();
    for (const pack of catalog.packs) {
      const label = document.createElement('label');label.className='pack';
      const input = document.createElement('input');input.type='checkbox';input.name='pack';input.value=pack.id;input.checked=pack.default;
      const body = document.createElement('span');body.className='pack-body';
      const name = document.createElement('span');name.className='pack-name';name.textContent=pack.name;
      const detail = document.createElement('small');detail.textContent=pack.detail;
      body.append(name,detail);
      const badge = document.createElement('span');badge.className='badge'+(pack.default?'':' optional');badge.textContent=pack.default?'De base':'Opcional';
      label.append(input,body,badge);$('packs').append(label);
    }
    for (const [name,value] of Object.entries(defaults)) if (!['packs','agents','skills'].includes(name)) setField(name,value);
    $('workspace').textContent = 'Dentro de: ' + catalog.workspace + ' · carpeta existente; usá . para el proyecto actual.';
    form.addEventListener('input', updateSummary);
    form.addEventListener('change', event => {
      const target = event.target;
      if (target.name === 'mode') {
        const mode = target.value;
        setField('testing',mode==='rigorous'?'strict':'balanced');
        setField('autonomy',mode==='fast'?'autonomous':mode==='rigorous'?'guided':'milestones');
        setField('parallel',false);
      }
      if (target.name === 'coordinator' && target.value === 'matt') form.querySelector('[name=pack][value=matt]').checked=true;
      if (target.name === 'coordinator' && target.value === 'superpowers') form.querySelector('[name=pack][value=superpowers]').checked=true;
      updateSummary();
    });
    form.elements.name.addEventListener('input', () => {
      if (form.elements.directory.value===previousName) form.elements.directory.value=form.elements.name.value;
      previousName=form.elements.name.value;
    });
    form.addEventListener('submit',e=>{e.preventDefault();preview();});
    $('preview-button').addEventListener('click',preview);
    $('create-button').addEventListener('click',create);
    $('edit-button').addEventListener('click',()=>reveal('layout'));
    $('another-button').addEventListener('click',()=>{clearTimeout(timer);reveal('layout');});
    $('export-button').addEventListener('click',()=>{
      if (!form.reportValidity()) return;
      const blob=new Blob([JSON.stringify(values(),null,2)+'\n'],{type:'application/json'}), url=URL.createObjectURL(blob), link=document.createElement('a');
      link.href=url;link.download='createapp-config.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
    });
    updateSummary();$('layout').hidden=false;
    const status=await api('/api/status');
    if (status.state==='running'||status.state==='done'||status.state==='error') {reveal('progress');await poll();}
  } catch(e) {showError(e.message);}
}
boot();
