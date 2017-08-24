#!/usr/bin/env python
# -*- coding: utf-8 -*-

'''
Francesco de Gasperin & Martijn Oei, 2017
In collaboration with: Reinout van Weeren, Tammo Jan Dijkema and Andre Offringa

This pipeline chunk
1. Performs the first chunk of flagging.

Notes:
Paths to directories do not end with a '/'.
'''

import glob, logging

import lib_ms, lib_util


def main():
    # Initialise parameter set settings.
    pathDirectoryParSet = "/disks/strw3/oei/code/PiLF/parset_cal"
    nameParSetFlag      = "DPPP-uGMRT-flag.parset"
    pathParSetFlag      = pathDirectoryParSet + '/' + nameParSetFlag
    
    # Initialise main folder setting.
    #pathDirectoryMain   = "/disks/strw3/oei/uGMRTCosmosCut-PiLF"
    pathDirectoryMain   = "/disks/strw3/oei/uGMRTCosmosCut-PiLF/fieldsTarget/P149.7+03.4/MSs"
    
    # Initialise logging settings.
    pathDirectoryLog    = "/disks/strw3/oei/uGMRTCosmosCut-PiLF/logs"
    nameFileLog         = "pipeline_uGMRT_flag.log"
    pathFileLog         = pathDirectoryLog + '/' + nameFileLog
    
    # Initialise baselines to be flagged in entirety.
    bl2flag             = ""
    
    
    lib_util.printLineBold("Starting log at '" + pathFileLog + "'...")
    
    logging.basicConfig(filename = pathFileLog, level = logging.DEBUG)
    logging.info("Started 'pipeline_uGMRT_flag.py'!")
    
    
    pathsMS = glob.glob(pathDirectoryMain + "/*MS")
    
    for pathMS in pathsMS:
        MSObject = lib_ms.MS(pathMS)
        print (MSObject.find_nchan())
        print (MSObject.find_chanband())
    
    
    logging.info('Flagging...')

    scheduler = lib_util.Scheduler(dry = False, log_dir = pathDirectoryLog)
    MSs       = lib_ms.AllMSs(pathsMS, scheduler)
    
    MSs.run("DPPP " + pathParSetFlag + " msin=$ms flag1.baseline=" + bl2flag, log = nameFileLog, cmd_type = "DPPP")


if (__name__ == "__main__"):
    main()