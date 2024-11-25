## Getting the excel sheet from the path

# Functions used to calculate various metrics used in the app

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import plotly.graph_objs as go
import plotly.express as px


def get_excel(path):
    sheet0_df = pd.read_excel(path, sheet_name='Sheet1')

    date = sheet0_df['Date']
    time = sheet0_df['Time']

    sheet0_df['Date'] = sheet0_df['Date'].dt.strftime('%Y-%m-%d')
    sheet0_df['Time'] = sheet0_df['Time'].astype(str)
    # Combine Date and Time columns into a single DateTime column
    sheet0_df['DateTime'] = pd.to_datetime(sheet0_df['Date'] + ' ' +
                                           sheet0_df['Time'])

    datetime = sheet0_df['DateTime']
    sheet0_df = sheet0_df[['DateTime', 'E_grid (33kV)', 'Wind']]

    e_grid = sheet0_df['E_grid (33kV)']
    wind = sheet0_df['Wind']

    return sheet0_df


## Calculating 'E-array' from 'E-grid' and 'Wind'


def calc_e_array(e_grid, wind, solar_cap, wind_cap):
    e_array1 = []
    if wind_cap == 0:
        for i in range(len(e_grid)):
            out = (e_grid[i] / 17.6) * solar_cap
            e_array1.append(out)
        return e_array1
    for i in range(len(e_grid)):
        solar_out = (e_grid[i] / 17.6) * solar_cap
        wind_out = (wind[i] / 500) * wind_cap
        out = solar_out + wind_out
        e_array1.append(out)
    return e_array1


## Calculating 'Capex' value for each combination
def capex_calc(solar_cap, wind_cap, bess, sol_cost_pMW, wind_cost_pMW,
               bess_cost_pMW):
    capex = (sol_cost_pMW * solar_cap) + (wind_cost_pMW *
                                          wind_cap) + (bess_cost_pMW * bess)
    return capex


## Calculating 'Success Rate' for a combination
## Updated 25/09/2024
def performance(e_array, battery_initial, battery_cap, rtc_required,
                trans_efficiency, ch_efficiency, dis_efficiency, pcs_converter,
                bat_dod_limit):
    rtc_delivered = []
    bat = []
    curtailment = []
    bat_output = []
    rtc_100 = []

    # System efficiencies
    trans_efficiency = trans_efficiency / 100
    #ch_efficiency = ch_efficiency / 100
    #dis_efficiency = dis_efficiency / 100
    ch_efficiency = np.sqrt(0.94) * 0.985 * 0.999 * 0.998
    dis_efficiency = ch_efficiency
    pcs_converter = pcs_converter / 100

    charge_const = trans_efficiency * ch_efficiency * pcs_converter
    discharge_const = trans_efficiency * dis_efficiency * pcs_converter

    # Battery Parameters
    battery_soc = 1.00
    battery = battery_initial
    battery_cap = battery_cap
    bat_dod_limit = bat_dod_limit / 100  # Depth of Discharge limit

    success_count = 0
    fail_count = 0

    rtc_required = rtc_required  # RTC demand

    ##
    energy_utilised = []
    rtc_delivered = []

    bat_output_l = []
    battery_rem_l = []
    ren_contribution_l = []
    rtc_delivered_l = []
    rtc_100_l = []
    curtailment_l = []
    rtc_req_l = []
    discharge_l = []
    bat_max_out = 0.0

    for i in range(len(e_array)):
        ren_energy = e_array[
            i]  # Power available from Renewable sources of energy (Solar and Wind)
        inv_out = 0  ## Inverter Output

        # Calculate RTC Delivered based on renewable energy
        if ren_energy >= rtc_required:
            inv_out = rtc_required
            bat_con = 0
            ren_con = rtc_required
            # Curtailment
            # Check if battery exceeds capacity after charging with excess energy

            excess_energy = ren_energy - rtc_required
            bat_max_charge = battery_cap * battery_soc  ## Max capacity to which battery can be charged

            if battery >= bat_max_charge:  ## Battery already fully charged
                curtailment.append(excess_energy)
                battery = bat_max_charge

            else:  ## Battery initially not fully charged
                bat_initial = battery
                battery += excess_energy * charge_const

                if battery > bat_max_charge:  ## Battery Charge exceeds max capacity
                    excess_charge = battery - bat_max_charge  ## Excess amount of energy after fully charging battery
                    curtailment.append(excess_charge / charge_const)
                    battery = bat_max_charge
                else:  ## Battery Charge doesn't exceed max capacity
                    curtailment.append(0)

        else:  # Battery needs to cover the shortfall
            curtailment.append(0)
            bat_min_discharge = battery_cap * (1.00 - bat_dod_limit
                                               )  ## Minimum Battery Discharge
            energy_shortfall = rtc_required - ren_energy
            req_bat_output = energy_shortfall / discharge_const
            bat_max_out = battery - bat_min_discharge
            ren_con = ren_energy

            if bat_max_out >= req_bat_output:  ## Battery can cover shortfall
                inv_out = rtc_required
                battery -= req_bat_output
                bat_con = energy_shortfall
            else:  ## Battery can't cover shortfall
                usable_energy = (battery - bat_min_discharge) * discharge_const
                battery = bat_min_discharge
                bat_con = usable_energy
                inv_out = ren_energy + bat_con

        # Success/Fail Count based on RTC Delivered

        if inv_out >= rtc_required:
            rtc_100.append(1)
        else:
            rtc_100.append(0)

        # Update battery status
        bat.append(battery)
        rtc_delivered.append(inv_out)

        battery_rem_l.append(battery)
        ren_contribution_l.append(ren_con)
        rtc_delivered_l.append(inv_out)
        rtc_req_l.append(rtc_required)
        bat_output_l.append(bat_con)

    success_rate = sum(rtc_100) / len(rtc_100)
    curtailment_mu = sum(curtailment) / 1000
    out_power = sum(rtc_delivered_l)

    return success_rate, curtailment_mu, out_power


