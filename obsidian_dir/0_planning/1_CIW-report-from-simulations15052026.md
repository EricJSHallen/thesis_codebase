Time for NDB Parsing: CPU = 402.212 ms, elapsed = 768.858 ms.  
  
Time accumulated: CPU = 545.651 ms, elapsed = 768.864 ms.  
  
Peak resident memory used = 95.7 Mbytes.  
  
  
  
Time for Elaboration: CPU = 25.741 ms, elapsed = 30.6311 ms.  
  
Time accumulated: CPU = 571.747 ms, elapsed = 802.432 ms.  
  
Peak resident memory used = 104 Mbytes.  
  
  
  
  
Notice from spectre during hierarchy flattening.  
    The value 'psf' specified for the 'checklimitdest' option will no longer be  
        supported in future releases. Use 'spectre -h' to see other recommended  
        values for the 'checklimitdest' option.  
  
  
 Start ADE Session ID: jjZq6WxQbIusBjTi  
  
  
  
Time for EDB Visiting: CPU = 1.497 ms, elapsed = 4.29893 ms.  
  
Time accumulated: CPU = 573.543 ms, elapsed = 809.713 ms.  
  
Peak resident memory used = 105 Mbytes.  
  
  
  
  
Warning from spectre during initial setup.  
    WARNING (CMI-2441): I56.M5.m1: Instance length width or area does not fit  
        the given lmax-lmin, wmax-wmin or areamax-areamin range for the model  
        'I56.M4.pemod'.  
  
    WARNING (CMI-2441): I56.M4.m1: Instance length width or area does not fit  
        the given lmax-lmin, wmax-wmin or areamax-areamin range for the model  
        'I56.M4.pemod'.  
  
    WARNING (CMI-2441): I56.M3.m1: Instance length width or area does not fit  
        the given lmax-lmin, wmax-wmin or areamax-areamin range for the model  
        'M4.nemod'.  
  
    WARNING (CMI-2441): I56.M2.m1: Instance length width or area does not fit  
        the given lmax-lmin, wmax-wmin or areamax-areamin range for the model  
        'M4.nemod'.  
  
    WARNING (CMI-2441): M2.m1: Instance length width or area does not fit the  
        given lmax-lmin, wmax-wmin or areamax-areamin range for the model  
        'M4.nemod'.  
        Further occurrences of this warning will be suppressed.  
  
  
Reading file:  
        /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/general_code/spike_train_output/st_1/241_hz/trial_1.pwl  
  
Reading file:  
        /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/general_code/spike_train_output/st_2/241_hz/trial_1.pwl  
  
  
Notice from spectre during initial setup.  
    Multithreading is disabled due to the size of the design being too small.  
  
  
  
Global user options:  
  
         psfversion = 1.4.0  
  
            vabstol = 1e-06  
  
            iabstol = 1e-12  
  
               temp = 27  
  
               gmin = 1e-12  
  
             rforce = 1  
  
           maxnotes = 5  
  
           maxwarns = 5  
  
             digits = 5  
  
               cols = 80  
  
             pivrel = 0.001  
  
           sensfile =  
        ../../../../../Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/output_single_data/st1_241_hz__st2_241_hz__trial_1/psf/sens.output  
  
     checklimitdest = psf  
  
               save = allpub  
  
             reltol = 0.001  
  
               tnom = 27  
  
             scalem = 1  
  
              scale = 1  
  
  
Scoped user options:  
  
  
Circuit inventory:  
  
              nodes 9  
  
            bsim3v3 6      
  
          capacitor 1      
  
            vsource 6      
  
  
Analysis and control statement inventory:  
  
               info 7      
  
               tran 1      
  
  
Output statements:  
  
             .probe 0      
  
           .measure 0      
  
               save 1      
  
  
Design checks inventory:  
  
          paramtest 1      
  
  
  
  
Notice from spectre during initial setup.  
    Protected devices exist and are not included in the circuit inventory.  
  
    APS enabled.  
  
    1 warning suppressed.  
  
  
Time for parsing: CPU = 13.713 ms, elapsed = 49.8769 ms.  
  
