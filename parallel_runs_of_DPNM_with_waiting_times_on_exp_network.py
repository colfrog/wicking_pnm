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
import pickle

temp_folder = r"Z:\users\firo\joblib_tmp"
# temp_folder = None

# TODO: build random sample choice

ecdf = robpylib.CommonFunctions.Tools.weighted_ecdf

sourceFolder = r"A:\Robert_TOMCAT_3_netcdf4_archives\processed_1200_dry_seg_aniso_sep"
sourceFolder = r"A:\Robert_TOMCAT_3_combined_archives"
dumpfilename = r"R:\Scratch\305\_Robert\simulation_dump\results_random_wait_v3_R4_no_extend_v2_512runs_repeat.p"
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
    intra_weights = 1 - intra_weights
    
    diffs = np.concatenate([inter_diffs.flatten(), intra_diffs.flatten()], axis=0)
    weights = np.concatenate([inter_weights.flatten(), intra_weights.flatten()])

    mask = diffs>0

    x_t, y_t = weighted_ecdf(diffs[mask].flatten(), weights[mask].flatten())
    
    # func = interp1d(y_t, x_t, fill_value = 'extrapolate')
    func = interp1d(y_t, x_t, fill_value=(0,x_t.max()),bounds_error=False)
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
    
    # peak_num[:] = 1
    
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

def DT(beta):
    DT = 4/beta
    return DT

def calibrate_waiting_time(waiting_times, data,seed=1000, cut_off = 10000):
    dt = DT(data['sig_fit_data'].sel(sig_fit_var = 'beta [1_s]').data)
    dt = dt[dt<cut_off]
    x,y = robpylib.CommonFunctions.Tools.weighted_ecdf(dt)
    func = interp1d(y, x, fill_value = 'extrapolate')
    
    prng = np.random.RandomState(seed)
    correction = func(prng.rand(waiting_times.size))
    waiting_times = waiting_times - correction
    waiting_times[waiting_times<0] = 0
    
    return waiting_times

def calibrate_waiting_time_theoretic(waiting_times, r_i, lengths, R0, cos = np.cos(48/180*np.pi), gamma = 72E-3, mu = 1E-3):
    # pc = RQ = R dV/dt = R pi r**2*l/dt
    # pc = 2*gamma*cos/r_i
    # dt = 2*R0*np.pi*r_i**2*lengths/pc + 2*8*mu*lengths**2/np.pi/r_i**2/pc
    #  get the proper formula from paper 1
    dt = lengths*R0*np.pi*r_i**3/2/gamma/cos*3
    waiting_times = waiting_times-dt
    waiting_times[waiting_times<0] = 0
    return waiting_times

def calibrate_waiting_time_with_previous_run(waiting_times, old_results, i):
    result = old_results[i]
    dt = result[4] - result[3]
    waiting_times = waiting_times - dt
    waiting_times[waiting_times<0] = 0
    return waiting_times
    

def core_simulation(r_i, lengths, adj_matrix, inlets, timesteps,  pnm_params, peak_fun, i, pnm, diff_data, R0=1, old_results=None):
    size = len(r_i)

    if len(diff_data)==2:
        waiting_times = generate_combined_waiting_times(diff_data, size, peak_fun, i)
    else:
        prng = np.random.RandomState(i)
        waiting_times = from_ecdf(diff_data, size, seed=i+1)
        # waiting_times = extend_waiting_time(waiting_times, from_ecdf, peak_fun(prng.rand(size)), diff_data, i)
        # waiting_times = calibrate_waiting_time(waiting_times, pnm.data, seed = i+1000)
        # waiting_times = calibrate_waiting_time_theoretic(waiting_times, r_i, lengths, R0)
        # if old_results is not None:
            # waiting_times = calibrate_waiting_time_with_previous_run(waiting_times, old_results, i-5)
    #  pass the pnm with the experimental activation time in the case of running the validation samples
    # time, V, V0, activation_time, filling_time = simulation(r_i, lengths, waiting_times, adj_matrix, inlets, timesteps, node_dict = pnm.label_dict, pnm = pnm, R0=R0,sample=pnm.sample)
    time, V, V0, activation_time, filling_time = simulation(r_i, lengths, waiting_times, adj_matrix, inlets, timesteps, node_dict = pnm.label_dict, R0=R0,sample=pnm.sample)
    V_fun = interp1d(time, V, fill_value = 'extrapolate')
    
    new_time = np.arange(3000)
    new_V = V_fun(new_time)
    new_V[new_V>V0] = V0
   
    return new_time, new_V, V0, activation_time, filling_time, waiting_times


