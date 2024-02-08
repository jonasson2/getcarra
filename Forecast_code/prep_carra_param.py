import pandas as pd
from datetime import datetime, timedelta
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def to_yesterday(date_str: object) -> str:
    date_obj = datetime.strptime(str(date_str), DATE_FORMAT)
    yesterday_obj = date_obj - timedelta(days=1)

    yesterday_str = yesterday_obj.strftime(DATE_FORMAT)
    yesterday_str = yesterday_str.replace(' ', "T")
    return yesterday_str


def statloc():
    stations = pd.read_feather("full_station_data.feather")
    stations['latlon'] = stations.apply(lambda row: [row['breidd'], row['lengd']], axis=1)
    return dict(zip(stations['stod'], stations['latlon']))


def datestat():
    df = pd.read_feather("f_klst_ALL.feather")
    df["yesterday"] = df["timi"].apply(to_yesterday)
    df = df.groupby('yesterday')['stod'].apply(list).reset_index()
    return dict(zip(df['yesterday'], df['stod']))


def dateloc(ds, sl):
    dl = dict()

    for k, v in ds.items():
        json_key = k
        json_val = []
        for station in v:
            json_val.append(sl[station])

        dl[json_key] = json_val

    return dl


def make_param(ts_loc):
    d = {"param": {}, "timestamp_location": {}}

    d["param"]["product_type"] = "forecast"
    d["param"]["variable"] = ["Wind speed", "Wind direction", "Pressure", "Temperature"]
    d["param"]["height_levels"] = [15, 100, 250, 500],
    d["param"]["leadtime_hour"] = "24"
    d["param"]["feather_file"] = "all.feather"

    d["timestamp_location"] = ts_loc

    return d


date_location = dateloc(datestat(), statloc())
param = make_param(date_location)

import json

with open('parameters.json', 'w') as file:
    json.dump(param, file, indent=4)






