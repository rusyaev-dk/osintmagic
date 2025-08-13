(function(){
  const root = document.documentElement;
  const themeToggle = document.getElementById('themeToggle');
  const printBtn = document.getElementById('printBtn');
  const searchInput = document.getElementById('searchInput');
  const tabs = document.querySelectorAll('.tab');
  const panels = document.querySelectorAll('.tab-panel');

  themeToggle?.addEventListener('click', () => {
    const next = root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
    root.setAttribute('data-theme', next);
  });
  printBtn?.addEventListener('click', () => window.print());

  tabs.forEach(btn => btn.addEventListener('click', () => {
    tabs.forEach(b => b.classList.remove('active'));
    panels.forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    const id = btn.getAttribute('data-tab');
    document.getElementById(id)?.classList.add('active');
  }));

  document.querySelectorAll('.copy').forEach(btn => {
    btn.addEventListener('click', async () => {
      await navigator.clipboard.writeText(btn.getAttribute('data-copy') || '');
      btn.textContent = 'Скопировано';
      setTimeout(() => (btn.textContent = 'Копировать'), 1200);
    });
  });

  // Фильтрация карточек
  searchInput?.addEventListener('input', () => {
    const q = (searchInput.value || '').toLowerCase();
    document.querySelectorAll('[data-filter]').forEach(el => {
      const ok = el.getAttribute('data-filter').toLowerCase().includes(q);
      el.style.display = ok ? '' : 'none';
    });
  });

  // Граф
  fetch('data.json').then(r => r.json()).then(data => {
    const container = document.getElementById('graphContainer');
    if(!container) return;
    const nodes = new vis.DataSet((data.graph.nodes || []).map(n => ({id:n.id, label:n.label || n.id})));
    const edges = new vis.DataSet((data.graph.edges || []).map(e => ({from:e.from, to:e.to})));
    new vis.Network(container, {nodes, edges}, {interaction:{hover:true}, physics:{stabilization:true}});
  });

  // Простая heatmap на canvas
  fetch('data.json').then(r=>r.json()).then(data => {
    const cvs = document.getElementById('heatmap');
    if(!cvs) return;
    const ctx = cvs.getContext('2d');
    const W = cvs.width, H = cvs.height;
    const days = 7, hours = 24;
    const cellW = Math.floor(W / hours);
    const cellH = Math.floor(H / days);
    const counts = Array.from({length: days}, () => Array(hours).fill(0));
    (data.activity || []).forEach(a => {
      const d = new Date(a.ts);
      const day = (d.getDay() + 6) % 7; // Mon=0
      counts[day][d.getHours()] += 1;
    });
    const max = counts.flat().reduce((m,v)=>Math.max(m,v), 1);

    for(let y=0; y<days; y++){
      for(let x=0; x<hours; x++){
        const v = counts[y][x] / max;
        const c = Math.floor(255 * v);
        ctx.fillStyle = `rgb(${c}, ${Math.floor(200*c/255)}, 64)`;
        ctx.fillRect(x*cellW, y*cellH, cellW-1, cellH-1);
      }
    }
  });
})();
