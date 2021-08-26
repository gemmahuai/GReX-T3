# plot triggered FRB candidates
# liam.dean.connor@gmail.com & ghellbourg@astro.caltech.edu
# 25/02/2021

import os
import os.path
import sys

import scipy.signal
from scipy import stats

import numpy as np
import matplotlib as mpl
import h5py
mpl.use('Agg') # hack
import matplotlib.pyplot as plt 
import json
import glob
import optparse
from mpl_toolkits.axes_grid.inset_locator import inset_axes

import multiprocessing
from joblib import Parallel, delayed

#import filterbank
from sigpyproc.Readers import FilReader
import slack

ncpu = multiprocessing.cpu_count() - 1 

# Keras neural network model for Freq/Time array
MLMODELPATH='/home/user/connor/software/machine_learning/20190501freq_time.hdf5'
BASEDIR='/mnt/data/dsa110/'
webPLOTDIR=BASEDIR+'webPLOTS/'
MLMODELPATH='/home/ubuntu/connor/MLmodel/20190501freq_time.hdf5'
BASEDIR='/data/dsa110/'
webPLOTDIR=BASEDIR+'webPLOTS/'

plt.rcParams.update({
                    'font.size': 12,
                    'font.family': 'serif',
                    'axes.labelsize': 14,
                    'axes.titlesize': 15,
                    'xtick.labelsize': 12,
                    'ytick.labelsize': 12,
                    'xtick.direction': 'in',
                    'ytick.direction': 'in',
                    'xtick.top': True,
                    'ytick.right': True,
                    'lines.linewidth': 0.5,
                    'lines.markersize': 5,
                    'legend.fontsize': 14,
                    'legend.borderaxespad': 0,
                    'legend.frameon': False,
                    'legend.loc': 'lower right'})

def read_fil_data_dsa(fn, start=0, stop=1):
    """ Read in filterbank data
    """
    fil_obj = FilReader(fn)
    header = fil_obj.header
    delta_t = fil_obj.header['tsamp'] # delta_t in seconds                                                                                                                  
    fch1 = header['fch1']
    nchans = header['nchans']
    foff = header['foff']
    fch_f = fch1 + nchans*foff
    freq = np.linspace(fch1,fch_f,nchans)
    try:
        data = fil_obj.readBlock(start, stop)
    except(ValueError):
        data = 0

    return data, freq, delta_t, header

