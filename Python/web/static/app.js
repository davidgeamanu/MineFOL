let state = null;
let flagMode = false;

function qs(id){ return document.getElementById(id); }

function clearMsgs(){
  qs("info").textContent = "";
  qs("whyButtons").textContent = "";
  qs("explanation").textContent = "";
  qs("error").textContent = "";
}

async function api(path, method="GET", body=null){
  const opts = { method, headers: {} };
  if(body){
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(path, opts);
  return await res.json();
}

function updateModeButtons() {
  const cursorBtn = qs("cursorMode");
  const flagBtn = qs("flagModeBtn");

  if (flagMode) {
    cursorBtn.classList.remove("active");
    flagBtn.classList.add("active");
  } else {
    cursorBtn.classList.add("active");
    flagBtn.classList.remove("active");
  }
}

function render(){
  if(!state) return;

  const statusDiv = qs("status");
  statusDiv.className = ""; // Reset class

  if (state.dead) {
    statusDiv.innerHTML = '❌ GAME OVER';
    statusDiv.classList.add("status-large", "status-bad");
  } else if (state.success) {
    statusDiv.innerHTML = '✅ SUCCESS!';
    statusDiv.classList.add("status-large", "status-ok");
  } else {
    statusDiv.innerHTML = `
      <div style="font-size: 14px; margin-bottom:4px; color:var(--muted)">POSITION</div>
      <div style="font-size: 18px; font-weight:bold; margin-bottom:12px">(${state.pos[0]}, ${state.pos[1]})</div>
      <div style="font-size: 14px; margin-bottom:4px; color:var(--muted)">MINES FOUND</div>
      <div style="font-size: 18px; font-weight:bold">${state.flaggedCount} / ${state.mines}</div>
    `;
  }

  // Update current cell message
  const currentMsgDiv = qs("currentMessage");
  if (state.currentMessage) {
    currentMsgDiv.textContent = state.currentMessage;
    currentMsgDiv.style.opacity = "1";
  } else {
    currentMsgDiv.textContent = "No message in this cell";
    currentMsgDiv.style.opacity = "0.5";
  }

  // Update Knowledge BAse
  const messagesDiv = qs("messages");
  if (state.messages && state.messages.length > 0) {
    messagesDiv.textContent = state.messages.join("\n");
  } else {
    messagesDiv.textContent = "No messages collected yet.";
  }

  // RENDER BOARD GRID

  const wrap = qs("boardGrid");
  wrap.innerHTML = "";

  // grid has (n+1) columns: first is row labels
  wrap.style.gridTemplateColumns = `48px repeat(${state.n}, var(--cellSize))`;
  wrap.style.gridTemplateRows = `48px repeat(${state.n}, var(--cellSize))`;

  // Top-left empty corner
  wrap.appendChild(makeLabel(""));

  // Column labels 1..n
  for (let c = 1; c <= state.n; c++) wrap.appendChild(makeLabel(String(c)));

  // Rows
  for (let r = 1; r <= state.n; r++) {
    // Row label
    wrap.appendChild(makeLabel(String(r)));

    for (let c = 1; c <= state.n; c++) {
      const cell = state.cells[r-1][c-1];
      const div = document.createElement("div");
      div.className = "cell";

      const isExploded = state.dead && cell.isCurrent;

      // Class Logic
      if (cell.visited) div.classList.add("visited");
      if (cell.provablySafe && !state.dead) div.classList.add("provablySafe");
      if (cell.forcedHint && !state.dead) div.classList.add("forcedHint");
      if (cell.isCurrent && !state.dead) div.classList.add("current");
      if (cell.flagged) div.classList.add("flagged");
      if (isExploded) div.classList.add("exploded");

      div.dataset.r = r;
      div.dataset.c = c;

      div.textContent = "";

      if (cell.flagged) {
        div.textContent = "💣🚩";
        div.style.fontSize = "20px";
      }
      else if (isExploded) {
        div.textContent = "💥";
      }
      else if (cell.isCurrent && !state.dead) {
        div.textContent = "●";
      }

      // Message Icon (paper)
      if (cell.showMessageIcon && !isExploded) {
        const ic = document.createElement("div");
        ic.className = "icon";
        ic.textContent = "📄";
        div.appendChild(ic);
      }

      div.addEventListener("click", onCellClick);
      wrap.appendChild(div);
    }
  }
}

function makeLabel(text){
  const d = document.createElement("div");
  d.className = "axisLabel";
  d.textContent = text;
  return d;
}

async function onCellClick(e){
  if(!state || state.dead || state.success) return;
  clearMsgs();

  const r = parseInt(e.currentTarget.dataset.r, 10);
  const c = parseInt(e.currentTarget.dataset.c, 10);

  if(flagMode){
    const res = await api("/api/flag", "POST", { r, c });
    if(res.error) qs("error").textContent = res.error;
    if(res.info) qs("info").textContent = res.info;
    state = res;
    render();
    return;
  }

  const res = await api("/api/move", "POST", { r, c });
  if(res.error) qs("error").textContent = res.error;
  state = res;
  render();
}

async function newGame(){
  clearMsgs();
  const diff = qs("difficulty").value;
  qs("info").textContent = "Generating new game...";
  state = await api("/api/new_game", "POST", { difficulty: diff });
  clearMsgs();
  render();
}

async function hintSafe(){
  clearMsgs();
  qs("info").textContent = "Computing safe moves with Mace4...";
  const res = await api("/api/hint_safe");
  clearMsgs();
  if(res.info) qs("info").textContent = res.info;
  state = res;
  render();
  showWhyButtons(res.safeMoves || []);
}

function showWhyButtons(moves){
  // One "Why?" button per safe move; Prover9 explains it on demand
  const box = qs("whyButtons");
  box.textContent = "";
  for (const [r, c] of moves) {
    const btn = document.createElement("button");
    btn.className = "whyBtn";
    btn.textContent = `Why is (${r},${c}) safe?`;
    btn.addEventListener("click", () => explainSafe(r, c));
    box.appendChild(btn);
  }
}

async function explainSafe(r, c){
  qs("explanation").textContent = `Asking Prover9 why (${r},${c}) is safe...`;
  const res = await api(`/api/explain_safe?r=${r}&c=${c}`);
  qs("explanation").textContent = res.error || res.explanation;
}

async function hintForced(){
  clearMsgs();
  qs("info").textContent = "Checking for forced mines with Mace4...";
  const res = await api("/api/hint_forced");
  clearMsgs();
  if(res.info) qs("info").textContent = res.info;
  state = res;
  render();
}

async function loadCustom(){
  clearMsgs();
  qs("info").textContent = "Loading custom handmade puzzle...";
  const res = await api("/api/load_custom", "POST", {});

  if(res.error) {
    qs("error").textContent = res.error;
  } else {
    qs("info").textContent = res.info || "Custom game loaded!";
    state = res;
    render();
  }
}

async function showSolution(){
  clearMsgs();
  qs("info").textContent = "Revealing solution...";
  const res = await api("/api/show_solution");

  if(res.error) {
    qs("error").textContent = res.error;
  } else {
    if(res.info) qs("info").textContent = res.info;
    state = res;
    render();
  }
}

function handleKey(e){
  if(!state || state.dead || state.success) return;

  const key = e.key.toLowerCase();
  let dir = null;
  if (key === "w" || key === "arrowup") dir = [-1, 0];
  else if (key === "s" || key === "arrowdown") dir = [1, 0];
  else if (key === "a" || key === "arrowleft") dir = [0, -1];
  else if (key === "d" || key === "arrowright") dir = [0, 1];

  if(!dir) return;
  e.preventDefault();

  const r = state.pos[0] + dir[0];
  const c = state.pos[1] + dir[1];

  if (r < 1 || r > state.n || c < 1 || c > state.n) return;

  api("/api/move", "POST", { r, c }).then(res => {
    clearMsgs();
    if(res.error) qs("error").textContent = res.error;
    state = res;
    render();
  });
}

function toggleCursorMode() {
  flagMode = false;
  updateModeButtons();
}

function toggleFlagMode() {
  flagMode = true;
  updateModeButtons();
}

window.addEventListener("DOMContentLoaded", async () => {
  qs("newGame").addEventListener("click", newGame);
  qs("hintSafe").addEventListener("click", hintSafe);
  qs("hintForced").addEventListener("click", hintForced);
  qs("loadCustom").addEventListener("click", loadCustom);
  qs("showSolution").addEventListener("click", showSolution);
  qs("cursorMode").addEventListener("click", toggleCursorMode);
  qs("flagModeBtn").addEventListener("click", toggleFlagMode);
  window.addEventListener("keydown", handleKey);

  qs("info").textContent = "Loading game...";
  state = await api("/api/state");
  clearMsgs();
  updateModeButtons();
  render();
});