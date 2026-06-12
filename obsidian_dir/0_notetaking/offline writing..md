
literature background.

since its inception, neuromorphic engineers havve been trying to develop electronics that can behave in similar ways to that of their biological counterparts upon which they have been inspired, whether that individual circuits, dedicated to implementing different models of biological components such as the leaky integrate and fire (LIF) neuron model, the architecture as a whole by changing how different neurons are connected and the number of inhibitory or excitatory neurons, or by changing the synaptic circuits and how different additional blocks are connected to them to gi e them different capabilities nad learning functionalities. This last Aspect of neuromorphic systems is of particular intereste for this paper as this paper investigates the DPI synapse.  This section is dedicated to seeing what place the DPI synapse has in the broader context of neuromorphic engineering, specifically a validation of the DPI synapse as a valid architecture for use as a synapse, what alternative silicon synapses have been proposed, how the DPI synapse can be implemented in larger architectures with other circuits for different functionalities, and laststly proposed architectures that are of interest for this paper such as multiplexing, or ....(anything else?)



ALTERNATIVE SILICON SYNAPSES

As discussed in the paper by (paper 2007) there has been a history in neuromorphic engineering for making different synapse circuit that aim to have more complex dynamics than a simple weighting transistor between the presynaptic neuron and the postsynaptic neuron. 

A small improvement to just a transistor is a pulsed current synapse, proposed in (find ref in 2007 paper). It relies on two transistors, one M_pre, and one M_w (essentially just the input branch of DPI synapse) to transmit a current signal to the postsynaptic neuron. The benefits of such a synapse is that its a very simple synaptic circuit but its drawbacks are such that it has few dynamics other than providng a weighted output current I_syn 

Improving upon the previous work, (new reference) proposed another synaptic circuit, the 

1. pulsed current synapse
2. reset and discharge synapse
3. linear charge and discharge synapse
4. current mirror integrator synapse 
5. log domain integrator synapse. 
6. DPI synapse 

DPI SYNAPSE VALIDATION

(this should also cover why the DPI synapse is better than previous silicon synapses and how it improved upon them)

The DPI synapse, first proposed back in (????when?), has been extensively tested researched for (a decade? 2?). The analytical behaviour, as derived in \ref{subsec:analytical} and explained in \cite{2007}, provides an analytical understand ing of DPI synapse, even if the nonlinear ODE describing it cannot be fully solved analytically. The circuit has been shown to have the important characteristics


VLSI ARCHITECTURES ADDED FUNCTIONALITIES (AND NON GOALS OF THE DPI)

While the DPI synapse circuit can act on its own as a synaptic connection between a presynaptic and postsynaptic neuron, there are then many different functionalities and dynamics found in biological synapses that would then not be possible to emulate. To this end it to make a more flushed out architecture (for lack of better words) it is possible to add on a variety of different extension circuits to add these functionalities. these, could include extension circuits such as STD, NMDA, and G extension circiuts as explained in further detail in \cite{2007}. They can also be other different extension circuits such as a hebbian leraning block, or (.... add a list of extension circuits espescially from the NCD lectures) 




(expand upon what these circuits are capable of, at a basic level.)

PROPOSED LARGER SCALE ARCHITECTURAL PRINCIPLES, SUCH AS MULTIPLEXING

While improving synapse circuits is important, it is important to not loose sight of the goal of building many neuromorphic systems, which is to construct a large spiking neural network capable of completing various tasks. In doing so large networks would be constructed from many of the above mentioned circuits, with chips ideally having vast numbers of neurons with an even greater number of synapses connected to them. These architectures have naturally improved over time with iterative development, from chips and designs such as (????) in ??? \cite??? to (????) in ??? \cite ????. Each time these architectures have improved there have been proposals for how to improve them and yet more on potential future improvments. some of these proposals/suggestions include things like multiplexing of synaptic circuits as mentioned in \cit{2007} and of relevance for this paper, or adding of different extension circuits to synapses to add unctionality. Previously these have of course been improved with the different

- multiplexing,
- mix of excitatory, and inhibitory by switching M_syn from pmos to nmos.
- (anything else)






NEXT SECTIONS TO WORK ON, THE METHODS AND THE RESULTS. 


Note of waning that the results thusfar are inconclusive and incomplete. 

%how much of the data processing should be in the resutls and how much of that should be in the method .
RESULTS

In the following section we will look at the results from the various experiments, mentioned in the previous methods section.
%what can I say happened??
%so basically: 
for the multiplexed and non multiplexed architectures sweeps were don of the various bias voltages. While the entire space was not investigated as that would take a lot longer for simulations the spaces that were investigated were sweeps for 2 static bias voltages and one sweeped bias voltage, as well as 1 static bias voltage and 2 sweeped bias voltages.  In figure \ref{reference figure with the bias sweep and 2 statics} V_thr, V_tau and V_w were sweeped independantly while keeping the remaining two bias voltages constant. then for each of these parameters, the a sweep was done to calculate the net charge difference that was output through I_syn from the 2DPI non multiplexed architecture vs the 1DPI multiplexed architecture. For this as seen in figure \ref{figure} there was an input spike given to input branch 1 and a second spike given to input branch 2. as shown in \ref{figure} then this resulted in two different output currentents I_syn_multiplexed and I_syn_nonmultiplexed. these currents can be seen in figure \ref{figure}.  These output currents were then integrated to compare the total charge that was transmitted through the synapse for the two architecture. The absolute difference in charge transmitted and the ratio between these tow architectures is then displayed on the graphs in figure \ref{figure}. This was done repeatedly for a range of interspike intervals between the input spike entering the synapse at channel one and the spike entering the synapse through channel 2. 

It is clear that for for instances when there is a greater from the analytical derivation earlier that when I_w >> I_\tau then then the system can be approximated to behave in a situation where it has linear dynamcis. from that we can also expect that for greater time constant V_tau there would be a greater impact of the nonlinear behaviour. We would also expect from this that when there is a lower input I_w then there would be a greater non linear effect. as for the threshold voltage, if there is a greater I_thr travelling through the differential pair (double check) then one would expect there to be a lower current that would (need to think through this) flow through M_in, thus resulting in a greater degree of nonlinear dynamics.

analysis of fig a) 

my analysis here is just wrong because I mixed up nmos and pmos. fix it 

For the case of sweeping a variety of time constant voltages,  it is clear that for when there are larger time constant voltages, then clearly there will be a greater current I_\tau. this results in system approaching the state in which I_syn >> I_gain. As a result what we see is in \ref{figure} that the greater the time constant bias voltage, the greater the degree of nonlinear effects, wheras for very small time constant there is much smaller amount, as the output spike of I_syn decays far faster as is clear in \ref{figure make new graphs showing this.} (make sure I didn't flip this the wrong way around.). Thus it is unsurprisinng that for lower time constants and for larger interspike intervals that there will be reduced nonlinear dynamics.  where in the figure we see that the ratio of the total transmitted charge is greater for highter V_tau. The simulations providing these particular outputs do not clearly show the limit of the minimum interspike interval at which the dynamics can be approximated to be linear again for large ISI's as they only look at ISI's between 0.1\mu s and 10 \mu s. later results will investigate greater ISI's in further detail. 

(double check that there was no spike overlap with how the data was generated. if there was, that my explain why the data is not monotonic, if so drop these data points. )

In a) i) 

analysis of fig b) 



analysis of fig c) 

