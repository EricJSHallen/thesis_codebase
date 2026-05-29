#code provided by Kenan Thalens

#import packages
import pandas as pd
import numpy as np
import re



def Data_extractor_sorted(filepath, chunksize=5000):

    # First read ONLY headers (very cheap)
    header_df = pd.read_csv(filepath, nrows=0)
    columns = header_df.columns

    # Pre-parse column metadata
    col_info = {}
    for col in columns:
        match = re.match(r"/(.+?)\s*\(([^=]+)=([^)]+)\)\s*(X|Y)", col)
        if not match:
            continue

        trace = match.group(1)
        param_name = match.group(2)
        param_value = float(match.group(3))
        axis = match.group(4)

        col_info[col] = (trace, param_value, axis)

    data_dict = {}

    # Now read in chunks
    for chunk in pd.read_csv(filepath, chunksize=chunksize):

        for col in chunk.columns:
            if col not in col_info:
                continue

            trace, param_value, axis = col_info[col]

            values = pd.to_numeric(chunk[col], errors='coerce').dropna().values

            if trace not in data_dict:
                data_dict[trace] = {}

            if param_value not in data_dict[trace]:
                data_dict[trace][param_value] = {}

            if axis not in data_dict[trace][param_value]:
                data_dict[trace][param_value][axis] = []

            data_dict[trace][param_value][axis].append(values)

    # Combine chunk pieces
    for trace in data_dict:
        for param in data_dict[trace]:
            for axis in data_dict[trace][param]:
                data_dict[trace][param][axis] = np.concatenate(
                    data_dict[trace][param][axis]
                )

    return data_dict



#gives all of the sorted data for one trace type :D. tr_name is the string name of the trace to grab. returns all x, all y, and the param to sort over
def sorted_data_extractor(df,tr_name):
    x_dat,y_dat,param_dat=[],[],[]

    for param in sorted(df[tr_name].keys()):
        x_dat.append(df[tr_name][param]["X"])
        y_dat.append(df[tr_name][param]["Y"])
        param_dat.append(param)

    return x_dat,y_dat,param_dat