const eventList = document.getElementById("event-list");
const detailBox = document.getElementById("detail-box");
const connectionStatus = document.getElementById("connection-status");
const characterGrid = document.getElementById("character-grid");
const worldState = document.getElementById("world-state");
const backendState = document.getElementById("backend-state");
const simingState = document.getElementById("siming-state");

const events = [];
const characterState = new Map();
let activeSequence = null;

function ensureCharacter(actorId) {
  if (!characterState.has(actorId)) {
    characterState.set(actorId, {
      input: "暂无",
      interpretation: "暂无",
      candidate: "暂无",
      output: "暂无",
    });
  }
  return characterState.get(actorId);
}

function renderCharacters() {
  characterGrid.innerHTML = "";
  const ids = [...characterState.keys()].sort();
  for (const actorId of ids) {
    const state = characterState.get(actorId);
    const card = document.createElement("div");
    card.className = "character-card";
    card.innerHTML = `
      <h3>${actorId}</h3>
      <div class="character-row"><span class="label">收到的信息</span><div>${state.input}</div></div>
      <div class="character-row"><span class="label">当前理解</span><div>${state.interpretation}</div></div>
      <div class="character-row"><span class="label">候选反应</span><div>${state.candidate}</div></div>
      <div class="character-row"><span class="label">最终输出</span><div>${state.output}</div></div>
    `;
    characterGrid.appendChild(card);
  }
}

function updateGlobalPanels(event) {
  if (event.domain === "world") {
    worldState.textContent = event.summary;
  }
  if (event.domain === "backend") {
    backendState.textContent = event.summary;
  }
  if (event.domain === "siming") {
    simingState.textContent = event.summary;
  }
}

function updateCharacterPanels(event) {
  if (event.domain !== "character" || !event.actor_id) {
    return;
  }
  const state = ensureCharacter(event.actor_id);
  if (event.stage === "character_input_received") {
    state.input = event.summary;
  } else if (event.stage === "character_interpretation_updated") {
    state.interpretation = event.summary;
  } else if (event.stage === "character_candidate_updated") {
    state.candidate = event.summary;
  } else if (event.stage === "character_output_emitted") {
    state.output = event.summary;
  }
}

function renderEvents() {
  eventList.innerHTML = "";
  for (const event of [...events].reverse()) {
    const node = document.createElement("div");
    node.className = `event ${event.domain}` + (event.sequence === activeSequence ? " active" : "");
    node.innerHTML = `
      <div class="meta">#${event.sequence} · ${event.domain} · ${event.stage}</div>
      <div>${event.summary}</div>
    `;
    node.onclick = () => {
      activeSequence = event.sequence;
      detailBox.textContent = JSON.stringify(event.detail, null, 2);
      renderEvents();
    };
    eventList.appendChild(node);
  }
}

function handleEvent(event) {
  events.push(event);
  if (events.length > 60) {
    events.shift();
  }
  updateGlobalPanels(event);
  updateCharacterPanels(event);
  renderCharacters();
  renderEvents();
  if (activeSequence === null) {
    activeSequence = event.sequence;
    detailBox.textContent = JSON.stringify(event.detail, null, 2);
  }
}

function connect() {
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  const socket = new WebSocket(`${protocol}://${window.location.host}/debug/ws`);
  socket.onopen = () => {
    connectionStatus.textContent = "已连接";
  };
  socket.onmessage = (message) => {
    const event = JSON.parse(message.data);
    handleEvent(event);
  };
  socket.onclose = () => {
    connectionStatus.textContent = "连接断开，3 秒后重连";
    setTimeout(connect, 3000);
  };
}

connect();
