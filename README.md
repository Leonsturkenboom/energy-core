<p align="center">
  <img src="logo.png" width="160" alt="Homie Energy Core logo">
</p>

# Homie Energy Core

Homie Energy Core is a Home Assistant custom integration that standardises **energy distribution KPIs** and provides **ready-to-use dashboard cards**, based on a robust and HA-safe calculation model.

The integration is intentionally lightweight and deterministic:  
**energy meters are treated as the source of truth**, and all energy flows are calculated using **interval-based delta values**.

---

## Core concept (important)

Energy Core does **not** calculate energy from power (W).

Instead:
- All input sensors are **cumulative energy totals** (kWh / Wh)
- Energy Core calculates **delta values per fixed interval**
- All base outputs represent **energy per interval**
- Period totals are built by **summing those deltas**

This approach:
- avoids power sampling errors
- survives restarts safely
- does not rely on HA statistics
- produces stable, reproducible results
- prevents historical bias and double-counting

---

## What this integration provides

### Core energy deltas (per interval)

These sensors represent **energy during the last calculation interval**  
(**kWh per interval**, not cumulative totals):

- **EC Imported Energy**
- **EC Exported Energy**
- **EC Produced Energy**
- **EC Battery Charge Energy**
- **EC Battery Discharge Energy**

> These sensors reset every interval by design.  
> They are intended as building blocks for period counters and dashboards.

---

### Derived energy distribution (per interval)

Calculated from the delta values:

- **EC Self Consumed Energy** (production → home)
- **EC Self Stored Energy** (production → battery)
- **EC Imported Battery Energy** (grid → battery)
- **EC Exported Battery Energy** (battery → grid)
- **EC Self Consumed Battery Energy** (battery → home)
- **EC Imported Residual Energy**
- **EC Exported Residual Energy**

All values represent **kWh during the interval**.

---

### Net KPIs (accounting-based)

- **EC Net Energy Use (On-site)**
- **EC Net Energy Imported (Grid)**

These KPIs represent **energy accounting**, not instantaneous physical flows.  
Negative values are valid and expected in net-export scenarios.

---

### Self-sufficiency

- **EC Self Sufficiency (%)**

Calculated from interval deltas.  
For period and lifetime values, the ratio is recomputed from accumulated energy parts  
(**never by averaging percentages**).

---

### Emissions (optional)

Based on the selected CO₂ intensity sensor:

- **EC Emissions Imported**
- **EC Emissions Avoided**
- **EC Emissions Net**

Units: **g CO₂-eq per interval**

Negative values for *Net* emissions indicate avoided emissions.

---

## Built-in period counters (always included)

For **every EC energy and emissions sensor**, Energy Core automatically generates:

- 15 minutes  
- Hour  
- Day  
- Week  
- Month  
- Year  
- **Overall (lifetime)**  

These counters:
- **sum interval-based delta values**
- are **restart-safe**
- do **not rely on Home Assistant statistics**
- accumulate **once per calculation interval**
- never double-count data

### Self-sufficiency period counters
Self-sufficiency also includes:
- Hour / Day / Week / Month / Year / **Overall**

These are calculated correctly as **ratios over accumulated energy**, not summed percentages.

---

## Required inputs

You may select **multiple entities per category**.

Required:
- **Energy imported** (kWh or Wh, cumulative)
- **Energy exported** (kWh or Wh, cumulative)
- **Energy produced** (kWh or Wh, cumulative)
- **Battery charge energy** (kWh or Wh, cumulative)
- **Battery discharge energy** (kWh or Wh, cumulative)
- **CO₂ intensity** (g CO₂-eq / kWh)

Optional:
- **Presence / occupancy entity** (for future coaching and notifications)

---

## Configuration

After installing:

1. Go to **Settings → Devices & Services**
2. Add **Homie Energy Core**
3. Select your input sensors
4. Choose the **delta calculation interval** (default: 300 seconds)

The configuration wizard:
- allows multiple sensors per category
- validates **kWh / Wh** units
- prevents selection of **W (power)** sensors
- checks `device_class` and `state_class`
- prevents accidental double-counting

---

## Dashboard cards

Energy Core includes ready-to-copy YAML dashboard cards:

- Energy distribution
- Daily energy balance
- Weekly energy balance
- Monthly energy balance
- Yearly energy balance
- Overall energy balance

All graphs are configured to **sum interval values**, not average them.

Cards can be found in: /cards


---

## Installation (HACS)

1. Add this repository as a **custom integration** in HACS
2. Install and restart Home Assistant
3. Add **Homie Energy Core** via **Settings → Devices & Services**
4. Copy dashboard cards from `/cards` into your dashboard

---

## Design goals

- Deterministic energy accounting
- Standardised naming and outputs
- Minimal configuration effort
- Restart-safe calculations
- HA-aligned performance characteristics
- Dashboard- and automation-friendly outputs

---

## Version history

### 0.3.3
- Hardened interval-based delta engine against sensor glitches
- Prevented energy spikes caused by `unknown` / `unavailable` input states
- Invalid intervals no longer update baselines or accumulators
- Added explicit `interval_valid` and `interval_reason` attributes
- Switched all emissions outputs from **g CO₂-eq** to **kg CO₂-eq**
- Emissions calculations now divide CO₂ intensity (g/kWh) by 1000
- Period and overall emission counters now accumulate **kg CO₂-eq**
- Ensured day/month/year/overall counters cannot be corrupted by restarts or meter resets

### 0.3.2
- Hardened interval-based delta engine against sensor glitches
- Prevented energy spikes caused by unknown / unavailable input states
- Invalid intervals no longer update baselines or accumulators
- Added explicit interval_valid and interval_reason attributes

### 0.3.1 / 0.3.2
- Added **Overall (lifetime)** counters
- Added period counters for **emissions**
- Added ratio-correct period counters for **self sufficiency**
- Added repository icon and logo

### 0.3.0
- Switched to **interval-based delta energy model**
- All EC sensors now represent **kWh per interval**
- Restart-safe accumulators
- No reliance on HA statistics
- Prevents historical bias and double-counting

### 0.2.x
- Cumulative energy totals with derived counters
- Persistent baselines for period counters

### 0.1.x
- Initial Energy Core sensors
- Unit validation in config wizard
- First dashboard card templates
