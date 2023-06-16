"""
analyze_log.py

Read and parse a RAMD log file. Construct a series of milestoning models from 
the trajectory fragments for a set of bins of RAMD force vectors. The 
information from the milestoning models will be used in a sigma-RAMD model
that will allow one to expand the residence time in a Taylor series expansion
according to sigma-RAMD theory.
"""

import sys
import argparse

import numpy as np

import parser
import milestoning
import sigma_ramd

def analyze_log(ramd_log_file_list, num_milestones=10, num_xi_bins=5, 
                verbose=True):
    if verbose:
        print(f"Using {num_milestones} milestones.")
        print(f"Using {num_xi_bins} angle bins.")
    xi_bins_ranges = np.linspace(-1.0, 1.0, num_xi_bins+1)
    trajectory_list = []
    forceOutFreq = None
    forceRAMD = None
    timeStep = None
    for ramd_log_filename in ramd_log_file_list:
        trajectories, forceOutFreq_, forceRAMD_, timeStep_ \
            = parser.parse_ramd_log_file(ramd_log_filename)
        if forceOutFreq is None:
            forceOutFreq = forceOutFreq_
            forceRAMD = forceRAMD_
            timeStep = timeStep_
        else:
            assert forceOutFreq == forceOutFreq_, "RAMD logs contain differing forceOutFreq values."
            assert forceRAMD == forceRAMD_, "RAMD logs contain differing forceRAMD values."
            assert timeStep == timeStep_, "RAMD logs contain differing timeStep values."
            
        trajectory_list += trajectories
    
    if verbose:
        print("Number of trajectories extracted from log file(s):", 
              len(trajectory_list))
        print("forceOutFreq:", forceOutFreq)
        print("forceRAMD:", forceRAMD, "kcal/(mole * Angstrom)")
        print("timeStep:", timeStep, "ps")
    
    # Each trajectory represents a set of frames between force changes
    # Align the trajectories and convert to 1D, and xi values
    one_dim_trajs = parser.condense_trajectories(trajectories)
    
    #Construct a milestoning model based on trajectory fragments
    milestones, min_location, max_location, starting_cv_val \
        = milestoning.uniform_milestone_locations(one_dim_trajs, num_milestones)
        
    xi_bins = []
    for j in range(num_xi_bins):
        xi_bins.append([])
        
    for i, trajectory in enumerate(one_dim_trajs):
        traj_xi = trajectory[0][1]
        found_bin = False
        for j in range(num_xi_bins):
            if (traj_xi >= xi_bins_ranges[j]) \
                    and (traj_xi <= xi_bins_ranges[j+1]):
                xi_bins[j].append(trajectory)
                found_bin = True
                break
        
        if not found_bin:
            raise Exception(f"xi value {traj_xi} not placed in bin.")
    
    frame_time = timeStep * forceOutFreq
    xi_bin_time_profiles = np.zeros((num_xi_bins, num_milestones, num_milestones))
    for i in range(num_xi_bins):
        if verbose:
            print(f"num in bin {i}: {len(xi_bins[i])}")
        xi_bin_trajs = xi_bins[i]
        count_matrix, time_vector, rate_matrix, transition_matrix \
            = milestoning.make_milestoning_model(xi_bin_trajs, milestones, frame_time, num_milestones)
        
        # use the milestoning model to construct time profiles
        
        time_profile_matrix = milestoning.make_time_profiles(transition_matrix, time_vector, num_milestones)
        xi_bin_time_profiles[i,:,:] = time_profile_matrix[:,:]
        
    # Use sigma-RAMD to analyze
    beta=0.0 # TODO: fill out
    calc = sigma_ramd.functional_expansion_1d_ramd(
        xi_bin_time_profiles, force_constant=forceRAMD, beta=beta,
        min_cv_val=min_location, max_cv_val=max_location, 
        starting_cv_val=starting_cv_val)
    time_estimate = calc.make_second_order_time_estimate()
    print("time_estimate:", time_estimate)
        
if __name__ == "__main__":
    argparser = argparse.ArgumentParser(description=__doc__)
    argparser.add_argument(
        "ramdLogFiles", metavar="RAMDLOGFILES", type=str, nargs="+",
        help="The RAMD log files to open and parse.")
    argparser.add_argument(
        "-n", "--numMilestones", dest="numMilestones", default=10,
        help="The number of milestones to use in the milestoning "\
        "calculation.", type=int)
    argparser.add_argument(
        "-a", "--numAngleBins", dest="numAngleBins", default=5,
        help="The number of bins to divide the force vectors into.", type=int)
    
    args = argparser.parse_args()
    args = vars(args)
    ramdLogFiles = args["ramdLogFiles"]
    numMilestones = args["numMilestones"]
    numAngleBins = args["numAngleBins"]
    
    analyze_log(ramdLogFiles, numMilestones, numAngleBins)