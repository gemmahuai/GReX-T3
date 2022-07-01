import traceback
import numpy as np
from dsautils import dsa_store
import dsautils.dsa_syslog as dsl
from dsaT3 import filplot_funcs as filf
import time, os
import json

ds = dsa_store.DsaStore()
LOGGER = dsl.DsaSyslogger()
LOGGER.subsystem("software")
LOGGER.app("dsaT3")
LOGGER.function("T3_manager")

TIMEOUT_FIL = 60
TIMEOUT_CORR = 21600
FILPATH = '/dataz/dsa110/operations/T1/'
OUTPUT_PATH = '/dataz/dsa110/operations/T3/'
FIL_CORRS = ['corr01','corr02','corr09','corr13']
TMPDIR = '/home/ubuntu/data/tmp/'


def run_filplot(a, wait=False):
    """ Given candidate dictionary, run filterbank analysis, plotting, and classification ("filplot").
    Returns dictionary with updated fields.
    """

    # set up output dict and datestring
    output_dict = a[list(a.keys())[0]]
    output_dict['trigname'] = list(a.keys())[0]
    fill_empty_dict(output_dict)

    # wait for specific filterbank file to be written
    ibeam = output_dict['ibeam'] + 1
    trigname = output_dict['trigname']
    filfile = f"{FILPATH}/{trigname}/{trigname}_{ibeam}.fil"

    print(filfile)
    LOGGER.info('Working on {0}'.format(output_dict['trigname']))
    if wait:
        found_filfile = wait_for_local_file(filfile,TIMEOUT_FIL)
    else:
        found_filfile = filfile if os.path.exists(filfile) else None
    output_dict['filfile'] = found_filfile
    
    if found_filfile is None:
        LOGGER.error('No filfile for {0}'.format(output_dict['trigname']))
        return output_dict
    
    # launch plot and classify
    try:
        output_dict['candplot'], output_dict['probability'], output_dict['real'] = filf.filplot_entry(a, rficlean=False)
    except Exception as exception:
        logging_string = "Could not make filplot {0} due to {1}.  Callback:\n{2}".format(
            output_dict['trigname'],
            type(exception).__name__,
            ''.join(
                traceback.format_tb(exception.__traceback__)
            )
        )
        print(logging_string)
        LOGGER.error(logging_string)

        return output_dict

    # write output_dict to disk
    with open(OUTPUT_PATH + output_dict['trigname'] + '.json', 'w') as f: #encoding='utf-8'                  
        json.dump(output_dict, f, ensure_ascii=False, indent=4)

    return output_dict


def run_burstfit(dd):
    """ Given candidate dictionary, run burstfit analysis.
    Returns new dictionary with refined DM, width, arrival time.
    """

    return dd.copy()


def run_hires(dd):
    """ Given candidate dictionary, create high time/freq filterbanks.
    Returns new dictionary with new file locations?
    """

    return dd.copy()


def run_pol(dd):
    """ Given candidate dictionary, run polarization analysis.
    Returns new dictionary with new file locations?
    """

    return dd.copy()


def make_filterbanks(od):
    """ Uses cand dictionary to get set up filterbanks.
    Returns list of file names.
    """

    # corr nodes
    corrs = ['corr03', 'corr04', 'corr05', 'corr06', 'corr07', 'corr08', 'corr10', 'corr11', 'corr12', 'corr14', 'corr15', 'corr16', 'corr18', 'corr19', 'corr21', 'corr22']
    freqs=["1498.75", "1487.03125", "1475.3125", "1463.59375", "1451.875", "1440.15625", "1428.4375", "1416.71875", "1405.0", "1393.28125", "1381.5625", "1369.84375", "1358.125", "1346.40625", "1334.6875", "1322.96875"]

    arg_splicer = ''
    
    # loop over corr nodes and run offline bf
    for ci in np.arange(16):

        if od[corrs[ci]+'_data'] is not None:

            # copy calibrations file
            os.system('scp '+corrs[ci]+'.sas.pvt:/home/ubuntu/proj/dsa110-shell/dsa110-xengine/utils/antennas.out '+TMPDIR+corrs[ci]+'.out')

            # run offline beamformer
            os.system('/home/ubuntu/proj/dsa110-shell/dsa110-xengine/src/dsaX_beamformer_offline -i '+od[corrs[ci]+'_data']+' -f '+TMPDIR+corrs[ci]+'.out -z '+freqs[ci]+' -a /home/ubuntu/vikram/process_voltages/flagants.dat')
            os.system('mv '+TMPDIR+'output.dat '+TMPDIR+corrs[ci]+'_output.dat')

            arg_splicer += ' '+TMPDIR+corrs[ci]+'_output.dat '

        else:

            arg_splicer += ' none '
            
    # run splicer
    arg_splicer += ' ' + FILPATH + 'fil ' + od['trigname']
    os.system('/home/ubuntu/proj/dsa110-shell/dsa110-xengine/src/splice_offline_beams '+arg_splicer)

    flist = []
    for i in np.arange(256):
        flist.append(FILPATH + 'fil_' + od['trigname'] + '/'+od['trigname']+'_'+str(i)+'.fil')
        
    return flist
    

