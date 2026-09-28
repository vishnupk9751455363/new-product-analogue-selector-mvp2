import re

with open('static/app.js', 'r', encoding='utf-8') as f:
    js = f.read()

funcs_called = [
    'initLiveClock', 'initNavigation', 'initWeightsAccordion', 'initCategoryFilters',
    'initOverrideHelpers', 'initBenchmarkSearch', 'initChartLegendToggles',
    'loadColdStartProducts', 'initDisruptionSimulator', 'setupEventListeners',
    'loadBenchmarkData', 'loadAuditTrail', 'submitPlannerOverride',
    'testTamperProtection', 'runEdgeCaseTest', 'runDisruptionSimulation',
    'logDisruptionOverride', 'showToast', 'runAnalogueForecast', 'onProductSelected'
]

for fn in funcs_called:
    pattern = rf'function\s+{fn}\s*\('
    found = re.search(pattern, js)
    status = "DEFINED" if found else "MISSING!"
    print(f'{fn:25}: {status}')