##[Solar, Wind, BESS]
def config_SWB(
    sol_range,
    wind_range,
    bess_range,
    e_grid,
    wind,
    rtc_required,
    trans_efficiency,
    ch_efficiency,
    dis_efficiency,
    pcs_converter,
    bat_dod_limit,
    sol_cost_pMW,
    wind_cost_pMW,
    bess_cost_pMW,
):

    solar_cap_l = []
    wind_cap_l = []
    bess_l = []
    rtc_success_rate = []
    sum_rtc_out = []
    capex_val = []
    curtailment_l = []

    for i in sol_range:
        for j in wind_range:
            for k in bess_range:
                bess_initial_cap = k
                bess_total_cap = k
                solar_cap_l.append(i)
                wind_cap_l.append(j)
                bess_l.append(k)

                e_array = calc_e_array(e_grid, wind, i, j)
                success, curtailment, out_power = performance(
                    e_array, k, k, rtc_required, trans_efficiency,
                    ch_efficiency, dis_efficiency, pcs_converter,
                    bat_dod_limit)
                capex = capex_calc(i, j, k, sol_cost_pMW, wind_cost_pMW,
                                   bess_cost_pMW)
                rtc_success_rate.append(success)
                sum_rtc_out.append(out_power)
                capex_val.append(capex)
                curtailment_l.append(curtailment)

        # Create the DataFrame

    return solar_cap_l, wind_cap_l, bess_l, rtc_success_rate, sum_rtc_out, capex_val, curtailment_l


## Compare the total value of E_array with the sum_rtc_out and total_battery_contribution
## If sum(E_array) ~= sum(sum_rtc_out) + sum(total_battery_contribution) that means that we just used the excess energy at times to recharge the beattery and use it later.

## But if for the same sum(rtc_out) and sum(E-array) if the battery contribution is


##[Solar, BESS]
def config_SB(
    sol_range,
    bess_range,
    e_grid,
    wind,
    rtc_required,
    trans_efficiency,
    ch_efficiency,
    dis_efficiency,
    pcs_converter,
    bat_dod_limit,
    sol_cost_pMW,
    wind_cost_pMW,
    bess_cost_pMW,
):

    solar_cap_l = []
    wind_cap_l = []
    bess_l = []
    rtc_success_rate = []
    sum_rtc_out = []
    capex_val = []
    curtailment_l = []

    for i in sol_range:
        for k in bess_range:
            bess_initial_cap = k
            bess_total_cap = k
            j = 0
            solar_cap_l.append(i)
            wind_cap_l.append(j)
            bess_l.append(k)

            e_array = calc_e_array(e_grid, wind, i, j)
            success, curtailment, out_power = performance(
                e_array, k, k, rtc_required, trans_efficiency, ch_efficiency,
                dis_efficiency, pcs_converter, bat_dod_limit)
            capex = capex_calc(i, j, k, sol_cost_pMW, wind_cost_pMW,
                               bess_cost_pMW)
            rtc_success_rate.append(success)
            sum_rtc_out.append(out_power)
            capex_val.append(capex)
            curtailment_l.append(curtailment)

        # Create the DataFrame

    return solar_cap_l, wind_cap_l, bess_l, rtc_success_rate, sum_rtc_out, capex_val, curtailment_l


