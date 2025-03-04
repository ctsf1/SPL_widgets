import pandas as pd
import numpy as np
from subprocess import run
from datetime import datetime

from spl_widgets.misc_util import *

def tune_col(
        freq_col: list[float],
        amp_col: list[float],
        interval: int,
        tune_freqs: bool,
        scale_notes: list[float]
    ) -> list[float]:

    freq_col = np.where(amp_col>0, freq_col, 0)
    new_col =[]
    
    for slice_start in range(0, len(freq_col), interval):

        slice_end = slice_start + interval
        freq_slice = freq_col[slice_start:slice_end]

        nz_amps = np.count_nonzero(amp_col[slice_start:slice_end])
        if nz_amps == 0:
            new_col.extend(freq_slice)
            continue

        range_freq = sum(freq_slice) / nz_amps

        if tune_freqs is True and range_freq != 0:
            range_freq = get_closest(scale_notes, range_freq)

        new_col+=[range_freq]*len(freq_slice)

    for i, cell in enumerate(new_col):
        if cell == 0:
            if max(amp_col[max(0,i-1):i+2]) == 0:
                continue

            new_col[i] = max(new_col[max(0,i-1):i+2])

    return new_col

def tune_cols(
        filepath: str,
        interval: int,
        scale: list[int],
        tune_freqs: bool,
        fmts_to_tune: list[int]|None
    ) -> str:

    df = read_df(filepath)

    formants = len(df.columns)//2
    out_df = pd.DataFrame(df.iloc[:,0])

    if fmts_to_tune == None:
        fmts_to_tune = [*range(1,formants+1)]

    fmts_to_tune = [*filter(lambda n: n<=formants, fmts_to_tune)]

    scale_notes = construct_note_freqs(scale)
    for fmt in range(1,formants+1):

        amp_col = df.iloc[:,2*fmt]
        freq_col = df.iloc[:,2*fmt-1]
 
        if fmt in fmts_to_tune:
            freq_col = tune_col(freq_col, amp_col, interval, tune_freqs, scale_notes)

        out_df[f'F{fmt}']=freq_col
        out_df[f'A{fmt}']=amp_col

    # Mel Scale Differencing (Summer 2024)
    difference_df = pd.DataFrame({
        "nat_mel": map(freq_to_mel, df[3]),
        "tuned_mel": map(freq_to_mel, out_df["F2"]),
        "amp": df[4]
    })
    difference_df = difference_df[difference_df["amp"] != 0]
    data = ( difference_df["nat_mel"] - difference_df["tuned_mel"] ).abs()

    out_df.columns = [formants]+['']*(2*formants)

    # Makes, populates and creates a folder for tuned file
    now_str = f'{datetime.now():%Y-%m-%d_%H.%M.%S.%f}'
    filename = filepath[filepath.rfind('/'):-4]

    out_dir_filepath = filepath[:filepath.rfind('/')]+f'/tuning_done_{now_str}'
    run(['mkdir', out_dir_filepath], capture_output=True)
    
    # convert df to tab-separated format and write to .swx file
    tsv = df_to_tsv(out_df)
    with open(f"{out_dir_filepath}/{filename}_tuned.swx", "w") as writer:
        writer.write(tsv)

    # Creates params.txt file
    notes_tuning = encode_num_list_as_hex(scale).zfill(3)
    fmts_tuned = encode_num_list_as_hex(fmts_to_tune).zfill(2)

    tuning_key = f"{ int(tune_freqs) }{ str(interval).zfill(2) }-{notes_tuning}-{fmts_tuned}"

    args=[
        'Tuning Parameters:',
        '*'*20,
        f'Interval: {10*interval}ms (setting: {interval})',
        f'Scale: {num_scale_to_strs(scale) if tune_freqs else "NOT TUNED"}',
        f"Tune Frequencies: {tune_freqs}",
        f"Formants Tuned: {fmts_to_tune}",
        f'Tuning Key: {tuning_key}',

        '\nMel Difference Stats:',
        '*'*20,
        f'Mean: {data.mean()}',
        f'Median: {data.median()}',
        f'Standard deviation: {data.std()}'
        ]
    
    with open(f'{out_dir_filepath}/params.txt','w') as writer:
        writer.write('\n'.join(args))
    
    return out_dir_filepath