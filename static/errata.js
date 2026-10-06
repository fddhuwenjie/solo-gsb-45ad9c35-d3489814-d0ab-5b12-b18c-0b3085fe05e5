let BATCHES = [];
let DETAIL = null;
let QMAP = {}; // qid -> { A: item|null, B: item|null }

async function init() {
  const data = await api("/api/batches");
  BATCHES = data.batches;
  if (!BATCHES.length) {
    document.getElementById("errata-form").style.display = "none";
    showMessage(document.getElementById("global-msg"),
      "尚无封存批次，请先在「编排」页封存。", true);
  } else {
    const sel = document.getElementById("batch-select");
    sel.innerHTML = BATCHES.map(b =>
      `<option value="${b.id}">#${b.id} ${esc(b.name)}（${esc(b.created_at)}）</option>`
    ).join("");
    sel.addEventListener("change", loadBatch);
    document.getElementById("question-select")
      .addEventListener("change", renderOptions);
    document.getElementById("submit-errata")
      .addEventListener("click", submitErrata);
    await loadBatch();
  }
  await loadHistory();
}

async function loadBatch() {
  const bid = document.getElementById("batch-select").value;
  DETAIL = await api("/api/batches/" + bid);
  QMAP = {};
  for (const v of ["A", "B"]) {
    for (const it of DETAIL.versions[v]) {
      QMAP[it.question_id] = QMAP[it.question_id] || { A: null, B: null };
      QMAP[it.question_id][v] = it;
    }
  }
  const qsel = document.getElementById("question-select");
  qsel.innerHTML = Object.entries(QMAP).map(([qid, m]) => {
    const stem = (m.A || m.B).stem;
    const pos = [
      m.A ? `A卷第${m.A.seq}题` : "A卷缺",
      m.B ? `B卷第${m.B.seq}题` : "B卷缺",
    ].join(" / ");
    return `<option value="${esc(qid)}">[${esc(qid)}] ${esc(stem.slice(0, 24))}（${pos}）</option>`;
  }).join("");
  renderOptions();
}

function renderOptions() {
  const qid = document.getElementById("question-select").value;
  const m = QMAP[qid];
  const root = document.getElementById("option-picker");
  if (!m) { root.innerHTML = ""; return; }
  const ids = [];
  const texts = {};
  const letters = { A: {}, B: {} };
  for (const v of ["A", "B"]) {
    if (!m[v]) continue;
    for (const o of m[v].options) {
      if (!ids.includes(o.option_id)) ids.push(o.option_id);
      if (!(o.option_id in texts)) texts[o.option_id] = o.text;
      letters[v][o.option_id] = o.letter;
    }
  }
  const rows = ids.map(oid => {
    const cur = (m.A && m.A.current_option_id === oid) ||
                (m.B && m.B.current_option_id === oid);
    return `<tr>
      <td><input type="radio" name="newopt" value="${esc(oid)}"></td>
      <td><code>${esc(oid)}</code></td>
      <td>${esc(texts[oid] || "")}</td>
      <td>${letters.A[oid] || "—"}</td>
      <td>${letters.B[oid] || "—"}</td>
      <td>${cur ? '<span class="tag">当前答案</span>' : ""}</td>
    </tr>`;
  }).join("");
  root.innerHTML = `
    <p>选择更正后的正确选项（即封存时印出的选项）：</p>
    <table class="opt-table">
      <thead><tr><th></th><th>选项标识</th><th>封存文本</th>
        <th>A卷字母</th><th>B卷字母</th><th></th></tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
}

async function submitErrata() {
  const msg = document.getElementById("form-msg");
  const checked = document.querySelector('input[name="newopt"]:checked');
  if (!checked) {
    showMessage(msg, "请选择更正后的正确选项。", true);
    return;
  }
  try {
    const r = await api("/api/errata", {
      method: "POST",
      body: {
        batch_id: Number(document.getElementById("batch-select").value),
        question_id: document.getElementById("question-select").value,
        option_id: checked.value,
        note: document.getElementById("note").value,
      },
    });
    const dets = r.errata.details
      .map(d => `${d.version}卷第${d.seq}题 ${d.old_letter}→${d.new_letter}`)
      .join("；");
    showMessage(msg, `勘误 #${r.errata.id} 已登记：${dets}`, false);
    document.getElementById("note").value = "";
    await loadBatch();
    await loadHistory();
  } catch (e) {
    showMessage(msg, e.message, true);
  }
}

async function loadHistory() {
  const data = await api("/api/errata");
  const root = document.getElementById("errata-history");
  if (!data.errata.length) {
    root.innerHTML = '<p class="muted">暂无勘误记录。</p>';
    return;
  }
  root.innerHTML = data.errata.map(e => {
    const dets = e.details
      .map(d => `${d.version}卷第${d.seq}题 ${d.old_letter}→${d.new_letter}`)
      .join("；");
    return `
    <div class="card">
      <div class="card-head">
        <strong>勘误 #${e.id}</strong>
        <span class="muted">批次 #${e.batch_id} · ${esc(e.created_at)}</span>
      </div>
      <p>题目 <code>${esc(e.question_id)}</code> 更正为选项
        <code>${esc(e.new_option_id)}</code>：${dets}</p>
      ${e.note ? `<p class="muted">备注：${esc(e.note)}</p>` : ""}
    </div>`;
  }).join("");
}

init();
