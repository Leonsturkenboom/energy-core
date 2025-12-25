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
- **EC Net Battery Flow** (positive = discharging, negative = charging)

> These sensors reset every interval by design.
> They are intended as building blocks for period counters and dashboards.
>
> **Note**: Net Battery Flow can be negative (charging) or positive (discharging), making it ideal for distribution graphs. Period counters are only available for 15min, hour, and day periods.

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

**Exception**: **EC Net Battery Flow** only generates period counters for:
- 15 minutes
- Hour
- Day

(Week/month/year/overall counters for net flow are not meaningful since positive and negative values would cancel out)

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

## Notifications

Energy Core includes smart notification sensors that monitor your energy patterns and alert you to:
- **Warnings**: High consumption, data gaps, rising baseload
- **Awards**: Self-sufficiency records, low emissions, low consumption
- **Tips**: Reduce export, weekly improvement goals

### Setup

1. **Create notification toggle** (via UI or YAML):
   ```yaml
   input_boolean:
     ec_notifications_enabled:
       name: EC Notifications Enabled
       initial: on
   ```

2. **Add notification board** to your dashboard:
   - Install `auto-entities` from HACS
   - Copy `/cards/notifications_board.yaml` to your dashboard

All notifications:
- Tagged with `tag: "Homie"` for easy filtering
- Hidden when `input_boolean.ec_notifications_enabled` is OFF
- Respect holiday mode (awards/tips only)
- Support Dutch + English

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

### 0.5.10
- **Added debug logging for event-driven updates**: Diagnose why event listeners may not trigger
  - Logs which entities are being tracked for state changes
  - Logs each state change event with old/new values
  - Logs when debounce completes and refresh is triggered
  - Helps identify if event listener is registering correctly

### 0.5.9
- **Hybrid polling + event-driven mode**: Ensures sensors update even when input entities don't change
  - Added 5-minute polling interval as fallback alongside event-driven updates
  - Fixes issue where sensors stayed at 0 when input entities had no state changes
  - Event-driven updates still work for immediate response to state changes
  - Removed 15-second delayed fallback (no longer needed with polling)
  - First successful update after baseline will now happen within 5 minutes maximum

### 0.5.8
- **Critical fix: Sensors now receive data updates**: Use async_refresh() instead of _async_update_data()
  - Event-driven updates now properly notify sensor entities via DataUpdateCoordinator
  - Fixes issue where sensors stayed at 0 even when input entities had valid data
  - Both debounced updates and fallback refresh now trigger proper sensor state updates
- **Fixed all state_class warnings**: Remove device_class from interval-based energy sensors
  - Interval sensors (kWh per interval) now have device_class=None instead of ENERGY
  - This allows state_class=MEASUREMENT which is correct for non-cumulative values
  - Period sensors still use device_class=ENERGY with state_class=TOTAL_INCREASING
  - Eliminates all Home Assistant warnings about invalid state_class configuration

### 0.5.7
- **Fixed AttributeError in delayed fallback refresh**: Correctly access dataclass attributes
  - Fixed "AttributeError: 'EnergyDeltas' object has no attribute 'get'" error
  - Delayed fallback now properly checks deltas.reason attribute instead of using .get()
  - Ensures fallback refresh executes correctly after 15 seconds

### 0.5.6
- **Added delayed fallback refresh**: Ensures data loads even if input entities don't change at startup
  - 15-second delayed refresh catches entities that were available but didn't trigger state change events
  - Fixes issue where sensors stayed at 0 when input entities already had valid states
- **Fixed state_class warnings**: Period sensors now use correct state_class for cumulative energy
  - Energy period sensors (day/week/month/year/overall) now use `TOTAL_INCREASING` instead of `MEASUREMENT`
  - Emissions and self-sufficiency period sensors still use `MEASUREMENT`
  - Eliminates Home Assistant warnings about incorrect state_class configuration

### 0.5.5
- **Fixed coordinator.data None error**: Initialize coordinator.data in __init__ to prevent AttributeError
  - Sensors no longer crash when trying to access coordinator.data during setup
  - Coordinator now has safe default data structure before first refresh
  - Fixes "AttributeError: 'NoneType' object has no attribute 'get'" errors
  - Event listeners can now properly update sensors once input entities become available

### 0.5.4
- **Improved event listener and initialization**:
  - Event listeners now trigger on initial state (not just changes) by allowing `old_state is None`
  - Added detailed logging when input entities are unavailable (`missing_input` warnings)
  - Reordered initialization: platforms load first, then listeners, then initial refresh
  - Helps diagnose entity availability issues during startup

### 0.5.3
- **Fixed initial data not loading**: Event-driven coordinator now performs initial refresh on startup
  - Changed from `async_config_entry_first_refresh()` to `async_refresh()`
  - Establishes baseline immediately instead of waiting for first state change
  - Fixes issue where all sensors showed 0 until entities updated

### 0.5.2
- **Fixed event listener compatibility**: Replaced deprecated `async_listen` with lambda filter
  - Now uses `async_track_state_change_event` for HA 2024+ compatibility
  - Prevents "Event filter is not a callback" error on startup
  - Follows Home Assistant best practices for state change tracking

### 0.5.1
- **BREAKING CHANGE**: Switched from polling to event-driven delta calculation
  - Delta calculations now triggered by sensor state changes instead of fixed intervals
  - Eliminates timestamp lag between energy measurement and delta attribution
  - Fixes issue where battery charge events were attributed to wrong time periods
  - Removed `delta_interval_seconds` configuration option (no longer needed)
  - Users must reconfigure integration after upgrade
- **Added 10-second debouncing**: Prevents excessive processing from rapid state changes
  - System waits 10 seconds after last state change before calculating deltas
  - Improves performance and reduces unnecessary computation
  - Automatic cleanup of debounce tasks on shutdown
- **Fixed dashboard double counting**: Updated balance charts to prevent showing production twice
  - Charts now use `self_consumed_energy` instead of `produced_energy`
  - Correctly displays: self-consumed (PV→home), self-stored (PV→battery), imported (grid→home)
  - Eliminates overlap in stacked energy balance charts
- **Renamed sensors**: `net_energy_use` → `net_energy_use_on_site` for clarity
  - Applies to all period sensors (daily, weekly, monthly, yearly, overall)
  - Updated all dashboard cards and charts

### 0.4.1
- **Added EC Net Battery Flow sensor**: Combined battery flow sensor that can be positive (discharging) or negative (charging)
  - Perfect for distribution graphs showing battery behavior
  - Period counters available for 15min, hour, and day only
  - Calculation: discharge - charge (positive = discharging to consumption)
- Added `period_keys` field to ECDescription for selective period counter creation
- Improves battery visualization in energy distribution dashboards

### 0.4.0
- **Added Notification System**: 11 intelligent notification types for energy monitoring
  - Warnings: Data gaps, consumption spikes (2x/4x daily avg), high night consumption, rising baseload
  - Awards: Records in self-sufficiency, CO2 emissions, and energy use
  - Tips: Reduce export suggestions, weekly improvement goals
- **Added NotificationMetricsStore**: Lightweight 90-day historical data tracking
  - Automatic daily snapshots at midnight
  - Rolling averages (7d, 30d, 90d) for trend detection
  - Min/max tracking for record comparison
- **Holiday Mode Suppression**: Info/award notifications auto-suppressed during holidays
- **Multi-language Support**: Notifications in Dutch and English
- **Notification Toggle**: Respects `input_boolean.ec_notifications_enabled`
- Added notifications board card with auto-entities filtering
- All notification sensors tagged with "Homie" for easy dashboard integration

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
