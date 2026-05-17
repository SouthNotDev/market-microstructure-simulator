const fallbackTrace = {
  symbol: "ABC",
  steps: [
    {
      eventNumber: 1,
      event: { kind: "LIMIT", side: "SELL", quantity: 300, price: "100.60", label: "SELL 300 @ 100.60", agent: "Trader Alpha" },
      incomingOrderId: 1,
      timestamp: 1,
      status: "RESTING",
      filledQuantity: 0,
      canceledQuantity: 0,
      restingQuantity: 300,
      trades: [],
      after: { bestBid: "-", bestAsk: "100.60", spread: null, midRaw: null, bidDepth: [], askDepth: [{ price: "100.60", size: 300, orders: 1 }] },
      midSeries: []
    }
  ]
};

let trace = fallbackTrace;
let stepIndex = 0;
let phaseIndex = 0;
let running = true;
let timer = null;
let packetAnimation = null;

const phases = ["agent", "exchange", "matcher", "book", "recorder", "snapshot"];
const el = (id) => document.getElementById(id);
const fallbackAgents = Array.from({ length: 16 }, (_, index) => `Agent ${String(index + 1).padStart(2, "0")}`);
const orderPalette = [
  "#9be71a",
  "#42d6ff",
  "#ffc857",
  "#ff7ab6",
  "#6ee7b7",
  "#c084fc",
  "#f97316",
  "#38bdf8",
  "#e879f9",
  "#a3e635",
  "#fb7185",
  "#2dd4bf"
];

async function loadTrace() {
  try {
    const response = await fetch("./trace.json", { cache: "no-store" });
    if (response.ok) trace = await response.json();
  } catch {
    trace = fallbackTrace;
  }

  if (Number.isInteger(trace.defaultStepIndex)) {
    stepIndex = trace.defaultStepIndex;
  }
}

function currentStep() {
  return trace.steps[stepIndex % trace.steps.length];
}

function stepAt(index) {
  const steps = trace.steps;
  return steps[((index % steps.length) + steps.length) % steps.length];
}

function setText(id, value) {
  const node = el(id);
  if (node) node.textContent = value ?? "-";
}

function orderAccent(orderId) {
  return orderPalette[(orderId - 1) % orderPalette.length];
}

function applyOrderTheme(step) {
  document.documentElement.style.setProperty("--order-accent", orderAccent(step.incomingOrderId));
}

function formatTime(step) {
  const ms = String(step.timestamp * 2173).padStart(3, "0");
  return `00:00:${String(step.timestamp * 2).padStart(2, "0")}.${ms.slice(-3)}`;
}

function eventClass(event) {
  if (event.kind === "MARKET") return "MarketOrder";
  return "LimitOrder";
}

function stepPayloads(step) {
  const event = step.event;
  const tradeText = step.trades.length
    ? step.trades.map((t) => `Trade #${t.tradeId}: ${t.quantity} @ ${t.price}`).join(" | ")
    : "No Trade";
  const bookAction = step.filledQuantity
    ? `Book update: filled ${step.filledQuantity}, resting ${step.restingQuantity}`
    : `BookOrder: remaining ${step.restingQuantity}`;

  return {
    event: `${eventClass(event)}(${event.side}, qty=${event.quantity}, price=${event.price})`,
    order: `Order(id=${step.incomingOrderId}, ts=${step.timestamp})`,
    match: `MatchResult(${step.status}, filled=${step.filledQuantity}, canceled=${step.canceledQuantity})`,
    book: bookAction,
    snapshot: `Snapshot(bestBid=${step.after.bestBid}, bestAsk=${step.after.bestAsk}, mid=${step.after.midRaw?.toFixed?.(3) ?? "-"})`,
    trades: tradeText
  };
}

function footerPayload(step) {
  const event = step.event;
  const fill = step.filledQuantity ? `filled ${step.filledQuantity}` : "no fill";
  const rest = step.restingQuantity ? `resting ${step.restingQuantity}` : "no rest";
  return `${event.agent} ${event.label} -> ${step.status} (${fill}, ${rest})`;
}

