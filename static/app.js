const $ = s => document.querySelector(s);
const $$ = s => Array.from(document.querySelectorAll(s));

let S = {
  all: [], filtered: [], selected: new Set(),
  tab: "all", position: "all", sort: "newest", search: "",
  config: null, tplKey: "default",
};

/* ── Toast ── */
function toast(m, k="ok") {
  const t=$("#toast"); t.textContent=m; t.className=`toast ${k}`;
  t.classList.remove("hidden");
  clearTimeout(window._tt);
  window._tt = setTimeout(()=>t.classList.add("hidden"), 3200);
}

/* ── API ── */
async function api(p, o={}) {
  const r = await fetch(p, {headers:{"Content-Type":"application/json"}, ...o});
  if (r.status === 401) { window.location.href = "/login"; throw new Error("Login required"); }
  const d = await r.json().catch(()=>({}));
  if (!r.ok || d.ok===false) throw new Error(d.error||`${r.status}`);
  return d;
}

/* ── Smart Score ── */
function score(a) {
  let s = 0;
  if (a.cv_attached) s += 25;
  if (a.linkedin) s += 20;
  if ((a.time_commitment||"").toLowerCase().includes("yes")) s += 15;
  if ((a.open_to_equity||"").toLowerCase().includes("yes")) s += 10;
  if (a.why_reliv && a.why_reliv.length > 30) s += 15;
  if (a.domains) s += 10;
  if (a.phone) s += 5;
  return Math.min(s, 100);
}
function scoreBadge(s) {
  const cls = s >= 70 ? "high" : s >= 40 ? "mid" : "low";
  return `<span class="score ${cls}">${s}</span>`;
}

/* ── Stats ── */
async function loadStats() {
  const s = await api("/api/stats");
  $("#stat-total").textContent = s.total;
  $("#stat-pending").textContent = s.pending;
  $("#stat-accepted").textContent = s.accepted;
  $("#stat-rejected").textContent = s.rejected;
  $("#tab-pending-n").textContent = s.pending ? `(${s.pending})` : "";
  $("#tab-accepted-n").textContent = s.accepted ? `(${s.accepted})` : "";
  $("#tab-rejected-n").textContent = s.rejected ? `(${s.rejected})` : "";
  // position filter
  const sel = $("#position-filter");
  const cur = sel.value;
  const opts = ['<option value="all">All positions</option>'];
  (s.positions||[]).forEach(p => opts.push(`<option value="${esc(p.name)}">${esc(p.name)} (${p.count})</option>`));
  sel.innerHTML = opts.join("");
  sel.value = cur || "all";
}

