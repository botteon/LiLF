#!/usr/bin/env python

import os, sys, glob, getpass, socket
from surveys_db import SurveysDB
from LiLF import lib_ms, lib_img, lib_util, lib_log
logger_obj = lib_log.Logger('PiLL.logger')
logger = lib_log.logger
s = lib_util.Scheduler(log_dir = logger_obj.log_dir, dry = False)
w = lib_util.Walker('PiLL.walker')

LiLF_dir = os.path.dirname(lib_util.__file__)
parset = lib_util.getParset(parsetFile='lilf.config')

survey_projects = 'LT14_002,LC12_017,LC9_016,LC8_031' # list of projects related with the LBA survey


################## RESET #####################
with SurveysDB(survey='lba',readonly=False) as sdb:  
    sdb.execute('UPDATE fields SET status="Observed" where status!="Not started"')  
###############################################

# get parameters
# use lilf.config (this is also used by all other scripits)
working_dir = os.path.abspath(parset.get('PiLL','working_dir'))
redo_cal = parset.getboolean('PiLL','redo_cal')
project = parset.get('PiLL','project')
target = parset.get('PiLL','target')
download_file = parset.get('PiLL','download_file')
if download_file != '': download_file =os.path.abspath(download_file)

def calibrator_tables_available(obsid):
    """
    check if calibrator data exist in the database
    """
    with SurveysDB(survey='lba',readonly=True) as sdb:
        sdb.execute('SELECT * FROM observations WHERE id=%f' % obsid)
        r = sdb.cur.fetchall()
        if len(r) == 0: return False
        if r[0]['location'] != '': return True


def local_calibrator_dirs(searchdir='', obsid=None):
    """
    Return the dirname of the calibrators
    """
    if searchdir != '': searchdir += '/'
    if obsid is None:
        calibrators = glob.glob(searchdir+'id*_3[C|c]196') + \
                  glob.glob(searchdir+'id*_3[C|c]295') + \
                  glob.glob(searchdir+'id*_3[C|c]380')
    else:
        calibrators = glob.glob(searchdir+'/id%i_3[C|c]196' % obsid) + \
                  glob.glob(searchdir+'id%i_3[C|c]295' % obsid) + \
                  glob.glob(searchdir+'id%i_3[C|c]380' % obsid)

    if len(calibrators) == 0: return None
    else: return calibrators


def update_status_db(field, status):
    with SurveysDB(survey='lba',readonly=False) as sdb:
        r = sdb.execute('UPDATE fields SET status="%s" WHERE id="%s"' % (status,field))


def check_done(logfile):
    """
    check if "Done" is written in the last line of the log file, otherwise quit with error.
    """
    with open(logfile, 'r') as f:
        last_line = f_read.readlines()[-1]
    if not "Done" in last_line:
        if survey: update_status_db(target, 'Error') 
        logger.error('Something went wrong in the last pipeline call.')
        sys.exit()

####################################################################################

# query the database for data to process
survey = False
if download_file == '' and project == '' and target == '':
    survey = True
    project = survey_projects
    logger.info('### Quering database...')
    with SurveysDB(survey='lba',readonly=True) as sdb:
        sdb.execute('SELECT * FROM fields WHERE status="Observed" order by priority desc')
        r = sdb.cur.fetchall()
        target = r[0]['id']
        sdb.execute('SELECT * FROM field_obs WHERE field_id="%s"' % target)
        r = sdb.cur.fetchall()
        obsid = ','.join([str(x['obs_id']) for x in r])

    logger.info("### Working on target: %s (obsid: %s)" % (target, obsid))
    # add other info, like cluster, node, user...
    username = getpass.getuser()
    clustername = s.cluster
    nodename = socket.gethostname()
    with SurveysDB(survey='lba',readonly=False) as sdb:
        r = sdb.execute('UPDATE fields SET username="%s" WHERE id="%s"' % (username, target))
        r = sdb.execute('UPDATE fields SET clustername="%s" WHERE id="%s"' % (clustername, target))
        r = sdb.execute('UPDATE fields SET nodename="%s" WHERE id="%s"' % (nodename, target))

    update_status_db(target, 'Download') 

#######
# setup
if not os.path.exists(working_dir):
    os.makedirs(working_dir)
if os.path.exists('lilf.config') and os.getcwd() != working_dir: 
    os.system('cp lilf.config '+working_dir)

os.chdir(working_dir)
if not os.path.exists('download'):
    os.makedirs('download')

if download_file != '':
    os.system('cp %s download/html.txt' % download_file)