function renderAgents(activeAgent) {
  const list = el("agentList");
  const agents = trace.agents?.length ? trace.agents : fallbackAgents;
  list.innerHTML = "";

  for (const agent of agents.slice(0, 24)) {
    const row = document.createElement("div");
    row.className = `agent-row ${agent === activeAgent ? "selected" : ""}`;
    row.textContent = agent;
    list.appendChild(row);
  }
}

function visibleRows(rows, count = 6) {
  const output = rows.slice(0, count);
  while (output.length < count) output.push(null);
  return output;
}

function renderDepth(containerId, rows, side, highlightPrice) {
  const container = el(containerId);
  container.innerHTML = "";
  for (const row of visibleRows(rows)) {
    const div = document.createElement("div");
    div.className = `book-row ${side}`;
    if (!row) {
      div.classList.add("empty");
      div.innerHTML = "<span>...</span><span></span><span></span>";
    } else {
      if (row.price === highlightPrice) div.classList.add("highlight");
      div.innerHTML = `<span>${row.price}</span><span>${row.size}</span><span>${row.orders}</span>`;
    }
    container.appendChild(div);
  }
}

function renderChart(series) {
  const grid = el("gridLines");
  grid.innerHTML = "";
  for (let x = 18; x <= 414; x += 49) {
    const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
    line.setAttribute("x1", x);
    line.setAttribute("x2", x);
    line.setAttribute("y1", 8);
    line.setAttribute("y2", 138);
    grid.appendChild(line);
  }
  for (let y = 18; y <= 138; y += 24) {
    const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
    line.setAttribute("x1", 18);
    line.setAttribute("x2", 414);
    line.setAttribute("y1", y);
    line.setAttribute("y2", y);
    grid.appendChild(line);
  }

  if (!series.length) {
    el("midLine").setAttribute("points", "");
    el("midDot").setAttribute("cx", 0);
    el("midDot").setAttribute("cy", 0);
    setText("midTag", "-");
    return;
  }

  const ys = series.map((point) => point.y);
  const rawMin = Math.min(...ys);
  const rawMax = Math.max(...ys);
  const center = (rawMin + rawMax) / 2;
  const span = Math.max(rawMax - rawMin, 0.03);
  const min = center - span * 0.62;
  const max = center + span * 0.62;
  const points = series.map((point, index) => {
    const x = 22 + index * (386 / Math.max(series.length - 1, 1));
    const y = 132 - ((point.y - min) / Math.max(max - min, 0.01)) * 105;
    return [x, y, point.y];
  });

  el("midLine").setAttribute("points", points.map(([x, y]) => `${x},${y}`).join(" "));
  const [x, y, value] = points[points.length - 1];
  el("midDot").setAttribute("cx", x);
  el("midDot").setAttribute("cy", y);
  el("midTag").setAttribute("x", Math.min(x + 12, 366));
  el("midTag").setAttribute("y", y + 4);
  setText("midTag", value.toFixed(3));
}

function setCanvasScale() {
  const scale = Math.min(window.innerWidth / 1600, window.innerHeight / 900);
  document.documentElement.style.setProperty("--scale", String(scale));
}

function portPosition(name) {
  const port = document.querySelector(`[data-port="${name}"]`);
  const frame = document.querySelector(".frame");
  const portRect = port.getBoundingClientRect();
  const frameRect = frame.getBoundingClientRect();
  const scale = frameRect.width / frame.offsetWidth;
  return {
    x: (portRect.left + portRect.width / 2 - frameRect.left) / scale,
    y: (portRect.top + portRect.height / 2 - frameRect.top) / scale
  };
}

