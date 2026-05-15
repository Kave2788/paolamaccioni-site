#!/usr/bin/env node
const http = require('http');
const fs   = require('fs');
const path = require('path');

const ROOT   = __dirname;
const SERIES = ['struttura-tensione', 'forma-organica'];
const PORT   = 3030;

function getWorks() {
  const result = [];
  for (const serie of SERIES) {
    const serieDir = path.join(ROOT, serie);
    if (!fs.existsSync(serieDir)) continue;
    const dirs = fs.readdirSync(serieDir)
      .filter(d => {
        try { return fs.statSync(path.join(serieDir, d)).isDirectory() && !['canvas','thumb'].includes(d); }
        catch { return false; }
      }).sort();
    for (const work of dirs) {
      const workDir = path.join(serieDir, work);
      const files = fs.readdirSync(workDir)
        .filter(f => /\.(jpg|jpeg|png|webp)$/i.test(f))
        .filter(f => { try { return fs.statSync(path.join(workDir, f)).isFile(); } catch { return false; } })
        .sort();
      if (files.length) result.push({ serie, work, files });
    }
  }
  return result;
}

function setFront(serie, work, filename) {
  const workDir   = path.join(ROOT, serie, work);
  const targetNum = path.basename(filename, path.extname(filename));
  if (targetNum === '01') return { ok: true };

  for (const sub of [workDir, path.join(workDir, 'canvas'), path.join(workDir, 'thumb')]) {
    if (!fs.existsSync(sub)) continue;
    const entries = fs.readdirSync(sub).filter(f => {
      try { return fs.statSync(path.join(sub, f)).isFile(); } catch { return false; }
    });
    const f01  = entries.find(f => path.basename(f, path.extname(f)) === '01');
    const fTgt = entries.find(f => path.basename(f, path.extname(f)) === targetNum);
    if (!fTgt) continue;
    const tmp = path.join(sub, `__tmp${Date.now()}${path.extname(fTgt)}`);
    if (f01) {
      fs.renameSync(path.join(sub, fTgt), tmp);
      fs.renameSync(path.join(sub, f01), path.join(sub, targetNum + path.extname(f01)));
      fs.renameSync(tmp, path.join(sub, '01' + path.extname(fTgt)));
    } else {
      fs.renameSync(path.join(sub, fTgt), path.join(sub, '01' + path.extname(fTgt)));
    }
  }
  return { ok: true };
}