##########
# data download
# here the pipeline downloads only the target, not the calibrator
if w.todo('download'):
    logger.info('### Starting download... #####################################')
    os.chdir(working_dir+'/download')

    if download_file == '':
        cmd = LiLF_dir+'/scripts/LOFAR_stager.py --projects %s --nocal' % project
        if target != '':
            cmd += ' --target %s' % target
        if obsid != '':
            cmd += ' --obsID %s' % obsid
        logger.debug("Exec: %s" % cmd)
        os.system(cmd)

    # TODO: how to be sure all MS were downloaded?
    os.system(LiLF_dir+'/pipelines/LOFAR_download.py')

    os.chdir(working_dir)
    os.system('mv download/mss/* ./')
    
    w.done('download')
### DONE

if survey: update_status_db(target, 'Calibrator')
calibrators = local_calibrator_dirs()
targets = [t for t in glob.glob('id*') if t not in calibrators]
logger.debug('CALIBRATORS: %s' % ( ','.join(calibrators) ) )
logger.debug('TARGET: %s' % (','.join(targets) ) )

for target in targets:
    
    ##########
    # calibrator
    # here the pipeline checks if the calibrator is available online, otherwise it downloads it
    # then it also runs the calibrator pipeline
    obsid = int(target.split('_')[0][2:])
    if w.todo('cal_id%i' % obsid):
        if redo_cal or not calibrator_tables_available(obsid):
            logger.info('### %s: Starting calibrator... #####################################' % target)
            # if calibrator not downaloaded, do it
            cal_dir = local_calibrator_dirs(working_dir, obsid)
        
            if cal_dir is None:
                os.chdir(working_dir+'/download')
                os.system(LiLF_dir+'/scripts/LOFAR_stager.py --cal --projects %s --obsid %i' % (project, obsid))
                os.system(LiLF_dir+'/pipelines/LOFAR_download.py')
                check_done('pipeline-download.logger')
    
                calibrator = local_calibrator_dirs('./mss/', obsid)[0]
                os.system('mv '+calibrator+' '+working_dir)

            os.chdir(local_calibrator_dirs(working_dir, obsid)[0])
            if not os.path.exists('data-bkp'):
                os.makedirs('data-bkp')
                os.system('mv *MS data-bkp')
            os.system(LiLF_dir+'/pipelines/LOFAR_cal.py')
            check_done('pipeline-download.logger')
    
        w.done('cal_id%i' % obsid)
    ### DONE

    ##########
    # timesplit
    # each target of each observation is then timesplit
    if w.todo('timesplit_%s' % target):
        logger.info('### %s: Starting timesplit... #####################################' % target)
        os.chdir(working_dir+'/'+target)
        if not os.path.exists('data-bkp'):
            os.makedirs('data-bkp')
            os.system('mv *MS data-bkp')

        os.system(LiLF_dir+'/pipelines/LOFAR_timesplit.py')
        check_done('pipeline-timesplit.logger')

        w.done('timesplit_%s' % target)
    ### DONE

# group targets with same name, assuming they are different pointings of the same dir
grouped_targets = set([t.split('_')[1] for t in targets])

for grouped_target in grouped_targets:
    if not os.path.exists(working_dir+'/'+grouped_target):
        os.makedirs(working_dir+'/'+grouped_target)
    os.chdir(working_dir+'/'+grouped_target)
    
    # collet mss for this grouped_target
    if not os.path.exists('mss'):
        os.makedirs('mss')
        for i, tc in enumerate(glob.glob('../id*_'+grouped_target+'/mss/TC*MS')):
            tc_ren = 'TC%02i.MS' % i
            logger.debug('mv %s mss/%s' % (tc,tc_ren))
            os.system('mv %s mss/%s' % (tc,tc_ren))

    # selfcal
    if w.todo('self_%s' % grouped_target):
        if survey: update_status_db(grouped_target, 'Self')
        logger.info('### %s: Starting selfcal #####################################' % grouped_target)
        os.system(LiLF_dir+'/pipelines/LOFAR_self.py')
        check_done('pipeline-self.logger')
        w.done('self_%s' % grouped_target)
    ### DONE

    # DD-cal
    if w.todo('dd_%s' % grouped_target):
        if survey: update_status_db(grouped_target, 'Ddcal')
        logger.info('### %s: Starting ddcal #####################################' % grouped_target)
        os.system(LiLF_dir+'/pipelines/LOFAR_dd-serial.py')
        check_done('pipeline-dd-serial.logger')
        w.done('dd_%s' % grouped_target)
    ### DONE

    if survey: update_status_db(grouped_target, 'Done')
    logger.info('### %s: Done. #####################################' % grouped_target)