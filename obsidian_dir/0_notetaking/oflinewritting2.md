
things that I need to work on. 

finish up and polish bio emulation portion of theory 
finish up and polish the literature review section of the report. 
rewrite the methodology, make sure to include equations that describe the methods that I used for the processing. 
write up a more detailed and complete results section for the results that I do have, and then write up a discussion component. I think the discussion comp I can do rn.

finally put in the conclusions component. also add an error analysis component at the end that goes in the appendix A and then I can put extra graphs and everything in appendix B maybe I can make a "appendix C" which is just notes of to does and such that I need to do.







%explain for multiplexed set up why we have to have multiple input branches 

%linear superposition principle of current from kirchoffs circuit laws.


In this paper the DPI synapse circuits that will be investigated are shown in Fig~\ref{fig:non-multiplexedsetup} and Fig~\ref{fig:multiplexedsetup}. The former of these two is the non multiplexed setup where there are two seperate DPI synapses that have a connected output. By Kirchhoff's circuit laws we know that the output current signal is simply a linear superposition of the synaptic currents, $I_\mathrm{out, non-multiplexed} =  I_\mathrm{syn1} + I_\mathrm{syn2}$ .    The latter of these two set ups is the multiplexed architecture. For this circuit, there are two input branches that are both connected to the differential pair component of the DPI. Under these conditions $I_\mathrm{out, multiplexed} = I_\mathrm{syn}$. Due to the non-linear dynamics of the circuit equation describing a DPI synapse, as expanded upon further in Section~\ref{analytical} $I_\mathrm{out, non-multiplexed} \neq I_\mathrm{out, multiplexed}$ generally. The purpose of this paper, as explained in Section~\ref{introduction} is to understand under what regimes of $V_\mathrm{w}$, $V_\mathrm{thr}$, $V_\tau$ and mean frequency $\nu$ of input spikes or ISIs for $V_\mathrm{pre,1}$ and $V_\mathrm{pre,2}$  the DPI maintains linear approximately linear dynamics and hence  $I_\mathrm{out, non-multiplexed} \approx I_\mathrm{out, multiplexed}$.  For The multiplexed setup it is important to remember that two input branches are required as the input voltage signals of $V_\mathrm{pre,1}$ and $V_\mathrm{pre,2}$ cannot share the same connection.




METHOD %this is where I should include the mathematical calculations that I put into python in order to make the data that I was using. 




RESULTS
%is there a more technical term for this than heatmap
...

From this data several heatmap plots were made. The first of these \ref{} shows the absolute difference in the charge transferred. This plot is mostly as one would expect where for high $V_\tau$ and low $V_\mathrm{thr}$ there was a greater difference in the net amount of charge transferred. This is logical as when there is a lower threshold, more current will flow through the transistor $M_\mathrm{in}$. As more current flows through this, then there will be a greater output signal, and the total charge difference will be more pronounced, even if the ratio between the output charge of the two setups qualitatively "small" compared to other domains. It also makes sense, as that there would be more charge transfer for greater $V_\tau$  because as there is a greater time constant, there will be less current flowing through $M_\tau$. this means that the capacitor will charge more slowly, the voltage $V_\mathrm{syn}$ will increase slower, and as a result there will be a more drawn out output signal with greater total charge transfer at $I_\mathrm{syn}$. 


HEATMAPS

The more interesting of the data is that displayed in the second and third heatmaps Fig~\ref{} and Fig~\ref{}. this show the ratio between the integrated  charge for the former, and the inverse of this for the latter. For understanding under which domains we can approximate the multipelexed set up as the non multiplexed set up, this metric is far more useful. These graphs show the percentage difference, or ratio between the total output charge for the non multiplex and multiplexed set ups for various Vtau and Vthr. We can then apply a mask to these heatmaps as seen in Fig~\ref{} In here a mask has been applied (black) to show the domain at which the multiplexed set up total charge transfer is below a tolerance threshold (here chosen as 20%, relatively arbitrarily). See appendix A for 3d heatmaps that represent the ratio as the of transmitted charge as the ISI increases. 
%explenation of how this was repeated for both of the other dual bias sweeps as well
MAX ISI

To approximate the ISIs at which the multiplexed set up is valid and the associated mean frequency, the curve plotting the ratio between the two setups against the interspike interval was extrapolated, for the different combinations of bias voltages. From this extrapolation the estimated ISI time at which the ratio crossed a tolerance threshold (again chosen as 20%). The result of this extrapolation is shown in ref fig heatmap where as, would be expected from the previous heatmaps, the domains which have the greatest degree of nonlinear effects are the domains that require the longest ISIs before the multiplexed set up can be approximated as maintaining linear dynamics. 
%explenation of how this was rrepeated for both the other dual bias sweeps. 







DISCUSSION (INIT COPY PASTE FROM OVERLEAF.)



%ok so now here in the discussion and need to discuss that was the point of all of this research and why does it matter. lets put it in bullet points.