/* ── Applicants ── */
async function loadApplicants() {
  const p = new URLSearchParams();
  if (S.tab !== "all") p.set("status", S.tab);
  if (S.position !== "all") p.set("position", S.position);
  p.set("sort", S.sort);
  S.all = await api(`/api/applicants?${p}`);
  S.all.forEach(a => a._score = score(a));
  applySearch();
}
function applySearch() {
  const q = S.search.toLowerCase();
  S.filtered = !q ? S.all : S.all.filter(a =>
    [a.full_name, a.email, a.domains, a.position, a.location, a.phone, a.referred_by]
      .some(f => (f||"").toLowerCase().includes(q))
  );
  render();
}
function render() {
  const tb = $("#tbody");
  const em = $("#empty-msg");
  if (!S.filtered.length) {
    tb.innerHTML = "";
    em.classList.remove("hidden");
    return;
  }
  em.classList.add("hidden");
  tb.innerHTML = S.filtered.map(rowHtml).join("");
  S.filtered.forEach(bindRow);
  updateBulk();
  $("#select-all").checked = S.filtered.length > 0 && S.filtered.every(a => S.selected.has(a.id));
}
function rowHtml(a) {
  const st = a.status||"pending";
  const sel = S.selected.has(a.id);
  const dt = a.received_at ? new Date(a.received_at).toLocaleDateString("en-IN",{day:"2-digit",month:"short",year:"2-digit"}) : "";
  const init = (a.full_name||"?").split(" ").map(s=>s[0]).slice(0,2).join("").toUpperCase();
  return `<tr class="${st} ${sel?'sel':''}" data-id="${a.id}">
    <td><input type="checkbox" class="rc" data-id="${a.id}" ${sel?'checked':''}></td>
    <td class="cell-who">
      <div class="avatar-sm">${init}</div>
      <div><div class="n">${esc(a.full_name||"")}</div><div class="e">${esc(a.email||"")}</div>
      ${a.phone?`<div class="e">${esc(a.phone)}</div>`:""}</div>
    </td>
    <td><span class="badge pos">${esc(a.position||"—")}</span></td>
    <td>${scoreBadge(a._score)}</td>
    <td class="e">${esc(a.domains||"—")}</td>
    <td>${a.cv_attached?`<a href="/cv/${a.id}" target="_blank" class="cv-link">CV</a>`:'<span class="muted">—</span>'}</td>
    <td class="e">${dt}</td>
    <td><span class="badge st-${st}">${st[0].toUpperCase()+st.slice(1)}</span></td>
    <td class="acts">
      <button class="ab view" data-act="view" title="View details">View</button>
      <button class="ab acc" data-act="accept" title="Accept" ${st==="accepted"?"disabled":""}>✓</button>
      <button class="ab rej" data-act="reject" title="Reject" ${st==="rejected"?"disabled":""}>✗</button>
      <button class="ab del" data-act="delete" title="Delete">🗑</button>
    </td>
  </tr>`;
}
function bindRow(a) {
  const tr = $(`tr[data-id="${a.id}"]`); if(!tr) return;
  tr.querySelector(".rc").onchange = e => { toggle(a.id, e.target.checked); };
  tr.querySelector('[data-act="view"]').onclick = () => openDetail(a);
  tr.querySelector('[data-act="accept"]').onclick = () => openDecision(a, "accepted");
  tr.querySelector('[data-act="reject"]').onclick = () => openDecision(a, "rejected");
  tr.querySelector('[data-act="delete"]').onclick = async () => {
    if (!confirm(`Delete ${a.full_name}?`)) return;
    await api(`/api/delete/${a.id}`, {method:"POST"});
    toast("Deleted","ok"); await reload();
  };
}
function toggle(id, on) { on ? S.selected.add(id) : S.selected.delete(id); render(); }
function updateBulk() {
  const bar = $("#bulk-bar");
  if (S.selected.size) { bar.classList.remove("hidden"); $("#bulk-count").textContent = `${S.selected.size} selected`; }
  else bar.classList.add("hidden");
}
async function doBulk(action) {
  const ids=[...S.selected]; if(!ids.length) return;
  if (action==="delete" && !confirm(`Delete ${ids.length} applicant(s)?`)) return;
  await api("/api/bulk",{method:"POST",body:JSON.stringify({ids,action})});
  toast(`${action==="delete"?"Deleted":"Updated"} ${ids.length}`,"ok");
  S.selected.clear(); await reload();
}
async function reload() { await loadStats(); await loadApplicants(); }