function connectorPath(from, to) {
  const dx = Math.max(40, Math.abs(to.x - from.x) * 0.45);
  if (Math.abs(to.y - from.y) < 70) {
    return `M ${from.x} ${from.y} C ${from.x + dx} ${from.y}, ${to.x - dx} ${to.y}, ${to.x} ${to.y}`;
  }
  const midY = (from.y + to.y) / 2;
  return `M ${from.x} ${from.y} C ${from.x + dx} ${from.y}, ${from.x + dx} ${midY}, ${(from.x + to.x) / 2} ${midY} S ${to.x - dx} ${to.y}, ${to.x} ${to.y}`;
}

function routedPath(from, to, flow) {
  if (flow.route === "observer") {
    const laneY = flow.laneY;
    return `M ${from.x} ${from.y} L ${from.x} ${laneY} L ${to.x} ${laneY} L ${to.x} ${to.y}`;
  }
  if (flow.route === "topbook") {
    const laneX = Math.min(from.x + 14, 1582);
    return `M ${from.x} ${from.y} L ${laneX} ${from.y} L ${laneX} ${to.y} L ${to.x} ${to.y}`;
  }
  return connectorPath(from, to);
}

function flowDefinitions(step) {
  const event = step.event;
  return [
    { key: "agent-ticket", phase: "agent", type: "active", from: "agent-out", to: "ticket-in", label: "emit", labelAt: [310, 186] },
    { key: "ticket-exchange", phase: "exchange", type: "active", from: "ticket-out", to: "exchange-in", label: "validate", labelAt: [514, 196] },
    { key: "exchange-id", phase: "exchange", type: "active", from: "exchange-out", to: "id-in", label: `id=${step.incomingOrderId}`, labelAt: [765, 196] },
    { key: "id-matcher", phase: "matcher", type: "active", from: "id-out", to: "matcher-in", label: "route", labelAt: [940, 196] },
    { key: "matcher-book", phase: "book", type: "active", from: "matcher-out", to: "book-in", label: step.filledQuantity ? `fill ${step.filledQuantity}` : `rest ${step.restingQuantity}`, labelAt: [1248, 204] },
    { key: "book-top", phase: "book", type: "passive", from: "book-out", to: "topbook-in", route: "topbook", label: "top", labelAt: [1504, 498] },
    { key: "match-recorder", phase: "recorder", type: "passive", from: "matcher-record", to: "recorder-in-a", route: "observer", laneY: 488, label: "result", labelAt: [500, 470] },
    { key: "book-recorder", phase: "recorder", type: "passive", from: "book-record", to: "recorder-in-b", route: "observer", laneY: 510, label: "snapshot", labelAt: [792, 492] },
    { key: "recorder-chart", phase: "snapshot", type: "passive", from: "recorder-out", to: "chart-in", route: "observer", laneY: 628, label: `mid=${step.after.midRaw?.toFixed?.(3) ?? "-"}`, labelAt: [900, 610] }
  ];
}

function renderConnectors(step) {
  const frame = document.querySelector(".frame");
  const svg = el("connectorLayer");
  const paths = el("connectorPaths");
  const labels = el("connectorLabels");
  const packets = el("flowPackets");
  const width = frame.offsetWidth;
  const height = frame.offsetHeight;
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  paths.innerHTML = "";
  labels.innerHTML = "";
  packets.innerHTML = "";
  const activePhase = phases[phaseIndex];
  const flows = flowDefinitions(step);

  for (const flow of flows) {
    const from = portPosition(flow.from);
    const to = portPosition(flow.to);
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("id", `flow-${flow.key}`);
    path.setAttribute("class", `connector-path ${flow.type} ${flow.phase === activePhase ? "active" : ""}`);
    path.setAttribute("d", routedPath(from, to, flow));
    paths.appendChild(path);

    if (flow.phase === activePhase) {
      const x = flow.labelAt ? flow.labelAt[0] : (from.x + to.x) / 2;
      const y = flow.labelAt ? flow.labelAt[1] : (from.y + to.y) / 2 - 14;
      const label = document.createElementNS("http://www.w3.org/2000/svg", "g");
      label.setAttribute("class", "connector-label");
      const text = flow.label;
      const labelWidth = Math.min(180, Math.max(56, text.length * 7.2 + 18));
      label.innerHTML = `<rect x="${x - labelWidth / 2}" y="${y - 15}" width="${labelWidth}" height="23"></rect><text x="${x - labelWidth / 2 + 8}" y="${y + 1}">${escapeXml(text)}</text>`;
      labels.appendChild(label);
    }
  }

  renderFlowPackets(flows, packets);
}