const HTML = `<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Foto Frontale</title>
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{--bg:#0e0d0c;--bg2:#161514;--border:#2a2825;--text:#e8e0d6;--text2:#8a8078;--gold:#c9a84c}
body{background:var(--bg);color:var(--text);font-family:Georgia,serif;padding:2.5rem 2rem 5rem;max-width:1300px;margin:0 auto}
h1{font-size:1.4rem;font-weight:400;margin-bottom:.3rem}
.sub{color:var(--text2);font-style:italic;font-size:.85rem;line-height:1.6;margin-bottom:3rem}
.serie-lbl{font-size:.6rem;letter-spacing:5px;text-transform:uppercase;font-family:sans-serif;color:var(--text2);margin:3rem 0 1rem;padding-bottom:.6rem;border-bottom:1px solid var(--border)}
.work{margin-bottom:1.25rem;background:var(--bg2);border:1px solid var(--border);padding:1.1rem 1.4rem}
.work-name{font-size:.62rem;letter-spacing:3.5px;text-transform:uppercase;font-family:sans-serif;color:var(--text2);margin-bottom:.9rem}
.photos{display:flex;flex-wrap:wrap;gap:5px}
.pw{position:relative;cursor:pointer;flex-shrink:0}
.pw img{width:105px;height:105px;object-fit:cover;display:block;border:2px solid transparent;opacity:.6;transition:opacity .2s,border-color .2s}
.pw:hover img{opacity:1}
.pw.front img{border-color:var(--gold);opacity:1}
.pw.sel img{border-color:#fff;opacity:1}
.badge{position:absolute;top:3px;left:3px;background:var(--gold);color:#000;font-size:6px;letter-spacing:1.5px;text-transform:uppercase;font-family:sans-serif;padding:2px 5px;font-weight:700;pointer-events:none}
.num{position:absolute;bottom:3px;right:3px;background:rgba(0,0,0,.75);color:#fff;font-size:8px;font-family:sans-serif;padding:1px 4px;pointer-events:none}
.action{margin-top:.9rem;display:none;align-items:center;gap:.9rem}
.action.show{display:flex}
.btn{background:var(--text);color:var(--bg);border:none;padding:.5rem 1.1rem;font-size:8px;letter-spacing:3px;text-transform:uppercase;font-family:sans-serif;cursor:pointer;transition:opacity .2s}
.btn:hover{opacity:.8}
.btn-sec{background:transparent;border:1px solid var(--border);color:var(--text2)}
.msg{font-size:.8rem;font-style:italic;color:var(--text2)}
.ok{color:#6ee7a8}.err{color:#ff8a8a}
</style>
</head>
<body>
<h1>Foto frontale — Paola Maccioni</h1>
<p class="sub">Cornice dorata = copertina attuale (01). Clicca un'altra foto e poi "Imposta frontale".</p>
<div id="app">Caricamento…</div>
<script>
var works=[], sel={};

function load(){
  fetch('/works').then(function(r){return r.json();}).then(function(d){works=d;render();});
}

function render(){
  var html='', lastSerie=null;
  for(var i=0;i<works.length;i++){
    var w=works[i], k=w.serie+'|'+w.work;
    if(w.serie!==lastSerie){
      html+='<div class="serie-lbl">'+h(w.serie.replace(/-/g,' '))+'</div>';
      lastSerie=w.serie;
    }
    var curSel=sel[k]||null;
    var front01=null;
    for(var j=0;j<w.files.length;j++){
      if(w.files[j].replace(/\.[^.]+$/,'')===('01')){front01=w.files[j];break;}
    }
    html+='<div class="work"><div class="work-name">'+h(w.work.replace(/-/g,' '))+'</div><div class="photos">';
    for(var j=0;j<w.files.length;j++){
      var f=w.files[j], num=f.replace(/\.[^.]+$/,'');
      var isFront=num==='01', isSel=curSel===f;
      html+='<div class="pw'+(isFront?' front':'')+(isSel?' sel':'')+'" data-k="'+h(k)+'" data-f="'+h(f)+'" onclick="pick(this)">';
      html+='<img src="/img/'+h(w.serie)+'/'+h(w.work)+'/'+h(f)+'" loading="lazy">';
      if(isFront) html+='<span class="badge">&#x2756; fronte</span>';
      html+='<span class="num">'+h(num)+'</span>';
      html+='</div>';
    }
    html+='</div>';
    var showAct=curSel&&curSel!==front01;
    html+='<div class="action'+(showAct?' show':'')+'" id="act'+i+'">';
    html+='<button class="btn" data-i="'+i+'" onclick="apply(this)">Imposta frontale</button>';
    html+='<button class="btn btn-sec" data-i="'+i+'" onclick="cancel(this)">Annulla</button>';
    html+='<span class="msg" id="msg'+i+'"></span>';
    html+='</div></div>';
  }
  document.getElementById('app').innerHTML=html;
}

function h(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}

function pick(el){
  var k=el.dataset.k, f=el.dataset.f;
  var num=f.replace(/\.[^.]+$/,'');
  if(num==='01'||sel[k]===f){sel[k]=null;}else{sel[k]=f;}
  render();
}

function cancel(btn){
  var i=parseInt(btn.dataset.i);
  var k=works[i].serie+'|'+works[i].work;
  sel[k]=null; render();
}

function apply(btn){
  var i=parseInt(btn.dataset.i), w=works[i];
  var k=w.serie+'|'+w.work, filename=sel[k];
  if(!filename)return;
  var msgEl=document.getElementById('msg'+i);
  msgEl.textContent='Salvataggio…'; msgEl.className='msg';
  fetch('/set-front',{
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({serie:w.serie,work:w.work,filename:filename})
  }).then(function(r){return r.json();}).then(function(j){
    if(j.ok){
      sel[k]=null;
      fetch('/works').then(function(r){return r.json();}).then(function(d){works=d;render();});
    }else{
      msgEl.textContent='Errore: '+(j.error||'?'); msgEl.className='msg err';
    }
  }).catch(function(){
    msgEl.textContent='Errore di rete.'; msgEl.className='msg err';
  });
}

load();
</script>
</body>
</html>`;

http.createServer(function(req, res) {
  if (req.method === 'GET' && req.url === '/') {
    res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
    return res.end(HTML);
  }
  if (req.method === 'GET' && req.url === '/works') {
    try {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(getWorks()));
    } catch(e) { res.writeHead(500); res.end(); }
    return;
  }
  if (req.method === 'GET' && req.url.startsWith('/img/')) {
    var rel = decodeURIComponent(req.url.slice(5));
    var abs = path.resolve(ROOT, rel);
    if (!abs.startsWith(ROOT + path.sep) || !SERIES.some(function(s){ return rel.startsWith(s+'/'); })) {
      res.writeHead(403); return res.end();
    }
    if (!fs.existsSync(abs)) { res.writeHead(404); return res.end(); }
    var ext  = path.extname(abs).toLowerCase();
    var mime = { '.jpg':'image/jpeg', '.jpeg':'image/jpeg', '.png':'image/png', '.webp':'image/webp' };
    res.writeHead(200, { 'Content-Type': mime[ext] || 'application/octet-stream' });
    return fs.createReadStream(abs).pipe(res);
  }
  if (req.method === 'POST' && req.url === '/set-front') {
    var body = '';
    req.on('data', function(d){ body += d; });
    req.on('end', function() {
      try {
        console.log('POST /set-front body:', body);
        var p = JSON.parse(body);
        console.log('Parsed:', p);
        if (!SERIES.includes(p.serie)) throw new Error('Serie non valida: ' + p.serie);
        var r = setFront(p.serie, p.work, p.filename);
        console.log('Result:', r);
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify(r));
      } catch(e) {
        console.error('Error:', e.message);
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ ok: false, error: e.message }));
      }
    });
    return;
  }
  res.writeHead(404); res.end();
}).listen(PORT, '127.0.0.1', function() {
  console.log('Reorder tool → http://localhost:' + PORT);
});