%The primary finding is that this characterises, the minimum conditions that are needed in order to have the DPI synapse act in the linear domain. 

%Under the condition that vw vtau or vthr are these static biases and the capacitance is set to this with these transistor sizes, then we can say that the synapse maintains linear dynamics under these particular domains. 

%this is for two spikes and the spacing or biases that they need. this can be extrapolated to give an approximate of the max mean frequency at which you can have a multiplexed set up before it starts to have nonlinear dynamics. 



%URGENT PROBLEM, WHILE I THINK SOME OF THE DYNAMICS IN THE GRAPHS REMAIN VALID, THERES A PROBLEM. for greater ISI's I forgot to dynamically adjust or callibrate the transient stop time. which means that the later data is not as valid as some area is being cut off. and for some of the other data entire spikes were just not included due to this bug. 

so the major points that I need to put in the discussion.

%Discuss valid domains for the dual bias sweeps and the static sweeps in which we can approximate having a linear domain. (i.e. make 1d heatmaps for the highly detailed data.)  ref tables in appendix with more precise domains

%discuss that this is just a set up with two synapses and the majority of simulations were only done with 2 input spikes, discuss then that extrapolating from that we would expect the mean input spike frequency to decrease that we can have and maintain linear dynamics as we increase the number of input branches

As is clear this paper has only investigated the case when there are two synapses that are being multiplexed. In more more realistic architectures there are going to be far more than just two synapses that are connected to a singular output synapse. Hence Ideally it makes sense to multiplex more than two DPIs. The linear domain n multiplexed synapses could be extrapolated from the data from this paper. However, an exptrapolation, can only act as a poor substitute for a proper investigation, of a multiplexed system with more synapses. %maybe  mention ISI and mean spike frequency. 

%Discuss that there were some anomalies in the simulationos, such as that weird pixel that just wouldnt go away and I don't know why. 

From the simulation, there were some outputs that were anomolous, and difficult to explain. In particular for this the ratio of the charge for Vtau = and Vthr = . this value deviates from what would be expected, with both the charge transfer and the ratio much higher than the adjacent bias voltage domain. It is unclear whether this is some fluke of the experiment, or if there is a strange behaviour that occurs at exactly these bias voltages.

%discuss that the simulation was done with ++aps and multithreading 4 to speed up the simulation but it still took a long time. (attempted to make shell scripts to speed up the workflow. took too much time to develop, so that attempt was abandoned after only moderate success). discuss that ++aps is a cadence mode that increases the simulation speed but reduces the accuracy (it was necessary considering the  low res simulations still took 5-7h with it on). unclear from cadence documentation on the exact impact it would have on the simulations.

As mention in the method, the cadence simulations that were run used a flag ++aps. Due to unclear documentation, only this flag was used and not ++aps="liberal,moderate,conservative". ++aps \cite{https://community.cadence.com/cadence_blogs_8/b/cic/posts/spectre-optimizing-spectre-aps-performance}. it was unclear what mode ++aps defaults too, and thus it is unclear how much of an accuracy degradation there was due to its usage in some of the simulations. Regardless, turning off ++aps would improve the accuracy of the simulations. Another issue when running these circuit simulations was that it was unclear from documentation how to get multiple parallel instances of cadence running when relying on oceanscripts rather than using the built in system in the GUI that was incompatible for this papers approach to running simulations. As a result, an attempt was made to produce some shell scripts to automate a process for running parallel virtuoso SPECTRE simulations. This proved possible, but ultimately unsuccessful as debugging, and getting the scripts to cooperate with encrypted proprietary software turned out to be too time consuming and thus would not be able to be fully developed in a short time frame.  As a result of or in spite of all of this, the granular simulations that were run took in the order of 5 to 7 hours to run. Hence there was a limitation to the possible parameter sweeps that were possible simply because of time constraints. 


%discuss that the resolution of the paramaters had to be set low, becuase the simulations took a very long time. discuss the cutoff transient time of the simulations.

Because of some of the issues mentioned above, the simulations that were done also had to use a relatively short transient cutoff time, 20us, to reduce the simulation times.  the resuult of this is that the simulations were sometimes cut off before the Isyn had fully decayed. this again provides some degree of uncertainty. %discuss approach for quantifying the uncertainty


%Discuss that this was a very small possible parameter space that was investigated, and that it was extrapolated from there. 

Because of the short transient window that was simulated, the results were extrapolated as previously discussed. This could again provide an indication 


%Discuss that this also only does the most basic set up of looking at potential multiplexing for 2 DPI synapses and doesn't look at more than that.

%Discuss that this was done for 2 input spikes and extrapolated from there poisson distributions were not used, as they proved to be too computationally heavy, and previously mentioned parallelisation fell through.

%Discuss that approximations were made during the analytical derivation, so the analytical derivation (in particular relating to the differential branch isn't quite valid.)

%Discuss that these were simulations, and so that ultimately it cannot be entirely validated if these results could be reproduced on a physical chip.

%Discuss the error propogation., that the error in this was based on the selected mode in the simulation. 