function escapeXml(text) {
  return text.replace(/[<>&"]/g, (char) => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;", '"': "&quot;" }[char]));
}

function packetRadius(step) {
  return Math.min(9.5, Math.max(4.2, Math.sqrt(step.event.quantity) / 2.15));
}

function packetOpacity(age) {
  return Math.max(0.36, 1 - age * 0.06);
}

function packetSlots() {
  return [
    { key: "agent-ticket", progressOffset: 0.06 },
    { key: "ticket-exchange", progressOffset: 0.02 },
    { key: "exchange-id", progressOffset: 0.08 },
    { key: "id-matcher", progressOffset: 0.03 },
    { key: "matcher-book", progressOffset: 0.04 },
    { key: "book-top", progressOffset: 0.12 },
    { key: "match-recorder", progressOffset: 0.00 },
    { key: "book-recorder", progressOffset: 0.09 },
    { key: "recorder-chart", progressOffset: 0.05 }
  ];
}

function renderFlowPackets(flows, packets) {
  if (packetAnimation) cancelAnimationFrame(packetAnimation);

  const slotDefinitions = packetSlots();
  const specs = slotDefinitions.map((slot, age) => {
    const path = el(`flow-${slot.key}`);
    if (!path) return null;

    const step = stepAt(stepIndex - age);
    const color = orderAccent(step.incomingOrderId);
    const d = path.getAttribute("d");
    const opacity = packetOpacity(age);
    const length = path.getTotalLength();
    const trailLength = Math.min(92, Math.max(34, length * 0.19));

    const trail = document.createElementNS("http://www.w3.org/2000/svg", "path");
    trail.setAttribute("class", "packet-trail");
    trail.setAttribute("d", d);
    trail.setAttribute("stroke", color);
    trail.setAttribute("opacity", String(opacity));
    trail.setAttribute("stroke-dasharray", `${trailLength} ${length}`);
    trail.setAttribute("stroke-dashoffset", String(length));
    packets.appendChild(trail);

    const packet = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    packet.setAttribute("r", String(packetRadius(step)));
    packet.setAttribute("class", "flow-packet");
    packet.setAttribute("fill", color);
    packet.setAttribute("opacity", String(opacity));
    packets.appendChild(packet);

    return {
      path,
      packet,
      trail,
      length,
      trailLength,
      progressOffset: slot.progressOffset,
    };
  }).filter(Boolean);

  let start = null;
  function frame(timestamp) {
    if (!start) start = timestamp;
    const elapsed = timestamp - start;
    const baseProgress = Math.min(elapsed / 250, 1);

    for (const spec of specs) {
      const progress = Math.min(0.97, Math.max(0.03, baseProgress * 0.9 + spec.progressOffset));
      const point = spec.path.getPointAtLength(spec.length * progress);
      spec.packet.setAttribute("cx", point.x);
      spec.packet.setAttribute("cy", point.y);
      spec.trail.setAttribute("stroke-dashoffset", String(spec.length * (1 - progress) + spec.trailLength / 2));
    }

    if (baseProgress < 1) packetAnimation = requestAnimationFrame(frame);
  }

  packetAnimation = requestAnimationFrame(frame);
}

