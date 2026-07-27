const elements = __PAYLOAD_JSON__;
const hasTimeline = __HAS_TIMELINE__;
const dagreAvailable = typeof cytoscapeDagre === "function";
const elkAvailable = typeof cytoscapeElk === "function";
if (dagreAvailable) {
  cytoscape.use(cytoscapeDagre);
}
if (elkAvailable) {
  cytoscape.use(cytoscapeElk);
}

function runBreadthLayout() {
  cy.layout({
    name: "breadthfirst",
    directed: true,
    spacingFactor: 1.2,
    fit: true,
    padding: 30
  }).run();
}

function runDagreLayout() {
  if (dagreAvailable) {
    cy.layout({
      name: "dagre",
      rankDir: "TB",
      nodeSep: 40,
      edgeSep: 12,
      rankSep: 85,
      fit: true,
      padding: 30
    }).run();
    return;
  }
  runBreadthLayout();
}

function runElkLayeredLayout() {
  if (elkAvailable) {
    cy.layout({
      name: "elk",
      fit: true,
      padding: 30,
      nodeDimensionsIncludeLabels: true,
      elk: {
        algorithm: "layered",
        "elk.direction": "RIGHT",
        "elk.spacing.nodeNode": "30.0",
        "elk.layered.spacing.nodeNodeBetweenLayers": "80.0",
        "elk.edgeRouting": "ORTHOGONAL"
      }
    }).run();
    return;
  }
  runDagreLayout();
}

const cy = cytoscape({
  container: document.getElementById("cy"),
  elements: [...elements.nodes, ...elements.edges],
  style: [
    {
      selector: "node",
      style: {
        "label": "__NODE_LABEL_FIELD__",
        "font-size": __NODE_FONT_SIZE__,
        "color": "#0b1f33",
        "text-wrap": "wrap",
        "text-max-width": __NODE_TEXT_MAX_WIDTH__,
        "text-valign": "center",
        "text-halign": "center",
        "width": __NODE_SIZE__,
        "height": __NODE_SIZE__,
        "background-color": "__OTHER_NODE_COLOR__",
        "border-width": 1.3,
        "border-color": "#23395b",
      }
    },
    { selector: "node.focus", style: { "border-width": 2.6, "border-color": "#0f172a" } },
    { selector: "node[nodeKind = 'hl_start']", style: { "background-color": "__HL_START_COLOR__" } },
    { selector: "node[nodeKind = 'hl_end']", style: { "background-color": "__HL_END_COLOR__" } },
    { selector: "node[nodeKind = 'll_start']", style: { "background-color": "__LL_START_COLOR__" } },
    { selector: "node[nodeKind = 'll_end']", style: { "background-color": "__LL_END_COLOR__" } },
    {
      selector: "edge",
      style: {
        "curve-style": "bezier",
        "target-arrow-shape": "triangle",
        "line-color": "__OTHER_EDGE_COLOR__",
        "target-arrow-color": "__OTHER_EDGE_COLOR__",
        "width": 1.8,
        "label": "__EDGE_LABEL_FIELD__",
        "font-size": 8,
        "text-background-color": "#ffffff",
        "text-background-opacity": 0.9,
        "text-background-padding": 2,
        "text-rotation": "autorotate",
      }
    },
    { selector: "edge.focus", style: { "width": 3.2 } },
    { selector: "edge[type = 'ordering']", style: { "line-color": "__ASSUMPTION_EDGE_COLOR__", "target-arrow-color": "__ASSUMPTION_EDGE_COLOR__", "line-style": "dashed" } },
    { selector: "edge[type = 'causal_link']", style: { "line-color": "__CAUSAL_EDGE_COLOR__", "target-arrow-color": "__CAUSAL_EDGE_COLOR__" } },
    { selector: "edge[type = 'duration']", style: { "line-color": "__OTHER_EDGE_COLOR__", "target-arrow-color": "__OTHER_EDGE_COLOR__", "line-style": "dashed" } },
  ],
  layout: hasTimeline ? {
    name: "preset",
    fit: true,
    padding: 50
  } : (dagreAvailable ? {
    name: "dagre",
    rankDir: "TB",
    nodeSep: 40,
    edgeSep: 12,
    rankSep: 85,
    fit: true,
    padding: 30
  } : {
    name: "breadthfirst",
    directed: true,
    spacingFactor: 1.2,
    fit: true,
    padding: 30
  })
});

const edgeTypeFilterControls = {};
document.querySelectorAll(".edge-type-filter").forEach((control) => {
  edgeTypeFilterControls[String(control.dataset.edgeType || "")] = control;
});

function isEdgeVisibleByType(edge) {
  const edgeType = String(edge.data("type") || "constraint");
  const control = edgeTypeFilterControls[edgeType];
  return !control || control.checked;
}

