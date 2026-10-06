const { batchId, version, kind } = window.PRINT_CTX;
const KIND_TITLE = { paper: "试卷", sheet: "答题卡", key: "答案表" };

async function load() {
  const d = await api("/api/batches/" + batchId);
  const items = d.versions[version];
  document.getElementById("doc-title").textContent =
    `${d.name} · ${version} 卷${KIND_TITLE[kind]}`;
  document.title = `${d.name} ${version}卷${KIND_TITLE[kind]}`;
  const root = document.getElementById("sheet");
  if (kind === "paper") root.innerHTML = renderPaper(d, items);
  else if (kind === "sheet") root.innerHTML = renderSheet(d, items);
  else root.innerHTML = renderKey(d, items);
}

function renderPaper(d, items) {
  return `
    <div class="exam-head">
      <h1>${esc(d.name)} · ${version} 卷</h1>
      <p>姓名：______________　准考证号：______________</p>
    </div>
    ${items.map(it => `
      <div class="q">
        <p class="q-stem">${it.seq}. ${esc(it.stem)}</p>
        <div class="q-opts">
          ${it.options.map(o =>
            `<span class="q-opt">${o.letter}. ${esc(o.text)}</span>`).join("")}
        </div>
      </div>`).join("")}`;
}

function renderSheet(d, items) {
  // 题号与选项字母直接取自同一封存数据，保证与卷面一致
  return `
    <div class="exam-head">
      <h1>${esc(d.name)} · ${version} 卷答题卡</h1>
      <p>姓名：______________　准考证号：______________</p>
    </div>
    <table class="sheet-table">
      <thead><tr><th>题号</th><th>A</th><th>B</th><th>C</th><th>D</th></tr></thead>
      <tbody>
        ${items.map(it => `
          <tr>
            <td class="num">${it.seq}</td>
            ${it.options.map(o =>
              `<td><span class="bubble">${o.letter}</span></td>`).join("")}
          </tr>`).join("")}
      </tbody>
    </table>`;
}

function renderKey(d, items) {
  const rows = items.map(it => `
    <tr class="${it.corrected ? "corrected" : ""}">
      <td class="num">${it.seq}</td>
      <td class="ans">${it.current_letter}</td>
      <td><code>${esc(it.question_id)}</code></td>
      <td>${it.corrected ? `原 ${it.original_letter}，已勘误` : ""}</td>
    </tr>`).join("");
  const ers = d.errata.map(e => {
    const det = e.details.find(x => x.version === version);
    if (!det) return "";
    return `<tr>
      <td>#${e.id}</td><td>${esc(e.created_at)}</td><td>第 ${det.seq} 题</td>
      <td>${det.old_letter} → ${det.new_letter}</td><td>${esc(e.note || "")}</td>
    </tr>`;
  }).join("");
  return `
    <div class="exam-head">
      <h1>${esc(d.name)} · ${version} 卷答案表</h1>
      <p>本表已包含截至打印时登记的全部勘误。</p>
    </div>
    <table class="key-table">
      <thead><tr><th>题号</th><th>答案</th><th>题目标识</th><th>备注</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
    ${ers ? `
      <h2 class="errata-h">勘误记录</h2>
      <table class="key-table">
        <thead><tr><th>勘误</th><th>时间</th><th>题号</th><th>答案变更</th><th>备注</th></tr></thead>
        <tbody>${ers}</tbody>
      </table>` : ""}`;
}

load();
