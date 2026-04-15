# Building 59 Digital Twin — Data Reference Guide

This document explains every piece of data in the project: what devices exist in the building, what sensors they have, what columns are in the CSV files, what was enriched and why, how the simulator packages the data, what Stream Analytics does with it, and how every metric on the dashboard is calculated.

---

## Section 1: The Building and Its Systems

Building 59 is a 10,400 square metre, two storey steel framed commercial office building at the Lawrence Berkeley National Laboratory in Berkeley, California. It was built in 2015 and has around 300 sensors connected to an Automated Logic WebCTRL Building Management System.

The building has four main systems that we monitor.

### 1.1 HVAC System (Heating, Ventilation, Air Conditioning)

The HVAC system uses an underfloor air distribution (UFAD) design. Cool or warm air is pushed into a plenum (the space between the structural floor and the raised floor tiles), and it rises through floor diffusers into the office zones.

There are 4 Rooftop Units (RTUs). These are the main air handling machines sitting on the roof. Each RTU pulls in outdoor air, mixes it with return air from the offices, conditions it (heats or cools), and pushes it into the underfloor plenum.

| RTU | Wing | Zones Served | Floor |
|-----|------|-------------|-------|
| RTU-001 | North | 36, 37, 38, 39, 40, 41, 42, 64, 65, 66, 67, 68, 69, 70 | Ground + Level 2 |
| RTU-002 | North | 19, 27, 28, 29, 30, 31, 32, 33, 34, 35, 43, 44, 49, 50, 57, 58, 59, 60, 62, 63 | Ground + Level 2 |
| RTU-003 | South | 18, 25, 26, 45, 48, 55, 56, 61 | Ground + Level 2 |
| RTU-004 | South | 16, 17, 21, 22, 23, 24, 46, 47, 51, 52, 53, 54 | Ground + Level 2 |

Each RTU has a design airflow capacity of 20,000 CFM (cubic feet per minute).

Each RTU contains the following sensors that are in the dataset:

| Sensor | Column Name | Unit | What It Measures |
|--------|-------------|------|-----------------|
| Supply Fan Speed | `rtu_001_sf_vfd_spd_fbk_tn` | % | How fast the supply fan motor is spinning as a percentage of its maximum (20 HP motor). 80% means 80% of max RPM. The VFD (Variable Frequency Drive) controls the motor speed electronically. |
| Return Fan Speed | `rtu_001_rf_vfd_spd_fbk_tn` | % | How fast the return fan motor is spinning (7.5 HP motor). This fan pulls stale air back from the offices to be reconditioned. |
| Supply Airflow | `rtu_001_fltrd_sa_flow_tn` | CFM | The actual volume of air being pushed into the building per minute. Measured by airflow sensors in the ductwork. "fltrd" means filtered (smoothed to remove noise). |

All four RTUs have the same three sensors. Replace `001` with `002`, `003`, or `004` for the other units. That gives us 12 RTU sensor columns total.

There are also 50 thermal zones, each with fan powered terminal units (UFTs) under the floor that can provide additional reheat to perimeter zones. Each zone has a heating setpoint, which is the target temperature the BMS tries to maintain. The dataset contains heating setpoints for 41 zones (some zones share setpoints or were not instrumented).

| Sensor | Column Pattern | Unit | What It Measures |
|--------|---------------|------|-----------------|
| Zone Heating Setpoint | `zone_016_heating_sp` | °F | The target temperature for that zone. The BMS opens hot water valves or adjusts fan speed to reach this number. |

### 1.2 Hot Water Plant

Hot water is produced by a 117 kW (400 MBH) heat pump located on the mechanical level. Before March 2019 it was an air source heat pump, later replaced with a water source type. Two 3 HP VFD pumps circulate the hot water to the fan powered terminal units for zone reheat.

| Sensor | Column Name | Unit | What It Measures |
|--------|-------------|------|-----------------|
| Hot Water Supply Temp | `hp_hws_temp` | °F | Temperature of water leaving the heat pump heading to the zones. This is critical for legionella compliance: if it drops below 140°F (60°C), bacteria can grow. |

Note: `hp_hws_temp` is not in the base 75 column CSV (it comes from a separate raw file). Our enrichment script synthesises it.

### 1.3 Electrical Distribution