/* ── Detail modal ── */
function openDetail(a) {
  $("#m-title").textContent = a.full_name;
  const fields = [
    ["Email", a.email], ["Phone", a.phone], ["Location", a.location],
    ["LinkedIn", a.linkedin ? `<a href="${esc(a.linkedin)}" target="_blank">${esc(a.linkedin)}</a>` : ""],
    ["Position", a.position], ["Domains", a.domains],
    ["Why Reliv?", a.why_reliv], ["Referred by", a.referred_by],
    ["Time commitment", a.time_commitment], ["Open to equity", a.open_to_equity],
    ["Smart Score", scoreBadge(a._score)],
    ["Status", `<span class="badge st-${a.status}">${(a.status||"pending")}</span>`],
    ["Received", a.received_at ? new Date(a.received_at).toLocaleString() : ""],
    ["Decision sent", a.sent_at ? new Date(a.sent_at).toLocaleString() : ""],
    ["CV", a.cv_attached && a.cv_filename ? `<a href="/cv/${a.id}" target="_blank">${esc(a.cv_filename)}</a>` : "No CV"],
  ];
  let h = fields.filter(([_,v])=>v).map(([k,v])=>`<div class="df"><div class="dl">${k}</div><div class="dv">${k==="LinkedIn"||k==="CV"||k==="Smart Score"||k==="Status"?v:esc(String(v))}</div></div>`).join("");
  h += `<div class="actions">
    <button class="btn ghost" id="m-reset" ${a.status==='pending'?'disabled':''}>Reset</button>
    <button class="btn ghost" id="m-del">Delete</button>
    <button class="btn reject" id="m-rej" ${a.status==='rejected'?'disabled':''}>Reject</button>
    <button class="btn accept" id="m-acc" ${a.status==='accepted'?'disabled':''}>Accept</button>
  </div>`;
  $("#m-body").innerHTML = h;
  $("#m-acc").onclick = () => openDecision(a,"accepted");
  $("#m-rej").onclick = () => openDecision(a,"rejected");
  $("#m-reset").onclick = async()=>{ await api(`/api/reset/${a.id}`,{method:"POST"}); toast("Reset","ok"); closeModal(); await reload(); };
  $("#m-del").onclick = async()=>{ if(!confirm("Delete?")) return; await api(`/api/delete/${a.id}`,{method:"POST"}); toast("Deleted","ok"); closeModal(); await reload(); };
  $("#modal").classList.remove("hidden");
}
async function openDecision(a, decision) {
  try { const p = await api(`/api/preview/${a.id}?decision=${decision}`); showEditor(a,decision,p); }
  catch(e) { toast(e.message,"err"); }
}
function showEditor(a, decision, preview) {
  const verb = decision==="accepted"?"Accept":"Reject";
  $("#m-title").textContent = `${verb} — ${a.full_name}`;
  $("#m-body").innerHTML = `
    <div class="df"><div class="dl">To</div><div class="dv">${esc(preview.to)}</div></div>
    <div class="mail-edit">
      <label>Subject</label><input id="ed-sub" type="text" />
      <label>Body</label><textarea id="ed-body"></textarea>
    </div>
    <div class="actions">
      <button class="btn ghost" id="ed-cancel">Cancel</button>
      <button class="btn ${decision==='accepted'?'accept':'reject'}" id="ed-send">Send ${verb.toLowerCase()} email</button>
    </div>`;
  $("#ed-sub").value = preview.subject;
  $("#ed-body").value = preview.body;
  $("#ed-cancel").onclick = closeModal;
  $("#ed-send").onclick = () => sendDecision(a, decision);
  $("#modal").classList.remove("hidden");
}
async function sendDecision(a, decision) {
  const btn=$("#ed-send"); btn.disabled=true; btn.textContent="Sending...";
  try {
    const r = await api(`/api/decide/${a.id}`,{method:"POST",body:JSON.stringify({decision,subject:$("#ed-sub").value,body:$("#ed-body").value})});
    closeModal(); toast(`Sent to ${r.sent_to}`,"ok"); await reload();
  } catch(e) { toast(e.message,"err"); btn.disabled=false; btn.textContent="Retry"; }
}
function closeModal() { $("#modal").classList.add("hidden"); }

/* ── Settings ── */
async function openSettings() {
  S.config = await api("/api/config");
  $("#cfg-email").value = S.config.email_address||"";
  $("#cfg-password").value = "";
  $("#cfg-password").placeholder = S.config.app_password==="***" ? "(saved)" : "xxxx xxxx xxxx xxxx";
  $("#cfg-from").value = S.config.from_name||"Team Reliv";
  $("#cfg-keyword").value = S.config.subject_keyword||"Applicant Info";
  $("#cfg-days").value = S.config.since_days||730;
  fillTplSelect(); loadTpl($("#tpl-select").value);
  $("#settings-modal").classList.remove("hidden");
}
function fillTplSelect() {
  const sel=$("#tpl-select"), keys=Object.keys(S.config.templates||{});
  if (!keys.includes("default")) keys.unshift("default");
  sel.innerHTML = keys.map(k=>`<option value="${esc(k)}">${esc(k)}</option>`).join("");
}
function loadTpl(k) {
  S.tplKey=k;
  const t=(S.config.templates&&S.config.templates[k])||S.config.templates.default;
  $("#tpl-accept-sub").value=t.accept_subject||"";
  $("#tpl-accept-body").value=t.accept_body||"";
  $("#tpl-reject-sub").value=t.reject_subject||"";
  $("#tpl-reject-body").value=t.reject_body||"";
}
function captureTpl() {
  S.config.templates[S.tplKey]={
    accept_subject:$("#tpl-accept-sub").value, accept_body:$("#tpl-accept-body").value,
    reject_subject:$("#tpl-reject-sub").value, reject_body:$("#tpl-reject-body").value,
  };
}