Time accumulated: CPU = 587.509 ms, elapsed = 862.366 ms.  
  
Peak resident memory used = 107 Mbytes.  
  
  
  
~~~~~~~~~~~~~~~~~~~~~~  
Pre-Simulation Summary  
~~~~~~~~~~~~~~~~~~~~~~  
  
   -   (APS) Multi-threading. The recommended number of threads is 1, consider  
        adding +mt=1 on command line.  
  
~~~~~~~~~~~~~~~~~~~~~~  
  
  
**********************************************  
Transient Analysis `tran': time = (0 s -> 1 s)  
**********************************************  
  
  
Notice from spectre during IC analysis, during transient analysis `tran'.  
    GminDC = 1 pS is large enough to noticeably affect the DC solution.  
  
        dV(Vin) = -20.5827 mV  
  
        Use the `gmin_check' option to eliminate or expand this report.  
  
Warning from spectre during IC analysis, during transient analysis `tran'.  
    WARNING (CMI-2139): I56.M5.m1: The bulk-source junction current exceeds  
        `imelt'.  The results computed by Spectre may be inaccurate because the  
        junction current model has been linearized.  
  
    WARNING (CMI-2144): I56.M5.m1: The bulk-source junction current exceeds  
        `imax'.  
  
    WARNING (CMI-2139): I56.M4.m1: The bulk-source junction current exceeds  
        `imelt'.  The results computed by Spectre may be inaccurate because the  
        junction current model has been linearized.  
  
    WARNING (CMI-2144): I56.M4.m1: The bulk-source junction current exceeds  
        `imax'.  
  
  
DC simulation time: CPU = 2.593 ms, elapsed = 7.96413 ms.  
  
  
Opening the PSFXL file  
        ../../../../../Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/output_single_data/st1_241_hz__st2_241_hz__trial_1/psf/tran.tran.tran  
        ...  
  
Important parameter values:  
  
    start = 0 s  
  
    outputstart = 0 s  
  
    stop = 1 s  
  
    step = 1 ms  
  
    maxstep = 20 ms  
  
    ic = all  
  
    useprevic = no  
  
    skipdc = no  
  
    reltol = 1e-03  
  
    abstol(V) = 1 uV  
  
    abstol(I) = 1 pA  
  
    temp = 27 C  
  
    tnom = 27 C  
  
    tempeffects = all  
  
    errpreset = moderate  
  
    method = traponly  
  
    lteratio = 3.5  
  
    relref = sigglobal  
  
    cmin = 0 F  
  
    gmin = 1 pS  
  
    rabsshort = 1 mOhm  
  
  
  
  
Notice from spectre during transient analysis `tran'.  
    Multithreading is disabled due to the size of the design being too small.  
  
  
  
Output and IC/nodeset summary:  
  
                 save   7       (current)  
  
                 save   9       (voltage)  
  
  
  
  
Warning from spectre at time = 440.026 us during transient analysis `tran'.  
  
    WARNING (CMI-2139): I56.M5.m1: The bulk-source junction current exceeds  
        `imelt'.  The results computed by Spectre may be inaccurate because the  
        junction current model has been linearized.  
  
    WARNING (CMI-2144): I56.M5.m1: The bulk-source junction current exceeds  
        `imax'.  
  
    WARNING (CMI-2139): I56.M4.m1: The bulk-source junction current exceeds  
        `imelt'.  The results computed by Spectre may be inaccurate because the  
        junction current model has been linearized.  
  
    WARNING (CMI-2144): I56.M4.m1: The bulk-source junction current exceeds  
        `imax'.  
  
Notice from spectre at time = 440.052 us during transient analysis `tran'.  
    Found trapezoidal ringing on node net1.  
  
Notice from spectre at time = 440.068 us during transient analysis `tran'.  
    Found trapezoidal ringing on node net1.  
  
Notice from spectre at time = 440.1 us during transient analysis `tran'.  
    Found trapezoidal ringing on node net1.  
  
Notice from spectre at time = 6.15339 ms during transient analysis `tran'.  
    Found trapezoidal ringing on node net1.  
  
