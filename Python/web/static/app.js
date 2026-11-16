let state = null;
let flagMode = false;
let puzzles = [];     // [{name, label, numbers}] from /api/puzzles
let current = null;   // {category, number} of the puzzle being played
let kbShown = 0;      // clues in the knowledge base at the last render
let kbOrder = [];     // cells ("r,c") in the order the player arranged the knowledge base
let dragKey = null;   // cell of the clue being dragged

// Board icons: plain line drawings in the style of logic-textbook diagrams.
// They use the cell's text colour (currentColor), so CSS decides their colour.
const ICONS = {
  check: '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg>',
  here:  '<svg class="icon" viewBox="0 0 24 24" aria-label="You"><circle cx="12" cy="12" r="7.5"/><circle class="solid" cx="12" cy="12" r="3"/></svg>',
  flag:  '<svg class="icon" viewBox="0 0 24 24" aria-label="Flag"><path d="M7 21V4"/><path d="M7 4.5h10l-2.5 4 2.5 4H7"/></svg>',
  mine:  '<svg class="icon" viewBox="0 0 24 24" aria-label="Mine"><circle class="solid" cx="12" cy="12" r="6.5"/><circle class="shine" cx="9.6" cy="9.6" r="1.7"/></svg>',
  // Small page in the corner of cells whose clue you have read
  clue:  '<svg class="clueMark" viewBox="0 0 24 24"><title>Clue read here</title><path d="M14 3H7a1 1 0 0 0-1 1v16a1 1 0 0 0 1 1h10a1 1 0 0 0 1-1V7z"/><path d="M14 3v4h4"/><path d="M9 12h6M9 16h4"/></svg>',
};

// Drag handle on knowledge-base rows
const GRIP_ICON = '<svg class="grip" viewBox="0 0 24 24" aria-hidden="true"><circle cx="9" cy="6" r="1.6"/><circle cx="15" cy="6" r="1.6"/><circle cx="9" cy="12" r="1.6"/><circle cx="15" cy="12" r="1.6"/><circle cx="9" cy="18" r="1.6"/><circle cx="15" cy="18" r="1.6"/></svg>';

function qs(id){ return document.getElementById(id); }