def plotfour(dataft, datats, datadmt, 
             beam_time_arr=None, figname_out=None, dm=0,
             dms=[0,1], 
             datadm0=None, suptitle='', heimsnr=-1,
             ibox=1, ibeam=-1, prob=-1, showplot=True,multibeam_dm0ts=None):
    """ Plot a trigger's dynamics spectrum, 
        dm/time array, pulse profile, 
        multibeam info (optional), and zerodm (optional)

        Parameter
        ---------
        dataft : 
            freq/time array (nfreq, ntime)
        datats : 
            dedispersed timestream
        datadmt : 
            dm/time array (ndm, ntime)
        beam_time_arr : 
            beam time SNR array (nbeam, ntime)
        figname_out : 
            save figure with this file name 
        dm : 
            dispersion measure of trigger 
        dms : 
            min and max dm for dm/time array 
        datadm0 : 
            raw data timestream without dedispersion
    """

    classification_dict = {'prob' : [],
                           'snr_dm0_ibeam' : [],
                           'snr_dm0_allbeam' : []}
    datats /= np.std(datats[datats!=np.max(datats)])
    nfreq, ntime = dataft.shape
    xminplot,xmaxplot = 200,800 # milliseconds
    dm_min, dm_max = dms[0], dms[1]
    tmin, tmax = 0., 1e3*dataft.header['tsamp']*ntime
    freqmax = dataft.header['fch1']
    freqmin = freqmax + dataft.header['nchans']*dataft.header['foff']
    tarr = np.linspace(tmin, tmax, ntime)
    fig = plt.figure(figsize=(8,10))

    plt.subplot(321)
    extentft=[tmin,tmax,freqmin,freqmax]
    plt.imshow(dataft, aspect='auto',extent=extentft, interpolation='nearest')
    plt.xlim(xminplot,xmaxplot)
    plt.xlabel('Time (ms)')
    plt.ylabel('Freq (MHz)')
    if prob!=-1:
        plt.text(xminplot+50,0.5*(freqmax+freqmin),"Prob=%0.2f" % prob, color='white', fontweight='bold')
        classification_dict['prob'] = prob
    plt.subplot(322)
    extentdm=[tmin, tmax, dm_min, dm_max]
    plt.imshow(datadmt[::-1], aspect='auto',extent=extentdm)
    plt.xlim(xminplot,xmaxplot)
    plt.xlabel('Time (ms)')
    plt.ylabel(r'DM (pc cm$^{-3}$)')

    plt.subplot(323)
    plt.plot(tarr, datats)
    plt.grid('on', alpha=0.25)
    plt.xlabel('Time (ms)')
    plt.ylabel(r'Power ($\sigma$)')
    plt.xlim(xminplot,xmaxplot)
    plt.text(0.55*(tmin+1000.), 0.5*(max(datats)+np.median(datats)), 
            'Heimdall S/N : %0.1f\nHeimdall DM : %d\
            \nHeimdall ibox : %d\nibeam : %d' % (heimsnr,dm,ibox,ibeam), 
            fontsize=8, verticalalignment='center')
    
    parent_axes=fig.add_subplot(324)
    if beam_time_arr is None:
        plt.xticks([])
        plt.yticks([])
        plt.text(0.20, 0.55, 'Multibeam info\nunder construction',
                fontweight='bold')
    else:
        parent_axes.imshow(beam_time_arr[::-1], aspect='auto', extent=[tmin, tmax, 0, beam_time_arr.shape[0]], 
                  interpolation='nearest')
        parent_axes.axvline(540, ymin=0, ymax=6, color='r', linestyle='--', alpha=0.55)
        parent_axes.axvline(460, ymin=0, ymax=6, color='r', linestyle='--', alpha=0.55)
        parent_axes.axhline(max(0,ibeam-1), xmin=0, xmax=100, color='r', linestyle='--', alpha=0.55)
        parent_axes.axhline(ibeam+1, xmin=0, xmax=100, color='r', linestyle='--', alpha=0.55)
        parent_axes.set_xlim(xminplot,xmaxplot)
        parent_axes.set_xlabel('Time (ms)')
        parent_axes.set_ylabel('Beam', fontsize=15)
        small_axes = inset_axes(parent_axes,
                    width="25%", # width = 30% of parent_bbox
                    height="25%", # height : 1 inch
                                loc=4)
        small_axes.imshow(beam_time_arr[ibeam-4:ibeam+4][::-1], aspect='auto', extent=[tmin, tmax, ibeam-4, ibeam+4],
                                            interpolation='nearest', cmap='afmhot')
        small_axes.set_xlim(400., 600.)

    if datadm0 is not None:
        plt.subplot(325)
        datadm0 -= np.median(datadm0.mean(0))
        datadm0_sigmas = datadm0.mean(0)/np.std(datadm0.mean(0)[-500:])
        snr_dm0ts_iBeam = np.max(datadm0_sigmas)
        plt.plot(np.linspace(0, tmax, len(datadm0[0])), datadm0_sigmas, c='k')
        classification_dict['snr_dm0_ibeam'] = snr_dm0ts_iBeam
        
        if multibeam_dm0ts is not None:
            multibeam_dm0ts = multibeam_dm0ts/np.std(multibeam_dm0ts[multibeam_dm0ts!=multibeam_dm0ts.max()])
            multibeam_dm0ts -= np.median(multibeam_dm0ts)
            snr_dm0ts_allbeams = np.max(multibeam_dm0ts)
            plt.plot(np.linspace(0, tmax, len(multibeam_dm0ts)), multibeam_dm0ts, color='C1', alpha=0.75)
            plt.legend(['iBeam=%d'%ibeam, 'All beams'], loc=1, fontsize=10)
            plt.ylabel(r'Power ($\sigma$)')
            classification_dict['snr_dm0_allbeam'] = snr_dm0ts_allbeams
        else:
            plt.legend(['DM=0 Timestream'], loc=2, fontsize=10)
        plt.xlabel('Time (ms)')
        
        plt.subplot(326)
        plt.plot(np.linspace(freqmax,freqmin,datadm0.shape[0]), np.mean(datadm0,axis=-1), color='k')
        plt.semilogy()
        plt.legend(['spectrum'], loc=2)
        plt.xlabel('freq [MHz]')

    print(classification_dict)
    not_real = False

    if multibeam_dm0ts is not None:
        if classification_dict['snr_dm0_allbeam']>7.0:
            if classification_dict['prob']<0.5:
                not_real = True

    if classification_dict['prob']<0.01:
        not_real = True

    if not_real==True:
        suptitle += ' (Probably not real)'
        
    plt.suptitle(suptitle, color='C1')
    plt.tight_layout()
    if figname_out is not None:
        plt.savefig(figname_out)
    if showplot:
        plt.show()

    return not_real
        
