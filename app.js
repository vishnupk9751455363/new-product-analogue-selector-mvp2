/**
 * DemandLens — Frontend Application Logic (v2.4 Enterprise)
 * Interactive Analogue Forecasting, Explainability, Audit Trail & Benchmarking
 */

// Prevent duplicate script execution
if (window.__DEMANDLENS_LOADED__) {
  console.log("DemandLens already initialized; skipping duplicate load.");
} else {
  window.__DEMANDLENS_LOADED__ = true;

// Resilient API Base: works seamlessly on http://127.0.0.1:8000 AND file:/// local browsing
var API_BASE = window.location.protocol === "file:" ? "http://127.0.0.1:8000" : "";

let allProducts = [];
let currentTargetProduct = null;
let currentFilteredProducts = [];
let lastForecasterData = null;
let launchChartInstance = null;
let weeklyBenchmarkChartInstance = null;
let edgeChartInstance = null;
let disruptionChartInstance = null;
let attributeChartInstance = null;
let currentAttributeChartView = "radar"; // "radar" or "bar"
let lastDisruptionResult = null;

function initApp() {
  initLiveClock();
  initNavigation();
  initWeightsAccordion();
  initCategoryFilters();
  initOverrideHelpers();
  initBenchmarkSearch();
  initChartLegendToggles();
  initAttributeChartViews();
  loadColdStartProducts();
  initDisruptionSimulator();
  setupEventListeners();
  loadBenchmarkData();
  loadAuditTrail();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initApp);
} else {
  initApp();
}

// 0. Live Clock Ticker
function initLiveClock() {
  const ticker = document.getElementById("header-clock-ticker");
  if (!ticker) return;
  function updateTime() {
    const now = new Date();
    const utcStr = now.toUTCString().split(" ")[4];
    ticker.textContent = `UTC ${utcStr}`;
  }
  updateTime();
  setInterval(updateTime, 1000);
}

// 1. Navigation & Tab Switching
function initNavigation() {
  const navBtns = document.querySelectorAll(".nav-btn");
  const tabPanes = document.querySelectorAll(".tab-pane");

  navBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      navBtns.forEach((b) => b.classList.remove("active"));
      tabPanes.forEach((p) => p.classList.remove("active"));

      btn.classList.add("active");
      const targetTab = btn.getAttribute("data-tab");
      const targetPane = document.getElementById(targetTab);
      if (targetPane) targetPane.classList.add("active");

      // Trigger redraw of charts on tab switch if needed
      if (targetTab === "tab-benchmark" && weeklyBenchmarkChartInstance) {
        weeklyBenchmarkChartInstance.resize();
      }
      if (targetTab === "tab-forecaster") {
        if (launchChartInstance) launchChartInstance.resize();
        if (attributeChartInstance) attributeChartInstance.resize();
      }
      if (targetTab === "tab-disruption") {
        if (disruptionChartInstance) disruptionChartInstance.resize();
        if (!lastDisruptionResult) runDisruptionSimulation();
      }
    });
  });
}

// 2. Weights Accordion & Real-Time Percentages
function initWeightsAccordion() {
  const toggleBtn = document.getElementById("toggle-weights-btn");
  const panel = document.getElementById("weights-panel");
  if (toggleBtn && panel) {
    toggleBtn.addEventListener("click", () => {
      panel.classList.toggle("open");
      const icon = toggleBtn.querySelector("svg");
      if (icon) {
        icon.style.transform = panel.classList.contains("open") ? "rotate(180deg)" : "rotate(0deg)";
      }
    });
  }

  const sliders = ["w-cat", "w-subcat", "w-fest", "w-tier", "w-pack", "w-shelf", "w-weather"];
  sliders.forEach((id) => {
    const el = document.getElementById(id);
    if (el) {
      el.addEventListener("input", () => {
        updateWeightPercentages();
        const cvBox = document.getElementById("cv-status-box");
        if (cvBox) cvBox.style.display = "none";
      });
    }
  });

  // Presets
  const btnBalanced = document.getElementById("preset-balanced");
  const btnCat = document.getElementById("preset-cat-heavy");
  const btnAttr = document.getElementById("preset-attr-heavy");
  const btnOpt = document.getElementById("btn-optimize-weights");
  const btnTriggerOpt = document.getElementById("btn-trigger-optimize");

  if (btnBalanced) {
    btnBalanced.addEventListener("click", () => {
      setSliderValues({ "w-cat": 25, "w-subcat": 20, "w-fest": 15, "w-tier": 15, "w-pack": 10, "w-shelf": 8, "w-weather": 7 });
      showToast("Applied Preset: Balanced Gower Scheme");
      runAnalogueForecast();
    });
  }
  if (btnCat) {
    btnCat.addEventListener("click", () => {
      setSliderValues({ "w-cat": 40, "w-subcat": 30, "w-fest": 5, "w-tier": 10, "w-pack": 5, "w-shelf": 5, "w-weather": 5 });
      showToast("Applied Preset: Category Dominant");
      runAnalogueForecast();
    });
  }
  if (btnAttr) {
    btnAttr.addEventListener("click", () => {
      setSliderValues({ "w-cat": 10, "w-subcat": 10, "w-fest": 10, "w-tier": 35, "w-pack": 25, "w-shelf": 10, "w-weather": 5 });
      showToast("Applied Preset: Pack Size & Price Tier");
      runAnalogueForecast();
    });
  }
  if (btnOpt) {
    btnOpt.addEventListener("click", runWeightOptimization);
  }
  if (btnTriggerOpt) {
    btnTriggerOpt.addEventListener("click", runWeightOptimization);
  }

  const resetBtn = document.getElementById("reset-weights-btn");
  if (resetBtn) {
    resetBtn.addEventListener("click", () => {
      setSliderValues({ "w-cat": 25, "w-subcat": 20, "w-fest": 15, "w-tier": 15, "w-pack": 10, "w-shelf": 8, "w-weather": 7 });
      const cvBox = document.getElementById("cv-status-box");
      if (cvBox) cvBox.style.display = "none";
      showToast("Weights restored to default heuristic scheme.");
      runAnalogueForecast();
    });
  }

  updateWeightPercentages();
}

function setSliderValues(vals) {
  for (const [id, val] of Object.entries(vals)) {
    const el = document.getElementById(id);
    if (el) el.value = val;
  }
  updateWeightPercentages();
}

function updateWeightPercentages() {
  const cat = parseFloat(document.getElementById("w-cat")?.value || 25);
  const subcat = parseFloat(document.getElementById("w-subcat")?.value || 20);
  const fest = parseFloat(document.getElementById("w-fest")?.value || 15);
  const tier = parseFloat(document.getElementById("w-tier")?.value || 15);
  const pack = parseFloat(document.getElementById("w-pack")?.value || 10);
  const shelf = parseFloat(document.getElementById("w-shelf")?.value || 8);
  const weather = parseFloat(document.getElementById("w-weather")?.value || 7);

  const total = cat + subcat + fest + tier + pack + shelf + weather || 1;

  setPctLabel("pct-w-cat", (cat / total) * 100);
  setPctLabel("pct-w-subcat", (subcat / total) * 100);
  setPctLabel("pct-w-fest", (fest / total) * 100);
  setPctLabel("pct-w-tier", (tier / total) * 100);
  setPctLabel("pct-w-pack", (pack / total) * 100);
  setPctLabel("pct-w-shelf", (shelf / total) * 100);
  setPctLabel("pct-w-weather", (weather / total) * 100);
}

function setPctLabel(id, pct) {
  const el = document.getElementById(id);
  if (el) el.textContent = `${pct.toFixed(0)}%`;
}

function getSelectedWeights() {
  const cat = parseFloat(document.getElementById("w-cat")?.value || 25);
  const subcat = parseFloat(document.getElementById("w-subcat")?.value || 20);
  const fest = parseFloat(document.getElementById("w-fest")?.value || 15);
  const tier = parseFloat(document.getElementById("w-tier")?.value || 15);
  const pack = parseFloat(document.getElementById("w-pack")?.value || 10);
  const shelf = parseFloat(document.getElementById("w-shelf")?.value || 8);
  const weather = parseFloat(document.getElementById("w-weather")?.value || 7);

  const total = cat + subcat + fest + tier + pack + shelf + weather || 1;
  return {
    category: cat / total,
    subcategory: subcat / total,
    festival: fest / total,
    price_tier: tier / total,
    pack_size: pack / total,
    shelf_life: shelf / total,
    weather_sensitivity: weather / total,
  };
}

