import os
import sys
import enum

from ControlObserveProbabCalculator import COPCalculator

import threading, sys
threading.stack_size(67108864)
sys.setrecursionlimit(2 ** 20)

class CELL(enum.Enum):
    TSMC = 'tsmc_cells/'
    SYNOPSIS = 'synopsis_cells/'

# Non Trojan = 0, Trojan = 1

def getFunctionalfeatures(input_file, trojan_nontrojan, file_name):
    r = COPCalculator(input_file)
    if(trojan_nontrojan=="0"):
        r.export(
            "../functional_results_non_trojan/" + file_name + "_control_observe.csv")
    elif(trojan_nontrojan=="1"):
        r.export(
            "../functional_results_trojan/" + file_name + "_control_observe.csv")

    r.export(
        "../functional_results_all/" + file_name + "_control_observe.csv")