function applyEdgeTypeFilter() {
  cy.edges().forEach((edge) => {
    edge.style("display", isEdgeVisibleByType(edge) ? "element" : "none");
  });
}

function showDetails(text) {
  document.getElementById("details").textContent = text;
}

let selectedElements = [];

function selectionKey(kind, id) {
  return `${kind}:${id}`;
}

function isAdditiveSelection(evt) {
  const originalEvent = evt.originalEvent || {};
  return Boolean(originalEvent.ctrlKey || originalEvent.metaKey);
}

function updateSelection(kind, id, additive) {
  const key = selectionKey(kind, id);
  if (!additive) {
    selectedElements = [{ kind, id }];
    return;
  }

  const existingIndex = selectedElements.findIndex((item) => selectionKey(item.kind, item.id) === key);
  if (existingIndex >= 0) {
    selectedElements.splice(existingIndex, 1);
  } else {
    selectedElements.push({ kind, id });
  }
}

function applySearchFilter() {
  const query = document.getElementById("search").value.trim().toLowerCase();
  if (!query) {
    cy.nodes().forEach((node) => node.style("opacity", 1.0));
    cy.edges().forEach((edge) => edge.style("opacity", 0.9));
    return;
  }

  const matchedNodeIds = new Set();
  cy.nodes().forEach((node) => {
    const hit = String(node.data("search") || "").includes(query);
    node.style("opacity", hit ? 1.0 : 0.18);
    if (hit) {
      matchedNodeIds.add(node.id());
    }
  });

  cy.edges().forEach((edge) => {
    const edgeHit = String(edge.data("search") || "").includes(query);
    const neighborHit = matchedNodeIds.has(edge.source().id()) || matchedNodeIds.has(edge.target().id());
    edge.style("opacity", (edgeHit || neighborHit) ? 1.0 : 0.08);
  });
}

function applyFocusFilter() {
  if (selectedElements.length === 0) {
    return false;
  }

  cy.nodes().forEach((node) => {
    node.style("opacity", 0.18);
    node.removeClass("focus");
  });
  cy.edges().forEach((edge) => {
    edge.style("opacity", 0.08);
    edge.removeClass("focus");
  });

  const validSelections = [];
  selectedElements.forEach((item) => {
    const selected = cy.$id(item.id);
    if (selected && selected.length > 0) {
      if (item.kind === "edge" && !isEdgeVisibleByType(selected)) {
        return;
      }
      selected.style("opacity", 1.0);
      selected.addClass("focus");
      validSelections.push(item);
    }
  });

  selectedElements = validSelections;
  return selectedElements.length > 0;
}

function refreshVisibility() {
  applyEdgeTypeFilter();
  if (!applyFocusFilter()) {
    applySearchFilter();
  }
}

cy.on("tap", "node", (evt) => {
  const d = evt.target.data();
  const timeText = d.timestamp !== undefined ? `\ntimestamp: ${d.timestamp}` : "";
  const detailText = d.detailLabel ? `\ninfo: ${d.detailLabel}` : "";
  updateSelection("node", evt.target.id(), isAdditiveSelection(evt));
  refreshVisibility();
  showDetails(`Node: ${d.id}\nphase: ${d.phase}\nkind: ${d.nodeKind}${timeText}${detailText}`);
});
cy.on("tap", "edge", (evt) => {
  const d = evt.target.data();
  updateSelection("edge", evt.target.id(), isAdditiveSelection(evt));
  refreshVisibility();
  showDetails(`Edge: ${d.source} -> ${d.target}\ntype: ${d.type}\nlabel: ${d.label}`);
});
cy.on("tap", (evt) => {
  if (evt.target === cy && !isAdditiveSelection(evt)) {
    selectedElements = [];
    refreshVisibility();
    showDetails(__DEFAULT_DETAILS_JSON__);
  }
});

__TIMELINE_SYNC_SCRIPT__
__TIMELINE_BUTTON_SCRIPT__
document.getElementById("layoutDagre").addEventListener("click", runDagreLayout);
document.getElementById("layoutElk").addEventListener("click", runElkLayeredLayout);
document.getElementById("layoutBreadth").addEventListener("click", runBreadthLayout);
document.getElementById("layoutCose").addEventListener("click", () => {
  cy.layout({
    name: "cose",
    animate: false,
    fit: true,
    padding: 30
  }).run();
});
document.getElementById("fit").addEventListener("click", () => {
  cy.fit(undefined, 30);
});
document.getElementById("search").addEventListener("input", () => {
  if (selectedElements.length > 0) {
    selectedElements = [];
  }
  refreshVisibility();
});
document.querySelectorAll(".edge-type-filter").forEach((control) => {
  control.addEventListener("change", () => {
    refreshVisibility();
  });
});
refreshVisibility();