// 2.1 Category Filter Chips
function initCategoryFilters() {
  const chips = document.querySelectorAll("#category-filter-bar .filter-chip");
  chips.forEach((chip) => {
    chip.addEventListener("click", () => {
      chips.forEach((c) => c.classList.remove("active"));
      chip.classList.add("active");
      const cat = chip.getAttribute("data-cat");
      filterCatalogByCategory(cat);
    });
  });
}

function filterCatalogByCategory(cat) {
  const select = document.getElementById("product-select");
  if (!select) return;

  currentFilteredProducts = cat === "all" ? allProducts : allProducts.filter((p) => p.category === cat);
  select.innerHTML = "";

  currentFilteredProducts.forEach((p) => {
    const opt = document.createElement("option");
    opt.value = p.product_id;
    opt.textContent = `${p.product_id} — ${p.product_name} (${p.category})`;
    select.appendChild(opt);
  });

  if (currentFilteredProducts.length > 0) {
    select.value = currentFilteredProducts[0].product_id;
    onProductSelected(currentFilteredProducts[0]);
    runAnalogueForecast(currentFilteredProducts[0].product_id);
  }
}

// 2.2 Override Helpers (Quick delta & rationale presets)
function initOverrideHelpers() {
  document.querySelectorAll(".adjust-chip").forEach((btn) => {
    btn.addEventListener("click", () => {
      const delta = parseFloat(btn.getAttribute("data-delta"));
      const input = document.getElementById("override-units");
      let currentVal = parseFloat(input.value);
      if (isNaN(currentVal) || currentVal <= 0) currentVal = 100;
      const newVal = Math.max(1, currentVal * (1 + delta / 100));
      input.value = newVal.toFixed(1);
      showToast(`Adjusted proposed volume by ${delta > 0 ? "+" : ""}${delta}%`);
    });
  });

  document.querySelectorAll(".reason-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      const reason = chip.getAttribute("data-reason");
      const textarea = document.getElementById("override-reason");
      textarea.value = reason;
      textarea.focus();
    });
  });
}

// 2.3 Benchmark Search Filter
function initBenchmarkSearch() {
  const input = document.getElementById("benchmark-search-input");
  if (!input) return;
  input.addEventListener("input", (e) => {
    const query = e.target.value.toLowerCase();
    const rows = document.querySelectorAll("#benchmark-tbody tr");
    rows.forEach((row) => {
      const text = row.textContent.toLowerCase();
      row.style.display = text.includes(query) ? "" : "none";
    });
  });
}

// 2.4 Chart Legend Interactive Toggles
function initChartLegendToggles() {
  const toggleForecast = document.getElementById("legend-toggle-forecast");
  const toggleBaseline = document.getElementById("legend-toggle-baseline");
  const toggleDebiased = document.getElementById("legend-toggle-debiased");
  const toggleAnalogues = document.getElementById("legend-toggle-analogues");

  if (toggleForecast) {
    toggleForecast.addEventListener("click", () => {
      if (!launchChartInstance) return;
      const ds = launchChartInstance.data.datasets[0];
      ds.hidden = !ds.hidden;
      launchChartInstance.update();
      toggleForecast.style.opacity = ds.hidden ? "0.4" : "1";
    });
  }

  if (toggleBaseline) {
    toggleBaseline.addEventListener("click", () => {
      if (!launchChartInstance) return;
      const ds = launchChartInstance.data.datasets[1];
      ds.hidden = !ds.hidden;
      launchChartInstance.update();
      toggleBaseline.style.opacity = ds.hidden ? "0.4" : "1";
    });
  }

  if (toggleDebiased) {
    toggleDebiased.addEventListener("click", () => {
      if (!launchChartInstance || launchChartInstance.data.datasets.length < 3) return;
      const ds = launchChartInstance.data.datasets[2];
      ds.hidden = !ds.hidden;
      launchChartInstance.update();
      toggleDebiased.style.opacity = ds.hidden ? "0.4" : "1";
    });
  }

  if (toggleAnalogues) {
    toggleAnalogues.addEventListener("click", () => {
      if (!launchChartInstance) return;
      const startIdx = document.getElementById("toggle-promo-debias")?.checked ? 3 : 2;
      const areAnaloguesHidden = launchChartInstance.data.datasets.slice(startIdx).some((ds) => ds.hidden);
      launchChartInstance.data.datasets.slice(startIdx).forEach((ds) => {
        ds.hidden = !areAnaloguesHidden;
      });
      launchChartInstance.update();
      toggleAnalogues.style.opacity = !areAnaloguesHidden ? "0.4" : "1";
    });
  }
}

// 2.5 Attribute Chart View Toggles (Radar vs Bar)
function initAttributeChartViews() {
  const btnRadar = document.getElementById("btn-chart-view-radar");
  const btnBar = document.getElementById("btn-chart-view-bar");
  const btnExport = document.getElementById("btn-export-csv");

  if (btnRadar && btnBar) {
    btnRadar.addEventListener("click", () => {
      btnRadar.classList.add("active");
      btnBar.classList.remove("active");
      currentAttributeChartView = "radar";
      if (lastForecasterData) {
        renderAttributeAttributionChart(
          lastForecasterData.analogues,
          lastForecasterData.target_product,
          lastForecasterData.weights_used
        );
      }
    });

    btnBar.addEventListener("click", () => {
      btnBar.classList.add("active");
      btnRadar.classList.remove("active");
      currentAttributeChartView = "bar";
      if (lastForecasterData) {
        renderAttributeAttributionChart(
          lastForecasterData.analogues,
          lastForecasterData.target_product,
          lastForecasterData.weights_used
        );
      }
    });
  }

  if (btnExport) {
    btnExport.addEventListener("click", exportLaunchPlanCSV);
  }
}

// 3. Load Cold-Start SKUs
async function loadColdStartProducts() {
  try {
    const res = await fetch(`${API_BASE}/api/products?is_historical=0`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    allProducts = data.products || [];
    currentFilteredProducts = [...allProducts];

    const select = document.getElementById("product-select");
    select.innerHTML = "";

    allProducts.forEach((p) => {
      const opt = document.createElement("option");
      opt.value = p.product_id;
      opt.textContent = `${p.product_id} — ${p.product_name} (${p.category})`;
      select.appendChild(opt);
    });

    // Also populate Disruption SKU selector
    const disruptSelect = document.getElementById("disrupt-sku-select");
    if (disruptSelect) {
      disruptSelect.innerHTML = "";
      allProducts.forEach((p) => {
        const dOpt = document.createElement("option");
        dOpt.value = p.product_id;
        dOpt.textContent = `${p.product_id} — ${p.product_name} (${p.category})`;
        disruptSelect.appendChild(dOpt);
      });
    }

    if (allProducts.length > 0) {
      select.value = allProducts[0].product_id;
      if (disruptSelect) disruptSelect.value = allProducts[0].product_id;
      onProductSelected(allProducts[0]);
      runAnalogueForecast(allProducts[0].product_id);
    }
  } catch (err) {
    console.error("Failed to load cold-start products:", err);
    showToast("Connecting to backend engine at http://127.0.0.1:8000...", true);
  }
}

function onProductSelected(prod) {
  currentTargetProduct = prod;
  document.getElementById("spec-sku").textContent = prod.product_id;
  const tierBadge = document.getElementById("spec-tier");
  const tier = (prod.price_tier || "budget").toLowerCase();
  tierBadge.textContent = tier.toUpperCase();
  tierBadge.className = `spec-tier ${tier}`;

  document.getElementById("spec-name").textContent = prod.product_name;
  document.getElementById("spec-cat").textContent = prod.category;
  document.getElementById("spec-subcat").textContent = prod.subcategory;
  document.getElementById("spec-pack").textContent = `${parseInt(prod.pack_size_units)} units`;
  document.getElementById("spec-shelf").textContent = `${prod.shelf_life_days} days`;
  document.getElementById("spec-festival").textContent = prod.is_festival_linked ? (prod.festival_name || "Linked") : "None";
  document.getElementById("spec-weather").textContent = prod.weather_sensitivity ? "High Sensitivity" : "Normal";
}

// 4. Run Analogue Selection & Forecasting API
async function runAnalogueForecast(productId) {
  const pId = productId || (currentTargetProduct ? currentTargetProduct.product_id : document.getElementById("product-select")?.value);
  if (!pId) return;

  const weights = getSelectedWeights();
  const debiasPromo = document.getElementById("toggle-promo-debias")?.checked || false;

  try {
    const res = await fetch(`${API_BASE}/api/analogues`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        product_id: pId,
        k: 5,
        custom_weights: weights,
        debias_promotions: debiasPromo,
      }),
    });

    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    lastForecasterData = data;
    renderForecasterResults(data);
  } catch (err) {
    console.error("Analogue matching error:", err);
    showToast("Engine offline. Please ensure 'python app.py' is running on port 8000.", true);
  }
}

