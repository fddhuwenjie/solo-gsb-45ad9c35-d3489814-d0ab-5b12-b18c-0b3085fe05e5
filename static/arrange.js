let ARR = { A: [], B: [] };

async function loadArr() {
  ARR = await api("/api/arrangement");
  render();
}

function render() {
  for (const v of ["A", "B"]) {
    const root = document.getElementById("col-" + v);
    const items = ARR[v] || [];
    root.innerHTML = items.length
      ? items.map((item, i) => card(v, item, i, items.length)).join("")
      : '<p class="muted">题库为空，请先到「题库」录题。</p>';
  }
}

function card(v, item, i, n) {
  const opts = item.options.map((o, j) => `
    <li>
      <span class="letter">${"ABCD"[j] || (j + 1)}</span>
      <span class="opt-text">${esc(o.text)}</span>
      <code>${esc(o.id)}</code>
      <span class="spacer"></span>
      <button data-act="opt-up" data-v="${v}" data-q="${esc(item.question_id)}"
        data-i="${j}" ${j === 0 ? "disabled" : ""}>↑</button>
      <button data-act="opt-down" data-v="${v}" data-q="${esc(item.question_id)}"
        data-i="${j}" ${j === item.options.length - 1 ? "disabled" : ""}>↓</button>
    </li>`).join("");
  return `
  <div class="card">
    <div class="card-head">
      <strong>第 ${i + 1} 题</strong> <code>${esc(item.question_id)}</code>
      <span class="spacer"></span>
      <button data-act="q-up" data-v="${v}" data-i="${i}" ${i === 0 ? "disabled" : ""}>↑</button>
      <button data-act="q-down" data-v="${v}" data-i="${i}" ${i === n - 1 ? "disabled" : ""}>↓</button>
    </div>
    <p class="stem">${esc(item.stem)}</p>
    <ul class="opts">${opts}</ul>
  </div>`;
}

document.addEventListener("click", async (e) => {
  const btn = e.target.closest("button");
  if (!btn || !btn.dataset.act) return;
  const v = btn.dataset.v;
  const act = btn.dataset.act;
  if (act === "q-up" || act === "q-down") {
    const i = Number(btn.dataset.i);
    const j = act === "q-up" ? i - 1 : i + 1;
    const arr = ARR[v];
    [arr[i], arr[j]] = [arr[j], arr[i]];
    render();
    await save(v);
  } else if (act === "opt-up" || act === "opt-down") {
    const item = ARR[v].find(x => x.question_id === btn.dataset.q);
    const i = Number(btn.dataset.i);
    const j = act === "opt-up" ? i - 1 : i + 1;
    [item.options[i], item.options[j]] = [item.options[j], item.options[i]];
    render();
    await save(v);
  }
});

async function save(v) {
  const msg = document.getElementById("seal-msg");
  try {
    const r = await api("/api/arrangement/" + v, {
      method: "PUT",
      body: {
        questions: ARR[v].map(x => x.question_id),
        options: Object.fromEntries(
          ARR[v].map(x => [x.question_id, x.options.map(o => o.id)])
        ),
      },
    });
    ARR[v] = r.arrangement;
    render();
  } catch (e) {
    showMessage(msg, e.message, true);
  }
}

document.getElementById("seal-btn").addEventListener("click", async () => {
  if (!confirm("以题库当前修订封存 A、B 两卷？\n封存后修改题库不影响本批卷面与答题卡。")) return;
  const msg = document.getElementById("seal-msg");
  try {
    const r = await api("/api/seal", { method: "POST", body: {} });
    showMessage(msg, `封存成功：${r.name}（批次 #${r.batch_id}）。`, false);
    msg.innerHTML += ` <a href="/batches/${r.batch_id}">查看封存卷</a>`;
  } catch (e) {
    showMessage(msg, e.message, true);
  }
});

loadArr();
