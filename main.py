from flask import Flask, render_template, request
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.io as pio
from functions import get_excel, calc_e_array, performance, capex_calc, config_SWB, config_SB, hourly_profile

app = Flask(__name__)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/financial')
def financial():
    return render_template('index_f.html')


@app.route('/results', methods=['POST'])
def results():
    # Get user input from the form
    sol_range_start = float(request.form['solar_capacity_start'])
    sol_range_end = float(request.form['solar_capacity_end'])
    solar_step = float(request.form['solar_step'])

    wind_range_start = float(request.form['wind_capacity_start'])
    wind_range_end = float(request.form['wind_capacity_end'])
    wind_step = float(request.form['wind_step'])
    bess_start_cap = float(request.form['bess_initial_cap'])
    bess_final_cap = float(request.form['bess_total_cap'])
    bess_step = float(request.form['bess_step'])

    #sol_cost_pMW = float(request.form['sol_cost_pMW'])
    #wind_cost_pMW = float(request.form['wind_cost_pMW'])
    #bess_cost_pMW = float(request.form['bess_cost_pMW'])

    sol_cost_pMW = 5.00  # 5 Cr. per MW
    wind_cost_pMW = 8.00  # 8 Cr. per MW
    bess_cost_pMW = 1.40  # 1.40 Cr. per MW

    # Batter parameters
    trans_efficiency = (float(request.form['trans_efficiency']))
    ch_efficiency = (float(request.form['ch_efficiency']))
    dis_efficiency = (float(request.form['dis_efficiency']))
    pcs_converter = (float(request.form['pcs_converter']))
    bat_dod_limit = (float(request.form['bat_dod_limit']))

    rtc_required = float(request.form['rtc_required'])
    cutoff = float(request.form['cutoff']) / 100

    # Assuming the Excel file is already present in the working directory
    excel_path = 'MVAC_rtc_wind_rtc_c(AutoRecovered).xlsm'
    sheet0_df = get_excel(excel_path)
    sheet0_df.dropna(inplace=True)

    # Extract the necessary columns
    e_grid = sheet0_df['E_grid (33kV)']
    wind = sheet0_df['Wind']

    sol_range = np.arange(sol_range_start, sol_range_end, solar_step)
    bess_range = np.arange(bess_start_cap, bess_final_cap, bess_step)
    if (wind_range_start == 0) and (wind_range_end == 0):
        wind_range = []
    else:
        wind_range = np.arange(wind_range_start, wind_range_end, wind_step)

    if len(wind_range) > 0:
        solar_cap_l, wind_cap_l, bess_l, rtc_success_rate, sum_rtc_out, capex_val, curtailment_l = config_SWB(
            sol_range, wind_range, bess_range, e_grid, wind, rtc_required,
            trans_efficiency, ch_efficiency, dis_efficiency, pcs_converter,
            bat_dod_limit, sol_cost_pMW, wind_cost_pMW, bess_cost_pMW)
    else:
        solar_cap_l, wind_cap_l, bess_l, rtc_success_rate, sum_rtc_out, capex_val, curtailment_l = config_SB(
            sol_range, bess_range, e_grid, wind, rtc_required,
            trans_efficiency, ch_efficiency, dis_efficiency, pcs_converter,
            bat_dod_limit, sol_cost_pMW, wind_cost_pMW, bess_cost_pMW)

    # Create the DataFrame
    curt_avg = np.mean(curtailment_l)
    capex_avg = np.mean(capex_val)

    #performance_number_l = []
    cap_to_power = []
    out_power_gw_l = []
    for i in range(len(curtailment_l)):
        #curt = round((curt_avg-curtailment_l[i])/curt_avg,2)
        #capex_var = round((capex_avg-capex_val[i])/capex_avg,2)
        capex = capex_val[i]
        out_power = sum_rtc_out[i]
        out_power_gw = out_power / 1000
        out_power_gw_l.append(out_power_gw)

        #Performance Number
        #performance_number = curt+capex_var
        #performance_number_l.append(performance_number)

        #Capex/Generation
        capex_rs = capex * 10000000
        units = out_power * 1000
        tmp = round(capex_rs / units, 2)
        cap_to_power.append(tmp)

    new_df = pd.DataFrame({
        'Solar Capacity (MW)': solar_cap_l,
        'Wind Capacity (MW)': wind_cap_l,
        'BESS Capacity (MWh)': bess_l,
        'Success Rate': rtc_success_rate,
        'Out Power (GW)': out_power_gw_l,
        'Total Curtailment (MU)': curtailment_l,
        'Capex (Crores INR)': capex_val,
        'Capex/Generation (INR/Unit)': cap_to_power
    })

    # Filter the DataFrame for Success Rate >= 85%
    success_df = new_df[new_df['Success Rate'] >= cutoff]
    success_df.sort_values(by='Capex/Generation (INR/Unit)',
                           ascending=True,
                           inplace=True)

    best_combination = success_df.head(1)

    min_capex_df = success_df.loc[success_df.groupby('Solar Capacity (MW)')
                                  ['Capex/Generation (INR/Unit)'].idxmin()]
    # Reset the index
    min_capex_df = min_capex_df.reset_index(drop=True)
    success_df = success_df.reset_index(drop=True)

    solar_cap = best_combination['Solar Capacity (MW)'].iloc[0]
    wind_cap = best_combination['Wind Capacity (MW)'].iloc[0]
    bess_cap = best_combination['BESS Capacity (MWh)'].iloc[0]
    e_array = calc_e_array(e_grid, wind, solar_cap, wind_cap)

    hp = hourly_profile(sheet0_df, solar_cap, wind_cap, bess_cap,e_array)

    # Generate Scatter Plot (Capex vs Success Rate)
    scatter_fig = px.scatter(success_df,
                             x='Capex (Crores INR)',
                             y='Success Rate',
                             title='Capex vs Success Rate Scatter Plot',
                             labels={
                                 'Capex (Crores INR)': 'Capex (Cr)',
                                 'Success Rate': 'Success Rate (%)'
                             },
                             hover_data={
                                 'Solar Capacity (MW)': True,
                                 'Wind Capacity (MW)': True,
                                 'BESS Capacity (MWh)': True,
                                 'Capex (Crores INR)': ':,.2f',
                                 'Success Rate': ':,.2f'
                             })
    scatter_html = pio.to_html(scatter_fig, full_html=False)

    # Generate Parallel Coordinates Plot with better colors
    fig = px.parallel_categories(
        min_capex_df,
        dimensions=[
            'Solar Capacity (MW)', 'Wind Capacity (MW)', 'BESS Capacity (MWh)',
            'Success Rate', 'Capex (Crores INR)'
        ],
        color='Capex (Crores INR)',
        color_continuous_scale=px.colors.sequential.Inferno)

    fig2 = px.parallel_coordinates(
        min_capex_df,
        dimensions=[
            'Solar Capacity (MW)', 'Wind Capacity (MW)', 'BESS Capacity (MWh)',
            'Success Rate', 'Capex (Crores INR)'
        ],
        color="Success Rate",
        title=
        'Parallel Coordinates Plot for Solar, Wind, Battery, Success Rate, and Capex'
    )

    # Save the plot as an HTML file
    plot1_html = pio.to_html(fig, full_html=False)
    plot2_html = pio.to_html(fig2, full_html=False)

    # Render the results on the results page
    return render_template('results.html',
                           plot1_html=plot1_html,
                           plot2_html=plot2_html,
                           scatter_html=scatter_html,
                           table1=min_capex_df.to_html(classes='data',
                                                       header="true"),
                           table2=success_df.to_html(classes='data',
                                                     header="true"),
                           table3=best_combination.to_html(classes='data',
                                                           header="true"),
                           table4=hp.to_html(classes='data',
                                                         header="true"))


if __name__ == '__main__':
    app.run(debug=True)