// 4.1 Cross-Validated Weight Optimization
async function runWeightOptimization() {
  const btnOpt = document.getElementById("btn-optimize-weights");
  const btnTrigger = document.getElementById("btn-trigger-optimize");
  if (btnOpt) btnOpt.textContent = "⚡ Optimizing (CV)...";
  if (btnTrigger) btnTrigger.textContent = "⚡ Running CV Optimizer...";

  try {
    const res = await fetch(`${API_BASE}/api/weights/optimize`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ cv_folds: 5, k: 5, apply_to_engine: true })
    });

    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    const optRes = data.optimization_result;
    const optW = optRes.optimal_weights;

    // Apply values to sliders
    setSliderValues({
      "w-cat": Math.round(optW.category * 100),
      "w-subcat": Math.round(optW.subcategory * 100),
      "w-fest": Math.round(optW.festival * 100),
      "w-tier": Math.round(optW.price_tier * 100),
      "w-pack": Math.round(optW.pack_size * 100),
      "w-shelf": Math.round(optW.shelf_life * 100),
      "w-weather": Math.round(optW.weather_sensitivity * 100)
    });

    // Display CV Status Card
    const cvBox = document.getElementById("cv-status-box");
    const cvDetail = document.getElementById("cv-status-detail");
    if (cvBox && cvDetail) {
      cvBox.style.display = "block";
      cvDetail.textContent = `5-Fold CV WAPE: ${optRes.baseline_cv_wape}% → ${optRes.optimized_cv_wape}% (+${optRes.wape_improvement_pts}% pts gain, ${optRes.pct_error_reduction}% err reduction)`;
    }

    showToast(`⚡ Optimal weights applied via 5-Fold Cross Validation! Gain: +${optRes.wape_improvement_pts}% pts`);
    runAnalogueForecast();
  } catch (err) {
    console.error("Weight optimization error:", err);
    showToast("Optimization failed: " + err.message, true);
  } finally {
    if (btnOpt) btnOpt.textContent = "⚡ Auto-Optimize (CV)";
    if (btnTrigger) btnTrigger.textContent = "⚡ Run CV Optimizer";
  }
}

// 5. Render Forecaster Results & Charts
function renderForecasterResults(data) {
  const { analogues, forecast, baseline_forecast, debias_promotions_applied, promotional_inflation_units, promotional_inflation_pct } = data;

  // Render Stats
  const topAnalogue = analogues && analogues.length > 0 ? analogues[0] : null;
  const confidence = forecast.confidence_score;
  document.getElementById("stat-confidence").textContent = `${(confidence * 100).toFixed(1)}%`;
  document.getElementById("stat-confidence-formula").textContent =
    confidence > 0.70 ? "High Consensus (Low Analogue CV)" : "Moderate / Sparse Pool Depth";

  if (topAnalogue) {
    document.getElementById("stat-top-sim").textContent = topAnalogue.similarity_score.toFixed(4);
    document.getElementById("stat-top-name").textContent = topAnalogue.product_name;
  }

  const w1Val = forecast.forecast_curve["W1"] || 0;
  document.getElementById("stat-w1-vol").textContent = `${w1Val.toFixed(1)} un`;
  document.getElementById("override-units").value = w1Val.toFixed(1);

  // Promotional inflation badge
  const promoBadge = document.getElementById("promo-inflation-badge");
  if (promoBadge) {
    if (debias_promotions_applied && promotional_inflation_units > 0) {
      promoBadge.style.display = "inline-flex";
      promoBadge.textContent = `-${promotional_inflation_units.toFixed(1)} U (-${promotional_inflation_pct.toFixed(0)}%)`;
      promoBadge.title = `Stripped ${promotional_inflation_units.toFixed(1)} units of artificial promo lift`;
    } else {
      promoBadge.style.display = "none";
    }
  }

  // Toggle legend for debiased curve
  const legendDebiased = document.getElementById("legend-toggle-debiased");
  if (legendDebiased) {
    legendDebiased.style.display = debias_promotions_applied ? "inline-flex" : "none";
  }

  // Render Launch Curve Chart
  renderLaunchCurveChart(
    forecast.forecast_curve,
    baseline_forecast,
    analogues,
    data.raw_curve,
    data.debiased_curve,
    debias_promotions_applied
  );

  // Render Attribute Attribution & Explainability Chart
  renderAttributeAttributionChart(analogues, data.target_product, data.weights_used);

  // Render Retrieved Analogues Cards
  renderAnaloguesGrid(analogues, debias_promotions_applied);
}

function renderLaunchCurveChart(activeForecast, baselineCurve, analogues, rawCurve, debiasedCurve, isDebiased) {
  const canvas = document.getElementById("launchCurveChart");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const weeks = ["W1", "W2", "W3", "W4", "W5", "W6", "W7", "W8"];

  const forecastData = weeks.map((w) => activeForecast[w] || 0);
  const baselineData = weeks.map((w) => baselineCurve[w] || 0);

  // Gradient under active curve
  const gradientFill = ctx.createLinearGradient(0, 0, 0, 360);
  gradientFill.addColorStop(0, isDebiased ? "rgba(52, 211, 153, 0.28)" : "rgba(6, 182, 212, 0.28)");
  gradientFill.addColorStop(0.65, "rgba(99, 102, 241, 0.08)");
  gradientFill.addColorStop(1, "rgba(6, 182, 212, 0)");

  const datasets = [
    {
      label: isDebiased ? "Organic Forecast (De-biased)" : "Analogue Forecast (Weighted)",
      data: forecastData,
      borderColor: isDebiased ? "#34D399" : "#22D3EE",
      backgroundColor: gradientFill,
      borderWidth: 3.5,
      pointRadius: 5,
      pointHoverRadius: 8,
      pointBackgroundColor: isDebiased ? "#34D399" : "#22D3EE",
      pointBorderColor: "#FFFFFF",
      pointBorderWidth: 2,
      tension: 0.35,
      fill: true,
      zIndex: 10,
    },
    {
      label: "Naive Baseline (Category Avg)",
      data: baselineData,
      borderColor: "#F59E0B",
      borderWidth: 2.2,
      borderDash: [6, 4],
      pointRadius: 3.5,
      pointBackgroundColor: "#F59E0B",
      tension: 0.25,
      fill: false,
    },
  ];

  // If debiasing is applied, also display raw inflated curve as comparison trace
  if (isDebiased && rawCurve) {
    const rawData = weeks.map((w) => rawCurve[w] || 0);
    datasets.push({
      label: "Raw Historical Curve (Inflated)",
      data: rawData,
      borderColor: "rgba(244, 63, 94, 0.8)",
      borderWidth: 2.0,
      borderDash: [4, 4],
      pointRadius: 3.0,
      pointBackgroundColor: "#F43F5E",
      tension: 0.3,
      fill: false,
    });
  }

  // Individual analogue lines
  const palette = [
    "rgba(148, 163, 184, 0.45)",
    "rgba(168, 85, 247, 0.45)",
    "rgba(99, 102, 241, 0.45)",
    "rgba(52, 211, 153, 0.45)",
    "rgba(251, 113, 133, 0.45)",
  ];

  if (analogues) {
    analogues.forEach((a, i) => {
      const aCurve = isDebiased ? (a.debiased_launch_curve || a.launch_curve) : a.launch_curve;
      const aData = weeks.map((w) => aCurve[w] || 0);
      datasets.push({
        label: `Analogue: ${a.product_id}`,
        data: aData,
        borderColor: palette[i % palette.length],
        borderWidth: 1.5,
        pointRadius: 2.5,
        tension: 0.3,
        fill: false,
      });
    });
  }

  if (launchChartInstance) {
    launchChartInstance.destroy();
  }

  launchChartInstance = new Chart(ctx, {
    type: "line",
    data: {
      labels: ["Week 1", "Week 2", "Week 3", "Week 4", "Week 5", "Week 6", "Week 7", "Week 8"],
      datasets: datasets,
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: "rgba(10, 16, 30, 0.95)",
          titleColor: "#F8FAFC",
          titleFont: { family: "Outfit", size: 13, weight: "bold" },
          bodyColor: "#94A3B8",
          bodyFont: { family: "Inter", size: 12 },
          borderColor: "rgba(255, 255, 255, 0.15)",
          borderWidth: 1,
          padding: 12,
          cornerRadius: 10,
          displayColors: true,
        },
      },
      scales: {
        x: {
          grid: { color: "rgba(255, 255, 255, 0.04)" },
          ticks: { color: "#94A3B8", font: { family: "Inter", size: 11, weight: 500 } },
        },
        y: {
          grid: { color: "rgba(255, 255, 255, 0.05)" },
          ticks: { color: "#94A3B8", font: { family: "Inter", size: 11 } },
          title: { display: true, text: "Average Units / Store / Week", color: "#64748B", font: { size: 11, family: "Inter" } },
        },
      },
    },
  });
}