Two transformers feed two main switchboards (4000A, 277/480V each). Six electrical panels are metered at the panel level.

| Sensor | Column Name | Unit | What It Measures |
|--------|-------------|------|-----------------|
| Plug Loads South | `mels_s` | kW | Miscellaneous Electrical Loads in the south wing. Computers, monitors, printers, kitchen appliances. |
| Plug Loads North | `mels_n` | kW | Same for the north wing. |
| Lighting South | `lig_s` | kW | Total lighting power consumption in the south wing. Note: north wing lighting was not metered. |
| HVAC North | `hvac_n` | kW | Total HVAC electrical consumption for the north wing (RTU-001 and RTU-002 plus elevators). |
| HVAC South | `hvac_s` | kW | Total HVAC electrical consumption for the south wing (RTU-003 and RTU-004). |

### 1.4 Weather Station

An onsite weather station provides outdoor conditions that directly affect building energy use and HVAC load.

| Sensor | Column Name | Unit | What It Measures |
|--------|-------------|------|-----------------|
| Outdoor Air Temp (primary) | `air_temp_set_1` | °C | Ambient air temperature outside the building. |
| Outdoor Air Temp (backup) | `air_temp_set_2` | °C | Second temperature sensor for validation. |
| Dew Point | `dew_point_temperature_set_1d` | °C | Temperature at which moisture condenses. Indicates humidity and cooling load. |
| Relative Humidity | `relative_humidity_set_1` | % | How saturated the outdoor air is with moisture. |
| Solar Radiation | `solar_radiation_set_1` | W/m² | Incoming solar energy hitting the building. Affects cooling load. |

### 1.5 Summary of the Base Dataset

The base CSV (`solis_digital_twin_jan2020.csv`) has 2,976 rows and 75 columns covering January 2020 at 15 minute intervals. After removing unnamed/empty columns, there are 64 meaningful columns:

- 12 RTU sensor columns (4 RTUs × 3 sensors each)
- 41 zone heating setpoint columns
- 5 electrical meter columns
- 5 weather station columns
- 1 timestamp column

---

## Section 2: Enrichment — What Was Added and Why

The base dataset is missing several things that a facilities manager would need. There are no actual zone temperatures (only setpoints), no supply or return air temperatures from the RTUs, no hot water temperature, no pump condition data, and no derived health metrics. The enrichment script (`enrich_bldg59_data.py`) adds 114 new columns to produce a 178 column enriched CSV.

### 2.1 What Was Added

**RTU Supply Air Temperatures (4 columns: `rtu_001_sa_temp` through `rtu_004_sa_temp`)**

These are the temperatures of the air leaving each RTU after it has been cooled or heated. The formula uses the fan speed as a proxy: when the fan runs faster, more air passes over the cooling coil, so supply air is slightly colder. Outdoor temperature also affects it because the economizer mixes in outside air.

Formula: `sa_temp = 55 + (fan_speed - 50) * 0.1 + (outdoor_temp_f - 50) * 0.02 + small_random_noise`

The base of 55°F is a typical HVAC design supply air temperature for cooling mode.

**RTU Return Air Temperatures (4 columns: `rtu_001_ra_temp` through `rtu_004_ra_temp`)**

This is the temperature of air being pulled back from the offices. It is always warmer than the supply air because the office spaces, people, computers, and lights add heat.

Formula: `ra_temp = sa_temp + delta_t`, where delta_t is derived from fan speed (typically 14 to 17°F difference).

**Zone Actual Temperatures (41 columns: `zone_016_temp` through `zone_071_temp`)**

The base dataset only has heating setpoints (what the BMS wants the temperature to be). The enrichment adds estimated actual temperatures that fluctuate around the setpoint based on outdoor temperature coupling (zones near windows are affected more by outdoor conditions), a daily sine wave pattern (buildings warm up during the day and cool at night), a thermal lag factor, and small random variation to simulate real sensor noise.

Formula: `zone_temp = setpoint + outdoor_coupling + daily_oscillation + random_noise`

**RTU Efficiency Index (4 columns: `rtu_001_efficiency` through `rtu_004_efficiency`)**

A derived metric that tells you how much airflow you get per unit of fan energy. Higher is better. If efficiency drops, it could mean a dirty filter, a failing belt, or duct leakage.

