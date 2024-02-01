# -*- coding: utf-8 -*-
import numpy as np, pygrib, datetime, json, pandas as pd, time, cdsapi
import tempfile, os
from datetime import datetime, timedelta

def retrieve_specific_time(timestamp:str, hl: list[str], vbs: list[str],
                           product_type: str):
    grib_file = tempfile.mktemp() + ".grib"
    print("grib_file:", grib_file)
    dt_obj = datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S")
    yr = dt_obj.year
    mt = dt_obj.month
    day = dt_obj.day
    hr = dt_obj.hour
    input_dict = {
        'domain':       'west_domain',
        'variable':     vbs,
        'height_level': hl,
        'product_type': product_type,
        'time':         hr,
        'year':         yr,
        'month':        mt,
        'day':          day,
        'format':       'grib',
        'grid':         [0.04180602, 0.01826484],
        'area':         [66.6, -24.6, 63.3, -13.4]
    }
    if product_type == 'forecast':
        input_dict.update({'leadtime_hour': '24'})
    cdsapi.Client().retrieve('reanalysis-carra-height-levels', input_dict, grib_file)
    running = True
    while running:
        time.sleep(1)
        print("Running>>>>")
        running = not os.path.exists(grib_file)
    print("Out of while loop")
    return grib_file

def retrieve_month(vbs: list[str], height_levels: list[int], product_type: str,
                   yrmonth:str, days: list[int]):
    grib_file = tempfile.mktemp() + ".grib"
    print("grib_file:", grib_file)
    dt_obj = datetime.strptime(yrmonth, "%Y-%m")
    yr = dt_obj.year
    mt = dt_obj.month
    hr_list = [12] if product_type == "forecast" else [15, 18]
    input_dict = {
        'domain':       'west_domain',
        'variable':     vbs,
        'height_level': height_levels,
        'product_type': product_type,
        'time':         hr_list,
        'year':         yr,
        'month':        mt,
        'day':          days,
        'format':       'grib',
        'grid':         [0.04180602, 0.01826484],
        'area':         [66.6, -24.6, 63.3, -13.4]
    }
    if product_type == 'forecast':
        input_dict.update({'leadtime_hour': '24'})
    cdsapi.Client().retrieve('reanalysis-carra-height-levels', input_dict, grib_file)
    running = True
    while running:
        time.sleep(1)
        print("Running>>>>")
        running = not os.path.exists(grib_file)
    print("Out of while loop")
    return grib_file

def add3hrs(date):
    fmt = "%Y-%m-%dT%H:%M:%S"
    dt_obj = datetime.strptime(date, fmt) + timedelta(hours=3)
    return dt_obj.strftime(fmt)

def grib_latlon(grib_file):
    with pygrib.open(grib_file) as grb:
        message = grb[1]
        (lat, lon) = message.latlons()
    return (np.flipud(lat), lon - 360)

def read_grib(grib_file, vbs: list[str], height_levels: list[int], 
              days: list[int], hr_list: list[int]):
    (lat_grid, lon_grid) = grib_latlon(grib_file)
    (nlat, nlon) = lat_grid.shape
    nheight = len(height_levels)
    results = {}
    for day in days:
        results[day] = {}
        for hr in hr_list:
            results[day][hr] = {}
            for var in vbs:
                results[day][hr][var] = np.zeros((nheight, nlat, nlon))
    with pygrib.open(grib_file) as grb:
        for msg in grb:
            for day in days:
                for hr in hr_list:
                    for var in vbs:
                        for k in range(nheight):
                            if msg.name == var and msg.day == day and msg.hour == hr \
                                    and msg.level == height_levels[k]:
                                results[day][hr][var][k, :, :] = np.flipud(msg.values)
        print("Successful run of read_grib")
    return results, lat_grid, lon_grid