// 5.1 Render Visual Attribute Attribution & Explainability Chart
function renderAttributeAttributionChart(analogues, targetProduct, weights) {
  const canvas = document.getElementById("attributeAttributionChart");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");

  const attrLabels = ["Category", "Subcategory", "Festival Link", "Price Tier", "Pack Size", "Shelf Life", "Weather Sens."];
  const attrKeys = ["category", "subcategory", "festival", "price_tier", "pack_size", "shelf_life", "weather_sensitivity"];

  if (attributeChartInstance) {
    attributeChartInstance.destroy();
  }

  const paletteColors = [
    { border: "#22D3EE", bg: "rgba(34, 211, 238, 0.25)" },
    { border: "#818CF8", bg: "rgba(129, 140, 248, 0.25)" },
    { border: "#34D399", bg: "rgba(52, 211, 153, 0.25)" },
    { border: "#FBBF24", bg: "rgba(251, 191, 36, 0.25)" },
    { border: "#C084FC", bg: "rgba(192, 132, 252, 0.25)" }
  ];

  if (currentAttributeChartView === "radar") {
    // RADAR CHART VIEW
    const datasets = [];

    // Scheme Weight Budget polygon (reference baseline)
    const weightBudget = attrKeys.map((k) => (weights[k] || 0) * 100);
    datasets.push({
      label: "Active Weight Scheme (%)",
      data: weightBudget,
      borderColor: "rgba(255, 255, 255, 0.4)",
      backgroundColor: "rgba(255, 255, 255, 0.04)",
      borderWidth: 1.5,
      borderDash: [4, 4],
      pointRadius: 2,
    });

    if (analogues) {
      analogues.slice(0, 3).forEach((a, i) => {
        const color = paletteColors[i % paletteColors.length];
        const dataVals = attrKeys.map((k) => {
          const contrib = a.contributing_attributes ? (a.contributing_attributes[k] || 0) : 0;
          return parseFloat((contrib * 100).toFixed(1));
        });

        datasets.push({
          label: `${a.product_id} (${(a.similarity_score * 100).toFixed(0)}% Match)`,
          data: dataVals,
          borderColor: color.border,
          backgroundColor: color.bg,
          borderWidth: 2.2,
          pointRadius: 4,
          pointBackgroundColor: color.border,
          fill: true
        });
      });
    }

    attributeChartInstance = new Chart(ctx, {
      type: "radar",
      data: {
        labels: attrLabels,
        datasets: datasets,
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          r: {
            angleLines: { color: "rgba(255, 255, 255, 0.08)" },
            grid: { color: "rgba(255, 255, 255, 0.08)" },
            pointLabels: {
              color: "#CBD5E1",
              font: { family: "Outfit", size: 11, weight: "600" }
            },
            ticks: {
              color: "#64748B",
              backdropColor: "transparent",
              font: { size: 9 }
            }
          }
        },
        plugins: {
          legend: {
            position: "bottom",
            labels: { color: "#94A3B8", font: { family: "Inter", size: 11 }, boxWidth: 12 }
          },
          tooltip: {
            backgroundColor: "rgba(10, 16, 30, 0.95)",
            titleColor: "#F8FAFC",
            bodyColor: "#94A3B8",
            borderColor: "rgba(255, 255, 255, 0.15)",
            borderWidth: 1,
            callbacks: {
              label: function(ctx) {
                return `${ctx.dataset.label}: ${ctx.raw}% contribution`;
              }
            }
          }
        }
      }
    });

  } else {
    // HORIZONTAL BAR ATTRIBUTION VIEW
    const datasets = [];
    if (analogues) {
      analogues.slice(0, 4).forEach((a, i) => {
        const color = paletteColors[i % paletteColors.length];
        const dataVals = attrKeys.map((k) => {
          const contrib = a.contributing_attributes ? (a.contributing_attributes[k] || 0) : 0;
          return parseFloat((contrib * 100).toFixed(2));
        });

        datasets.push({
          label: `${a.product_id} (${(a.similarity_score * 100).toFixed(0)}%)`,
          data: dataVals,
          backgroundColor: color.bg,
          borderColor: color.border,
          borderWidth: 1.5,
          borderRadius: 4
        });
      });
    }

    attributeChartInstance = new Chart(ctx, {
      type: "bar",
      data: {
        labels: attrLabels,
        datasets: datasets
      },
      options: {
        indexAxis: "y",
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: {
            grid: { color: "rgba(255, 255, 255, 0.04)" },
            ticks: { color: "#94A3B8" },
            title: { display: true, text: "Similarity Contribution % Points", color: "#64748B", font: { size: 10 } }
          },
          y: {
            grid: { color: "rgba(255, 255, 255, 0.05)" },
            ticks: { color: "#CBD5E1", font: { family: "Outfit", weight: "500" } }
          }
        },
        plugins: {
          legend: {
            position: "bottom",
            labels: { color: "#94A3B8", font: { family: "Inter", size: 11 }, boxWidth: 12 }
          }
        }
      }
    });
  }
}

function renderAnaloguesGrid(analogues, isDebiased) {
  const container = document.getElementById("analogues-grid");
  if (!container) return;
  container.innerHTML = "";

  if (!analogues || analogues.length === 0) {
    container.innerHTML = `<div style="color: var(--text-muted); font-size: 0.9rem;">No analogues retrieved for this configuration.</div>`;
    return;
  }

  analogues.forEach((a, idx) => {
    const card = document.createElement("div");
    card.className = "analogue-card";

    let barsHtml = "";
    for (const [attr, val] of Object.entries(a.contributing_attributes || {})) {
      const pct = a.similarity_score > 0 ? (val / a.similarity_score) * 100 : 0;
      barsHtml += `
        <div class="contrib-row">
          <div class="contrib-info">
            <span>${formatAttrName(attr)}</span>
            <span style="font-family: var(--font-mono);">${pct.toFixed(0)}% (${val.toFixed(3)})</span>
          </div>
          <div class="contrib-track">
            <div class="contrib-fill" style="width: ${Math.min(100, pct)}%"></div>
          </div>
        </div>
      `;
    }

    const promoBadgeHtml = a.has_promo_activity
      ? `<span class="badge badge-warning" style="font-size: 0.65rem; margin-left: auto;">PROMO INFLATION +${(a.promo_lift_pct || 28).toFixed(0)}%</span>`
      : "";

    card.innerHTML = `
      <div class="analogue-rank-medal"></div>
      <div class="analogue-header" style="display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap;">
        <span class="analogue-rank">ANALOGUE #${idx + 1} · ${a.product_id}</span>
        <span class="analogue-sim-badge">${(a.similarity_score * 100).toFixed(1)}% MATCH</span>
        ${promoBadgeHtml}
      </div>
      <div class="analogue-title">${a.product_name}</div>
      <div class="analogue-rationale">${a.explanation}</div>
      <div class="contrib-header">
        <span>Attribute Attribution</span>
        <span style="color: var(--cyan-400);">Gower Weight</span>
      </div>
      <div class="contrib-bars-list">
        ${barsHtml}
      </div>
    `;
    container.appendChild(card);
  });
}