Formula: `efficiency = airflow_cfm / fan_speed_pct`

For example, if RTU-001 delivers 14,700 CFM at 81% fan speed, the efficiency is 14700/81 = 181.5. A healthy RTU should be in the 170 to 190 range. Below 150 suggests a problem.

**RTU Delta-T (4 columns: `rtu_001_delta_t` through `rtu_004_delta_t`)**

The temperature difference between return air and supply air. This is the primary indicator of whether the RTU is actually doing work. If delta-T drops toward zero, the unit is running its fans but not cooling or heating effectively.

Formula: `delta_t = return_air_temp - supply_air_temp`

Healthy range: 14 to 17°F. Below 10°F is a problem.

**RTU Speed Volatility (4 columns: `rtu_001_speed_volatility` through `rtu_004_speed_volatility`)**

Measures how much the fan speed is fluctuating over short periods. High volatility means the unit is "hunting" or short cycling, which wastes energy and stresses components. Calculated as the rolling standard deviation of supply fan speed over a 2 hour window.

Formula: `volatility = rolling_std(fan_speed, window=8)` (8 intervals × 15 min = 2 hours)

Normal: below 2.0. Warning: 2.0 to 5.0. Problem: above 5.0.

**Zone Comfort Gaps (41 columns: `zone_016_comfort_gap` through `zone_071_comfort_gap`)**

The difference between the actual zone temperature and its heating setpoint. Positive means the zone is warmer than desired (overheating). Negative means it is colder (underheating).

Formula: `comfort_gap = zone_temp - heating_setpoint`

Acceptable: within ±2°F (per CIBSE guidelines). Outside ±2°F means occupants are uncomfortable.

**Hot Water Supply Temperature (`hp_hws_temp` in °F and `hw_temp_celsius` in °C)**

The temperature of hot water leaving the heat pump. Synthesised with a deliberate legionella risk event injected on January 15 to 17, where the temperature drops below 60°C (140°F). This simulates a real boiler underperformance event that a Digital Twin should detect.

Normal: 64 to 66°C. Legionella risk: below 60°C (per HSG274 Part 2, the UK Health and Safety Executive guidance on legionella control in hot and cold water systems).

**Legionella Risk Flag (`legionella_risk`)**

Binary flag: 1 if hot water temperature is below 60°C, 0 otherwise.

**Pump Power (`pump_power_kw`)**

Synthesised linear degradation from a healthy baseline of 8.0 kW to approximately 12.5 kW over the month. As bearings wear, the pump needs more power to maintain the same flow rate.

Formula: `pump_power = 8.0 + (row_index / total_rows) * 4.5 + random_noise`

**Pump Vibration (`pump_vibration_mms`)**

Synthesised linear degradation from 2.5 mm/s to approximately 8.0 mm/s over the month. Bearing wear causes increased vibration, which is the primary predictive maintenance signal.

Formula: `vibration = 2.5 + (row_index / total_rows) * 5.5 + random_noise`

Thresholds are from ISO 10816 (vibration severity for rotating machinery): below 4.5 mm/s is acceptable, 4.5 to 7.0 is warning, above 7.0 is critical, above 8.0 requires immediate shutdown.

**Pump Remaining Useful Life (`pump_rul_days`)**

Estimated days until vibration reaches the 8.0 mm/s failure threshold at the current degradation rate.

Formula: `rul = (8.0 - current_vibration) / daily_degradation_rate`

**Chilled Water Temperatures (`chw_supply_temp`, `chw_return_temp`)**

Supply and return water temperatures for the chilled water loop. The difference (delta-T) indicates how much cooling work is being done.

**Total Building Energy (`total_energy_kw`, `hvac_energy_kw`, `hvac_pct`)**

Aggregated totals. `total_energy_kw` sums all five electrical meter columns. `hvac_energy_kw` sums the two HVAC panels. `hvac_pct` is the HVAC share of total building energy as a percentage.

**Ghost Lighting (`ghost_lighting`)**

Binary flag: 1 if south wing lighting (`lig_s`) is above 0.5 kW between 10 PM and 5 AM (when the building should be unoccupied), 0 otherwise. This detects wasted energy from lights left on overnight.

### 2.2 Libraries Used for Enrichment

