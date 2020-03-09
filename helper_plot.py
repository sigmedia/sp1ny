#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AUTHOR

    Sébastien Le Maguer <lemagues@tcd.ie>

DESCRIPTION

LICENSE
    This script is in the public domain, free from copyrights or restrictions.
    Created:  6 March 2020
"""

# System/default
import sys
import os

# Arguments
import argparse

###############################################################################
# Main function
###############################################################################
def main():
    """Main entry function
    """
    global args

    types = dict()
    types["sp"] = (0.005, 512, "SP", "SP", "sp")
    types["neur_ft"] = (0.00016, 40, "NEUR_FT", "NEUR", "neur")
    types["neur_mr"] = (0.0064, 40, "NEUR_MR", "NEUR", "neur")

    model = "hmm"

    alignment_file="/home/lemagues/work/maintained_tools/src/merlin/merlin/egs/slt_arctic/s1/experiments/slt_arctic_demo/acoustic_model/data/label_phone_align/%s.lab" % args.basename
    src="results_qomex/%s_qomex/%s/data/%s/%s/%s.%s" % (model, types[args.type][2], types[args.type][3], args.exp, args.basename, types[args.type][4])
    tgt="results_qomex/%s_wavenet/%s/data/%s/%s/%s_gen.%s" % (model, types[args.type][2], types[args.type][3], args.exp, args.basename, types[args.type][4])
    wav_src="results_qomex/%s_qomex/preprocessed_input/%s/wav/%s.wav" % (model, args.exp, args.basename)
    wav_tgt = "results_qomex/%s_wavenet/preprocessed_input/%s/wav/%s_gen.wav" % (model, args.exp, args.basename)

    cmd = "python3 compare_precomputed_coefficients.py -f %s -d %s -a %s %s %s %s %s" % (types[args.type][0], types[args.type][1], alignment_file, wav_src, src, wav_tgt, tgt)
    os.system(cmd)


###############################################################################
#  Envelopping
###############################################################################
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="")

    # Options
    parser.add_argument("-e", "--exp", default="as")

    # Add arguments
    parser.add_argument("basename")
    parser.add_argument("type")

    # Parsing arguments
    args = parser.parse_args()

    # Running main function <=> run application
    main()