def core_function(samples, timesteps, i, peak_fun=peak_fun, inlet_count = 2, diff_data=None, old_results=None):
    prng3 = np.random.RandomState(i)
    sample = prng3.choice(samples)
    pnm_params = {
           'data_path': r"A:\Robert_TOMCAT_3_combined_archives",
          # 'data_path': r"A:\Robert_TOMCAT_3_netcdf4_archives\processed_1200_dry_seg_aniso_sep",
            'sample': sample,
            # 'graph': nx.watts_strogatz_graph(400,8,0.1, seed=i+1),
        # 'sample': 'T3_100_7_III',
        # 'sample': 'T3_025_3_III',
        # 'sample': 'T3_300_8_III',
          'inlet_count': inlet_count,
           # 'randomize_pore_data': True,
          'seed': (i+3)**3
    }

    pnm = PNM(**pnm_params)
    graph = pnm.graph.copy()
    R0 = 4E17#4E15
    # print('inlet R '+str(R0))
    
    # ####fixed inlets for validation samples##############
    # inlet_nodes = [162,171,207]
    # if pnm.sample == 'T3_100_7_III': inlet_nodes = [86, 89, 90, 52]
    # if pnm.sample == 'T3_300_8_III': inlet_nodes = [   13,    63,   149]
    # inlets = []
    # found_inlets = []
    # for inlet in inlet_nodes:
    #     inlet = int(inlet)
    #     if inlet in pnm.label_dict:
    #         inlets.append(pnm.label_dict[inlet])
    #         found_inlets.append(inlet)
    #     else:
    #         print('Failed to find node named', inlet)

    # print('Got inlet labels:', inlets)
   
    # pnm.inlets = inlets
    # pnm.build_inlets()
    ############# 
    
    if diff_data is None:    
        diff_data = pnm.pore_diff_data
    
    sourcesraw = np.unique(pnm.data['label_matrix'][:,:,0])[1:]
    targetsraw = np.unique(pnm.data['label_matrix'][:,:,-1])[1:]

    sources = []
    targets = []
    for k in sourcesraw:
        if k in graph.nodes():
            sources.append(k)
    for k in targetsraw:
        if k in graph.nodes():
            targets.append(k)
    sources2 = sources.copy()
    inlets = pnm.inlets.copy()  
    # prng7 = np.random.RandomState(i+3)
    # # inlets = prng7.choice(sources, 2)
    # sources = prng7.choice(sources, 4)
    # inlets = sources
    
    found_inlets = []
    for inlet in inlets:
        
        found_inlets.append(pnm.nodes[inlet])


    v_inlets = -1*(np.arange(len(inlets))+1)
    for k in range(len(inlets)):
        graph.add_edge(found_inlets[k], v_inlets[k])
    inlets = v_inlets
    sources = inlets
            
    inlet_radii = np.zeros(len(inlets))
    inlet_heights = np.zeros(len(inlets))
    
    r_i = pnm.radi.copy()
    lengths = pnm.volumes.copy()/np.pi/r_i**2
    
    
    r_i = np.concatenate([r_i, inlet_radii])
    lengths = np.concatenate([lengths, inlet_heights])
    
    adj_matrix = nx.to_numpy_array(graph)
    result_sim = core_simulation(r_i, lengths, adj_matrix, inlets, timesteps,  pnm_params, peak_fun, i, pnm, diff_data, R0=R0, old_results=old_results)
    centrality = np.array(list(nx.betweenness_centrality(graph).values()))
    centrality3 = np.array(list(nx.betweenness_centrality_source(graph, sources=sources2).values()))
    centrality2 = np.array(list(nx.betweenness_centrality_subset(graph, sources, targets, normalized=True).values()))
    centrality4 = np.array(list(nx.betweenness_centrality_subset(graph, sources2, targets, normalized=True).values()))
    centrality5 = np.array(list(nx.betweenness_centrality_source(graph, sources=sources).values()))
    result_sim = result_sim + (sample,)
    result_sim = result_sim + (centrality5,)
    result_sim = result_sim + (centrality4,)
    result_sim = result_sim + (centrality3,)
    result_sim = result_sim + (centrality2,)
    result_sim = result_sim + (pnm.data.attrs['tension'], centrality)
    
    # V0 = result_sim[2]
    time = result_sim[0]
    V = result_sim[1]
    ref = np.argmax(V)
    mean_flux = V[ref]/time[ref]
    result_sim = result_sim + (mean_flux,)
    result_sim = result_sim + (graph, )
    
    return result_sim

print('Warning: diff data path is hard-coded!')
# print('Warning: Inlets and inlet resistance hard-coded')
print('Warning: Inlet resistance hard-coded')
# print('Warning peak number hard-coded to 1')
njobs = 32
timesteps = 5000000#0#0#0

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

samples_3b = ['T3_025_10_IV',
  'T3_025_3_IV',
  'T3_025_6_IV',
  'T3_025_9_IV',
  'T3_100_07_IV',
  'T3_100_08_IV',
  'T3_100_10_IV',
  # 'T3_300_13_IV', some strange errors, ignore
  'T3_300_15_IV',
  'T3_300_9_IV']

not_extreme_samples = paper_samples + samples_3b
not_extreme_samples.remove('T3_100_1') #processing artefacts from moving sample
not_extreme_samples.remove('T3_025_4') #very little uptake --> v3
not_extreme_samples.remove('T3_025_9_III') #very little uptake --> v2,v3
# not_extreme_samples.remove('T3_300_4') #very little uptake
# not_extreme_samples.remove('T3_100_7') #very little uptake

old_results = None
if os.path.exists(dumpfilename):
    old_results = pickle.load(open(dumpfilename,'rb'))
    dumpfilename = r"R:\Scratch\305\_Robert\simulation_dump\results_random_wait_v3_R4_no_extend_v2.p"
# temp_folder = None
results = Parallel(n_jobs=njobs, temp_folder=temp_folder)(delayed(core_function)(not_extreme_samples, timesteps, i+5, old_results=old_results) for i in range(512))  

dumpfile = open(dumpfilename, 'wb')
pickle.dump(results, dumpfile)
dumpfile.close()

# act_times = np.zeros((len(results),len(results[0][3])))
# finish_times = np.zeros((len(results),len(results[0][3])))

# results_np = np.zeros((len(results),3000))
# for i in range(len(results)):
#     results_np[i,:] = results[i][1]
#     # act_times[i,:]= results[i][3]
#     # finish_times[i,:]= results[i][4]
# np.save(r"H:\11_Essential_Data\06_PNM\PNM_results_random_samples_R_1_v3", results_np)