| Library | What It Does In This Project |
|---------|------------------------------|
| Pandas | Reading CSV files, column manipulation, resampling time series, rolling window calculations |
| NumPy | Mathematical operations, random noise generation, array arithmetic |
| scikit-learn (KNeighborsRegressor / KNNImputer) | Used in the build pipeline (`build_bldg59_data.py`) to fill gaps in sensor data where sensors dropped out for more than 30 minutes. KNN looks at the 5 most similar time periods (based on other sensor readings) and estimates what the missing sensor would have read. |

### 2.3 Why KNN for Imputation

Building sensors drop out for various reasons: network glitches, sensor resets, BMS restarts. Short gaps (under 30 minutes) are filled with linear interpolation (draw a straight line between the last known value and the next known value). Longer gaps cannot be reliably interpolated because building conditions change. KNN imputation works here because building sensor data is highly correlated: if you know the outdoor temperature, time of day, and other RTU readings, you can reliably estimate what a missing RTU sensor would have read. KNN with K=5 looks at the 5 time periods in the dataset that had the most similar conditions and averages their values for the missing sensor.

---

## Section 3: The Simulator — How It Packages and Sends Data

The simulator (`digital_twin_simulator.py`) reads the enriched CSV row by row (each row is a 15 minute interval) and creates four JSON payloads per row, one for each "sector." It then sends each payload as an MQTT message through Azure IoT Hub.

### 3.1 The Four Sector Payloads

**HVAC Payload** — sent with `sector: "HVAC"` and `asset_id: "RTU-001"`

This represents the primary rooftop unit. The metrics object contains:

| Field | Source Column | Unit | Description |
|-------|--------------|------|-------------|
| supply_air_flow_cfm | rtu_001_fltrd_sa_flow_tn | CFM | Airflow from RTU-001 |
| supply_fan_speed_pct | rtu_001_sf_vfd_spd_fbk_tn | % | Supply fan VFD speed |
| return_fan_speed_pct | rtu_001_rf_vfd_spd_fbk_tn | % | Return fan VFD speed |
| supply_air_temp_f | rtu_001_sa_temp | °F | Supply air temperature (enriched) |
| return_air_temp_f | rtu_001_ra_temp | °F | Return air temperature (enriched) |
| delta_t_f | rtu_001_delta_t | °F | Supply/return temperature difference (enriched) |
| efficiency_index | rtu_001_efficiency | ratio | Airflow per unit fan speed (enriched) |
| speed_volatility | rtu_001_speed_volatility | unitless | Fan speed fluctuation (enriched) |
| comfort_gap_f | zone_016_comfort_gap | °F | Zone 16 comfort deviation (enriched) |
| outdoor_temp_c | air_temp_set_1 | °C | Weather station outdoor temp |
| outdoor_humidity_pct | relative_humidity_set_1 | % | Weather station humidity |
| oee_pct | computed | % | Overall Equipment Effectiveness (see Section 4) |

**Pumps Payload** — sent with `sector: "Pumps"` and `asset_id: "HWP-01"`

This represents the primary hot water pump.

| Field | Source Column | Unit | Description |
|-------|--------------|------|-------------|
| vibration_mms | pump_vibration_mms | mm/s | Bearing vibration level (enriched, degrades over time) |
| pump_power_kw | pump_power_kw | kW | Motor power consumption (enriched, increases with degradation) |
| hw_supply_temp_c | hw_temp_celsius | °C | Hot water temperature in Celsius (enriched) |
| estimated_rul_days | pump_rul_days | days | Remaining Useful Life estimate (enriched) |
| legionella_risk | legionella_risk | binary | 1 if hot water below 60°C (enriched) |
| oee_pct | computed | % | Pump OEE |
| mtbf_hours | computed | hours | Mean Time Between Failures |
| mttr_hours | computed | hours | Mean Time To Repair |

**Electrical Payload** — sent with `sector: "Electrical"` and `asset_id: "ELEC-MAIN"`