/* ── Init ── */
document.addEventListener("DOMContentLoaded", () => {
  // Status tabs
  $$(".stab").forEach(b => b.onclick = () => {
    $$(".stab").forEach(x=>x.classList.remove("active")); b.classList.add("active");
    S.tab = b.dataset.status; S.selected.clear(); loadApplicants();
  });
  // Stat cards click
  $$(".stat-card.clickable").forEach(c => c.onclick = () => {
    const t = c.dataset.tab;
    $$(".stab").forEach(x=>x.classList.toggle("active", x.dataset.status===t));
    S.tab = t; S.selected.clear(); loadApplicants();
  });
  // Sort & position
  $("#sort-select").onchange = e => { S.sort=e.target.value; loadApplicants(); };
  $("#position-filter").onchange = e => { S.position=e.target.value; loadApplicants(); };
  $("#search").oninput = e => { S.search=e.target.value; applySearch(); };
  // Select all
  $("#select-all").onchange = e => {
    S.filtered.forEach(a => e.target.checked ? S.selected.add(a.id) : S.selected.delete(a.id));
    render();
  };
  // Bulk
  $("#bulk-accept").onclick = () => doBulk("accepted");
  $("#bulk-reject").onclick = () => doBulk("rejected");
  $("#bulk-reset").onclick = () => doBulk("pending");
  $("#bulk-delete").onclick = () => doBulk("delete");
  $("#bulk-clear").onclick = () => { S.selected.clear(); render(); };
  // Fetch
  $("#btn-fetch").onclick = async () => {
    $("#fetch-spin").classList.remove("hidden"); $("#btn-fetch").disabled=true;
    try {
      const r = await api("/api/fetch",{method:"POST"});
      toast(`${r.fetched} emails scanned, ${r.new} new`,"ok"); await reload();
    } catch(e) { toast("Fetch: "+e.message,"err"); }
    finally { $("#fetch-spin").classList.add("hidden"); $("#btn-fetch").disabled=false; }
  };
  // Export
  $("#btn-export").onclick = () => window.open("/api/export.csv","_blank");
  // Settings
  $("#btn-settings").onclick = openSettings;
  $("#s-close").onclick = () => $("#settings-modal").classList.add("hidden");
  $("#m-close").onclick = closeModal;
  $$(".tab").forEach(t => t.onclick = () => {
    $$(".tab").forEach(x=>x.classList.remove("active")); t.classList.add("active");
    $$(".tab-panel").forEach(p=>p.classList.toggle("hidden",p.dataset.panel!==t.dataset.tab));
  });
  $("#cfg-save").onclick = async () => {
    const st=$("#cfg-status");
    try {
      await api("/api/config",{method:"POST",body:JSON.stringify({
        email_address:$("#cfg-email").value.trim(),
        app_password:$("#cfg-password").value.trim()||"***",
        from_name:$("#cfg-from").value.trim()||"Team Reliv",
        subject_keyword:$("#cfg-keyword").value.trim()||"Applicant Info",
        since_days:parseInt($("#cfg-days").value)||730,
      })});
      st.textContent="Saved"; st.className="status ok";
    } catch(e) { st.textContent=e.message; st.className="status err"; }
  };
  $("#cfg-verify").onclick = async () => {
    const st=$("#cfg-status"); st.textContent="Testing..."; st.className="status";
    try { const r=await api("/api/verify",{method:"POST"}); st.textContent=r.message; st.className=`status ${r.ok?"ok":"err"}`; }
    catch(e) { st.textContent=e.message; st.className="status err"; }
  };
  $("#tpl-select").onchange = e => { captureTpl(); loadTpl(e.target.value); };
  $("#tpl-add").onclick = () => {
    const n=$("#tpl-new").value.trim(); if(!n) return; captureTpl();
    if(!S.config.templates[n]) S.config.templates[n]={accept_subject:"",accept_body:"",reject_subject:"",reject_body:""};
    fillTplSelect(); $("#tpl-select").value=n; loadTpl(n); $("#tpl-new").value="";
  };
  $("#tpl-save").onclick = async () => {
    captureTpl(); const st=$("#tpl-status");
    try { await api("/api/config",{method:"POST",body:JSON.stringify({templates:S.config.templates})}); st.textContent="Saved"; st.className="status ok"; }
    catch(e) { st.textContent=e.message; st.className="status err"; }
  };
  // Logout
  $("#btn-logout").onclick = async () => {
    await fetch("/api/logout",{method:"POST"});
    window.location.href = "/login";
  };
  // Password change
  $("#sec-save").onclick = async () => {
    const st=$("#sec-status"), o=$("#sec-old").value, n=$("#sec-new").value, c=$("#sec-confirm").value;
    if (n !== c) { st.textContent="Passwords don't match"; st.className="status err"; return; }
    try {
      await api("/api/change-password",{method:"POST",body:JSON.stringify({old:o,new:n})});
      st.textContent="Password changed!"; st.className="status ok";
      $("#sec-old").value=""; $("#sec-new").value=""; $("#sec-confirm").value="";
    } catch(e) { st.textContent=e.message; st.className="status err"; }
  };
  // Keyboard
  document.onkeydown = e => {
    if (e.key==="Escape") { closeModal(); $("#settings-modal").classList.add("hidden"); }
  };
  // Go
  reload();
});

function esc(s) { return String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c])); }
