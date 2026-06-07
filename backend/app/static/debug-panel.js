const eventList = document.getElementById("event-list");
const detailBox = document.getElementById("detail-box");
const connectionStatus = document.getElementById("connection-status");
const characterGrid = document.getElementById("character-grid");
const worldState = document.getElementById("world-state");
const backendState = document.getElementById("backend-state");
const simingState = document.getElementById("siming-state");
const actorFilter = document.getElementById("actor-filter");
const domainFilters = [...document.querySelectorAll("[data-domain-filter]")];

const events = [];
let activeSequence = null;
const actorIds = new Set();

function getSelectedDomains() {
  return new Set(
    domainFilters
      .filter((input) => input.checked)
      .map((input) => input.value),
  );
}

function getFilteredEvents() {
  const selectedDomains = getSelectedDomains();
  const selectedActor = actorFilter.value;
  return events.filter((event) => {
    if (!selectedDomains.has(event.domain)) {
      return false;
    }
    if (!selectedActor) {
      return true;
    }
    return event.actor_id === selectedActor;
  });
}

function buildCharacterState(filteredEvents) {
  const state = new Map();
  function ensureCharacter(actorId) {
    if (!state.has(actorId)) {
      state.set(actorId, {
        input: "暂无",
        interpretation: "暂无",
        candidate: "暂无",
        output: "暂无",
        timeline: [],
      });
    }
    return state.get(actorId);
  }

  for (const event of filteredEvents) {
    if (event.domain !== "character" || !event.actor_id) {
      continue;
    }
    const actorState = ensureCharacter(event.actor_id);
    actorState.timeline.push({
      sequence: event.sequence,
      stage: event.stage,
      summary: event.summary,
    });
    if (event.stage === "character_input_received") {
      actorState.input = event.summary;
    } else if (event.stage === "character_interpretation_updated") {
      actorState.interpretation = event.summary;
    } else if (event.stage === "character_candidate_updated") {
      actorState.candidate = event.summary;
    } else if (event.stage === "character_output_emitted") {
      actorState.output = event.summary;
    }
  }
  return state;
}

function renderCharacters(filteredEvents) {
  const characterState = buildCharacterState(filteredEvents);
  characterGrid.innerHTML = "";
  const ids = [...characterState.keys()].sort();
  for (const actorId of ids) {
    const state = characterState.get(actorId);
    const timelineItems = state.timeline.slice(-5).reverse().map((item) => `
      <div class="timeline-item">
        <div class="meta">#${item.sequence} · ${item.stage}</div>
        <div>${item.summary}</div>
      </div>
    `).join("");
    const card = document.createElement("div");
    card.className = "character-card";
    card.innerHTML = `
      <h3>${actorId}</h3>
      <div class="character-row"><span class="label">收到的信息</span><div>${state.input}</div></div>
      <div class="character-row"><span class="label">当前理解</span><div>${state.interpretation}</div></div>
      <div class="character-row"><span class="label">候选反应</span><div>${state.candidate}</div></div>
      <div class="character-row"><span class="label">最终输出</span><div>${state.output}</div></div>
      <div class="timeline">
        <span class="label">最近动态</span>
        ${timelineItems || '<div class="timeline-item"><div>暂无动态</div></div>'}
      </div>
    `;
    characterGrid.appendChild(card);
  }
}

function updateGlobalPanels(filteredEvents) {
  worldState.textContent = "暂无";
  backendState.textContent = "暂无";
  simingState.textContent = "暂无";
  for (const event of [...filteredEvents].reverse()) {
    if (event.domain === "world" && worldState.textContent === "暂无") {
      worldState.textContent = event.summary;
    }
    if (event.domain === "backend" && backendState.textContent === "暂无") {
      backendState.textContent = event.summary;
    }
    if (event.domain === "siming" && simingState.textContent === "暂无") {
      simingState.textContent = event.summary;
    }
  }
}

function renderEvents(filteredEvents) {
  eventList.innerHTML = "";
  for (const event of [...filteredEvents].reverse()) {
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

function refreshView() {
  const filteredEvents = getFilteredEvents();
  updateGlobalPanels(filteredEvents);
  renderCharacters(filteredEvents);
  renderEvents(filteredEvents);
  const activeStillVisible = filteredEvents.some((event) => event.sequence === activeSequence);
  if (!activeStillVisible) {
    const latest = filteredEvents[filteredEvents.length - 1];
    activeSequence = latest ? latest.sequence : null;
    detailBox.textContent = latest ? JSON.stringify(latest.detail, null, 2) : "{}";
  }
}

function syncActorFilterOptions() {
  const current = actorFilter.value;
  const sortedActors = [...actorIds].sort();
  actorFilter.innerHTML = `<option value="">全部角色</option>`;
  for (const actorId of sortedActors) {
    const option = document.createElement("option");
    option.value = actorId;
    option.textContent = actorId;
    actorFilter.appendChild(option);
  }
  actorFilter.value = sortedActors.includes(current) ? current : "";
}

function handleEvent(event) {
  events.push(event);
  if (events.length > 60) {
    events.shift();
  }
  if (event.actor_id) {
    actorIds.add(event.actor_id);
    syncActorFilterOptions();
  }
  refreshView();
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

actorFilter.addEventListener("change", refreshView);
for (const checkbox of domainFilters) {
  checkbox.addEventListener("change", refreshView);
}

connect();