def hourly_profile(sheet_df, solar_cap, wind_cap, bess_cap, e_array):
    df = pd.DataFrame()
    df['datetime'] = pd.to_datetime(sheet_df['DateTime'])
    df['date'] = df['datetime'].dt.date
    df['time'] = df['datetime'].dt.time
    date = df['date'].tolist()
    time = df['time'].tolist()
    e_grid = sheet_df['E_grid (33kV)']
    wind = sheet_df['Wind']
    rtc_delivered = []
    bat = []
    curtailment = []
    bat_output = []
    rtc_100 = []

    # System efficiencies
    trans_efficiency = 99 / 100
    ch_efficiency = np.sqrt(0.94) * 0.985 * 0.999 * 0.998
    dis_efficiency = ch_efficiency
    pcs_converter = 98.40 / 100

    charge_const = trans_efficiency * ch_efficiency * pcs_converter
    discharge_const = trans_efficiency * dis_efficiency * pcs_converter

    # Battery Parameters
    battery_soc = 1.00
    battery = 24000.00
    battery_cap = 24000.00
    bat_dod_limit = 0.98  # Depth of Discharge limit

    success_count = 0
    fail_count = 0

    rtc_required = 1600.00  # RTC demand

    ##
    energy_utilised = []
    rtc_delivered = []

    bat_output_l = []
    battery_rem_l = []
    ren_contribution_l = []
    rtc_delivered_l = []
    rtc_100_l = []
    curtailment_l = []
    rtc_req_l = []
    bat_max_out = 0.0

    for i in range(len(e_array)):
        ren_energy = e_array[
            i]  # Power available from Renewable sources of energy (Solar and Wind)
        inv_out = 0  ## Inverter Output

        # Calculate RTC Delivered based on renewable energy
        if ren_energy >= rtc_required:
            inv_out = rtc_required
            bat_con = 0
            ren_con = rtc_required
            # Curtailment
            # Check if battery exceeds capacity after charging with excess energy

            excess_energy = ren_energy - rtc_required
            bat_max_charge = battery_cap * battery_soc  ## Max capacity to which battery can be charged

            if battery >= bat_max_charge:  ## Battery already fully charged
                curtailment.append(excess_energy)
                battery = bat_max_charge

            else:  ## Battery initially not fully charged
                bat_initial = battery
                battery += excess_energy * charge_const

                if battery > bat_max_charge:  ## Battery Charge exceeds max capacity
                    excess_charge = battery - bat_max_charge  ## Excess amount of energy after fully charging battery
                    curtailment.append(excess_charge / charge_const)
                    battery = bat_max_charge
                else:  ## Battery Charge doesn't exceed max capacity
                    curtailment.append(0)

        else:  # Battery needs to cover the shortfall
            curtailment.append(0)
            bat_min_discharge = battery_cap * (1.00 - bat_dod_limit
                                               )  ## Minimum Battery Discharge
            energy_shortfall = rtc_required - ren_energy
            req_bat_output = energy_shortfall / discharge_const
            bat_max_out = battery - bat_min_discharge
            ren_con = ren_energy

            if bat_max_out >= req_bat_output:  ## Battery can cover shortfall
                inv_out = rtc_required
                battery -= req_bat_output
                bat_con = energy_shortfall
            else:  ## Battery can't cover shortfall
                usable_energy = (battery - bat_min_discharge) * discharge_const
                battery = bat_min_discharge
                bat_con = usable_energy
                inv_out = ren_energy + bat_con

        # Success/Fail Count based on RTC Delivered

        if inv_out >= rtc_required:
            rtc_100.append(1)
        else:
            rtc_100.append(0)

        # Update battery status
        bat.append(battery)
        rtc_delivered.append(inv_out)

        battery_rem_l.append(battery)
        ren_contribution_l.append(ren_con)
        rtc_delivered_l.append(inv_out)
        rtc_req_l.append(rtc_required)
        bat_output_l.append(bat_con)

    new_df = pd.DataFrame({
        'Date': date,
        'Time': time,
        'E_grid (33kV)': e_grid,
        'E-Array': e_array,
        'RTC Required': rtc_req_l,
        'RTC Delivered': rtc_delivered_l,
        'Curtailment': curtailment,
        'Solar Contribution in RTC': ren_contribution_l,
        'Current Power in Battery': battery_rem_l,
        'Battery Contribution in RTC': bat_output_l,
        'RTC Yes': rtc_100
    })

    return new_df