def interpolate(lat_grid, lon_grid, lat, lon, res, variable_list):
    # Returns a dictionary with variables as keys and numpy vectors
    # each of length nheights as values.
    distances = np.sqrt((lat_grid - lat)**2 +
                        np.cos(np.radians(lat_grid))*(lon_grid - lon)**2)
    four_closest_indices = np.argsort(distances, axis=None)[:4]
    four_closest_2D_indices = np.unravel_index(four_closest_indices, distances.shape)
    invs = np.zeros(4)
    nheights = res[variable_list[0]].shape[0]

    values = {v: np.zeros((4, nheights)) for v in variable_list}

    for i in range(4):
        lat_idx = four_closest_2D_indices[0][i]
        lon_idx = four_closest_2D_indices[1][i]
        for vbl in variable_list:
            for hl in range(nheights):
                values[vbl][i, hl] = res[vbl][hl, lat_idx, lon_idx]

        invs[i] = 1/np.maximum(0.001, distances[lat_idx, lon_idx])

    w = invs/sum(invs)
    result = {v: w@values[v] for v in variable_list}
    return result

def get_carra_param(file_path):
    with open(file_path, 'r') as file:
        entry = json.load(file)
        carra_dict = entry["param"]
        timestamp_location = entry["timestamp_location"]
    return carra_dict, timestamp_location

file_path = 'carra_param.json'
carra_dict, timestamp_location = get_carra_param(file_path)
var_list = carra_dict["variable"]
height_lev = carra_dict["height_levels"]
product_type = carra_dict["product_type"]

df = pd.DataFrame()

# Create set of year-month for which to retrieve data
yr_month = set()
fmt = "%Y-%m-%dT%H:%M:%S"
for date in timestamp_location.keys():
    dt_obj = datetime.strptime(date, fmt)
    yr_month.add(date[:7])
    if dt_obj.hour >= 21:
        next_dt = dt_obj + timedelta(days=1)
        dt_obj = datetime.strptime(date, fmt) + timedelta(hours=3)
        next_day = dt_obj.strftime(fmt)
        yr_month.add(next_day[:7])

hr_list = [12] if product_type == "forecast" else [15, 18]

for month in yr_month:
    timestamps = [int(d[8:10]) for d in timestamp_location.keys() if d[:7] == month]
    grib_file = retrieve_month(var_list, height_lev, product_type, month, timestamps)
    time.sleep(1)
    res, lat_grid, lon_grid = read_grib(grib_file, var_list, height_lev, timestamps, hr_list)
    for ts in timestamps:
        dt_obj = datetime.strptime(date, fmt)
        dt_next = dt_obj + timedelta(hr=3)
        hr0 = (dt_obj.hour // 3)*3
        day0 = dt_obj.day
        mt0 = dt_obj.month
        yr0 = dt_obj.year
        hr1 = (dt_next.hour // 3)*3
        day1 = dt_next.day
        mt1 = dt_obj.strftime("%Y-%m")
        ts0 = datetime(yr0, mt0, day0, hr0, 0, 0)
        w0 = 1 - ((ts - ts0).seconds)/60/60/3
        ts1 = f"{mt1}-{day1:02d}T{hr1:02d}:00:00"
        for (lat, lon) in timestamp_location[ts]:
            val0 = interpolate(lat_grid, lon_grid, lat, lon, res[day0][hr0], var_list)
            val1 = interpolate(lat_grid, lon_grid, lat, lon, res[day1][hr1], var_list)
            if ts == ts0 or mt0 != mt1:
                values = val0
            else:
                values = {}
                for var in var_list:
                    values[var] = w0*val0[var] + (1 - w0)*val1[var]
            for (kh, h) in enumerate(height_lev):
                df_row = {}
                df_row["time"] = ts
                df_row["lat"] = lat
                df_row["lon"] = lon
                df_row["height_level"] = h
                for v in var_list:
                    df_row[v] = values[v][kh]
                df = pd.concat([df, pd.DataFrame([df_row])], ignore_index=True, axis=0)

filename = "prufa.feather"
df.to_feather(filename)

frame = pd.read_feather(filename)
pd.set_option("display.max_columns", None)
pd.set_option("display.expand_frame_repr", None)
print(frame)
