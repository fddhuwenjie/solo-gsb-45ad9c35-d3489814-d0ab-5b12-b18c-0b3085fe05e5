async function load() {
  const data = await api("/api/batches");
  const root = document.getElementById("batch-list");
  if (!data.batches.length) {
    root.innerHTML = '<p class="muted">尚无封存批次，请先在「编排」页封存。</p>';
    return;
  }
  root.innerHTML = data.batches.map(b => `
    <div class="card">
      <div class="card-head">
        <strong>#${b.id} ${esc(b.name)}</strong>
        <span class="muted">${esc(b.created_at)} · ${b.question_count} 题 · 勘误 ${b.errata_count} 条</span>
      </div>
      <p class="links">
        <a href="/batches/${b.id}">查看封存内容</a>
        <span class="sep">|</span> A 卷：
        <a href="/batches/${b.id}/print/A/paper" target="_blank">试卷</a>
        <a href="/batches/${b.id}/print/A/sheet" target="_blank">答题卡</a>
        <a href="/batches/${b.id}/print/A/key" target="_blank">答案表</a>
        <span class="sep">|</span> B 卷：
        <a href="/batches/${b.id}/print/B/paper" target="_blank">试卷</a>
        <a href="/batches/${b.id}/print/B/sheet" target="_blank">答题卡</a>
        <a href="/batches/${b.id}/print/B/key" target="_blank">答案表</a>
      </p>
    </div>`).join("");
}

load();
