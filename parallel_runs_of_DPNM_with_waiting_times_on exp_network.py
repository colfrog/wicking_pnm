# -*- coding: utf-8 -*-
"""
Created on Tue Aug 11 14:52:30 2020

@author: firo


parallel run of experimental network with gamma fit waiting time distribution
"""
import sys

homeCodePath=r"H:\10_Python\005_Scripts_from_others\Laurent\wicking_pnm"
if homeCodePath not in sys.path:
	sys.path.append(homeCodePath)


import scipy as sp
import numpy as np
from scipy.interpolate import interp1d
from joblib import Parallel, delayed
import networkx as nx
from wickingpnm.model import PNM
from wickingpnm.old_school_DPNM_v5 import simulation
import xarray as xr
import os
import robpylib
virtual_inlets = True
temp_folder = r"Z:\users\firo\joblib_tmp"

# TODO: build random sample choice

ecdf = robpylib.CommonFunctions.Tools.weighted_ecdf

sourceFolder = r"A:\Robert_TOMCAT_3_netcdf4_archives\processed_1200_dry_seg_aniso_sep"

#  extract distribution of peaks per pore
peak_num = np.array([])
comb_diff_data = np.array([])
comb_weight_data = np.array([])
samples = []
for sample in os.listdir(sourceFolder):
    if sample[:3] == 'dyn':
        data = xr.load_dataset(os.path.join(sourceFolder, sample))
        num_sample = data['dynamics'].sel(parameter = 'num filling peaks').data
        peak_num = np.concatenate([peak_num, num_sample])
        samples.append(data.attrs['name'])
    if sample[:14] == 'peak_diff_data':
        diff_data = xr.load_dataset(os.path.join(sourceFolder, sample))
        inter_diffs = diff_data['diffs_v2'][2:,:].data
        inter_weights = np.ones(inter_diffs.shape)
    
        intra_diffs = diff_data['diffs_v4'][2:,:].data
        intra_weights = np.ones(intra_diffs.shape) * diff_data['diffs_v4'][1,:].data
        intra_weights = 1- intra_weights
        
        diffs = np.concatenate([inter_diffs.flatten(), intra_diffs.flatten()], axis=0)
        weights = np.concatenate([inter_weights.flatten(), intra_weights.flatten()])
        
        comb_diff_data = np.concatenate([comb_diff_data, diffs], axis=0)
        comb_weight_data = np.concatenate([comb_weight_data, diffs], axis=0)
        
        
peak_num = peak_num[peak_num>1]

x, y = ecdf(peak_num)

peak_fun = interp1d(y, x, fill_value = 'extrapolate')



def generalized_gamma_cdf(x, xm, d, b, x0):
    y = sp.special.gammainc(d/b, ((x-x0)/xm)**b)/sp.special.gamma(d/b)
    return y

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


def from_ecdf(diff_data, n, seed=1):
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
    prng2 = np.random.RandomState(seed)
    waiting_times = func(prng2.rand(n))
    
    return waiting_times

def from_gamma_fit(n, p=[56.97385398, 0.77929465,  0.84938767,  6.999599]):
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

def extend_waiting_time(waiting_times, waiting_time_gen, peak_num, diff_data, seed):
    size = len(waiting_times)
    for i in range(size):
        j = 1
        while j < peak_num[i]:
            j = j + 1
            waiting_times[i] = waiting_times[i] + waiting_time_gen(diff_data, 1, seed=j*i**2)[0]
    return waiting_times

def generate_combined_waiting_times(diff_data, size,peak_fun, i):
    prng = np.random.RandomState(i)
    peak_num = peak_fun(prng.rand(size))
    
    diffs = diff_data[0]
    weights = diff_data[1]
    mask = diffs>0
    x_t, y_t = weighted_ecdf(diffs[mask].flatten(), weights[mask].flatten())
    
    seed = i+1
    func = interp1d(y_t, x_t, fill_value = 'extrapolate')
    prng2 = np.random.RandomState(seed**2+17)
    waiting_times = func(prng2.rand(size))
    
    for i in range(size):
        j = 1
        while j < peak_num[i]:
            j = j + 1
            prng3 = np.random.RandomState(i*j*(i+j)+7)
            waiting_times[i] = waiting_times[i] + func(prng3.rand())
    return waiting_times

def core_simulation(r_i, lengths, adj_matrix, inlets, timesteps,  pnm_params, peak_fun, i, pnm, diff_data, R0=0):
    size = len(r_i)

    if len(diff_data)==2:
        waiting_times = generate_combined_waiting_times(diff_data, size, peak_fun, i)
    else:
        prng = np.random.RandomState(i)
        waiting_times = from_ecdf(diff_data, size, seed=i+1)
        waiting_times = extend_waiting_time(waiting_times, from_ecdf, peak_fun(prng.rand(size)), diff_data, i)
    
    #  pass the pnm with the experimental activation time in the case of running the validation samples
    # time, V, V0, activation_time, filling_time = simulation(r_i, lengths, waiting_times, adj_matrix, inlets, timesteps, node_dict = pnm.label_dict, pnm = pnm, R0=R0,sample=pnm.sample)
    time, V, V0, activation_time, filling_time = simulation(r_i, lengths, waiting_times, adj_matrix, inlets, timesteps, node_dict = pnm.label_dict, R0=R0,sample=pnm.sample)
    V_fun = interp1d(time, V, fill_value = 'extrapolate')
    
    new_time = np.arange(3000)
    new_V = V_fun(new_time)
    new_V[new_V>V0] = V0
   
    return new_time, new_V, V0, activation_time, filling_time, waiting_times


