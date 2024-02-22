# -*- coding: utf-8 -*-
import numpy as np, pygrib, datetime, json, pandas as pd, time, cdsapi
import tempfile, os, sys
from datetime import datetime, timedelta

from tqdm import tqdm

def retrieve_month(vbs: list[str], height_levels: list[int], product_type: str,
                   yrmonth: str, days: list[int], hr_list: list[int]) -> str:
    """
    Downloads data from CARRA into the file grib_file. Returns a string with the
    file-name to pass down the process.

    :param vbs: A list of variables, e.g. ["Pressure", "Temperature"]
    :param height_levels: A list of height levels to get analysis/forecast, e.g. [15, 100]
    :param product_type: 'forecast'/'analysis'
    :param yrmonth: String of form "yyyy-mm" indicating month to retrieve data for
    :param days: List of days to get forecast/analysis for, e.g. [1, 3, 6]
    :param hr_list: List of hours (modulo 3) in which we fetch analysis/forecast for, e.g. [9, 12, 15]
    :return: name of .grib file within which data is stored
    """
    grib_file = tempfile.mktemp() + ".grib"
    dt_obj = datetime.strptime(yrmonth, "%Y-%m")
    yr = dt_obj.year
    mt = dt_obj.month
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
    print(input_dict)
    cdsapi.Client().retrieve('reanalysis-carra-height-levels', input_dict, grib_file)
    running = True
    while running:
        time.sleep(1)
        print("Running>>>>")
        running = not os.path.exists(grib_file)
    print("Out of while loop")
    return grib_file


def date_format() -> str:
    # Returns string with format for date strings.
    # Arguable: More appropriate as a constant
    return "%Y-%m-%dT%H:%M:%S"


def add3hrs(date: str):
    """
    :param date: date-like string of format "%Y-%m-%dT%H:%M:%S",
    :return: date-like string of same format, 3 hours later
    """
    fmt = date_format()
    dt_obj = datetime.strptime(date, fmt) + timedelta(hours=3)
    return dt_obj.strftime(fmt)


def grib_latlon(grib_file: str) -> (np.ndarray, np.ndarray):
    """
    :param grib_file: file name of .grib file containing forecasts/analysis
    :return: Arrays of latitudes and longitudes from .grib file
    """
    with pygrib.open(grib_file) as grb:
        message = grb[1]
        (lat, lon) = message.latlons()
    return np.flipud(lat), lon - 360


def read_grib(grib_file, vbs: list[str], height_levels: list[int],
              days: list[int], hr_list: list[int]) -> (dict[any], np.ndarray, np.ndarray):
    """
    Goes through a .grib file and picks out data relevant to parameters.
    :param grib_file: Name of .grib
    :param vbs: List of variables, e.g. ["Temperature", "Pressure"]
    :param height_levels: List of height levels, e.g. [15, 100]
    :param days: List of days to pick data from, e.g. [1, 5, 7]
    :param hr_list: List of hours (modulo 3) to retrieve forecast/analysis from, e.g. [3,6,9]
    :return: (a dictionary with keys dictionary[day][hour][variable] and values are arrays of 3 dimensions
             one of whom is height level, the latter two aligning with arrays of latitudes and containing
             forecast or analysis of variable in kay at day and hour,
             latitude array,
             longitude array)
    """
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


def interpolate(lat_grid: np.ndarray, lon_grid: np.ndarray, lat: float, lon: float,
                res: dict[any], variable_list: list[str]) -> dict[np.ndarray]:
    """

    :param lat_grid: array of latitudes
    :param lon_grid: array of longitudes
    :param lat: latitude of position we wish to interpolate on
    :param lon: longitude of                -||-
    :param res: Results from grib file, refer to function read_grib
    :param variable_list: A list of variables to interpolate, e.g. ["Temperature", ...]
    :return: a dictionary, key: variable interpolated, value: array of interpolations
             w/ indices corresponding to height levels
    """

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


def get_carra_param(file_path: str) -> (dict[str, any], dict[str, any]):
    """
    :param file_path: file-path to .json file containing parameters for the process
    :return: A dictionary of said parameters and values, And a dictionary wherein keys
             are strings of format date_format() and values are lists of positions for
             which we wish to interpolate analysis/forecasts on
    """
    with open(file_path, 'r') as file:
        entry = json.load(file)
        if type(entry) == str:
            entry = json.loads(entry)  # Magic trick from BGS
        carra_dict = entry["param"]
        timestamp_location = entry["timestamp_location"]
    return carra_dict, timestamp_location


