let QUESTIONS = [];

async function loadQuestions() {
  const data = await api("/api/questions");
  QUESTIONS = data.questions;
  renderQuestions();
}

function renderQuestions() {
  const root = document.getElementById("question-list");
  if (!QUESTIONS.length) {
    root.innerHTML = '<p class="muted">题库为空，请在下方新增题目。</p>';
    return;
  }
  root.innerHTML = QUESTIONS.map((q, i) => {
    const opts = q.options.map(o => `
      <li class="${o.id === q.correct_option_id ? "correct" : ""}">
        ${esc(o.text)} <code>${esc(o.id)}</code>
        ${o.id === q.correct_option_id ? '<span class="tag">正确</span>' : ""}
      </li>`).join("");
    return `
    <div class="card" data-qid="${esc(q.id)}">
      <div class="card-head">
        <strong>#${i + 1}</strong> <code>${esc(q.id)}</code>
        <span class="spacer"></span>
        <button data-act="edit" data-qid="${esc(q.id)}">编辑</button>
        <button data-act="del" data-qid="${esc(q.id)}" class="danger">删除</button>
      </div>
      <p class="stem">${esc(q.stem)}</p>
      <ul class="opts">${opts}</ul>
    </div>`;
  }).join("");
}

function openEdit(qid) {
  const q = QUESTIONS.find(x => x.id === qid);
  const card = document.querySelector(`.card[data-qid="${CSS.escape(qid)}"]`);
  card.innerHTML = `
    <div class="card-head"><strong>编辑题目</strong> <code>${esc(q.id)}</code></div>
    <textarea class="edit-stem">${esc(q.stem)}</textarea>
    ${q.options.map(o => `
      <div class="form-row opt-row">
        <input type="radio" name="edit-correct" value="${esc(o.id)}"
          ${o.id === q.correct_option_id ? "checked" : ""} title="设为正确选项">
        <input type="text" class="edit-opt" data-oid="${esc(o.id)}" value="${esc(o.text)}">
        <code>${esc(o.id)}</code>
      </div>`).join("")}
    <p class="muted">仅更新题库与之后的封存；已封存卷的卷面与答题卡不受影响。</p>
    <button class="primary" data-act="save" data-qid="${esc(q.id)}">保存</button>
    <button data-act="cancel">取消</button>
    <div class="msg edit-msg" style="display:none"></div>`;
}

async function saveEdit(qid) {
  const card = document.querySelector(`.card[data-qid="${CSS.escape(qid)}"]`);
  const msg = card.querySelector(".edit-msg");
  const stem = card.querySelector(".edit-stem").value;
  const options = [...card.querySelectorAll(".edit-opt")]
    .map(i => ({ id: i.dataset.oid, text: i.value }));
  const correct = card.querySelector('input[name="edit-correct"]:checked');
  try {
    await api("/api/questions/" + encodeURIComponent(qid), {
      method: "PUT",
      body: { stem, options, correct_option_id: correct ? correct.value : null },
    });
    await loadQuestions();
  } catch (e) {
    showMessage(msg, e.message, true);
  }
}

document.getElementById("question-list").addEventListener("click", async (e) => {
  const btn = e.target.closest("button");
  if (!btn) return;
  const qid = btn.dataset.qid;
  if (btn.dataset.act === "edit") {
    openEdit(qid);
  } else if (btn.dataset.act === "save") {
    saveEdit(qid);
  } else if (btn.dataset.act === "cancel") {
    renderQuestions();
  } else if (btn.dataset.act === "del") {
    if (!confirm(`删除题目 ${qid}？\n（不影响已封存卷）`)) return;
    await api("/api/questions/" + encodeURIComponent(qid), { method: "DELETE" });
    loadQuestions();
  }
});

document.getElementById("add-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const msg = document.getElementById("add-msg");
  const correct = document.querySelector('input[name="new-correct"]:checked');
  try {
    await api("/api/questions", {
      method: "POST",
      body: {
        stem: document.getElementById("new-stem").value,
        options: [...document.querySelectorAll(".new-opt")].map(i => ({ text: i.value })),
        correct_index: correct ? Number(correct.value) : null,
      },
    });
    showMessage(msg, "已添加。", false);
    e.target.reset();
    loadQuestions();
  } catch (err) {
    showMessage(msg, err.message, true);
  }
});

loadQuestions();