def core_function(samples, timesteps, i, peak_fun=peak_fun, inlet_count = 2, diff_data=None):
    prng3 = np.random.RandomState(i)
    sample = prng3.choice(samples)
    pnm_params = {
           'data_path': r"A:\Robert_TOMCAT_3_netcdf4_archives\for_PNM",
          # 'data_path': r"A:\Robert_TOMCAT_3_netcdf4_archives\processed_1200_dry_seg_aniso_sep",
            'sample': sample,
        # 'sample': 'T3_100_7_III',
        # 'sample': 'T3_025_3_III',
        # 'sample': 'T3_300_8_III',
          'inlet_count': inlet_count,
        'seed': (i+3)**3
    }

    pnm = PNM(**pnm_params)
    graph = pnm.graph.copy()
    R0 = 1E17#4E15
    
    
    # ####fixed inlets for validation samples##############
   #  inlet_nodes = [162,171,207]
   #  if pnm.sample == 'T3_100_7_III': inlet_nodes = [86, 89, 90, 52]
   #  if pnm.sample == 'T3_300_8_III': inlet_nodes = [   13,    63,   149]
   #  inlets = []
   #  found_inlets = []
   #  for inlet in inlet_nodes:
   #      inlet = int(inlet)
   #      if inlet in pnm.label_dict:
   #          inlets.append(pnm.label_dict[inlet])
   #          found_inlets.append(inlet)
   #      else:
   #          print('Failed to find node named', inlet)

   #  print('Got inlet labels:', inlets)
    
   #  pnm.inlets = inlets
   #  pnm.build_inlets()
   # ############# 
    
    if diff_data is None:    
        diff_data = pnm.pore_diff_data
        
        
    inlets = pnm.inlets.copy()  
    found_inlets = []
    for inlet in inlets:
        found_inlets.append(pnm.nodes[inlet])
    
    if virtual_inlets:
        v_inlets = -1*(np.arange(len(inlets))+1)
        for i in range(len(inlets)):
            graph.add_edge(found_inlets[i], v_inlets[i])
        inlets = v_inlets
            
    inlet_radii = np.zeros(len(inlets))
    inlet_heights = np.zeros(len(inlets))
    
    r_i = pnm.radi.copy()
    lengths = pnm.volumes.copy()/np.pi/r_i**2
    
    if virtual_inlets:
        r_i = np.concatenate([r_i, inlet_radii])
        lengths = np.concatenate([lengths, inlet_heights])
    adj_matrix = nx.to_numpy_array(graph)
    result_sim = core_simulation(r_i, lengths, adj_matrix, inlets, timesteps,  pnm_params, peak_fun, i, pnm, diff_data, R0=R0)
    
    return result_sim

print('Warning: diff data path is hard-coded!')
# print('Warning: Inlets and inlet resistance hard-coded')
print('Warning: Inlet resistance hard-coded')
njobs = 32
timesteps = 1000000#0#0#0

# multi-sample run
paper_samples = [
    'T3_025_3_III',
    'T3_025_4',
    'T3_025_7_II',
    'T3_025_9_III',
    'T3_100_1',
    'T3_100_10',
    'T3_100_10_III',
    'T3_100_4_III',
    'T3_100_6',
    'T3_100_7',
    'T3_100_7_III',
    'T3_300_3',
    'T3_300_4',
    'T3_300_8_III',
    'T3_300_9_III'
]
# not_extreme_samples = ['T3_100_7_III', 'T3_300_5', 'T3_100_1',  'T3_300_5_III', 'T3_100_6', 'T3_300_8_III', 'T3_025_3_III']
not_extreme_samples = paper_samples
# not_extreme_samples.remove('T3_300_8_III')
not_extreme_samples.remove('T3_025_7_II')
not_extreme_samples.remove('T3_100_1')
results = Parallel(n_jobs=njobs, temp_folder=temp_folder)(delayed(core_function)(not_extreme_samples, timesteps, i) for i in range(128))  
# results = Parallel(n_jobs=njobs)(delayed(core_function)(not_extreme_samples, timesteps, i, diff_data=[comb_diff_data, comb_weight_data]) for i in range(16))  
 

# act_times = np.zeros((len(results),len(results[0][3])))
# finish_times = np.zeros((len(results),len(results[0][3])))

results_np = np.zeros((len(results),3000))
for i in range(len(results)):
    results_np[i,:] = results[i][1]
    # act_times[i,:]= results[i][3]
    # finish_times[i,:]= results[i][4]
np.save(r"H:\11_Essential_Data\06_PNM\PNM_results_random_samples_R_1E17_2_inlet_no_extreme_samples", results_np)