function el(tag, className, text){
  const e = document.createElement(tag);
  if (className) e.className = className;
  if (text !== undefined) e.textContent = text;
  return e;
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

// ---- Messages ----
// Game events (moves, flags, game over) go in the status line under the board;
// hint results and proofs go in the Hints card.

function setStatus(text, kind="info"){
  // kind: "info", "error" (game over, invalid move) or "success" (solved)
  const line = qs("statusLine");
  line.textContent = text || "";
  line.classList.toggle("error", kind === "error");
  line.classList.toggle("success", kind === "success");
}

function endMessage(){
  // Shown when there is no other message, so the banner always says something useful
  if (state.dead) return "Game over. Restart to try this puzzle again.";
  if (state.success) return "Solved: every mine is flagged.";
  const left = state.mines - state.flaggedCount;
  if (left === state.mines) return `GOAL: Flag all ${left} mines.`;
  return left === 1 ? "1 mine left to flag." : `${left} mines left to flag.`;
}

function clearHint(){
  qs("hintList").textContent = "";
}

function showResult(res){
  // No game (it expired): show the error and keep the board.
  if (!res.cells) return setStatus(res.error || "Something went wrong. Reload the page.", "error");
  state = res;
  const kind = (res.error || state.dead) ? "error" : state.success ? "success" : "info";
  setStatus(res.error || res.info || endMessage(), kind);
  render();
}

// ---- Rendering ----

function render(){
  if(!state) return;
  qs("minesFlagged").textContent = `${state.flaggedCount} / ${state.mines}`;
  qs("position").textContent = `(${state.pos[0]}, ${state.pos[1]})`;
  renderBoard();
  renderKnowledgeBase();
}

function orderedClues(){
  // The player's arrangement first, then clues they haven't placed yet, in the order found
  const rank = clue => {
    const i = kbOrder.indexOf(clue.cell.join(","));
    return i === -1 ? Infinity : i;
  };
  return (state.clues || []).map((clue, found) => ({ clue, found }))
    .sort((a, b) => (rank(a.clue) - rank(b.clue)) || (a.found - b.found))
    .map(item => item.clue);
}

function renderKnowledgeBase(){
  // One row per clue, in the player's order (drag and drop), new clues at the bottom.
  // The row of the cell you stand on is highlighted.
  const list = qs("kb");
  const clues = orderedClues();
  const scroll = list.scrollTop;
  qs("kbCount").textContent = clues.length === 1 ? "1 clue" : `${clues.length} clues`;
  qs("kbReset").hidden = kbOrder.length === 0;
  list.textContent = "";

  for (const clue of clues) {
    const [r, c] = clue.cell;
    const key = `${r},${c}`;
    const row = el("li", "kbRow");
    row.dataset.cell = key;
    row.draggable = true;
    if (r === state.pos[0] && c === state.pos[1]) row.classList.add("here");

    row.append(el("span", "badge", `(${r},${c})`), el("span", "formula", clue.text));
    row.insertAdjacentHTML("beforeend", GRIP_ICON);   // drag handle on the right edge

    // Hovering a clue outlines the cell it came from
    row.addEventListener("mouseenter", () => highlightCell(r, c, true));
    row.addEventListener("mouseleave", () => highlightCell(r, c, false));
    addDragHandlers(row, key);
    list.appendChild(row);
  }

  if (clues.length === 0) {
    list.innerHTML = '<li class="kbEmpty">No clues yet. Step on cells to collect them.</li>';
  }
  // Show a newly found clue (it is added at the bottom); otherwise keep the scroll position
  list.scrollTop = clues.length !== kbShown ? list.scrollHeight : scroll;
  kbShown = clues.length;
}

function dropClue(key, targetKey, before){
  // Put the dragged clue just above or below the one it was dropped on
  if (key === targetKey) return;
  const keys = orderedClues().map(clue => clue.cell.join(",")).filter(k => k !== key);
  keys.splice(keys.indexOf(targetKey) + (before ? 0 : 1), 0, key);
  kbOrder = keys;
  renderKnowledgeBase();
}

function addDragHandlers(row, key){
  // Dropping on the top half of a row puts the clue above it, the bottom half below it
  const topHalf = e => {
    const box = row.getBoundingClientRect();
    return e.clientY < box.top + box.height / 2;
  };
  row.addEventListener("dragstart", e => {
    dragKey = key;
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/plain", key);   // Firefox only starts a drag with some data
    row.classList.add("dragging");
  });
  row.addEventListener("dragend", () => {
    dragKey = null;
    renderKnowledgeBase();
  });
  row.addEventListener("dragover", e => {
    if (!dragKey || dragKey === key) return;
    e.preventDefault();   // allows dropping here
    row.classList.toggle("dropBefore", topHalf(e));
    row.classList.toggle("dropAfter", !topHalf(e));
  });
  row.addEventListener("dragleave", () => row.classList.remove("dropBefore", "dropAfter"));
  row.addEventListener("drop", e => {
    e.preventDefault();
    if (dragKey) dropClue(dragKey, key, topHalf(e));
  });
}

function resetClueOrder(){
  kbOrder = [];
  renderKnowledgeBase();
}

function highlightCell(r, c, on){
  const cell = document.querySelector(`.cell[data-r="${r}"][data-c="${c}"]`);
  if (cell) cell.classList.toggle("kbHover", on);
}

function renderBoard(){
  const wrap = qs("boardGrid");
  wrap.innerHTML = "";

  // grid has (n+1) columns: first is row labels; --rows lets CSS size the cells to fit the window
  wrap.style.setProperty("--rows", state.n);
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

      if (cell.flagged) div.innerHTML = ICONS.flag;
      else if (isExploded) div.innerHTML = ICONS.mine;
      else if (cell.isCurrent && !state.dead) div.innerHTML = ICONS.here;
      else if (cell.visited) div.innerHTML = ICONS.check;

      // Cells whose clue you have read get a small page icon in the corner
      if (cell.showMessageIcon && !isExploded) div.insertAdjacentHTML("beforeend", ICONS.clue);

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

// ---- Playing ----

async function onCellClick(e){
  if(!state || state.dead || state.success) return;
  clearHint();

  const r = parseInt(e.currentTarget.dataset.r, 10);
  const c = parseInt(e.currentTarget.dataset.c, 10);
  showResult(await api(flagMode ? "/api/flag" : "/api/move", "POST", { r, c }));
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

  clearHint();
  api("/api/move", "POST", { r, c }).then(showResult);
}

function updateModeButtons() {
  qs("cursorMode").classList.toggle("active", !flagMode);
  qs("flagModeBtn").classList.toggle("active", flagMode);
  qs("boardGrid").classList.toggle("flagMode", flagMode);   // crosshair cursor on the cells
}

function toggleCursorMode() {
  flagMode = false;
  updateModeButtons();
}

function toggleFlagMode() {
  flagMode = true;
  updateModeButtons();
}

// ---- Puzzle picker ----

function categoryInfo(name){
  return puzzles.find(cat => cat.name === name);
}

function lastNumber(cat){
  // Last puzzle played in this category (remembered per browser), else the first one
  let saved = {};
  try { saved = JSON.parse(localStorage.getItem("minefolLast") || "{}"); } catch (e) {}
  return cat.numbers.includes(saved[cat.name]) ? saved[cat.name] : cat.numbers[0];
}

function rememberNumber(category, number){
  try {
    const saved = JSON.parse(localStorage.getItem("minefolLast") || "{}");
    saved[category] = number;
    localStorage.setItem("minefolLast", JSON.stringify(saved));
  } catch (e) {}
}

function renderPicker(){
  const box = qs("categories");
  box.textContent = "";
  for (const cat of puzzles) {
    const btn = document.createElement("button");
    btn.textContent = cat.label;
    if (cat.name === current.category) btn.classList.add("active");
    btn.addEventListener("click", () => loadPuzzle(cat.name, lastNumber(cat)));
    box.appendChild(btn);
  }

  const cat = categoryInfo(current.category);
  const idx = cat.numbers.indexOf(current.number);
  qs("puzzleLabel").textContent = `${cat.label} #${current.number} of ${cat.numbers.length}`;
  qs("prevPuzzle").disabled = idx <= 0;
  qs("nextPuzzle").disabled = idx >= cat.numbers.length - 1;
}

function showPuzzle(res){
  current = { category: res.category, number: res.number };
  rememberNumber(current.category, current.number);
  history.replaceState(null, "", `?d=${current.category}&n=${current.number}`);
  renderPicker();
  clearHint();
  kbOrder = [];   // a new or restarted puzzle starts with clues in the order found
  showResult(res);
}

async function loadPuzzle(category, number){
  setStatus("Loading puzzle...");
  const res = await api("/api/new_game", "POST", { category, number });
  if (res.error) {
    setStatus(res.error, "error");
    return;
  }
  showPuzzle(res);
}

function stepPuzzle(delta){
  const cat = categoryInfo(current.category);
  const idx = cat.numbers.indexOf(current.number) + delta;
  if (idx >= 0 && idx < cat.numbers.length) loadPuzzle(cat.name, cat.numbers[idx]);
}

function newGame(){
  loadPuzzle(current.category, current.number);
}

async function showSolution(){
  setStatus("Revealing solution...");
  showResult(await api("/api/show_solution"));
}

let revealTimer = null;   // set while the button says "Click again to reveal"

function revealSolution(){
  // It spoils the puzzle, so the first click only asks; a second click within 4 s reveals
  if (!revealTimer) {
    qs("showSolution").textContent = "Click again to reveal";
    revealTimer = setTimeout(resetRevealButton, 4000);
    return;
  }
  resetRevealButton();
  showSolution();
}

function resetRevealButton(){
  clearTimeout(revealTimer);
  revealTimer = null;
  qs("showSolution").textContent = "Reveal solution";
}

// ---- Hints and proofs ----

function showHintMessage(text, tip=""){
  // A readable box at the top of the hint list; tip = what to try next
  const list = qs("hintList");
  list.textContent = "";
  const box = el("div", "hintSummary", text);
  if (tip) box.appendChild(el("div", "hintTip", tip));
  list.appendChild(box);
}

function countText(n, one, many){
  return n === 1 ? one : `${n} ${many}`;
}

async function hintSafe(){
  showHintMessage("Checking your neighbours with Mace4...");
  const res = await api("/api/hint_safe");
  if (!res.cells) return showHintMessage(res.error || "Something went wrong. Reload the page.");
  state = res;
  render();
  if (state.dead) return showHintMessage("The game is over.");

  const moves = res.safeMoves;
  if (moves.length === 0) {
    return showHintMessage("No provably safe moves next to you yet.",
      "This hint only checks the cells next to you. Step back onto another visited cell, or try Show forced mines.");
  }
  showHintMessage(countText(moves.length, "1 safe move next to you:", "safe moves next to you:"));
  for (const [r, c] of moves) qs("hintList").appendChild(safeMoveRow(r, c));
}

async function hintForced(){
  showHintMessage("Checking every cell with Mace4...");
  const res = await api("/api/hint_forced");
  if (!res.cells) return showHintMessage(res.error || "Something went wrong. Reload the page.");
  state = res;
  render();

  const mines = res.forcedMines;
  if (mines.length === 0) {
    return showHintMessage("No forced mines with what you know so far.", "Collect more clues, then check again.");
  }
  showHintMessage(countText(mines.length, "1 cell must be a mine:", "cells must be mines:"));
  for (const [r, c] of mines) {
    const row = el("div", "hintRow mine");
    row.append(el("span", "badge", `(${r},${c})`), el("span", "hintLabel", "Must be a mine"));
    qs("hintList").appendChild(row);
  }
}

function safeMoveRow(r, c){
  // "(1,3)  Provably safe  [Show proof]", with the proof unfolding underneath
  const row = el("div", "hintRow safe");
  const head = el("div", "hintHead");
  const toggle = el("button", "proofToggle", "Show proof");
  head.append(el("span", "badge", `(${r},${c})`), el("span", "hintLabel", "Provably safe"), toggle);
  const proof = el("div", "proof");
  proof.hidden = true;
  row.append(head, proof);
  toggle.addEventListener("click", () => toggleProof(r, c, toggle, proof));
  return row;
}

async function toggleProof(r, c, toggle, proof){
  const opening = proof.hidden;
  closeProofs();   // one proof open at a time
  if (!opening) return;

  proof.hidden = false;
  toggle.textContent = "Hide proof";
  proof.textContent = "Asking Prover9...";
  const res = await api(`/api/explain_safe?r=${r}&c=${c}`);
  if (!proof.hidden) renderProof(proof, res);   // unless it was closed while waiting
}

function closeProofs(){
  for (const p of document.querySelectorAll(".proof")) p.hidden = true;
  for (const b of document.querySelectorAll(".proofToggle")) b.textContent = "Show proof";
  markProofCells([]);
}

function renderProof(box, res){
  box.textContent = "";
  if (res.error) return box.appendChild(el("p", "proofNote", res.error));
  if (res.status === "not_safe") return box.appendChild(el("p", "proofNote", "Not provably safe with what you know so far."));
  if (res.status === "no_short_proof") {
    return box.appendChild(el("p", "proofNote",
      "Safe, but Prover9 found no short proof. This usually means it follows from counting the mines."));
  }

  box.appendChild(el("p", "proofNote", "Follows from:"));
  for (const fact of res.facts) box.appendChild(factRow(fact));
  if (res.usesMineCount) box.appendChild(factRow({ kind: "count", text: `There are exactly ${res.mines} mines.` }));
  markProofCells(res.facts.filter(fact => fact.cell).map(fact => fact.cell));
}

function factRow(fact){
  const row = el("div", "factRow");
  if (fact.cell) row.appendChild(el("span", "badge", `(${fact.cell[0]},${fact.cell[1]})`));
  if (fact.kind === "clue") row.appendChild(el("span", "formula", fact.text));
  else if (fact.kind === "visited") row.appendChild(el("span", "", "You stood here, so it has no mine."));
  else if (fact.kind === "flag") row.appendChild(el("span", "", "You flagged this as a mine."));
  else row.appendChild(el("span", "", fact.text));
  return row;
}

function markProofCells(cells){
  // Highlight the clues a proof uses, both in the knowledge base and on the board
  for (const e of document.querySelectorAll(".inProof")) e.classList.remove("inProof");
  for (const [r, c] of cells) {
    for (const e of document.querySelectorAll(`.cell[data-r="${r}"][data-c="${c}"], .kbRow[data-cell="${r},${c}"]`)) {
      e.classList.add("inProof");
    }
  }
}

// ---- Theme ----
// index.html sets data-theme before the page is drawn; this button switches it and saves the choice.

const THEME_ICONS = {
  light: '<svg class="uiIcon" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2.5v2M12 19.5v2M4.6 4.6l1.4 1.4M18 18l1.4 1.4M2.5 12h2M19.5 12h2M4.6 19.4L6 18M18 6l1.4-1.4"/></svg>',
  dark:  '<svg class="uiIcon" viewBox="0 0 24 24" aria-hidden="true"><path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z"/></svg>',
};

function otherTheme(){
  return document.documentElement.dataset.theme === "dark" ? "light" : "dark";
}

function renderThemeButton(){
  // The button shows the theme you would switch to
  const btn = qs("themeToggle");
  btn.innerHTML = THEME_ICONS[otherTheme()];
  btn.title = `Switch to ${otherTheme()} theme`;
  btn.setAttribute("aria-label", btn.title);
}

function toggleTheme(){
  const next = otherTheme();
  document.documentElement.dataset.theme = next;
  try { localStorage.setItem("minefolTheme", next); } catch (e) {}
  renderThemeButton();
}

// ---- How to play ----
// A <details> that opens upward (see style.css). It also closes when you click
// anywhere else or press Esc, and opens by itself on your first visit.

function setupHelp(){
  const help = qs("help");
  document.addEventListener("click", e => { if (!help.contains(e.target)) help.open = false; });
  document.addEventListener("keydown", e => { if (e.key === "Escape") help.open = false; });

  let seen = "1";
  try {
    seen = localStorage.getItem("minefolHelpSeen");
    localStorage.setItem("minefolHelpSeen", "1");
  } catch (e) {}
  if (!seen) help.open = true;
}

// ---- Start ----

window.addEventListener("DOMContentLoaded", async () => {
  qs("newGame").addEventListener("click", newGame);
  qs("hintSafe").addEventListener("click", hintSafe);
  qs("hintForced").addEventListener("click", hintForced);
  qs("prevPuzzle").addEventListener("click", () => stepPuzzle(-1));
  qs("nextPuzzle").addEventListener("click", () => stepPuzzle(1));
  qs("showSolution").addEventListener("click", revealSolution);
  qs("cursorMode").addEventListener("click", toggleCursorMode);
  qs("flagModeBtn").addEventListener("click", toggleFlagMode);
  qs("themeToggle").addEventListener("click", toggleTheme);
  qs("kbReset").addEventListener("click", resetClueOrder);
  window.addEventListener("keydown", handleKey);
  renderThemeButton();
  setupHelp();

  setStatus("Loading game...");
  puzzles = (await api("/api/puzzles")).categories;
  const session = await api("/api/state");
  updateModeButtons();

  // A link like ?d=hard&n=2 opens that puzzle; otherwise continue the current game
  const params = new URLSearchParams(location.search);
  const cat = categoryInfo(params.get("d"));
  const n = parseInt(params.get("n"), 10);
  if (cat && cat.numbers.includes(n) && (cat.name !== session.category || n !== session.number)) {
    loadPuzzle(cat.name, n);
  } else {
    showPuzzle(session);
  }
});
