# def retrieve_specific_time(timestamp:str, hl: list[str], vbs: list[str],
#                            product_type: str):
#     grib_file = tempfile.mktemp() + ".grib"
#     print("grib_file:", grib_file)
#     dt_obj = datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S")
#     yr = dt_obj.year
#     mt = dt_obj.month
#     day = dt_obj.day
#     hr = dt_obj.hour
#     input_dict = {
#         'domain':       'west_domain',
#         'variable':     vbs,
#         'height_level': hl,
#         'product_type': product_type,
#         'time':         hr,
#         'year':         yr,
#         'month':        mt,
#         'day':          day,
#         'format':       'grib',
#         'grid':         [0.04180602, 0.01826484],
#         'area':         [66.6, -24.6, 63.3, -13.4]
#     }
#     if product_type == 'forecast':
#         input_dict.update({'leadtime_hour': '24'})
#     cdsapi.Client().retrieve('reanalysis-carra-height-levels', input_dict, grib_file)
#     running = True
#     while running:
#         time.sleep(1)
#         print("Running>>>>")
#         running = not os.path.exists(grib_file)
#     print("Out of while loop")
#     return grib_file