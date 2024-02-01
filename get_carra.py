# -*- coding: utf-8 -*-
import numpy as np, pygrib, datetime, json, pandas as pd, time, cdsapi
from datetime import datetime, timedelta

GRIB_PATH = "download.grib"

def retrieve_specific_time(time:str, hl: list[str], vbs: list[str],
                           product_type: str):
  c = cdsapi.Client()
  year = time[0:4]
  dt_obj = datetime.strptime(time, "%Y-%m-%dT%H:%M:%S")
  yr = dt_obj.year
  mt = dt_obj.month
  day = dt_obj.day
  hr = dt_obj.hour
  input_dict = {
    'domain': 'west_domain',
    'variable': vbs,
    'height_level': hl,
    'product_type': product_type,
		'time': hr,
		'year': yr,
    'month': mt,
    'day': day,
    'format': 'grib',
    'grid': [0.04180602, 0.01826484],
    'area': [66.6, -24.6, 63.3, -13.4]
  }
  if product_type == 'forecast':
  	input_dict.update({'leadtime_hour': '24'})
  c.retrieve('reanalysis-carra-height-levels', input_dict, GRIB_PATH)
  return

def add3hrs(date):
  fmt = "%Y-%m-%dT%H:%M:%S"
  dt_obj = datetime.strptime(date, fmt) + timedelta(hours=3)
  return dt_obj.strftime(fmt)

def grib_latlon(grib_path):
    with pygrib.open(GRIB_PATH) as grb:
        message = grb[1]
        (lat, lon) = message.latlons()
    return (np.flipud(lat), lon - 360)

def read_grib(variables:list[str], height_levels:list[int]):
    (lat_grid, lon_grid) = grib_latlon(GRIB_PATH)
    (nlat, nlon) = lat_grid.shape
    nheight = len(height_levels)
    results = {}
    for var in variables:
        results[var] = np.zeros((nlat, nlon, nheight))
    with pygrib.open(GRIB_PATH) as grb:
        for message in grb:
            for var in variables:
                for k in range(nheight):
                    if message.name == var and message.level == height_levels[k]:
                        results[var][:,:,k] = np.flipud(message.values)
        print("Successful run of read_grib")
    return results, lat_grid, lon_grid

def interpolate(lat_grid, lon_grid, lat, lon, res, variable_list):
  distances = np.sqrt((lat_grid - lat) ** 2 +
                      np.cos(np.radians(lat_grid))*(lon_grid - lon) ** 2)
  four_closest_indices = np.argsort(distances, axis=None)[:4]
  four_closest_2D_indices = np.unravel_index(four_closest_indices, distances.shape)
  invs = np.zeros(4)
  nheights = res[variable_list[0]].shape[-1]

  values = {v: np.zeros((4, nheights)) for v in variable_list}

  for i in range(4):
    lat_idx = four_closest_2D_indices[0][i]
    lon_idx = four_closest_2D_indices[1][i]
    for vbl in variable_list:
      for hl in range(nheights):
        values[vbl][i, hl] = res[vbl][lat_idx, lon_idx, hl]

    invs[i] = 1 / np.maximum(0.001, distances[lat_idx, lon_idx])

  w = invs / sum(invs)
  result = {v: w @ values[v] for v in variable_list}
  return result

def get_carra_param(file_path):
    with open(file_path, 'r') as file:
        entry = json.load(file)
        carra_dict = entry["param"]
        date_location = entry["date_location"]
    return carra_dict, date_location

def process_dates(date_location):
  min = dt_obj.minute
  if hr % 3 != 0 or min != 0:
    hr0 = (hr//3)*3
    pass
  
  pass
  
  
file_path = 'carra_param.json'
carra_dict, date_location = get_carra_param(file_path)
var_list = carra_dict["variable"]
height_lev = carra_dict["height_levels"]
prod_type = carra_dict["product_type"]

# Create Pandas dataframe
df = pd.DataFrame()

for (date,loc) in date_location.items():
  retrieve_specific_time(date, height_lev, var_list, prod_type)
  time.sleep(1)
  res, lat_grid, lon_grid = read_grib(var_list, height_lev)
  date_p3 = add3hrs(date)
  retrieve_specific_time(date_p3, height_lev, var_list, prod_type)
  res, lat_grid, lon_grid = read_grib(var_list, height_lev)  
  for (lat, lon) in loc:
    values = interpolate(lat_grid, lon_grid, lat, lon, res, var_list)
    for (kh, h) in enumerate(height_lev):
      df_row = {}
      df_row["time"] = date
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
