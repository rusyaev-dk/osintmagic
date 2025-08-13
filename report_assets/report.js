
(function(){
  const $ = (sel, el=document)=>el.querySelector(sel);
  const $$ = (sel, el=document)=>Array.from(el.querySelectorAll(sel));
  const data = window.__OSINT_DATA__;

  function fmtDate(s){
    if(!s) return "";
    try{
      const d = new Date(s);
      return d.toISOString().slice(0,10);
    } catch(e){ return s; }
  }

  function confidenceBadge(level){
    if(level.includes("Высок")) return '<span class="badge ok">Высокая уверенность</span>';
    if(level.includes("Сред")) return '<span class="badge warn">Средняя уверенность</span>';
    return '<span class="badge low">Возможное совпадение</span>';
  }

  function card(title, html){
    const el = document.createElement('section'); el.className='card';
    el.innerHTML = `<h2>${title}</h2>${html}`;
    return el;
  }

  function renderCards(){
    const wrap = $('#cards');
    const groups = data.groups;
    const grid = document.createElement('div'); grid.className='grid';
    for (const [section, items] of Object.entries(groups)) {
      const lis = items.map(it => {
        const img = it.og_image ? `<img class="thumb" src="${it.og_image}" alt="">` : '<div class="thumb"></div>';
        const snap = it.saved_path ? `<a class="pill" href="${it.saved_path}" target="_blank">snapshot</a>` : '';
        const conf = (data.confidence && data.confidence[it.url]) ? confidenceBadge(data.confidence[it.url]) : '';
        const copyEmail = it.email ? `<button class="btn copy-btn" data-copy="${it.email}">Скопировать email</button>` : '';
        const openBtn = `<a class="btn" href="${it.url}" target="_blank">Открыть</a>`;
        return `<div class="result">
          ${img}
          <div class="grow">
            <a class="title" href="${it.url}" target="_blank">${it.title || it.url}</a>
            <div class="pill-row"><span class="badge">${section}</span>${conf}</div>
            <div class="snippet">${it.snippet || ''}</div>
            <div class="buttons">${openBtn}${snap}${copyEmail}</div>
            <small class="muted">Провайдер: ${it.provider || '-'} | Активность: ${fmtDate(it.last_activity) || '-'}</small>
          </div>
        </div>`;
      }).join('');
      const sec = card(section, `<div class="grid">${lis}</div>`);
      grid.appendChild(sec);
    }
    wrap.innerHTML = ''; wrap.appendChild(grid);

    document.addEventListener('click', (e)=>{
      const t = e.target.closest('.copy-btn'); if(!t) return;
      navigator.clipboard.writeText(t.dataset.copy || '').then(()=>{
        t.textContent = "Скопировано";
        setTimeout(()=>t.textContent = "Скопировать email", 1200);
      });
    });
  }

  function renderTimeline(){
    const cont = $('#timeline');
    cont.innerHTML = '<svg width="100%" height="100%"></svg>';
    const svg = $('svg', cont);
    const pad = {l:30,r:20,t:20,b:30};
    const w = svg.clientWidth - pad.l - pad.r;
    const h = svg.clientHeight - pad.t - pad.b;
    const g = document.createElementNS('http://www.w3.org/2000/svg','g');
    g.setAttribute('transform', `translate(${pad.l},${pad.t})`);
    svg.appendChild(g);

    const items = [];
    for(const [section, arr] of Object.entries(data.groups)){
      for(const it of arr){
        const ts = it.last_activity || it.created_at; if(!ts) continue;
        const d = new Date(ts);
        if(!isFinite(d)) continue;
        items.push({date:d, section, title: it.title || it.url});
      }
    }
    items.sort((a,b)=>a.date-b.date);
    if(items.length === 0){
      g.innerHTML = '<text x="0" y="24" fill="#9aa0a6">Нет данных для таймлайна</text>';
      return;
    }
    const min = items[0].date, max = items[items.length-1].date;
    const x = d => (d - min) / (max - min || 1) * w;
    items.forEach((it,i)=>{
      const cx = x(it.date), cy = 20 + (i % Math.max(1, Math.floor(h/40))) * 20;
      const circle = document.createElementNS('http://www.w3.org/2000/svg','circle');
      circle.setAttribute('cx', cx); circle.setAttribute('cy', cy); circle.setAttribute('r', 4);
      circle.setAttribute('fill', '#8b5cf6');
      circle.addEventListener('mouseenter', ()=>{ circle.setAttribute('r', 6)});
      circle.addEventListener('mouseleave', ()=>{ circle.setAttribute('r', 4)});
      g.appendChild(circle);
    });
  }

  function renderHeatmap(){
    const cont = $('#heatmap');
    cont.innerHTML = '<svg width="100%" height="100%"></svg>';
    const svg = $('svg', cont);
    const pad = {l:30,r:10,t:20,b:30};
    const w = svg.clientWidth - pad.l - pad.r;
    const h = svg.clientHeight - pad.t - pad.b;
    const g = document.createElementNS('http://www.w3.org/2000/svg','g');
    g.setAttribute('transform', `translate(${pad.l},${pad.t})`);
    svg.appendChild(g);

    const items = (data.activity_heatmap || []);
    if(items.length === 0){
      g.innerHTML = '<text x="0" y="24" fill="#9aa0a6">Нет данных активности</text>';
      return;
    }
    const years = Array.from(new Set(items.map(it=>it.y))).sort();
    const months = [1,2,3,4,5,6,7,8,9,10,11,12];
    const cellW = Math.max(12, Math.floor(w / months.length) - 2);
    const cellH = Math.max(12, Math.floor(h / years.length) - 2);
    const valueMax = Math.max(...items.map(it=>it.v), 1);

    items.forEach(it=>{
      const x = (it.m-1) * (cellW+2);
      const y = (years.indexOf(it.y)) * (cellH+2);
      const val = it.v / valueMax;
      const col = `rgba(139,92,246, ${0.2 + val*0.8})`;
      const rect = document.createElementNS('http://www.w3.org/2000/svg','rect');
      rect.setAttribute('x', x); rect.setAttribute('y', y);
      rect.setAttribute('width', cellW); rect.setAttribute('height', cellH);
      rect.setAttribute('fill', col); rect.setAttribute('rx', 4);
      g.appendChild(rect);
    });
  }

  // lightweight force graph
  function renderGraph(){
    const cont = $('#graph');
    cont.innerHTML = '';
    const canvas = document.createElement('canvas');
    canvas.width = cont.clientWidth; canvas.height = cont.clientHeight;
    cont.appendChild(canvas);
    const ctx = canvas.getContext('2d');

    // Build nodes/edges
    const nodes = []; const edges = [];
    const personId = `person:${data.subject}`;
    nodes.push({id:personId, label:data.subject, type:'person', fx:canvas.width/2, fy:canvas.height/2});

    const map = new Map();
    function addNode(n){ if(!map.has(n.id)){ map.set(n.id,n); nodes.push(n);} }
    function addEdge(a,b,label){ edges.push({a,b,label}); }

    for(const [section, arr] of Object.entries(data.groups)){
      for(const it of arr){
        const pid = `profile:${it.url}`;
        addNode({id:pid, label: it.title || it.url, type:'profile'});
        addEdge(personId, pid, section);
        if(it.email){ const id = `email:${it.email}`; addNode({id, label:it.email, type:'email'}); addEdge(pid,id,"email"); }
        if(it.username){ const id = `user:${it.username}`; addNode({id, label:it.username, type:'user'}); addEdge(pid,id,"username"); }
        if(it.phone){ const id = `phone:${it.phone}`; addNode({id, label:it.phone, type:'phone'}); addEdge(pid,id,"phone"); }
      }
    }

    // simple force sim
    const pos = new Map(nodes.map(n=>[n.id,{x: Math.random()*canvas.width, y: Math.random()*canvas.height, vx:0, vy:0}]));
    const center = {x: canvas.width/2, y: canvas.height/2};
    function step(){
      // forces
      nodes.forEach(n=>{
        const p = pos.get(n.id);
        // center pull
        p.vx += (center.x - p.x) * 0.0005;
        p.vy += (center.y - p.y) * 0.0005;
      });
      // link force
      edges.forEach(e=>{
        const a = pos.get(e.a), b = pos.get(e.b);
        const dx = b.x - a.x, dy = b.y - a.y;
        const dist = Math.hypot(dx,dy) || 1;
        const k = 0.0008 * (dist - 120);
        const fx = k * dx, fy = k * dy;
        a.vx += fx; a.vy += fy; b.vx -= fx; b.vy -= fy;
      });
      // charge
      for(let i=0;i<nodes.length;i++){
        for(let j=i+1;j<nodes.length;j++){
          const a = pos.get(nodes[i].id), b = pos.get(nodes[j].id);
          const dx = b.x - a.x, dy = b.y - a.y;
          const dist2 = dx*dx + dy*dy + 0.01;
          const f = 6000 / dist2;
          const fx = f * dx, fy = f * dy;
          a.vx -= fx; a.vy -= fy; b.vx += fx; b.vy += fy;
        }
      }
      // integrate + damping
      pos.forEach(p=>{ p.x += p.vx; p.y += p.vy; p.vx *= 0.85; p.vy *= 0.85; });
      // draw
      ctx.clearRect(0,0,canvas.width,canvas.height);
      ctx.strokeStyle = "#2a3247"; ctx.lineWidth = 1;
      edges.forEach(e=>{
        const a = pos.get(e.a), b = pos.get(e.b);
        ctx.beginPath(); ctx.moveTo(a.x,a.y); ctx.lineTo(b.x,b.y); ctx.stroke();
      });
      nodes.forEach(n=>{
        const p = pos.get(n.id);
        let r = 6, fill = "#8b5cf6";
        if(n.type==='person'){ r = 12; fill = "#22c55e"; }
        else if(n.type==='email'){ fill = "#60a5fa"; }
        else if(n.type==='phone'){ fill = "#f59e0b"; }
        else if(n.type==='user'){ fill = "#ef4444"; }
        ctx.beginPath(); ctx.arc(p.x,p.y,r,0,Math.PI*2); ctx.fillStyle=fill; ctx.fill();
      });
      requestAnimationFrame(step);
    }
    step();
  }

  function bootstrap(){
    $('#subject').textContent = data.subject;
    $('#meta').textContent = `${data.city||''} ${data.country||''}`.trim();
    renderCards(); renderTimeline(); renderHeatmap(); renderGraph();
  }
  bootstrap();
})();