Notice from spectre at time = 6.1534 ms during transient analysis `tran'.  
    Found trapezoidal ringing on node net1.  
        Further occurrences of this notice will be suppressed (except in log  
        file).  
  
  
    tran: time = 25.29 ms    (2.53 %), step = 442.8 us    (44.3 m%)  
  
    tran: time = 75.73 ms    (7.57 %), step = 885.7 us    (88.6 m%)  
  
    tran: time = 125.5 ms    (12.5 %), step = 885.7 us    (88.6 m%)  
  
    tran: time = 175.1 ms    (17.5 %), step = 1.771 ms     (177 m%)  
  
    tran: time = 228.7 ms    (22.9 %), step = 3.675 ms     (368 m%)  
  
    tran: time = 275.5 ms    (27.6 %), step = 922.5 us    (92.3 m%)  
  
    tran: time = 326.5 ms    (32.6 %), step = 1.845 ms     (185 m%)  
  
    tran: time = 375 ms      (37.5 %), step = 922.5 us    (92.3 m%)  
  
    tran: time = 425.2 ms    (42.5 %), step = 461.3 us    (46.1 m%)  
  
    tran: time = 475 ms      (47.5 %), step = 9.493 us     (949 u%)  
  
    tran: time = 526.9 ms    (52.7 %), step = 14.7 ms      (1.47 %)  
  
    tran: time = 586.9 ms    (58.7 %), step = 20 ms           (2 %)  
  
    tran: time = 626.9 ms    (62.7 %), step = 20 ms           (2 %)  
  
    tran: time = 686.9 ms    (68.7 %), step = 20 ms           (2 %)  
  
    tran: time = 726.9 ms    (72.7 %), step = 20 ms           (2 %)  
  
    tran: time = 786.9 ms    (78.7 %), step = 20 ms           (2 %)  
  
    tran: time = 826.9 ms    (82.7 %), step = 20 ms           (2 %)  
  
    tran: time = 886.9 ms    (88.7 %), step = 20 ms           (2 %)  
  
    tran: time = 926.9 ms    (92.7 %), step = 20 ms           (2 %)  
  
    tran: time = 983.4 ms    (98.3 %), step = 16.55 ms     (1.66 %)  
  
Number of accepted tran steps =             23559  
  
  
Notice from spectre during transient analysis `tran'.  
    Trapezoidal ringing is detected during tran analysis.  
        Please use method=trap for better results and performance.  
  
  
  
Maximum value achieved for any signal of each quantity:  
  
V: V(Vdd) = 1.8 V  
  
I: I(V1:p) = 955.9 mA  
  
If your circuit contains signals of the same quantity that are vastly different  
        in size (such as high voltage circuitry combined with low voltage  
        control circuitry), you should consider specifying global option  
        `bin_relref=yes'.  
  
  
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~  
  
Post-Transient Simulation Summary  
  
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~  
  
   -   To further speed up simulation, consider  
  
          add ++aps on command line  
  
   -   Features that may significantly slowing down simulation  
  
          iprobe = 11.76 % of total equations  
  
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~  
  
  
  
During simulation, the CPU load for active processors is :  
         0 (9.5 %)       1 (55.7 %)      2 (9.9 %)       3 (6.3 %)  
         4 (8.4 %)       5 (3.7 %)       6 (14.1 %)      7 (5.9 %)  
         8 (15.3 %)      9 (9.4 %)      10 (9.6 %)      11 (5.3 %)  
        Total: 153.1%  
  
Initial condition solution time: CPU = 2.798 ms, elapsed = 8.77905 ms.  
  
Intrinsic tran analysis time:    CPU = 974.081 ms, elapsed = 1.04032 s.  
  
Total time required for tran analysis `tran': CPU = 985.997 ms, elapsed =  
        1.08398 s, util. = 91%.  
  
Time accumulated: CPU = 1.61915 s, elapsed = 2.20126 s.  
  
Peak resident memory used = 122 Mbytes.  
  
  
  
  
Notice from spectre.  
    714 notices suppressed.  
  
  
