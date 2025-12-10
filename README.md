# Homie Energy Core

Home Assistant custom integration that standardises energy distribution KPIs and provides ready-to-use dashboard cards.

This integration is designed to be lightweight and HA-safe: it calculates standardised energy totals and derived splits from a small set of input sensors.

---

## What this provides

### Core energy totals (from inputs)
- **EC Imported Energy**
- **EC Exported Energy**
- **EC Produced Energy**
- **EC Battery Charge Energy**
- **EC Battery Discharge Energy**

### Derived energy splits
- **EC Self Consumed Energy** (direct usage from production)
- **EC Self Stored Energy** (production → battery)
- **EC Imported Battery Energy** (grid → battery)
- **EC Exported Battery Energy** (battery → grid)
- **EC Self Battery Energy** (battery → home)

### Net KPIs
- **EC Net Energy Use (On-site)**
- **EC Net Import Energy (Grid)**

### Self-sufficiency
- **EC Self Sufficiency (%)**

### Emissions (based on selected CO₂ intensity)
- **EC Emissions Imported**
- **EC Emissions Avoided**
- **EC Emissions Net**

---

## Built-in period counters (always included)

For each ENERGY sensor that is a total, Energy Core automatically generates:
- 15m
- Hour
- Day
- Week
- Month
- Year

These counters are derived as deltas within each time bucket and are included by default.

> From v0.2.0 onward, period baselines are stored persistently so counters do not reset incorrectly after a Home Assistant restart.

---

## Required inputs

You can select multiple entities per category.

- **Energy imported** (kWh or Wh)
- **Energy exported** (kWh or Wh)
- **Energy produced** (kWh or Wh)
- **Battery charge energy** (kWh or Wh)
- **Battery discharge energy** (kWh or Wh)
- **CO₂ intensity** (g CO₂-eq/kWh)

---

## Configuration

After installing:
1. Go to **Settings → Devices & Services**
2. Add **Homie Energy Core**
3. Select your input sensors

The configuration wizard:
- Allows selecting multiple sensors per category
- Validates that energy sensors use **kWh** or **Wh**
- Prevents accidental selection of **W (power)** sensors

---

## Dashboard cards

Energy Core includes ready-to-copy YAML cards:

- Visual energy distribution
- Graph daily energy balance
- Graph weekly energy balance
- Graph monthly energy balance
- Graph yearly energy balance
- Graph overall energy balance

You can find them in:
- `/cards`

---

## Installation (HACS)

1. Add this repository as a **custom integration** in HACS
2. Install and restart Home Assistant
3. Add the integration via **Settings → Devices & Services**
4. Copy cards from `/cards` into your dashboard

---

## Design goals

- Standardised naming and outputs
- Minimal configuration effort
- Lightweight calculations
- Compatible with automations and dashboards
- Safe defaults for Home Assistant performance

---

## Version history

### 0.2.0
- Added persistent period baselines for counters
- Counters no longer reset incorrectly after restarts

### 0.1.x
- Initial working Energy Core sensors
- Unit validation in config wizard
- Ready-to-copy dashboard cards
