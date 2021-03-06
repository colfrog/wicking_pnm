# -*- coding: utf-8 -*-
"""
Created on Mon Jul 13 09:18:30 2020

@author: firo
"""

import xarray as xr
import os
import numpy as np
import scipy as sp
from scipy.interpolate import interp1d

def weighted_ecdf(data, weight = False):
    """
    input: 1D arrays of data and corresponding weights
    sets weight to 1 if no weights given (= "normal" ecdf, but better than the statsmodels version)
    """
    if not np.any(weight):
        weight = np.ones(len(data))
    
    sorting = np.argsort(data)
    x = data[sorting]
    weight = weight[sorting]
    y = np.cumsum(weight)/weight.sum()
     
    # clean duplicates, statsmodels does not do this, but it is necessary for us
    
    x_clean = np.unique(x)
    y_clean = np.zeros(x_clean.shape)
    
    for i in range(len(x_clean)):
        y_clean[i] = y[x==x_clean[i]].max()
    return x_clean, y_clean


def generalized_gamma_cdf(x, xm, d, b, x0):
    y = sp.special.gammainc(d/b, ((x-x0)/xm)**b)/sp.special.gamma(d/b)
    return y

def generalized_gamma(x, xm, d, b, x0):
    y= b/xm**d/sp.special.gamma(d/b)*(x-x0)**(d-1)*np.exp(-((x-x0)/xm)**b)
    return y



sample = 'T3_025_3_III' #sample name, get e.g. by dyn_data.attrs['name']
path = r"W:\Robert_TOMCAT_3_netcdf4_archives\processed_1200_dry_seg_aniso_sep"

file = os.path.join(path, ''.join(['peak_diff_data_',sample,'.nc']))

diff_data = xr.load_dataset(file)


def waiting_time_from_ecdf(diff_data, n):
    """
    
    Parameters
    ----------
    diff_data : netcdf4
        dataset containing waiting times as peak differences.
    n : int
        number of nodes.

    Returns
    -------
    array of waiting times with lentgh n.

    """
    inter_diffs = diff_data['diffs_v2'][2:,:].data
    inter_weights = np.ones(inter_diffs.shape)

    intra_diffs = diff_data['diffs_v4'][2:,:].data
    intra_weights = np.ones(intra_diffs.shape) * diff_data['diffs_v4'][1,:].data
    intra_weights = 1- intra_weights
    
    diffs = np.concatenate([inter_diffs.flatten(), intra_diffs.flatten()], axis=0)
    weights = np.concatenate([inter_weights.flatten(), intra_weights.flatten()])

    mask = diffs>0

    x_t, y_t = weighted_ecdf(diffs[mask].flatten(), weights[mask].flatten())
    
    func = interp1d(y_t, x_t, fill_value = 'extrapolate')
    waiting_times = func(np.random.rand(n))
    
    return waiting_times


def waiting_time_from_gamma_fit(n, p=[56.97385398, 0.77929465,  0.84938767,  6.999599  ]):
    """
    

    Parameters
    ----------
    n : int
        number of nodes.
    p : array of float, optional
        4 parameters of the generalized gamma function. The default is [56.97385398, 0.77929465,  0.84938767,  6.999599  ].

    Returns
    -------
    array of waiting times with lentgh n.

    """
    
    x = np.arange(p[3]+0.01,1000,1)
    y = generalized_gamma_cdf(x, *p)
    ymax = y.max()
    y[y>=1] = 1
    
    func = interp1d(y, x, fill_value = 'extrapolate')
    
    rands = np.random.rand(n)
    rands[rands>ymax] = ymax
    
    waiting_times = func(rands)
    
    return waiting_times
    
    
# fun = generalized_gamma_cdf

# p, cov = sp.optimize.curve_fit(fun,x_t, y_t, maxfev=50000, p0=[56.97385398, 0.77929465,  0.84938767,  6.999599  ])#, p0 = [77.43496969,  0.5, 0])







