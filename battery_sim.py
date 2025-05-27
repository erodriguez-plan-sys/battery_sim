import pandas as pd
import time
import json
import sys 

# Load Config File
try:
    with open("config.json", "r") as f:
        config = json.load(f)

    BATTERY_CAPACITY_KWH = config.get("battery_capacity_kwh", 27)
    CSV_FILE = config.get("csv_file", "med_eq.csv")
    SIMULATION_SPEED = config.get("simulation_speed", 60)
    USE_CASE_CONFIG = config.get("use_case_config", {})
    SELECTED_SCENARIO = config.get("selected_scenario")

    if SELECTED_SCENARIO is None:
        print("Error: 'selected_scenario' not defined in config.json.")
        exit()

except FileNotFoundError:
    print("Error: config.json not found. Please create this file.")
    exit()
except json.JSONDecodeError:
    print("Error: Invalid JSON format in config.json.")
    exit()

# Load CSV file (equipment power)
df = pd.read_csv(CSV_FILE)
df["Power_kW"] = df["Power_W"] / 1000
df["Time_hr"] = df["Time_min"] / 60
df["Energy_kWh"] = df["Power_kW"] * df["Time_hr"]
df["battery_powered"] = df["battery_powered"].astype(bool)
df["always_on"] = df["always_on"].astype(bool)