function formatAttrName(attr) {
  return attr.replace("_", " ").replace(/\b\w/g, (l) => l.toUpperCase());
}

// 5.2 Export Launch Plan to CSV
function exportLaunchPlanCSV() {
  if (!currentTargetProduct || !lastForecasterData) {
    showToast("Please run a forecast first before exporting.", true);
    return;
  }
  const prod = currentTargetProduct;
  const fc = lastForecasterData.forecast.forecast_curve;
  const base = lastForecasterData.baseline_forecast;
  const raw = lastForecasterData.raw_curve || fc;
  const debiased = lastForecasterData.debiased_curve || fc;
  const analogues = lastForecasterData.analogues || [];

  let csv = "DEMANDLENS NEW-PRODUCT LAUNCH FORECAST PLAN\n";
  csv += `Generated At (UTC),${new Date().toISOString()}\n`;
  csv += `Product SKU,${prod.product_id}\n`;
  csv += `Product Name,"${prod.product_name}"\n`;
  csv += `Category,${prod.category}\n`;
  csv += `Subcategory,${prod.subcategory}\n`;
  csv += `Price Tier,${prod.price_tier}\n`;
  csv += `Pack Size Units,${prod.pack_size_units}\n`;
  csv += `Shelf Life Days,${prod.shelf_life_days}\n`;
  csv += `Festival Linked,${prod.is_festival_linked ? (prod.festival_name || "Yes") : "No"}\n`;
  csv += `Weather Sensitivity,${prod.weather_sensitivity ? "High" : "Normal"}\n`;
  csv += `Forecast Confidence,${(lastForecasterData.forecast.confidence_score * 100).toFixed(1)}%\n`;
  csv += `Promotional De-Biasing Applied,${lastForecasterData.debias_promotions_applied ? "YES" : "NO"}\n`;
  csv += `Promotional Inflation Stripped Units,${(lastForecasterData.promotional_inflation_units || 0).toFixed(2)}\n\n`;

  csv += "WEEKLY LAUNCH PROFILE (Units / Store / Week)\n";
  csv += "Week,Active Forecast,Naive Baseline,Raw Historical Curve,De-biased Organic Curve\n";
  for (let w = 1; w <= 8; w++) {
    const k = `W${w}`;
    csv += `${k},${fc[k] || 0},${base[k] || 0},${raw[k] || 0},${debiased[k] || 0}\n`;
  }

  csv += "\nRETRIEVED ANALOGUES & ATTRIBUTE ATTRIBUTION\n";
  csv += "Rank,Analogue SKU,Analogue Name,Similarity Match %,Category,Subcategory,Festival,Price Tier,Pack Size,Shelf Life,Weather Sensitivity,Explanation\n";
  analogues.forEach((a, i) => {
    const ca = a.contributing_attributes || {};
    csv += `${i + 1},${a.product_id},"${a.product_name}",${(a.similarity_score * 100).toFixed(1)}%,` +
      `${ca.category || 0},${ca.subcategory || 0},${ca.festival || 0},${ca.price_tier || 0},` +
      `${ca.pack_size || 0},${ca.shelf_life || 0},${ca.weather_sensitivity || 0},"${a.explanation.replace(/"/g, '""')}"\n`;
  });

  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.setAttribute("href", url);
  link.setAttribute("download", `DemandLens_Launch_Plan_${prod.product_id}.csv`);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);

  showToast(`📥 Exported launch plan for ${prod.product_id} to CSV!`);
}

// 6. Planner Override Action
async function submitPlannerOverride() {
  if (!currentTargetProduct) return;

  const week = document.getElementById("override-week").value;
  const units = parseFloat(document.getElementById("override-units").value);
  const reason = document.getElementById("override-reason").value.trim();

  if (isNaN(units) || units <= 0) {
    showToast("Please specify valid positive units for override.", true);
    return;
  }
  if (!reason) {
    showToast("Business justification reason is mandatory.", true);
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/api/audit/override`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        product_id: currentTargetProduct.product_id,
        changed_by: "planner_ui_session",
        field_changed: `launch_curve_${week}`,
        old_value: "system_generated",
        new_value: units,
        reason: reason,
      }),
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Override failed");

    const alertBox = document.getElementById("override-alert");
    alertBox.className = "alert-box alert-box-success";
    alertBox.innerHTML = `<strong>Entry #${data.change_id} Committed:</strong> Immutable audit trigger verified. Change locked to ledger.`;
    alertBox.classList.remove("hidden");

    showToast(`Committed override for ${week} to immutable audit ledger!`);
    document.getElementById("override-reason").value = "";
    loadAuditTrail();
  } catch (err) {
    showToast("Failed to commit override: " + err.message, true);
  }
}