function setActiveNodes() {
  document.querySelectorAll(".node,.payload-card,.top-book,.chart-panel").forEach((node) => node.classList.remove("active"));
  const phase = phases[phaseIndex];
  const idsByPhase = {
    agent: ["agentsNode", "orderCard"],
    exchange: ["exchangeNode", "idCard"],
    matcher: ["matcherNode"],
    book: ["bookNode", "topBookNode"],
    recorder: ["recorderNode"],
    snapshot: ["chartNode", "recorderNode"]
  };
  for (const id of idsByPhase[phase] ?? []) el(id)?.classList.add("active");
}

function render() {
  const step = currentStep();
  const event = step.event;
  const book = step.after;
  const payloads = stepPayloads(step);
  const impactedPrice = step.trades[0]?.price ?? (event.kind === "LIMIT" ? event.price : null);

  setCanvasScale();
  applyOrderTheme(step);
  setActiveNodes();
  setText("timeLabel", formatTime(step));
  setText("eventCount", String(12840 + step.eventNumber));
  setText("orderCount", String(step.incomingOrderId));
  setText("symbolLabel", trace.symbol || "ABC");
  renderAgents(event.agent);
  setText("agentIntent", `${event.agent}\n${event.label}`);
  setText("eventClass", eventClass(event));
  setText("ticketSide", event.side);
  setText("ticketQty", event.quantity);
  setText("ticketPrice", event.price);
  setText("ticketType", event.kind === "LIMIT" ? "GTC" : "IOC");
  setText("acceptedCount", step.incomingOrderId);
  setText("exchangeClock", step.timestamp);
  setText("nextId", step.incomingOrderId + 1);
  setText("assignedId", step.incomingOrderId);
  setText("assignedTs", step.timestamp);
  setText("incomingText", `ID ${step.incomingOrderId} ${event.label}`);
  setText("matchResult", step.status);
  setText("bestAsk", book.bestAsk);
  setText("bestBid", book.bestBid);
  setText("midPrice", book.midRaw ? book.midRaw.toFixed(3) : "-");
  setText("chartMid", book.midRaw ? book.midRaw.toFixed(3) : "-");
  setText("legendId", `ID ${step.incomingOrderId}`);
  setText("footerOrder", footerPayload(step));
  setText("orderLog", `ID ${step.incomingOrderId}\n${event.label}\n${step.status}`);
  setText("tradeLog", step.trades.length ? step.trades.map((trade) => `#${trade.tradeId} ${trade.quantity} @ ${trade.price}`).join("\n") : "No Trade");
  setText("snapshotLog", `bid ${book.bestBid}\nask ${book.bestAsk}\nmid ${book.midRaw ? book.midRaw.toFixed(3) : "-"}`);
  setText("metricLog", `spread ${book.spread ?? "-"}\ndepth levels ${(book.bidDepth?.length || 0) + (book.askDepth?.length || 0)}`);
  renderDepth("asks", book.askDepth || [], "ask", impactedPrice);
  renderDepth("bids", book.bidDepth || [], "bid", impactedPrice);
  renderChart(step.midSeries || []);
  requestAnimationFrame(() => renderConnectors(step));
}

function advance() {
  phaseIndex = (phaseIndex + 1) % phases.length;
  stepIndex = (stepIndex + 1) % trace.steps.length;
  render();
}

function previous() {
  phaseIndex = (phaseIndex - 1 + phases.length) % phases.length;
  stepIndex = (stepIndex - 1 + trace.steps.length) % trace.steps.length;
  render();
}

function startTimer() {
  clearInterval(timer);
  timer = setInterval(() => {
    if (running) advance();
  }, 280);
}

document.addEventListener("DOMContentLoaded", async () => {
  await loadTrace();
  setCanvasScale();
  window.addEventListener("resize", render);
  el("toggleRun").addEventListener("click", () => {
    running = !running;
    setText("toggleRun", running ? "PAUSE" : "RUN");
  });
  el("stepNext").addEventListener("click", advance);
  el("stepBack").addEventListener("click", previous);
  render();
  startTimer();
});
