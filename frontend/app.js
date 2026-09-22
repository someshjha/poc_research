(() => {
  "use strict";

  const ORCHESTRATOR_BASE = window.ORCHESTRATOR_BASE || "/api/orchestrator";
  const GATEWAY_BASE = window.GATEWAY_BASE || "/api/gateway";

  const stageOrder = ["literature", "derivation", "comparisons", "simulation", "review", "writeup", "trace"];
  const stageMeta = {
    literature: { eyebrow: "STAGE 01 · LITERATURE & CONTEXT", title: "Retrieving relevant prior work" },
    derivation: { eyebrow: "STAGE 02 · HYPOTHESIS & DERIVATION", title: "Live model derivation" },
    comparisons: { eyebrow: "STAGE 03 · MODEL COMPARISON", title: "Fanning out across providers" },
    simulation: { eyebrow: "STAGE 04 · SIMULATION", title: "Real numerical diagonalization" },
    review: { eyebrow: "STAGE 05 · PEER REVIEW", title: "Live critique pass" },
    writeup: { eyebrow: "STAGE 06 · WRITE-UP & EXPORT", title: "Assembled draft section" },
    trace: { eyebrow: "STAGE 07 · OBSERVABILITY", title: "Every call this run made" }
  };

  const stageTabs = [...document.querySelectorAll("[data-stage]")];
  const stageViews = [...document.querySelectorAll("[data-view]")];
  const stagePanel = document.querySelector("#stage-panel");
  let activeStage = "literature";
  let latestState = null;

  const escapeHtml = value => String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");

  function selectStage(stage) {
    if (!stageOrder.includes(stage)) return;
    activeStage = stage;
    stageViews.forEach(view => { view.hidden = view.dataset.view !== stage; });
    stageTabs.forEach(tab => {
      const isActive = tab.dataset.stage === stage;
      tab.classList.toggle("is-active", isActive);
      tab.setAttribute("aria-selected", String(isActive));
      tab.tabIndex = isActive ? 0 : -1;
    });
    document.querySelector("#stage-eyebrow").textContent = stageMeta[stage].eyebrow;
    document.querySelector("#stage-title").textContent = stageMeta[stage].title;
  }

  stageTabs.forEach(tab => tab.addEventListener("click", () => selectStage(tab.dataset.stage)));

  async function checkBackend() {
    const status = document.querySelector("#backend-status");
    try {
      const response = await fetch(`${GATEWAY_BASE}/healthz`);
      if (!response.ok) throw new Error("bad response");
      status.innerHTML = '<i aria-hidden="true"></i> Backend reachable';
    } catch {
      status.innerHTML = '<i aria-hidden="true"></i> Backend unreachable — check the gateway service';
    }
  }

  async function loadProviders() {
    const select = document.querySelector("#default-model-select");
    const picker = document.querySelector("#model-picker");
    try {
      const response = await fetch(`${GATEWAY_BASE}/v1/providers`);
      const providers = await response.json();

      const options = [];
      providers.forEach(provider => {
        provider.models.forEach(model => {
          options.push({ provider: provider.provider, model, configured: provider.configured });
        });
      });

      select.replaceChildren(...options.map(opt => {
        const el = document.createElement("option");
        el.value = JSON.stringify({ provider: opt.provider, model: opt.model });
        el.textContent = `${opt.provider} / ${opt.model}${opt.configured ? "" : " (no key set)"}`;
        el.disabled = !opt.configured;
        return el;
      }));
      const firstConfigured = options.find(o => o.configured);
      if (firstConfigured) select.value = JSON.stringify({ provider: firstConfigured.provider, model: firstConfigured.model });

      // Default-check at most two configured models so a first run doesn't
      // fan out across every locally pulled Ollama model.
      let defaultChecks = 2;
      picker.replaceChildren(...options.map(opt => {
        const label = document.createElement("label");
        label.className = "model-pill";
        const input = document.createElement("input");
        input.type = "checkbox";
        input.dataset.provider = opt.provider;
        input.dataset.model = opt.model;
        input.checked = opt.configured && defaultChecks > 0;
        if (input.checked) defaultChecks -= 1;
        input.disabled = !opt.configured;
        input.addEventListener("change", () => label.classList.toggle("is-checked", input.checked));
        if (input.checked) label.classList.add("is-checked");
        label.append(input, document.createTextNode(`${opt.provider}/${opt.model}${opt.configured ? "" : " (no key)"}`));
        return label;
      }));
    } catch (err) {
      picker.textContent = "Could not load providers from the gateway service.";
    }
  }

  function formatAuthors(authors) {
    if (!authors) return "Unknown authors";
    const names = authors.split(",").map(n => n.trim()).filter(Boolean);
    if (names.length <= 4) return names.join(", ");
    // Large-collaboration papers (e.g. CMS, LHCb) can list hundreds of authors.
    return `${names.slice(0, 3).join(", ")}, and ${names.length - 3} more`;
  }

  function renderLiterature(papers) {
    const list = document.querySelector("#paper-list");
    if (!papers || papers.length === 0) {
      list.innerHTML = "<li class=\"paper-item\">No papers were retrieved.</li>";
      return;
    }
    list.replaceChildren(...papers.map(paper => {
      const item = document.createElement("li");
      item.className = "paper-item";
      item.innerHTML = `
        <div class="paper-meta"><span>${escapeHtml(formatAuthors(paper.authors))}</span></div>
        <p class="paper-title"><a href="${escapeHtml(paper.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(paper.title)}</a></p>
        <p class="paper-relevance">${escapeHtml((paper.summary || "").slice(0, 320))}${(paper.summary || "").length > 320 ? "…" : ""}</p>
      `;
      return item;
    }));
  }

  function renderComparisons(results) {
    const grid = document.querySelector("#model-grid");
    if (!results || results.length === 0) {
      grid.innerHTML = "<p>No comparison results.</p>";
      return;
    }
    grid.replaceChildren(...results.map(result => {
      const card = document.createElement("div");
      card.className = "model-card";
      const body = result.error
        ? `<p class="model-answer is-error">${escapeHtml(result.error)}</p>`
        : `<p class="model-answer">${escapeHtml(result.text).slice(0, 600)}</p>`;
      card.innerHTML = `
        <div class="model-card-heading">
          <strong>${escapeHtml(result.provider)} / ${escapeHtml(result.model)}</strong>
          <span class="model-confidence is-high">${result.latency_ms} ms</span>
        </div>
        ${body}
      `;
      return card;
    }));
  }

  function renderSimulation(sim) {
    if (!sim) return;
    const chart = document.querySelector("#energy-chart");
    const width = 420, height = 220, padding = 36;
    const levels = [
      { label: "0th order", value: sim.perturbative.zeroth_order },
      { label: "1st order", value: sim.perturbative.first_order },
      { label: "2nd order", value: sim.perturbative.second_order },
      { label: "numerical", value: sim.numerical_ground_state }
    ];
    const maxValue = Math.max(...levels.map(l => l.value));
    const minValue = Math.min(...levels.map(l => l.value));
    const barWidth = (width - padding * 2) / levels.length - 16;

    const bars = levels.map((level, index) => {
      const x = padding + index * ((width - padding * 2) / levels.length);
      const barHeight = ((level.value - minValue * 0.98) / (maxValue - minValue * 0.98 || 1)) * (height - padding * 2);
      const y = height - padding - barHeight;
      const color = index === levels.length - 1 ? "#0d8f83" : "#7a5cf0";
      return `
        <rect x="${x}" y="${y}" width="${barWidth}" height="${barHeight}" rx="4" fill="${color}" opacity="${index === levels.length - 1 ? 1 : 0.65 + index * 0.08}" />
        <text x="${x + barWidth / 2}" y="${y - 8}" text-anchor="middle" font-size="11" font-weight="700" fill="#1f1a33">${level.value.toFixed(4)}</text>
        <text x="${x + barWidth / 2}" y="${height - padding + 18}" text-anchor="middle" font-size="9" fill="#6c6680">${escapeHtml(level.label)}</text>
      `;
    }).join("");

    chart.setAttribute("viewBox", `0 0 ${width} ${height}`);
    chart.innerHTML = `<line x1="${padding}" y1="${height - padding}" x2="${width - padding}" y2="${height - padding}" stroke="#e1ddec" stroke-width="1" />${bars}`;

    const stats = document.querySelector("#sim-stats");
    const rows = [
      ["Perturbation strength (λ)", sim.lambda],
      ["Basis size", sim.basis_size],
      ["2nd-order estimate", sim.perturbative.second_order.toFixed(5)],
      ["Numerical result", sim.numerical_ground_state.toFixed(5)],
      ["Agreement", `${sim.agreement_pct_difference.toFixed(3)}% difference`]
    ];
    stats.replaceChildren(...rows.map(([label, value], index) => {
      const row = document.createElement("div");
      const dt = document.createElement("dt");
      dt.textContent = label;
      const dd = document.createElement("dd");
      dd.textContent = value;
      if (index === rows.length - 1) dd.classList.add("is-good");
      row.append(dt, dd);
      return row;
    }));
  }

  function formatJson(value) {
    return escapeHtml(JSON.stringify(value, null, 2));
  }

  function renderTrace(trace) {
    const summaryEl = document.querySelector("#trace-summary");
    const timeline = document.querySelector("#trace-timeline");

    if (!trace || trace.length === 0) {
      summaryEl.innerHTML = "";
      timeline.innerHTML = "<li class=\"trace-event\">No run has completed yet — nothing recorded.</li>";
      return;
    }

    const totalMs = trace.reduce((sum, event) => sum + event.duration_ms, 0);
    const allCalls = trace.flatMap(event => event.calls);
    const errorCalls = allCalls.filter(call => call.error);
    const providersUsed = [...new Set(allCalls.filter(c => c.provider).map(c => `${c.provider}/${c.model}`))];

    summaryEl.replaceChildren(
      ...[
        [`${trace.length} stages`, `${totalMs.toLocaleString()} ms total`],
        [`${allCalls.length} calls`, `${errorCalls.length} failed`],
        [`${providersUsed.length} provider/model pairs`, providersUsed.join(", ") || "—"]
      ].map(([label, sub]) => {
        const stat = document.createElement("span");
        stat.className = "trace-stat";
        stat.innerHTML = `<strong>${escapeHtml(label)}</strong> · ${escapeHtml(sub)}`;
        return stat;
      })
    );

    timeline.replaceChildren(...trace.map(event => {
      const hasError = event.calls.some(call => call.error);
      const item = document.createElement("li");
      item.className = `trace-event${hasError ? " has-error" : ""}`;

      const callsHtml = event.calls.map(call => {
        const label = call.provider
          ? `${call.target} · ${call.provider}/${call.model}`
          : `${call.target} · ${call.endpoint}`;
        const requestBlock = call.request
          ? `<div><p class="field-label">Request</p><pre>${formatJson(call.request)}</pre></div>`
          : "";
        const responseBlock = call.error
          ? `<div><p class="field-label">Error</p><pre>${escapeHtml(call.error)}</pre></div>`
          : `<div><p class="field-label">Response</p><pre>${escapeHtml(call.response ?? call.response_summary ?? "")}</pre></div>`;
        return `
          <details class="trace-call${call.error ? " is-error" : ""}">
            <summary><span>${escapeHtml(label)}</span><span class="trace-call-latency">${call.latency_ms != null ? `${call.latency_ms} ms` : ""}</span></summary>
            <div class="trace-call-body">
              <div><p class="field-label">Endpoint</p><pre>${escapeHtml(call.endpoint)}</pre></div>
              ${requestBlock}
              ${responseBlock}
            </div>
          </details>
        `;
      }).join("");

      item.innerHTML = `
        <div class="trace-event-heading">
          <strong>${escapeHtml(event.stage)}</strong>
          <span class="trace-duration">${event.duration_ms} ms</span>
        </div>
        <p class="trace-summary-line">${escapeHtml(event.summary)}</p>
        <div class="trace-calls">${callsHtml}</div>
      `;
      return item;
    }));
  }

  function renderAll(state) {
    latestState = state;
    renderLiterature(state.literature);
    document.querySelector("#derivation-text").textContent = state.derivation_error
      ? `Error: ${state.derivation_error}`
      : (state.derivation || "");
    renderComparisons(state.comparisons);
    renderSimulation(state.simulation);
    document.querySelector("#review-text").textContent = state.review || "";
    document.querySelector("#writeup-text").textContent = state.writeup || "";
    renderTrace(state.trace);
  }

  document.querySelector("#run-button").addEventListener("click", async () => {
    const button = document.querySelector("#run-button");
    const status = document.querySelector("#run-status");
    const question = document.querySelector("#question-input").value.trim();
    if (!question) {
      status.textContent = "Enter a research question first.";
      return;
    }

    const defaultModel = JSON.parse(document.querySelector("#default-model-select").value || "null");
    const comparisonModels = [...document.querySelectorAll("#model-picker input:checked")].map(input => ({
      provider: input.dataset.provider,
      model: input.dataset.model
    }));
    const lam = parseFloat(document.querySelector("#lambda-input").value) || 0.02;
    const basisSize = parseInt(document.querySelector("#basis-input").value, 10) || 40;

    button.disabled = true;
    status.textContent = "Creating session…";

    try {
      const createResponse = await fetch(`${ORCHESTRATOR_BASE}/v1/sessions`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ question })
      });
      const session = await createResponse.json();

      status.textContent = "Running the six-stage pipeline — this can take a minute with local models…";
      const runResponse = await fetch(`${ORCHESTRATOR_BASE}/v1/sessions/${session.id}/run`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          default_model: defaultModel,
          comparison_models: comparisonModels.length ? comparisonModels : undefined,
          lam,
          basis_size: basisSize
        })
      });
      if (!runResponse.ok) throw new Error(`run failed: ${runResponse.status}`);
      const result = await runResponse.json();

      renderAll(result.state);
      status.textContent = `Run ${result.status}.`;
      selectStage("literature");
    } catch (err) {
      status.textContent = `Failed: ${err.message}`;
    } finally {
      button.disabled = false;
    }
  });

  document.querySelector("#copy-writeup").addEventListener("click", async () => {
    const statusEl = document.querySelector("#writeup-status");
    if (!latestState || !latestState.writeup) {
      statusEl.textContent = "Nothing to copy yet — run the lifecycle first.";
      return;
    }
    try {
      await navigator.clipboard.writeText(latestState.writeup);
      statusEl.textContent = "Copied to clipboard.";
    } catch {
      statusEl.textContent = "Copy isn't available in this context — select the text manually.";
    }
  });

  checkBackend();
  loadProviders();
  selectStage(activeStage);
})();