def construct_year_month_set(timestamp_location: dict[str, any]) -> set[str]:
    """
    :param timestamp_location: A dictionary of which we use the keys: date-like strings of format date_format()
    :return: A set of unique timestamps "yyyy-mm" for which carra data is retrievable
    """
    # Create set of year-month for which to retrieve data
    yr_month = set()
    fmt = date_format()
    for date in timestamp_location.keys():
        dt_obj = datetime.strptime(date, fmt)
        yr_month.add(date[:7])
        if dt_obj.hour >= 21:
            next_dt = dt_obj + timedelta(days=1)
            dt_obj = datetime.strptime(date, fmt) + timedelta(hours=3)
            next_day = dt_obj.strftime(fmt)
            yr_month.add(next_day[:7])
    return yr_month

def select_timestamps_in_yr_month(timestamp_location, yr_month):
    selected = {ts: val for (ts,val) in timestamp_location.items() if ts[:7]==yr_month}
    return selected

def get_month(df: pd.DataFrame, carra_dict: dict[str, any],
              timestamp_location: dict[str, any], yr_month: str):
    """
    Retrieves data for a specific month and appends it to a dataframe for further utilization
    :param df: a pandas dataframe containing data up to this point
    :param carra_dict: A dictionary of parameters for carra retrieval
    :param timestamp_location: A dictionary w/ keys date_format() and values are lists of locations
    :param yr_month: the month for which we want to retrieve the data
    :return: df with added data for the month in questions
    """
    # Gets one month from Carra and adds the retrieved info to the data frame df
    fmt = date_format()
    var_list = carra_dict["variable"]
    height_lev = carra_dict["height_levels"]
    product_type = carra_dict["product_type"]
    hr_list = [12] if product_type == "forecast" else [0, 3, 6, 9, 12, 15, 18, 21]
    days = [int(d[8:10]) for d in timestamp_location.keys() if d[:7] == yr_month]
    grib_file = retrieve_month(var_list, height_lev, product_type, yr_month, days, hr_list)
    print("About to read grib")
    res, lat_grid, lon_grid = read_grib(grib_file, var_list, height_lev, days, hr_list)
    print("Finished reading grib")
    timestamps_of_month = select_timestamps_in_yr_month(timestamp_location, yr_month)
    for timestamp in timestamps_of_month.keys():
        dt_obj = datetime.strptime(timestamp, fmt)
        dt_next = dt_obj + timedelta(hours=3)
        hr0 = (dt_obj.hour // 3)*3
        min0 = (dt_obj.minute)
        day0 = dt_obj.day
        mt0 = dt_obj.month
        mt1 = dt_next.month
        yr0 = dt_obj.year
        whole_3_hours = hr0 % 3 == 0 and min0 == 0 or mt0 != mt1
        if not whole_3_hours:
            hr1 = (dt_next.hour // 3)*3
            day1 = dt_next.day
        ts0 = datetime(yr0, mt0, day0, hr0, 0, 0)
        wgt = 1 - ((dt_obj - ts0).seconds)/60/60/3
        for (lat, lon) in timestamp_location[timestamp]:
            val0 = interpolate(lat_grid, lon_grid, lat, lon, res[day0][hr0], var_list)
            if whole_3_hours:
                values = val0
            else:
                print(res.keys(), day0, hr0, day1, hr1, timestamp)
                val1 = interpolate(lat_grid, lon_grid, lat, lon, res[day1][hr1], var_list)
                values = {}
                for var in var_list:
                    values[var] = wgt*val0[var] + (1 - wgt)*val1[var]
            for (kh, h) in enumerate(height_lev):
                df_row = {}
                df_row["yr_month"] = timestamp[:7]
                df_row["time"] = timestamp
                df_row["lat"] = lat
                df_row["lon"] = lon
                df_row["height_level"] = h
                for v in var_list:
                    df_row[v] = values[v][kh]
                df = pd.concat([df, pd.DataFrame([df_row])], ignore_index=True, axis=0)

    os.remove(grib_file)
    return df

assert len(sys.argv) >= 2, "Json file must be specified on command line"
json_file = sys.argv[1]
carra_dict, timestamp_location = get_carra_param(json_file)
#if len(sys.argv) > 2:
#    df = pd.read_feather(sys.argv[2])
#else:
df = pd.DataFrame()
yr_month_set = construct_year_month_set(timestamp_location)
#df['yr_month'] = df.time.str[:7]
for yr_month in tqdm(yr_month_set, total = len(yr_month_set)):
    if len(df) > 0 and any(df.yr_month == yr_month):
        continue
    df = get_month(df, carra_dict, timestamp_location, yr_month)
    #df.to_feather(sys.argv[2])

filename = carra_dict["feather_file"]
df.to_feather(filename)
frame = pd.read_feather(filename)
pd.set_option("display.max_columns", None)
pd.set_option("display.expand_frame_repr", None)
print(frame)