# Time format
def format_time(seconds):
    if seconds >= 3600:
        hours = int(seconds // 3600)
        remaining_seconds = int(seconds % 3600)
        minutes = int(remaining_seconds // 60)
        sec = int(remaining_seconds % 60)
        return f"{hours} hr {minutes} min {sec} sec"
    elif seconds >= 60:
        minutes = int(seconds // 60)
        sec = int(seconds % 60)
        return f"{minutes} min {sec} sec"
    else:
        return f"{seconds:.2f} sec"

# Simulation Loop
def simulate_use_case(devices: pd.DataFrame, battery_kwh: float, duration_hours: int, scenario_name: str, sim_speed: float = 1):
    total_simulation_seconds = duration_hours * 3600
    total_simulation_minutes = duration_hours * 60

    print(f"Starting Simulation for '{scenario_name}' — Initial Battery: {battery_kwh:.2f} kWh, Duration: {duration_hours} hours, Speed: {sim_speed}x\n")

    if sim_speed == 0:
        # Instant Calculation Mode (remains the same)
        # print out power per med equipment 
        total_energy_consumed_kwh = 0
        for _, row in devices.iterrows():
            power_kw = row["Power_W"] / 1000
            if row["always_on"]:
                total_energy_consumed_kwh += power_kw * duration_hours
            elif not pd.isna(row["Time_min"]) and row["Time_min"] > 0:
                runtime_hours = row["Time_min"] / 60
                effective_duration_hours = min(duration_hours, runtime_hours)
                total_energy_consumed_kwh += power_kw * effective_duration_hours

        final_battery_kwh = battery_kwh - total_energy_consumed_kwh
        pct_remaining = max(0,(final_battery_kwh / battery_kwh) * 100)
        print(f"Simulation Complete (Instant Calculation):")
        print(f"  Duration: {format_time(total_simulation_seconds)}")
        print(f"  Total Energy Consumed: {total_energy_consumed_kwh:.2f} kWh")
        print(f"  Final Battery Remaining: {max(0, final_battery_kwh):.2f} kWh | Pct: {pct_remaining:.2f}%")
        if final_battery_kwh <= 0:
            time_to_depletion_hours = battery_kwh / (total_energy_consumed_kwh / duration_hours) if (total_energy_consumed_kwh / duration_hours) > 0 else float('inf')
            time_to_depletion_seconds = time_to_depletion_hours * 3600
            print(f"\n⚠️ Battery depleted! Estimated time to depletion: {format_time(time_to_depletion_seconds)}")
            print("❌ Simulation indicates battery depletion before the full duration.")
        else:
            print("\n✅ Simulation indicates sufficient battery for the full duration.")
    # HOUR / SEC
    elif sim_speed == 3600:
        # Hour Calculation Mode (remains the same)
        # Print power per med eq
        battery_remaining_kwh = battery_kwh
        power_draw = 0

    
        for hour in range(duration_hours):
            total_power_draw_kw = 0
            for _, row in devices.iterrows():
                power_kw = row["Power_W"] / 1000
                if row["always_on"]:
                    total_power_draw_kw += power_kw
                elif not pd.isna(row["Time_min"]) and row["Time_min"] > 0 and hour * 60 < row["Time_min"]:
                    total_power_draw_kw += power_kw
    
            energy_drawn_this_hour_kwh = total_power_draw_kw * 1
            battery_remaining_kwh -= energy_drawn_this_hour_kwh
            power_draw += total_power_draw_kw
    
            print(f"Hour {hour + 1} — Power Draw: {total_power_draw_kw:.2f} kW | Energy Used: {power_draw:.2f} kWh | Battery Remaining: {max(0, battery_remaining_kwh):.2f} kWh", end='\r')
    
            if battery_remaining_kwh <= 0:
                print(f"\n⚠️ Battery depleted after {hour + 1} hour(s).")
                print("❌ Simulation ended - Battery depleted before the full duration.")
                break
    
            time.sleep(1)  # 1 real second per simulated hour
    
        if battery_remaining_kwh > 0:
            print("\n✅ Simulation ended - Duration reached.")
        pct_remaining = max(0,(battery_remaining_kwh / battery_kwh) * 100)
        print(f"\nFinal Battery Remaining: {max(0, battery_remaining_kwh):.2f} kWh | Pct: {pct_remaining:.2f}%")
    



    else:
        # Time-Stepping Simulation Mode with Dynamic Time Display
        battery_remaining_kwh = battery_kwh
        time_elapsed_seconds = 0

        while time_elapsed_seconds < total_simulation_seconds and battery_remaining_kwh > 0:
            total_power_draw_kw = 0
            for _, row in devices.iterrows():
                power_kw = row["Power_W"] / 1000
                if row["always_on"]:
                    total_power_draw_kw += power_kw
                elif not pd.isna(row["Time_min"]) and row["Time_min"] > 0 and time_elapsed_seconds / 60 <= row["Time_min"]:
                    total_power_draw_kw += power_kw

            energy_drawn_per_second_kwh = total_power_draw_kw / 3600
            battery_remaining_kwh -= energy_drawn_per_second_kwh
            time_elapsed_seconds += 1

            estimated_time_left_seconds = (battery_remaining_kwh / total_power_draw_kw * 3600) if total_power_draw_kw > 0 else float('inf')

            print(f"Time: {format_time(time_elapsed_seconds)} / {format_time(total_simulation_seconds)}, Battery Remaining: {battery_remaining_kwh:.2f} kWh, Est. Time Left: {format_time(estimated_time_left_seconds)}", end='\r')
            sys.stdout.flush()
            time.sleep(1 / sim_speed)

        pct_remaining = max(0,(battery_remaining_kwh / battery_kwh) * 100)

        print("\nSimulation Complete:")
        print(f"  Elapsed Time: {format_time(time_elapsed_seconds)} / {format_time(total_simulation_seconds)}")
        print(f"  Final Battery Remaining: {max(0, battery_remaining_kwh):.2f} kWh | Pct: {pct_remaining:.2f}%")
        if battery_remaining_kwh <= 0:
            print("\n⚠️ Battery depleted!")
            print("❌ Simulation ended - Battery depleted before the full duration.")
        else:
            print("\n✅ Simulation ended - Duration reached.")



# Main Loop
if __name__ == "__main__":
    if SELECTED_SCENARIO in USE_CASE_CONFIG:
        scenarios = USE_CASE_CONFIG  
        scenario = scenarios[SELECTED_SCENARIO]
        devices_to_simulate = scenario.get("devices", []) + scenarios["always_on_only"]["devices"]
        simulation_duration = scenario.get("duration_hours", 1)
        use_case_df = df[df['Device'].isin(devices_to_simulate)].copy()
        simulate_use_case(use_case_df, BATTERY_CAPACITY_KWH, simulation_duration, SELECTED_SCENARIO, SIMULATION_SPEED)
    else:
        print(f"Error: Scenario '{SELECTED_SCENARIO}' not found in config.json.")
