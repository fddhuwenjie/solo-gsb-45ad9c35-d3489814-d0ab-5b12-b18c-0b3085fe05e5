let DETAIL = null;

async function load() {
  DETAIL = await api("/api/batches/" + window.BATCH_ID);
  renderHeader();
  for (const v of ["A", "B"]) renderVersion(v);
  renderErrata();
}

function renderHeader() {
  document.getElementById("batch-title").textContent =
    `${DETAIL.name}（批次 #${DETAIL.id}）`;
  document.getElementById("batch-meta").textContent = `封存时间：${DETAIL.created_at}`;
  const parts = [];
  for (const v of ["A", "B"]) {
    parts.push(
      `${v} 卷：<a href="/batches/${DETAIL.id}/print/${v}/paper" target="_blank">试卷</a>` +
      ` <a href="/batches/${DETAIL.id}/print/${v}/sheet" target="_blank">答题卡</a>` +
      ` <a href="/batches/${DETAIL.id}/print/${v}/key" target="_blank">答案表</a>`
    );
  }
  document.getElementById("print-links").innerHTML = parts.join("　");
}

function renderVersion(v) {
  const items = DETAIL.versions[v];
  const root = document.getElementById("version-" + v);
  root.innerHTML = items.map(it => {
    const opts = it.options.map(o => `
      <li class="${o.option_id === it.current_option_id ? "correct" : ""}">
        <span class="letter">${o.letter}</span>
        <span class="opt-text">${esc(o.text)}</span>
        <code>${esc(o.option_id)}</code>
        ${o.option_id === it.current_option_id ? '<span class="tag">当前答案</span>' : ""}
      </li>`).join("");
    const corr = it.corrected
      ? `<span class="tag warn">已勘误：${it.original_letter} → ${it.current_letter}</span>`
      : "";
    return `
    <div class="card">
      <div class="card-head">
        <strong>第 ${it.seq} 题</strong> <code>${esc(it.question_id)}</code> ${corr}
      </div>
      <p class="stem">${esc(it.stem)}</p>
      <ul class="opts">${opts}</ul>
    </div>`;
  }).join("") || '<p class="muted">无题目</p>';
}

function renderErrata() {
  const root = document.getElementById("errata-list");
  if (!DETAIL.errata.length) {
    root.innerHTML = '<p class="muted">本批次暂无勘误。</p>';
    return;
  }
  root.innerHTML = DETAIL.errata.map(e => {
    const dets = e.details
      .map(d => `${d.version}卷第${d.seq}题：${d.old_letter} → ${d.new_letter}`)
      .join("；");
    return `
    <div class="card">
      <div class="card-head">
        <strong>勘误 #${e.id}</strong>
        <span class="muted">${esc(e.created_at)}</span>
      </div>
      <p>题目 <code>${esc(e.question_id)}</code> 更正为选项
        <code>${esc(e.new_option_id)}</code>：${dets}</p>
      ${e.note ? `<p class="muted">备注：${esc(e.note)}</p>` : ""}
    </div>`;
  }).join("");
}

load();