| Field | Source Column | Unit | Description |
|-------|--------------|------|-------------|
| total_building_kw | total_energy_kw | kW | Sum of all 5 electrical panels (enriched) |
| hvac_south_kw | hvac_s | kW | HVAC panel south (raw) |
| hvac_north_kw | hvac_n | kW | HVAC panel north (raw) |
| lighting_south_kw | lig_s | kW | Lighting panel south (raw) |
| mels_south_kw | mels_s | kW | Plug loads south (raw) |
| mels_north_kw | mels_n | kW | Plug loads north (raw) |
| hvac_pct_of_total | hvac_pct | % | HVAC as percentage of total (enriched) |
| ghost_lighting_alert | ghost_lighting | binary | 1 if lights on during unoccupied hours (enriched) |

**Compliance Payload** — sent with `sector: "Compliance"`

This is a building wide summary that does not belong to a single asset.

| Field | Source Column | Unit | Description |
|-------|--------------|------|-------------|
| hw_temp_celsius | hw_temp_celsius | °C | Hot water temperature |
| checks_passed | computed | count | How many of 4 compliance checks pass |
| checks_total | computed | count | Always 4 |
| overall_status | computed | text | GREEN (all pass), AMBER (3 pass), RED (2 or fewer pass) |

### 3.2 How the Simulator Works as an Edge Gateway

The simulator acts as a simulated edge device (like a Raspberry Pi or industrial gateway at a building site). In a real deployment, this device would be physically connected to the BMS via BACnet, Modbus, or OPC UA, reading live sensor values and forwarding them to the cloud.

In our simulation, the CSV file substitutes for the live BMS connection. The script reads one row at a time, packages the sensor values into four JSON messages, and sends them via MQTT to Azure IoT Hub using the `azure-iot-device` Python SDK. Each message has a custom property `sector` that Stream Analytics uses to route it to the correct blob container.

The simulator sends 4 messages every 30 seconds (configurable via `SEND_INTERVAL`). With IoT Hub F1 free tier allowing 8,000 messages per day, this gives approximately 16 hours of continuous operation per day.

Libraries used: `pandas` (CSV reading), `azure-iot-device` (MQTT client for IoT Hub), `python-dotenv` (loading connection string from .env file), `json` (payload serialisation).

---

## Section 4: Stream Analytics — What Happens in the Cloud

Azure Stream Analytics sits between IoT Hub and Blob Storage. It reads the raw JSON messages from IoT Hub, runs SQL queries against them, and writes aggregated results to blob containers every 15 minutes.

There are four queries, one per sector. Each uses a "tumbling window" of 15 minutes, meaning it collects all messages that arrive within each 15 minute window, computes averages (or sums or maximums), and writes one output row per window.

**HVAC Query Output** — written to `telemetry-hvac` container:

| Output Field | SQL Expression | What It Is |
|-------------|----------------|------------|
| flow_cfm | AVG(metrics.supply_air_flow_cfm) | Average airflow over 15 min |
| sf_pct | AVG(metrics.supply_fan_speed_pct) | Average supply fan speed |
| rf_pct | AVG(metrics.return_fan_speed_pct) | Average return fan speed |
| delta_t | AVG(metrics.delta_t_f) | Average supply/return temp difference |
| efficiency | AVG(metrics.efficiency_index) | Average efficiency index |
| volatility | AVG(metrics.speed_volatility) | Average fan speed volatility |
| comfort_gap | AVG(metrics.comfort_gap_f) | Average zone comfort deviation |
| outdoor_temp | AVG(metrics.outdoor_temp_c) | Average outdoor temperature |
| oee | AVG(metrics.oee_pct) | Average OEE |

**Pumps Query Output** — written to `telemetry-pumps` container:

| Output Field | SQL Expression | What It Is |
|-------------|----------------|------------|
| vibration | AVG(metrics.vibration_mms) | Average bearing vibration |
| power_kw | AVG(metrics.pump_power_kw) | Average pump power |
| hw_temp_c | AVG(metrics.hw_supply_temp_c) | Average hot water temperature |
| legionella | MAX(metrics.legionella_risk) | Whether legionella risk occurred in window |
| oee | AVG(metrics.oee_pct) | Average pump OEE |
| mtbf | AVG(metrics.mtbf_hours) | Mean Time Between Failures |
| mttr | AVG(metrics.mttr_hours) | Mean Time To Repair |

**Electrical Query Output** — written to `telemetry-elec` container:

| Output Field | SQL Expression | What It Is |
|-------------|----------------|------------|
| total_kw | AVG(metrics.total_building_kw) | Average total building power |
| hvac_south | AVG(metrics.hvac_south_kw) | Average HVAC south panel |
| hvac_north | AVG(metrics.hvac_north_kw) | Average HVAC north panel |
| lighting | AVG(metrics.lighting_south_kw) | Average lighting power |
| hvac_pct | AVG(metrics.hvac_pct_of_total) | HVAC percentage of total |
| ghost_alerts | SUM(metrics.ghost_lighting_alert) | Count of ghost lighting events in window |

**Compliance Query Output** — written to `telemetry-compliance` container:

| Output Field | SQL Expression | What It Is |
|-------------|----------------|------------|
| hw_temp_c | AVG(metrics.hw_temp_celsius) | Average hot water temperature |
| checks_passed | MIN(metrics.checks_passed) | Worst case compliance score in window |
| checks_total | MAX(metrics.checks_total) | Always 4 |

---

## Section 5: Dashboard — How Every Metric Is Calculated

The dashboard receives data either from the local JSON file (replay mode) or from blob storage (live mode). In both cases, the data structure is the same short field names like `sf001`, `vib`, `te`, etc. Here is how every visible metric on each view is calculated.

### 5.1 HVAC View

The RTU dropdown selects which unit (001 to 004) to display. All formulas use the selected RTU's data.

| Widget | Formula | Explanation |
|--------|---------|-------------|
| OEE | `(Availability × Performance × Quality) / 100` | See breakdown below |
| Efficiency | `ef001` directly from data | Airflow divided by fan speed. Higher = healthier. |
| Delta-T | `dt001` directly from data | Return air temp minus supply air temp in °F |
| Supply Fan | `sf001` directly from data | Fan speed as percentage of motor maximum |
| Return Fan | `rf001` directly from data | Return fan speed percentage |
| Comfort Gap | Absolute value of `cg036` | Distance from setpoint in °F |
| Volatility | `vo001` directly from data | Rolling standard deviation of fan speed |
| Outdoor | `oat` directly from data | Weather station temperature in °C |
| MTBF | `5000 + (RTU_number × 100)` | Static estimate. RTU-001 = 5100h, RTU-002 = 5200h, etc. |
| MTTR | `2.0 + (RTU_number × 0.2)` | Static estimate. RTU-001 = 2.2h, RTU-002 = 2.4h, etc. |

**OEE Breakdown for HVAC:**

OEE (Overall Equipment Effectiveness) is a manufacturing metric adapted for HVAC. It has three components:

- Availability: Is the unit running? If supply fan speed is above 10%, availability is 100%. If below 10%, it is 0% (unit is off or failed).
- Performance: How much of the design capacity is being used? `airflow / 20,000 CFM × 100`. If delivering 15,000 CFM out of a possible 20,000, performance is 75%.
- Quality: Is the output meeting specifications? If the comfort gap is within ±2°F, quality is 100%. If outside ±2°F, quality drops to 50% (the unit is running but not keeping people comfortable).

OEE = Availability × Performance × Quality / 10,000 (to normalise to percentage).

**Status Logic:**

- Offline: supply fan speed below 10%
- Critical: volatility above 5.0 (severe short cycling)
- Warning: volatility above 2.0
- Online: everything normal

### 5.2 Pumps and Plant View

| Widget | Formula | Explanation |
|--------|---------|-------------|
| Vibration | `vib` directly from data | Bearing vibration in mm/s |
| Power | `pwr` directly from data | Motor consumption in kW |
| Predicted RUL | `(8.0 - vibration) / 0.18` | Days until vibration reaches 8.0 mm/s failure threshold at the observed degradation rate of 0.18 mm/s per day |
| Pump OEE | `100 - (vibration - 2.5) × 12` | Decreases as vibration increases above the 2.5 mm/s healthy baseline |
| MTBF | `6000 - (vibration × 500)` | Decreases as condition worsens. At healthy vibration (2.5): 4750h. At failure (8.0): 2000h. |
| MTTR | `2.5 + (vibration × 0.3)` | Repair takes longer when equipment is in worse condition |
| HW Temp | `hwc` directly from data | Hot water temperature in °C |
| Legionella | "RISK" if hwc below 60°C, "OK" otherwise | Per HSG274 Part 2 |
| Degradation | `(vibration / 8.0) × 100` | Percentage of failure threshold reached |