finalTimeOP: writing operating point information to rawfile.  
  
  
Opening the PSF file  
        ../../../../../Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/output_single_data/st1_241_hz__st2_241_hz__trial_1/psf/finalTimeOP.info  
        ...  
  
modelParameter: writing model parameter values to rawfile.  
  
  
Opening the PSF file  
        ../../../../../Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/output_single_data/st1_241_hz__st2_241_hz__trial_1/psf/modelParameter.info  
        ...  
  
element: writing instance parameter values to rawfile.  
  
  
Opening the PSF file  
        ../../../../../Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/output_single_data/st1_241_hz__st2_241_hz__trial_1/psf/[element.info](http://element.info/)  
        ...  
  
outputParameter: writing output parameter values to rawfile.  
  
  
Opening the PSF file  
        ../../../../../Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/output_single_data/st1_241_hz__st2_241_hz__trial_1/psf/outputParameter.info  
        ...  
  
designParamVals: writing netlist parameters to rawfile.  
  
  
Opening the PSFASCII file  
        ../../../../../Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/output_single_data/st1_241_hz__st2_241_hz__trial_1/psf/designParamVals.info  
        ...  
  
primitives: writing primitives to rawfile.  
  
  
Opening the PSFASCII file  
        ../../../../../Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/output_single_data/st1_241_hz__st2_241_hz__trial_1/psf/primitives.info.primitives  
        ...  
  
subckts: writing subcircuits to rawfile.  
  
  
Opening the PSFASCII file  
        ../../../../../Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/output_single_data/st1_241_hz__st2_241_hz__trial_1/psf/subckts.info.subckts  
        ...  
  
Licensing Information:  
  
Lic Summary:  
[17:22:28.290155] Cdslmd [servers:5280@lic009.workspace.rug.nl](mailto:servers%3A5280@lic009.workspace.rug.nl)  
[17:22:28.290195] Feature usage summary:  
[17:22:28.290195] Virtuoso_Multi_mode_Simulation  
  
  
  
Aggregate audit (5:22:28 PM, Fri May 15, 2026):  
  
Time used: CPU = 1.67 s, elapsed = 2.38 s, util. = 70.4%.  
  
Time spent in licensing: elapsed = 72.2 ms.  
  
Peak memory used = 123 Mbytes.  
  
Simulation started at: 5:22:26 PM, Fri May 15, 2026, ended at: 5:22:28 PM, Fri  
        May 15, 2026, with elapsed time (wall clock): 2.38 s.  
  
spectre completes with 0 errors, 13 warnings, and 15 notices.  
  
INFO (ADE-3071): Simulation completed successfully.  
reading simulation data...  
      ...successful.  
WARNING (PRINT-1048): Printing can become very slow because the data exceeds 10000 points. You can  
             cancel this command and print the data to a file using the command i("/I56/Iout" ?resultsDir "/home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/output_single_data/st1_241_hz__st2_241_hz__trial_1" ?result "tran") v("/vpre" ?resultsDir "/home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/output_single_data/st1_241_hz__st2_241_hz__trial_1" ?result "tran") v("/vpre1" ?resultsDir "/home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/output_single_data/st1_241_hz__st2_241_hz__trial_1" ?result "tran") ?output "./myOutFile" ?numberNotation 'none).  
Finished: st1_241_hz__st2_241_hz__trial_1  
Finished all simulations.  
Manifest written to: /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/output_single_data/run_manifest.csv  
Output base directory: /home/s5117909/Documents/thesis/sebastian_thesis_repo/processing/cadence_extraction/output_single_data  
t  
INFO (SCH-1170): Extracting "synapsedualinputtb schematic"  
INFO (SCH-1426): Schematic check completed with no errors.  
INFO (SCH-1181): "sebastian_thesis_pilot synapsedualinputtb schematic" saved.  
INFO (SCH-1170): Extracting "dynapsetb1 schematic"  
INFO (SCH-1426): Schematic check completed with no errors.  
INFO (SCH-1181): "sebastian_thesis_pilot dynapsetb1 schematic" saved.