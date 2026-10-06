async function api(path, options = {}) {
  const opts = { headers: { "Content-Type": "application/json" }, ...options };
  if (opts.body && typeof opts.body !== "string") opts.body = JSON.stringify(opts.body);
  const res = await fetch(path, opts);
  let data = null;
  try { data = await res.json(); } catch (e) { /* 非 JSON 响应 */ }
  if (!res.ok) {
    const msg = data && data.errors ? data.errors.join("\n") : ("请求失败：" + res.status);
    const err = new Error(msg);
    err.data = data;
    throw err;
  }
  return data;
}

function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function showMessage(el, text, isError) {
  el.textContent = text;
  el.className = "msg " + (isError ? "error" : "ok");
  el.style.display = text ? "" : "none";
}