// 7. Load & Render Benchmark Tab
async function loadBenchmarkData() {
  try {
    const res = await fetch(`${API_BASE}/api/benchmark`);
    if (!res.ok) throw new Error("Could not fetch benchmark.");
    const data = await res.json();

    const overall = data.overall;
    document.getElementById("bench-sel-wape").textContent = `${overall.selector_wape.toFixed(2)}%`;
    document.getElementById("bench-base-wape").textContent = `${overall.baseline_wape.toFixed(2)}%`;
    document.getElementById("bench-improvement").textContent = `+${overall.wape_reduction_pts.toFixed(2)}% pts`;
    document.getElementById("bench-pct-err").textContent = `-${overall.wape_pct_improvement.toFixed(1)}% error reduction`;
    document.getElementById("bench-sel-mape").textContent = `${overall.selector_mape.toFixed(2)}%`;

    // Render Weekly Benchmark Chart
    renderWeeklyBenchmarkChart(data.weekly);

    // Populate Table
    const tbody = document.getElementById("benchmark-tbody");
    tbody.innerHTML = "";

    data.per_product.forEach((p) => {
      const tr = document.createElement("tr");
      const isBetter = p.wape_improvement > 0;
      const statusBadge = isBetter
        ? `<span class="badge badge-emerald">BETTER (+${p.wape_improvement.toFixed(1)}%)</span>`
        : `<span class="badge badge-neutral">COMPARABLE (${p.wape_improvement.toFixed(1)}%)</span>`;

      tr.innerHTML = `
        <td><span class="spec-sku">${p.product_id}</span></td>
        <td><strong>${p.product_name}</strong></td>
        <td>${p.category}</td>
        <td>${(p.confidence * 100).toFixed(1)}%</td>
        <td>${p.baseline_wape.toFixed(2)}%</td>
        <td>${p.selector_wape.toFixed(2)}%</td>
        <td style="color: ${isBetter ? 'var(--emerald-400)' : '#CBD5E1'}; font-weight: 700; font-family: var(--font-mono);">
          ${isBetter ? "-" : "+"}${Math.abs(p.wape_improvement).toFixed(2)}%
        </td>
        <td>${statusBadge}</td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    console.error("Benchmark error:", err);
  }
}

function renderWeeklyBenchmarkChart(weeklyData) {
  const canvas = document.getElementById("benchmarkWeeklyChart");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const labels = weeklyData.map((w) => `Week ${w.week.replace("W", "")}`);
  const baseWapes = weeklyData.map((w) => w.baseline_wape);
  const selWapes = weeklyData.map((w) => w.selector_wape);

  if (weeklyBenchmarkChartInstance) {
    weeklyBenchmarkChartInstance.destroy();
  }

  weeklyBenchmarkChartInstance = new Chart(ctx, {
    type: "bar",
    data: {
      labels: labels,
      datasets: [
        {
          label: "Analogue Selector WAPE (%)",
          data: selWapes,
          backgroundColor: "rgba(16, 185, 129, 0.8)",
          borderColor: "#10B981",
          borderWidth: 1.5,
          borderRadius: 6,
        },
        {
          label: "Naive Baseline WAPE (%)",
          data: baseWapes,
          backgroundColor: "rgba(245, 158, 11, 0.65)",
          borderColor: "#F59E0B",
          borderWidth: 1.5,
          borderRadius: 6,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: {
          grid: { color: "rgba(255, 255, 255, 0.04)" },
          ticks: { color: "#94A3B8", font: { family: "Inter" } },
        },
        y: {
          grid: { color: "rgba(255, 255, 255, 0.05)" },
          ticks: { color: "#94A3B8", font: { family: "Inter" } },
          title: { display: true, text: "WAPE Error % (Lower is Better)", color: "#64748B", font: { family: "Inter" } },
        },
      },
      plugins: {
        legend: {
          labels: { color: "#94A3B8", font: { family: "Inter" } },
        },
      },
    },
  });
}

// 8. Load & Render Audit Trail
async function loadAuditTrail() {
  try {
    const res = await fetch(`${API_BASE}/api/audit/trail`);
    const data = await res.json();
    const tbody = document.getElementById("audit-tbody");
    if (!tbody) return;
    tbody.innerHTML = "";

    const records = data.audit_trail || [];
    records.reverse(); // newest first

    records.forEach((r) => {
      const tr = document.createElement("tr");
      const isOverride = r.source === "planner_override";
      const sourceBadge = isOverride
        ? `<span class="badge badge-warning">PLANNER OVERRIDE</span>`
        : `<span class="badge badge-accent">SYSTEM PROPOSAL</span>`;

      tr.innerHTML = `
        <td><span class="spec-sku">#${r.change_id}</span></td>
        <td><strong>${r.product_id}</strong></td>
        <td>${sourceBadge}</td>
        <td><code style="color: var(--cyan-400); font-family: var(--font-mono);">${r.changed_by}</code></td>
        <td><small style="color: #94A3B8; font-family: var(--font-mono);">${r.changed_at.replace("T", " ").substring(0, 19)}</small></td>
        <td><code style="color: #A5B4FC; font-family: var(--font-mono);">${r.field_changed}</code></td>
        <td><small style="color: #64748B;">${truncateText(r.old_value, 20)}</small></td>
        <td><strong style="color: var(--emerald-400);">${truncateText(r.new_value, 20)}</strong></td>
        <td><em>${r.reason}</em></td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    console.error("Audit load error:", err);
  }
}

function truncateText(str, maxLen) {
  if (!str) return "null";
  return str.length > maxLen ? str.substring(0, maxLen) + "..." : str;
}

// 9. Test Tamper Protection
async function testTamperProtection() {
  const resultBox = document.getElementById("tamper-result-box");
  try {
    const res = await fetch(`${API_BASE}/api/audit/test-tamper?change_id=1`, { method: "POST" });
    const data = await res.json();

    resultBox.classList.remove("hidden");
    if (data.trigger_blocked) {
      resultBox.style.borderColor = "var(--emerald-500)";
      resultBox.style.background = "rgba(16, 185, 129, 0.12)";
      resultBox.innerHTML = `
        <strong style="color: var(--emerald-400);">🛡️ [SECURITY VERIFIED] SQLite Database Trigger Blocked Tampering:</strong><br>
        <code style="display: block; margin: 0.5rem 0; padding: 0.4rem; background: rgba(0,0,0,0.3); border-radius: 4px; font-family: var(--font-mono); color: #FCA5A5;">${data.error_message}</code>
        <span style="font-size: 0.82rem; color: #6EE7B7;">SQLite trigger <code>trg_prevent_plan_changes_update</code> successfully blocked the unauthorized UPDATE statement. Audit records remain strictly immutable.</span>
      `;
      showToast("Security check verified: Tampering blocked by DB trigger!");
    } else {
      resultBox.style.borderColor = "var(--rose-500)";
      resultBox.innerHTML = `<strong>WARNING:</strong> Tamper was permitted. Please check triggers.`;
    }
  } catch (err) {
    showToast("Error running security check: " + err.message, true);
  }
}

// 10. Edge Case Sandbox
async function runEdgeCaseTest() {
  const scenario = document.getElementById("edge-preset-select").value;
  let novelProduct = null;

  if (scenario === "cellular") {
    novelProduct = {
      product_id: "PRD_EDGE_CELLULAR",
      product_name: "Cellular Bio-Agriculture Caviar (Premium 1pk)",
      category: "Cellular Agriculture",
      subcategory: "Cultured Delicacies",
      price_tier: "premium",
      pack_size_units: 1.0,
      shelf_life_days: 90,
      is_festival_linked: 0,
      festival_name: null,
      weather_sensitivity: 0,
    };
  } else if (scenario === "insect") {
    novelProduct = {
      product_id: "PRD_EDGE_ALGAE",
      product_name: "Cricket & Spirulina Energy Bites (Mid 4pk)",
      category: "Novel Alternative Proteins",
      subcategory: "Entomological Snacks",
      price_tier: "mid",
      pack_size_units: 4.0,
      shelf_life_days: 180,
      is_festival_linked: 0,
      festival_name: null,
      weather_sensitivity: 1,
    };
  } else {
    novelProduct = {
      product_id: "PRD_EDGE_BULK",
      product_name: "Bulk Catering Wrap Pack (Budget 100pk)",
      category: "Bakery",
      subcategory: "Flatbreads & Wraps",
      price_tier: "budget",
      pack_size_units: 100.0,
      shelf_life_days: 5,
      is_festival_linked: 0,
      festival_name: null,
      weather_sensitivity: 0,
    };
  }

  try {
    const res = await fetch(`${API_BASE}/api/analogues`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ custom_product: novelProduct, k: 5 }),
    });

    const data = await res.json();
    const fc = data.forecast;
    const alertBox = document.getElementById("edge-alert-box");
    const badge = document.getElementById("edge-status-badge");

    if (fc.is_degraded) {
      badge.className = "badge badge-warning";
      badge.textContent = "Degraded Fallback Mode";
      alertBox.className = "alert-box alert-box-warning";
      alertBox.innerHTML = `
        <strong>Safe Degradation Activated:</strong><br>
        ${fc.degradation_reason}<br>
        <span style="font-size: 0.8rem; margin-top: 4px; display: block;">
          Confidence penalized to <strong>${(fc.confidence_score * 100).toFixed(1)}%</strong>. System defaulted to global catalogue baseline safely without crashing or hallucinations.
        </span>
      `;
    } else {
      badge.className = "badge badge-accent";
      badge.textContent = "Normal Analogue Match";
      alertBox.className = "alert-box alert-box-info";
      alertBox.textContent = `Category matched with ${(fc.confidence_score * 100).toFixed(1)}% confidence.`;
    }

    renderEdgeChart(fc.forecast_curve);
    showToast(`Edge test executed: ${novelProduct.product_name}`);
  } catch (err) {
    showToast("Edge test error: " + err.message, true);
  }
}

