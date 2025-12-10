# Homie Energy Core

Home Assistant custom integration that standardises energy distribution KPIs and provides ready-to-use dashboard cards.

## What this will provide (v1)
- Core energy totals and derived splits based on:
  - Energy imported
  - Energy exported
  - Energy produced
  - Battery charge energy
  - Battery discharge energy
- Self-sufficiency and CO₂ KPIs based on CO₂ intensity entity (g CO₂-eq/kWh)
- Ready-to-copy YAML cards:
  - Energy distribution
  - Daily/Weekly/Monthly/Yearly/Overall balances

## Installation (HACS)
1. Add this repository as a custom integration in HACS.
2. Install and restart Home Assistant.
3. Add the integration via Settings → Devices & Services.
4. Copy cards from `/cards`.