def dm_transform(data, dm_max=20,
                 dm_min=0, dm0=None, ndm=64, 
                 freq_ref=None, downsample=16):
    """ Transform freq/time data to dm/time data.                                                                                                                                           
    """
    ntime = data.shape[1]

    dms = np.linspace(dm_min, dm_max, ndm, endpoint=True)

    if dm0 is not None:
        dm_max_jj = np.argmin(abs(dms-dm0))
        dms += (dm0-dms[dm_max_jj])

    data_full = np.zeros([ndm, ntime//downsample])

    for ii, dm in enumerate(dms):
        dd = data.dedisperse(dm)
        _dts = np.mean(dd,axis=0)
        data_full[ii] = _dts[:ntime//downsample*downsample].reshape(ntime//downsample, downsample).mean(1)

    return data_full, dms

def proc_cand_fil(fnfil, dm, ibox, snrheim=-1, 
                  pre_rebin=1, nfreq_plot=64,
                  heim_raw_tres=1, 
                  rficlean=False, ndm=64):
    """ Take filterbank file path, preprocess, and 
    plot trigger

    Parameters:
    ----------

    fnfil   : str 
        path to .fil file 
    DM      : float 
        dispersion measure of trigger 
    ibox    : int 
        preferred boxcar width 
    snrheim : float 
        S/N of candidate found by Heimdall
    pre_rebin : int 
        rebin in time by this factor *before* dedispersion (saves time)
    nfreq_plot : int 
        number of frequency channels in output
    heim_raw_tres : 32  
    """
    header = read_fil_data_dsa(fnfil, 0, 1)[-1]
    # read in 4 seconds of data
    nsamp = int(4.0/header['tsamp'])
    data, freq, delta_t_raw, header = read_fil_data_dsa(fnfil, start=0, 
                                                       stop=nsamp)

    nfreq0, ntime0 = data.shape

    if pre_rebin>1:
        # Ensure that you do not pre-downsample by more than the total boxcar
        pre_rebin = min(pre_rebin, ibox*heim_raw_tres)
        data = data.downsample(pre_rebin)

    datadm0 = data.copy()
    
    if rficlean:
#        print("Cleaning data perchannel")
        data = cleandata(data, clean_type='aladsa')

    tsdm0 = np.mean(data,axis=0)

    datadm, dms = dm_transform(data, dm_max=dm+250,
                               dm_min=dm-250, dm0=dm, ndm=ndm, 
                               freq_ref=None, 
                               downsample=heim_raw_tres*ibox//pre_rebin)
    data = data.dedisperse(dm)
    data = data.downsample(heim_raw_tres*ibox//pre_rebin)
    data = data.reshape(nfreq_plot, data.shape[0]//nfreq_plot, 
                        data.shape[1]).mean(1)

    data = data-np.median(data,axis=1,keepdims=True)
    data /= np.std(data)

    return data, datadm, tsdm0, dms, datadm0


def medflagdata(spec, filtsize, thres):
    specfilt = scipy.signal.medfilt(spec,kernel_size=int(filtsize));
    speccorrec = spec - specfilt;
    specstd = stats.median_absolute_deviation(speccorrec);
    return np.concatenate((np.argwhere(speccorrec > thres*specstd),np.argwhere(speccorrec < -thres*specstd)))

def cleandata(data, threshold_time=3.25, threshold_frequency=2.75, bin_size=32,
              n_iter_time=3, n_iter_frequency=3, clean_type='time', wideclean=None):
    """ Take filterbank object and mask
    RFI time samples with average spectrum.

    Parameters:
    ----------
    data :
        data array (nfreq, ntime)
    threshold_time : float
        units of sigma
    threshold_frequency : float
        units of sigma
    bin_size : int
        quantization bin size
    n_iter_time : int
        Number of iteration for time cleaning
    n_iter_frequency : int
        Number of iteration for frequency cleaning
    clean_type : str
        type of cleaning to be done.
        Accepted values: 'time', 'frequency', 'both', 'perchannel'

    Returns:
    -------
    cleaned filterbank object
    """
    if clean_type not in ['time', 'both', 'frequency', 'perchannel', 'aladsa']:
        return data
        
    nfreq = data.shape[0]
    ntimes = data.shape[1]

    dtmean = np.mean(data, axis=-1)
    # Clean in time
    #sys_temperature_bandpass(data.data)
    #remove_noisy_freq(data.data, 3)
    #remove_noisy_channels(data.data, sigma_threshold=2, iters=5)
    if clean_type in ['time', 'both']:
        for i in range(n_iter_time):
            dfmean = np.mean(data, axis=0)
            stdevf = np.std(dfmean)
            medf = np.median(dfmean)
            maskf = np.where(np.abs(dfmean - medf) > threshold_time*stdevf)[0]
            # replace with mean spectrum
            data[:, maskf] = dtmean[:, None]*np.ones(len(maskf))[None]
            
    if clean_type=='aladsa':
        print('flagging a la DSA\n');
        meanidx = medflagdata(dtmean, 21, 5.);
        varidx = medflagdata(np.var(data,axis=-1), 21, 5.);
        allidx = np.concatenate((meanidx,varidx));
        allidx = np.asarray(list(set(list(np.ravel(allidx)))));
        data[allidx,:] = np.zeros((len(allidx),ntimes));
        

    if clean_type=='perchannel':
        for ii in range(n_iter_time):
            dtmean = np.mean(data, axis=1, keepdims=True)
            dtsig = np.std(data, axis=1)
            for nu in range(data.shape[0]):
                d = dtmean[nu]
                sig = dtsig[nu]
                maskpc = np.where(np.abs(data[nu]-d)>threshold_time*sig)[0]
                data[nu][maskpc] = d

    # Clean in frequency
    # remove bandpass by averaging over bin_size ajdacent channels
    if clean_type in ['frequency', 'both']:
        for ii in range(n_iter_frequency):
            dtmean_nobandpass = data.mean(1) - dtmean.reshape(-1, bin_size).mean(-1).repeat(bin_size)
            stdevt = np.std(dtmean_nobandpass)
            medt = np.median(dtmean_nobandpass)
            maskt = np.abs(dtmean_nobandpass - medt) > threshold_frequency*stdevt
            data[maskt] = np.median(dtmean)#dtmean.reshape(-1, bin_size).mean(-1).repeat(bin_size)[maskt]

    return data

def generate_beam_time_arr(fl, ibeam=0, pre_rebin=1, 
                           dm=0, ibox=1, heim_raw_tres=1):
    """ Take list of nbeam .fil files, dedisperse each 
    to the dm of the main trigger, and generate an 
    (nbeam, ntime) SNR array.

    Parameters:
    -----------
    fl : list 
        list of .fil files, each 4 seconds long
    ibeam : int 
        beam number of trigger
    pre_rebin : 
        downsample by this factor before dedispersion to save time
    dm : int 
        dm of ibeam candidate
    ibox : int 
        boxcar width of ibeam candidate 
    heim_raw_tres : int 
        ratio of 

    Returns:
    --------
    beam_time_arr : ndarray 
        array of SNR values (nbeam, ntime)
    """
    fl.sort()
    nbeam = len(fl[:])
    header = read_fil_data_dsa(fl[0], 0, 1)[-1]
    # read in 4 seconds of data
    nsamp = int(4.0/header['tsamp'])
    nsamp_final = nsamp // (heim_raw_tres*ibox)
    nfreq_final = 1024
    
#    beam_time_arr = np.zeros([nbeam, nsamp_final])
    beam_time_arr = np.zeros([nbeam, nfreq_final, nsamp_final])    
    multibeam_dm0ts = 0
    beamno_arr=[]
    
    for jj,fnfil in enumerate(fl):
        print(fnfil, beam_time_arr.shape)
        beamno = int(fnfil.strip('.fil').split('_')[-1])
        data, freq, delta_t_raw, header = read_fil_data_dsa(fnfil, start=0, 
                                                           stop=nsamp)
        nfreq0, ntime0 = data.shape

        # Ensure that you do not pre-downsample by more than the total boxcar
        pre_rebin = min(pre_rebin, ibox*heim_raw_tres)

        multibeam_dm0ts += data.mean(0) 
        # Rebin in frequency by 8x
        data = data.downsample(pre_rebin)
        data = data.dedisperse(dm)
        data = data.downsample(heim_raw_tres*ibox//pre_rebin)
        datats = np.mean(data, axis=0)

        # Low resolution nbeam, nfreq, ntime array
        data_ftb = data.reshape(nfreq_final, data.shape[0]//nfreq_final, data.shape[1]).mean(1)
        # Normalize data excluding outliers
        datatscopy = datats.copy()
        datatscopy.sort()
        medts = np.median(datatscopy[:int(0.975*len(datatscopy))])
        sigts = np.std(datatscopy[:int(0.975*len(datatscopy))])
        datats -= medts 
        datats /= sigts
        beamno_arr.append(beamno)

#        beam_time_arr[beamno, :] = datats
        beam_time_arr[jj, :] = data_ftb 

    return beam_time_arr, multibeam_dm0ts, beamno_arr


def plot_fil(fn, dm, ibox, multibeam=None, figname_out=None,
             ndm=32, suptitle='', heimsnr=-1,
             ibeam=-1, rficlean=True, nfreq_plot=32, 
             classify=False, heim_raw_tres=1, 
             showplot=True, save_data=False):
    """ Vizualize FRB candidates on DSA-110
    """
#    if type(multibeam)==list:
#        beam_time_arr, multibeam_dm0ts = generate_beam_time_arr(multibeam, ibeam=ibeam, pre_rebin=1, 
#                                             dm=dm, ibox=ibox, 
#                                             heim_raw_tres=heim_raw_tres)
#                                                               
#        x,y = np.where(beam_time_arr==beam_time_arr.max())
#        ibeam = x[0]
#        fn = flist[ibeam]
#        for fn_ in flist:
#            print(fn_, fn_.strip('_')[-1])
#            if str(ibeam) in fn_.strip('_')[-1]:
#                print(ibeam,'here')
#    else:
#        beam_time_arr = None
#        multibeam_dm0ts = None

    if type(multibeam)==list:
        data_beam_freq_time = []
        beam_time_arr_results = Parallel(n_jobs=ncpu)(delayed(generate_beam_time_arr)(multibeam[8*ii:8*(ii+1)],
                                                              ibox=ibox, pre_rebin=1,
                                                              dm=dm, heim_raw_tres=heim_raw_tres)
                                                              for ii in range(32))
#        for datacube in beam_time_arr_results:
        beamno_arr=[]
        for ii in range(len(beam_time_arr_results)):
            beamno_arr.append(beam_time_arr_results[ii][2])
            data_beam_freq_time.append(beam_time_arr_results[ii][0])
        data_beam_freq_time = np.concatenate(data_beam_freq_time, axis=0)
        print(data_beam_freq_time.shape)
        beam_time_arr = data_beam_freq_time.mean(1)
        multibeam_dm0ts = beam_time_arr.mean(0)
    else:
        beam_time_arr = None
        multibeam_dm0ts = None            
            
        
    dataft, datadm, tsdm0, dms, datadm0 = proc_cand_fil(fn, dm, ibox, snrheim=-1, 
                                               pre_rebin=1, nfreq_plot=nfreq_plot,
                                               ndm=ndm, rficlean=rficlean,
                                               heim_raw_tres=heim_raw_tres)
    
    if classify:
        from keras.models import load_model
        fnmodel=MLMODELPATH
        model = load_model(fnmodel)
        mm = np.argmax(dataft.mean(0))
        tlow, thigh = mm-32, mm+32
        if mm<32:
            tlow=0
            thigh=64
        if thigh>dataft.shape[1]:
            thigh=dataft.shape[1]
            tlow=thigh-64
        dataml = dataft[:,tlow:thigh]
        dataml -= np.median(dataml, axis=1, keepdims=True)
        dataml /= np.std(dataml, axis=-1)[:, None]
        dataml[dataml!=dataml] = 0.0
        dataml = dataml[None,..., None]
        prob = model.predict(dataml)[0,1]
    else:
        prob = -1
        
    if save_data:
        fnout = (fn.split('/')[-1]).strip('.fil') + '.hdf5'
        fnout = '/home/ubuntu/connor/software/misc/data/MLtraining/' + fnout
        
        paramsdict = {'dm' : dm, 'ibox' : ibox, 'ibeam' : ibeam,
                      'snr' : heimsnr}
        
        g = h5py.File(fnout,'w')
        g.create_dataset('data_freq_time',data=dataft)
        g.create_dataset('data_dm_time',data=datadm)
        if beam_time_arr is None:
            g.create_dataset('data_beam_time',data=[])
        else:
            g.create_dataset('data_beam_time',data=beam_time_arr)
        g.create_dataset('params',data=str(paramsdict))
        g.close()
    
        
    not_real = plotfour(dataft, dataft.mean(0), datadm, datadm0=datadm0, 
             beam_time_arr=beam_time_arr, figname_out=figname_out, dm=dm,
             dms=[dms[0],dms[-1]], 
             suptitle=suptitle, heimsnr=heimsnr,
             ibox=ibox, ibeam=ibeam, prob=prob, showplot=showplot, multibeam_dm0ts=multibeam_dm0ts)

    return not_real
    
def read_json(jsonfile):
    with open(jsonfile) as f:
        triggerdata = json.load(f)

    timehr   = float(triggerdata.get(list(triggerdata.keys())[0]).get('mjds'))
    snr      = float(triggerdata.get(list(triggerdata.keys())[0]).get('snr'))
    dm       = float(triggerdata.get(list(triggerdata.keys())[0]).get('dm'))
    ibeam    = int(triggerdata.get(list(triggerdata.keys())[0]).get('ibeam'))
    ibox     = int(triggerdata.get(list(triggerdata.keys())[0]).get('ibox'))

    return timehr,snr,dm,ibeam,ibox


if __name__=='__main__':

    parser = optparse.OptionParser(prog="filplotter",
                                   version="",
                                   usage="%prog fname datestr specnum [OPTIONS]",
                                   description="Visualize and classify filterbank data")

    parser.add_option('-s', '--slack', dest='slack', action="store_true",help="send figure to slack")
    parser.add_option('-d', '--dm', dest='dm',
                      help="DM ", default=None)
    parser.add_option('-c', '--classify', dest='classify', action="store_true",
                      help="classify using ML")    
    parser.add_option('-r', '--rficlean', dest='rficlean', action="store_true",
                      help="excise RFI from data")
    parser.add_option('-w', '--ibox', dest='ibox', type=int,
                      help="ibox found by Heimdall", default=1)
    parser.add_option('--ndm', dest='ndm', type=int, default=32, 
                      help="number of DMs for DM/time plot")
    parser.add_option('--ntime_plot', dest='ntime_plot', type=int, default=64, 
                      help="number of samples to plot")
    parser.add_option('--nfreq_plot', dest='nfreq_plot', type=int, default=32, 
                      help="number of freq channels to plot")
    parser.add_option('--save_data', dest='save_data', action='store_true',
                      help="save data to hdf5 for ML classifier training")

    options, args = parser.parse_args()
    datestr = args[0]
    specnum = args[1]

    flist = glob.glob(BASEDIR+'/T1/corr*/'+datestr+'/fil_%s/*.fil' % specnum)
    flist.sort()
    jsonfile = glob.glob(BASEDIR+'/T3/corr01/'+datestr+'/*%s*.json' % specnum)[0]
    
    timehr,snr,dm,ibeam,ibox = read_json(jsonfile)
    ibeam += 1 # hack until ibeam is figured out
#    timehr,snr,dm,ibeam,ibox=0,10,26.8,115,8
#    print('Read (FAKE) JSON file') #hack

    beamindlist = []
    for fnfil in flist:
        beamno = int(fnfil.strip('.fil').split('_')[-1])
        beamindlist.append(beamno)
        if beamno==ibeam:
            fname = fnfil
    flist_=[]

    # reorder the filename list in beam number
    for ii in range(len(flist)):
        flist_.append(flist[np.where(np.array(beamindlist)==ii)[0][0]])
    flist = flist_

    if options.slack:
        showplot=False
    else:
        showplot=True

    outstr = (specnum, dm, int(ibox), datestr, int(ibeam), timehr)
    suptitle = 'specnum:%s  DM:%0.2f  boxcar:%d \n%s ibeam:%d MJD:%f' % outstr

    fnameout = fname.replace('.fil','.png')
    figdirout = webPLOTDIR+datestr+'/candidates/'
    figdirout = './plots/'
    os.system('mkdir -p %s' % figdirout)
    fnameout = figdirout+specnum+'.png'
    
    not_real = plot_fil(fname, dm, ibox, figname_out=fnameout,
             ndm=options.ndm, suptitle=suptitle, heimsnr=snr,
             ibeam=ibeam, rficlean=options.rficlean, 
             nfreq_plot=options.nfreq_plot, 
             classify=options.classify, showplot=showplot, 
             multibeam=flist,
             heim_raw_tres=1, save_data=options.save_data)
    print(not_real)
    if options.slack and not_real==False:
        print("Sending to slack")
        slack_file = '{0}/.config/slack_api'.format(
            os.path.expanduser("~")
        )
        if not os.path.exists(slack_file):
            raise RuntimeError(
                "Could not find file with slack api token at {0}".format(
                    slack_file
                    )
            )
        with open(slack_file) as sf_handler:
            slack_token = sf_handler.read()
        client = slack.WebClient(token=slack_token);
        client.files_upload(channels='candidates',file=fnameout,initial_comment=fnameout);