**Status Logic:**

- Critical: vibration above 7.0 mm/s
- Warning: vibration above 4.5 mm/s (ISO 10816 alert threshold)
- Online: vibration above 0 and below 4.5
- Offline: vibration is 0 (no data)

### 5.3 Electrical View

| Widget | Formula | Explanation |
|--------|---------|-------------|
| Total Load | `te` directly from data | Sum of all electrical panels in kW |
| HVAC Share | `hp` directly from data | HVAC energy as percentage of total building energy |
| HVAC South | `hs` directly from data | South wing HVAC panel in kW |
| HVAC North | `hn` directly from data | North wing HVAC panel in kW |
| Lighting | `li` directly from data | South wing lighting in kW |
| Ghost Light | "ALERT" if `gh` is nonzero | Lights detected on during unoccupied hours |
| Panel OEE | 99.9% (static) | Electrical panels rarely fail. This is a fixed value for the demo. |
| MTBF | 12,000h (static) | Electrical panels have very long lifespans |
| MTTR | 0.5h (static) | Panel faults are typically quick to resolve (breaker reset) |

### 5.4 Compliance View

This view aggregates four regulatory checks that a facilities manager must monitor.

| Check | Standard | Pass Condition | Data Source |
|-------|----------|---------------|-------------|
| Hot Water Temperature | HSG274 Part 2 (UK Health and Safety Executive) | Hot water supply above 60°C | `hwc` field |
| Zone Comfort | CIBSE Guide A (Chartered Institution of Building Services Engineers) | Zone temperature within ±2°F of setpoint | `cg036` field |
| Equipment Vibration | ISO 10816 (Mechanical Vibration Severity) | Pump vibration below 8.0 mm/s | `vib` field |
| Ghost Lighting | Energy waste detection | No lighting above 0.5 kW during unoccupied hours | `gh` field |

The compliance score is simply how many of these four checks pass. 4/4 = all compliant. 3/4 = one issue. 2/4 or less = multiple failures requiring attention.

---

## Section 6: Field Name Mapping Reference

When data moves through the pipeline, the field names change at each stage. This table shows the complete mapping.

| What It Represents | Enriched CSV Column | Simulator JSON Field | Stream Analytics Output | Dashboard Key |
|-------------------|---------------------|---------------------|----------------------|--------------|
| RTU-001 Supply Fan Speed | rtu_001_sf_vfd_spd_fbk_tn | metrics.supply_fan_speed_pct | sf_pct | sf001 |
| RTU-001 Return Fan Speed | rtu_001_rf_vfd_spd_fbk_tn | metrics.return_fan_speed_pct | rf_pct | rf001 |
| RTU-001 Airflow | rtu_001_fltrd_sa_flow_tn | metrics.supply_air_flow_cfm | flow_cfm | fl001 |
| RTU-001 Efficiency | rtu_001_efficiency | metrics.efficiency_index | efficiency | ef001 |
| RTU-001 Delta-T | rtu_001_delta_t | metrics.delta_t_f | delta_t | dt001 |
| RTU-001 Volatility | rtu_001_speed_volatility | metrics.speed_volatility | volatility | vo001 |
| Zone Comfort Gap | zone_016_comfort_gap | metrics.comfort_gap_f | comfort_gap | cg036 |
| Outdoor Temperature | air_temp_set_1 | metrics.outdoor_temp_c | outdoor_temp | oat |
| Pump Vibration | pump_vibration_mms | metrics.vibration_mms | vibration | vib |
| Pump Power | pump_power_kw | metrics.pump_power_kw | power_kw | pwr |
| Hot Water Temp | hw_temp_celsius | metrics.hw_supply_temp_c | hw_temp_c | hwc |
| Total Energy | total_energy_kw | metrics.total_building_kw | total_kw | te |
| HVAC South | hvac_s | metrics.hvac_south_kw | hvac_south | hs |
| HVAC North | hvac_n | metrics.hvac_north_kw | hvac_north | hn |
| Lighting | lig_s | metrics.lighting_south_kw | lighting | li |
| HVAC Percentage | hvac_pct | metrics.hvac_pct_of_total | hvac_pct | hp |
| Ghost Lighting | ghost_lighting | metrics.ghost_lighting_alert | ghost_alerts | gh |