def fill_empty_dict(od, emptyCorrs=True, correctCorrs=False):
    """ Takes standard candidate dict, od, and resets entries to default values (e.g., None/False).
    """

    od['filfile'] = None
    od['candplot'] = None
    od['save'] = False
    od['label'] = None
    if emptyCorrs is True:
        for corr in ['corr03','corr04','corr05','corr06','corr07','corr08','corr10','corr11','corr12','corr14','corr15','corr16','corr18','corr19','corr21','corr22']:
            od[corr+'_data'] = None
            od[corr+'_header'] = None

    if correctCorrs is True:
        for corr in ['corr03','corr04','corr05','corr06','corr07','corr08','corr10','corr11','corr12','corr14','corr15','corr16','corr18','corr19','corr21','corr22']:
            if od[corr+'_data'] is not None:
                od[corr+'_data'] = od[corr+'_data'][:-19]
            if od[corr+'_header'] is not None:
                od[corr+'_header'] = od[corr+'_header'][:-22]
        

def wait_for_local_file(fl, timeout):
    """ Wait for file named fl to be written.
    If timeout (in seconds) exceeded, then return None.
    """

    time_counter = 0
    while not os.path.exists(fl):
        time.sleep(1)
        time_counter += 1
        if time_counter > timeout:
            return None

    # wait in case file hasn't been written
    time.sleep(10)

    return fl
    

# a is dict from voltage copy service
def run_copied(a):

    # set up output dict and datestring
    datestring = ds.get_dict('/cnf/datestring')
    output_dict = a[list(a.keys())[0]]
    output_dict['trigname'] = list(a.keys())[0]
    output_dict['datestring'] = datestring
    fill_empty_dict(output_dict, emptyCorrs=False)

    # make and merge filterbank files
    flist = make_filterbanks(output_dict)
    ibeam = output_dict['ibeam'] + 1
    output_dict['filfile'] = FILPATH + datestring + '/fil_' + output_dict['trigname'] + '/' + output_dict['trigname'] +	'_' + str(ibeam) + '.fil'

    # launch candplotter
    try:
        output_dict['candplot'] = filf.filplot_entry(datestring,a,fllisting=flist,rficlean=False)
    except Exception as exception:
        logging_string = "Could not make filplot {0} due to {1}.  Callback:\n{2}".format(
            output_dict['trigname'],
            type(exception).__name__,
            ''.join(
                traceback.format_tb(exception.__traceback__)
            )
        )
        print(logging_string)
        LOGGER.error(logging_string)
        #with open(OUTPUT_PATH + output_dict['trigname'] + '.json', 'w') as f: #encoding='utf-8'
        #    json.dump(output_dict, f, ensure_ascii=False, indent=4)

        return output_dict

    # wait for voltage files to be written
    

    # write output_dict to disk
    with open(OUTPUT_PATH + output_dict['trigname'] + '.json', 'w') as f: #encoding='utf-8'                  
        json.dump(output_dict, f, ensure_ascii=False, indent=4)

    return output_dict

# to scp files
def copy(a,nrep=5):

    # make dir
    datestring = ds.get_dict('/cnf/datestring')
    odir = "/media/ubuntu/ssd/T3/"+datestring+"/"
    os.system("mkdir -p "+odir)

    # scp file
    corrname = a[list(a.keys())[0]]
    b = a[list(a.keys())[1]]
    output_dict = b[list(b.keys())[0]]
    output_dict['trigname'] = list(b.keys())[0]
    output_dict['datestring'] = datestring
    output_dict['corrname'] = corrname

    remote_loc = "/home/ubuntu/data/"+output_dict['trigname']+"_header.json"
    local_loc = odir+corrname+"_"+output_dict['trigname']+"_header.json"
    #cmd = "ssh "+corrname+".sas.pvt 'sudo loginctl enable-linger ubuntu; source ~/.bashrc; screen -d -m scp "+remote_loc+" 10.41.0.182:"+local_loc+"'"
    cmd = "ssh "+corrname+".sas.pvt 'sudo loginctl enable-linger ubuntu; source ~/.bashrc; screen -d -m rsync --partial --timeout=20 -avz "+remote_loc+" 10.41.0.182:"+local_loc+"'"    
    os.system(cmd)
    
    remote_loc = "/home/ubuntu/data/"+output_dict['trigname']+"_data.out"
    local_loc = odir+corrname+"_"+output_dict['trigname']+"_data.out"
    #cmd = "ssh "+corrname+".sas.pvt 'sudo loginctl enable-linger ubuntu; source ~/.bashrc; screen -d -m scp "+remote_loc+" 10.41.0.182:"+local_loc+"'"
    cmd = "ssh "+corrname+".sas.pvt 'sudo loginctl enable-linger ubuntu; source ~/.bashrc; screen -L -d -m bash /home/ubuntu/proj/dsa110-shell/dsa110-xengine/scripts/run_rsync.bash "+remote_loc+" 10.41.0.182:"+local_loc+"'"
    os.system(cmd)

    return output_dict