function renderEdgeChart(forecastCurve) {
  const canvas = document.getElementById("edgeCurveChart");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const weeks = ["W1", "W2", "W3", "W4", "W5", "W6", "W7", "W8"];
  const vals = weeks.map((w) => forecastCurve[w] || 0);

  if (edgeChartInstance) {
    edgeChartInstance.destroy();
  }

  edgeChartInstance = new Chart(ctx, {
    type: "line",
    data: {
      labels: weeks,
      datasets: [
        {
          label: "Fallback Launch Curve (Safe Default)",
          data: vals,
          borderColor: "#F43F5E",
          backgroundColor: "rgba(244, 63, 94, 0.15)",
          borderWidth: 3,
          pointRadius: 4,
          tension: 0.3,
          fill: true,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: { grid: { color: "rgba(255, 255, 255, 0.04)" }, ticks: { color: "#94A3B8" } },
        y: { grid: { color: "rgba(255, 255, 255, 0.05)" }, ticks: { color: "#94A3B8" } },
      },
    },
  });
}

// 11. Event Listeners Setup
function setupEventListeners() {
  document.getElementById("product-select")?.addEventListener("change", (e) => {
    const selected = allProducts.find((p) => p.product_id === e.target.value);
    if (selected) {
      onProductSelected(selected);
      runAnalogueForecast(selected.product_id);
    }
  });

  document.getElementById("btn-run-forecast")?.addEventListener("click", () => {
    runAnalogueForecast();
    showToast("Re-running analogue matching with current weights...");
  });

  document.getElementById("btn-submit-override")?.addEventListener("click", submitPlannerOverride);

  document.getElementById("btn-refresh-benchmark")?.addEventListener("click", () => {
    loadBenchmarkData();
    showToast("Benchmark metrics refreshed.");
  });

  document.getElementById("btn-refresh-audit")?.addEventListener("click", () => {
    loadAuditTrail();
    showToast("Audit trail refreshed.");
  });

  document.getElementById("btn-test-tamper")?.addEventListener("click", testTamperProtection);
  document.getElementById("btn-run-edge-test")?.addEventListener("click", runEdgeCaseTest);
  
  // Promotional De-Biasing Toggle listener
  document.getElementById("toggle-promo-debias")?.addEventListener("change", (e) => {
    runAnalogueForecast();
    showToast(e.target.checked ? "Promotional de-biasing activated: organic baseline isolated." : "Promotional de-biasing deactivated: raw history restored.");
  });
}

// Toast helper
function showToast(msg, isError = false) {
  const toast = document.getElementById("toast");
  if (!toast) return;
  toast.textContent = msg;
  toast.style.borderColor = isError ? "var(--rose-500)" : "var(--cyan-500)";
  toast.style.display = "block";
  setTimeout(() => {
    toast.style.display = "none";
  }, 3500);
}

// 12. Disruption Stress Testing Simulator Logic
function initDisruptionSimulator() {
  const scenarioSelect = document.getElementById("disrupt-scenario-select");
  const panelSupplier = document.getElementById("disrupt-params-supplier");
  const panelCapacity = document.getElementById("disrupt-params-capacity");
  const panelSpike = document.getElementById("disrupt-params-spike");
  const panelWeather = document.getElementById("disrupt-params-weather");
  const panelFestival = document.getElementById("disrupt-params-festival");

  if (scenarioSelect) {
    scenarioSelect.addEventListener("change", (e) => {
      const val = e.target.value;
      if (panelSupplier) panelSupplier.style.display = val === "supplier_delay" ? "block" : "none";
      if (panelCapacity) panelCapacity.style.display = val === "capacity_loss" ? "block" : "none";
      if (panelSpike) panelSpike.style.display = val === "unplanned_spike" ? "block" : "none";
      if (panelWeather) panelWeather.style.display = val === "weather_anomaly" ? "block" : "none";
      if (panelFestival) panelFestival.style.display = val === "festival_shift" ? "block" : "none";
    });
  }

  // Parameter Range Sliders & Tickers
  document.getElementById("param-delay-weeks")?.addEventListener("input", (e) => {
    const el = document.getElementById("val-delay-weeks");
    if (el) el.textContent = `${e.target.value} Wks`;
  });
  document.getElementById("param-spoilage-rate")?.addEventListener("input", (e) => {
    const el = document.getElementById("val-spoilage-rate");
    if (el) el.textContent = `${e.target.value}% / wk`;
  });
  document.getElementById("param-capacity-ceiling")?.addEventListener("input", (e) => {
    const el = document.getElementById("val-capacity-ceiling");
    if (el) el.textContent = `${e.target.value} U`;
  });
  document.getElementById("param-spillover-rate")?.addEventListener("input", (e) => {
    const el = document.getElementById("val-spillover-rate");
    if (el) el.textContent = `${e.target.value}%`;
  });
  document.getElementById("param-spike-week")?.addEventListener("input", (e) => {
    const el = document.getElementById("val-spike-week");
    if (el) el.textContent = `Week ${e.target.value}`;
  });
  document.getElementById("param-spike-multiplier")?.addEventListener("input", (e) => {
    const el = document.getElementById("val-spike-multiplier");
    if (el) el.textContent = `${(parseFloat(e.target.value) / 10).toFixed(1)}x`;
  });
  document.getElementById("param-weather-intensity")?.addEventListener("input", (e) => {
    const el = document.getElementById("val-weather-intensity");
    if (el) el.textContent = `${e.target.value}%`;
  });
  document.getElementById("param-weather-week")?.addEventListener("input", (e) => {
    const el = document.getElementById("val-weather-week");
    if (el) el.textContent = `Week ${e.target.value}`;
  });
  document.getElementById("param-fest-shift-weeks")?.addEventListener("input", (e) => {
    const el = document.getElementById("val-fest-shift-weeks");
    if (el) el.textContent = `${e.target.value} Wks`;
  });
  document.getElementById("param-fest-multiplier")?.addEventListener("input", (e) => {
    const el = document.getElementById("val-fest-multiplier");
    if (el) el.textContent = `${(parseFloat(e.target.value) / 10).toFixed(1)}x`;
  });

  // Preset Buttons
  document.getElementById("preset-disrupt-port")?.addEventListener("click", () => {
    setDisruptionPreset("supplier_delay", { delay: 2, spoilage: 5 });
    showToast("Loaded Preset: 2-Week Port Congestion");
  });
  document.getElementById("preset-disrupt-reefer")?.addEventListener("click", () => {
    setDisruptionPreset("capacity_loss", { capacity: 110, spillover: 35 });
    showToast("Loaded Preset: Reefer Truck Cap (110 units)");
  });
  document.getElementById("preset-disrupt-viral")?.addEventListener("click", () => {
    setDisruptionPreset("unplanned_spike", { spikeWeek: 3, multiplier: 25 });
    showToast("Loaded Preset: Viral Demand Surge (2.5x)");
  });
  document.getElementById("preset-disrupt-heatwave")?.addEventListener("click", () => {
    setDisruptionPreset("weather_anomaly", { weatherType: "heatwave", intensity: 65, week: 2 });
    showToast("Loaded Preset: Heatwave Demand Surge (+65%)");
  });
  document.getElementById("preset-disrupt-monsoon")?.addEventListener("click", () => {
    setDisruptionPreset("weather_anomaly", { weatherType: "torrential_rain", intensity: 60, week: 2 });
    showToast("Loaded Preset: Monsoon Flooding Footfall Drop (-30%)");
  });
  document.getElementById("preset-disrupt-diwali")?.addEventListener("click", () => {
    setDisruptionPreset("festival_shift", { direction: "earlier", shiftWeeks: 2, multiplier: 19 });
    showToast("Loaded Preset: Diwali Date Drift (-2 Weeks Ahead)");
  });

  document.getElementById("btn-run-disruption")?.addEventListener("click", runDisruptionSimulation);
  document.getElementById("btn-log-disruption-override")?.addEventListener("click", logDisruptionOverride);
}

function setDisruptionPreset(type, params) {
  const select = document.getElementById("disrupt-scenario-select");
  if (select) {
    select.value = type;
    select.dispatchEvent(new Event("change"));
  }
  if (type === "supplier_delay") {
    const d = document.getElementById("param-delay-weeks");
    const s = document.getElementById("param-spoilage-rate");
    if (d) { d.value = params.delay; d.dispatchEvent(new Event("input")); }
    if (s) { s.value = params.spoilage; s.dispatchEvent(new Event("input")); }
  } else if (type === "capacity_loss") {
    const c = document.getElementById("param-capacity-ceiling");
    const sp = document.getElementById("param-spillover-rate");
    if (c) { c.value = params.capacity; c.dispatchEvent(new Event("input")); }
    if (sp) { sp.value = params.spillover; sp.dispatchEvent(new Event("input")); }
  } else if (type === "unplanned_spike") {
    const w = document.getElementById("param-spike-week");
    const m = document.getElementById("param-spike-multiplier");
    if (w) { w.value = params.spikeWeek; w.dispatchEvent(new Event("input")); }
    if (m) { m.value = params.multiplier; m.dispatchEvent(new Event("input")); }
  } else if (type === "weather_anomaly") {
    const wt = document.getElementById("param-weather-type");
    const wi = document.getElementById("param-weather-intensity");
    const ww = document.getElementById("param-weather-week");
    if (wt) { wt.value = params.weatherType; }
    if (wi) { wi.value = params.intensity; wi.dispatchEvent(new Event("input")); }
    if (ww) { ww.value = params.week; ww.dispatchEvent(new Event("input")); }
  } else if (type === "festival_shift") {
    const fd = document.getElementById("param-fest-direction");
    const fsw = document.getElementById("param-fest-shift-weeks");
    const fm = document.getElementById("param-fest-multiplier");
    if (fd) { fd.value = params.direction; }
    if (fsw) { fsw.value = params.shiftWeeks; fsw.dispatchEvent(new Event("input")); }
    if (fm) { fm.value = params.multiplier; fm.dispatchEvent(new Event("input")); }
  }
  runDisruptionSimulation();
}

async function runDisruptionSimulation() {
  const pId = document.getElementById("disrupt-sku-select")?.value || (currentTargetProduct ? currentTargetProduct.product_id : "PRD_NEW_083");
  const scenarioType = document.getElementById("disrupt-scenario-select")?.value || "supplier_delay";

  const delayWeeks = parseInt(document.getElementById("param-delay-weeks")?.value || 2);
  const spoilageRate = parseFloat(document.getElementById("param-spoilage-rate")?.value || 5) / 100.0;
  const capacityCeiling = parseFloat(document.getElementById("param-capacity-ceiling")?.value || 110);
  const spilloverRate = parseFloat(document.getElementById("param-spillover-rate")?.value || 35) / 100.0;
  const spikeWeek = parseInt(document.getElementById("param-spike-week")?.value || 3);
  const spikeMultiplier = parseFloat(document.getElementById("param-spike-multiplier")?.value || 25) / 10.0;

  const weatherType = document.getElementById("param-weather-type")?.value || "heatwave";
  const weatherIntensity = parseFloat(document.getElementById("param-weather-intensity")?.value || 65) / 100.0;
  const weatherWeek = parseInt(document.getElementById("param-weather-week")?.value || 2);

  const festDirection = document.getElementById("param-fest-direction")?.value || "earlier";
  const festShiftWeeks = parseInt(document.getElementById("param-fest-shift-weeks")?.value || 2);
  const festMultiplier = parseFloat(document.getElementById("param-fest-multiplier")?.value || 19) / 10.0;

  const payload = {
    product_id: pId,
    scenario_type: scenarioType,
    delay_weeks: delayWeeks,
    spoilage_rate_pct: spoilageRate,
    max_weekly_store_capacity: capacityCeiling,
    spillover_rate: spilloverRate,
    spike_week: spikeWeek,
    spike_multiplier: spikeMultiplier,
    weather_type: weatherType,
    intensity_pct: weatherIntensity,
    affected_weeks: [weatherWeek, weatherWeek + 1],
    shift_direction: festDirection,
    shift_weeks: festShiftWeeks,
    peak_multiplier: festMultiplier
  };

  try {
    const res = await fetch(`${API_BASE}/api/disruptions/simulate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    lastDisruptionResult = data.result;
    renderDisruptionResults(data.result);
    showToast(`Simulation complete: ${data.result.scenario_name}`);
  } catch (err) {
    console.error("Disruption simulation error:", err);
    showToast("Simulation error: " + err.message, true);
  }
}

function renderDisruptionResults(result) {
  const lostEl = document.getElementById("disrupt-lost-sales");
  const spoilEl = document.getElementById("disrupt-spoilage");
  const riskEl = document.getElementById("disrupt-stockout-risk");
  const buffEl = document.getElementById("disrupt-buffer-rec");

  if (lostEl) lostEl.textContent = `${result.lost_sales_units.toFixed(1)} un`;
  if (spoilEl) spoilEl.textContent = `${result.spoilage_units.toFixed(1)} un`;
  if (riskEl) riskEl.textContent = `${result.stockout_risk_pct.toFixed(1)}%`;
  if (buffEl) buffEl.textContent = `+${result.recommended_buffer_units.toFixed(1)} un`;

  const badge = document.getElementById("disrupt-status-badge");
  if (badge) {
    badge.textContent = result.stockout_risk_pct > 50 ? "Severe Impact" : "Mitigated Risk";
    badge.className = result.stockout_risk_pct > 50 ? "badge badge-rose" : "badge badge-warning";
  }

  const guidanceBox = document.getElementById("disrupt-guidance-box");
  if (guidanceBox) {
    guidanceBox.textContent = result.operational_guidance;
  }

  renderDisruptionChart(result.original_forecast, result.disrupted_forecast, result.scenario_name);
}

function renderDisruptionChart(origCurve, disruptedCurve, scenarioName) {
  const canvas = document.getElementById("disruptionChart");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const weeks = ["W1", "W2", "W3", "W4", "W5", "W6", "W7", "W8"];

  const origData = weeks.map((w) => origCurve[w] || 0);
  const disruptData = weeks.map((w) => disruptedCurve[w] || 0);

  if (disruptionChartInstance) {
    disruptionChartInstance.destroy();
  }

  disruptionChartInstance = new Chart(ctx, {
    type: "line",
    data: {
      labels: weeks,
      datasets: [
        {
          label: "Baseline Plan (Undisrupted)",
          data: origData,
          borderColor: "#10B981",
          borderWidth: 2.5,
          borderDash: [5, 4],
          pointRadius: 4,
          pointBackgroundColor: "#10B981",
          tension: 0.3,
          fill: false,
        },
        {
          label: `Disrupted Profile (${scenarioName})`,
          data: disruptData,
          borderColor: "#F43F5E",
          backgroundColor: "rgba(244, 63, 94, 0.16)",
          borderWidth: 3.5,
          pointRadius: 5,
          pointHoverRadius: 8,
          pointBackgroundColor: "#F43F5E",
          tension: 0.3,
          fill: true,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: true,
          labels: { color: "#CBD5E1", font: { family: "'Inter', sans-serif", size: 12 } },
        },
      },
      scales: {
        x: { grid: { color: "rgba(255, 255, 255, 0.04)" }, ticks: { color: "#94A3B8" } },
        y: {
          grid: { color: "rgba(255, 255, 255, 0.05)" },
          ticks: { color: "#94A3B8" },
          title: { display: true, text: "Units / Store / Week", color: "#64748B" },
        },
      },
    },
  });
}

function logDisruptionOverride() {
  if (!lastDisruptionResult) {
    showToast("Please run a disruption simulation first.", true);
    return;
  }

  const pId = document.getElementById("disrupt-sku-select")?.value || (currentTargetProduct ? currentTargetProduct.product_id : "PRD_NEW_083");
  const bufferUnits = lastDisruptionResult.recommended_buffer_units;
  const reasonText = `Disruption Buffer: ${lastDisruptionResult.scenario_name}. Buffer mitigation: +${bufferUnits.toFixed(1)} units.`;

  // Pre-fill planner console on forecaster tab
  const weekSelect = document.getElementById("override-week");
  const unitsInput = document.getElementById("override-units");
  const reasonInput = document.getElementById("override-reason");

  if (weekSelect) weekSelect.value = "W1";
  if (unitsInput) {
    const currentBase = lastDisruptionResult.original_forecast["W1"] || 100;
    unitsInput.value = (currentBase + bufferUnits).toFixed(1);
  }
  if (reasonInput) {
    reasonInput.value = reasonText;
  }

  // Switch to forecaster tab to review
  const navForecaster = document.getElementById("nav-btn-forecaster");
  if (navForecaster) {
    navForecaster.click();
    showToast("Transferred disruption buffer parameters to Planner Console.");
  }
}
}
