15052026 simulation discussion:
parameters likely incorrect [[1_CIW-report-from-simulations15052026]]:  
- warning of high current/melting transistors, 
- input spike voltage == 1.8, probably should reduce, multiple spikes increase voltage further, but in supra threshold regime have approx same effect as a wider 1.8V spike.

Simulations (i)
1) Run simulation with lower input spike voltage.
2) figure out how to do montecarlo simulations with ocean script
3) figure out how to use more jobs when using .ocn script to reduce simulation time
4) figure out what parameters we want for the circuit, (analytically)
5) how to use said 4) params to optimize W,L. 
6) set up script, or program to optimize W,L and use provided outputs for base setting around which I can use a monte carlo for simulations.
7) add randomness to voltage of input spike.
8) make sure to use seed for next simulations for reproducible results
9) generalize my programs to work for comparing n input synapses to 1 input synapse. 
10) for 9) make a testbench with array of synapses, variable number that can be altered by .ocn script.

Processing (ii)
1) write a script that integrates the difference between what is expected and what is found between 1syn 2 input and (1syn 1 input)x2, make it generalised for n_syn, m_inputs
2) write a script, or modify python script to adjust spiketrain files to be of the same dimensions to simplify data processing (likely to do it for output csv's as spectre simulation will add new data points.)
3) write a script that plots a view of syn_1_frequency syn_2_frequency and display spike train overlap (heatmap.) generalise to n dimensions (where n is the number of synapses)
4) similar to 3) write a s

Analytical work (iii)
1) derive approximate outcomes?
2) general analytical analysis?

Report writing (iv)
1) write down some methods
2) write down introduction

Literature(v)
1) read following papers:
2) read a little about early voltage 

extras (vi)
1) if possible switch uni computer to Ubuntu to make it easier to use, ask vincent

questions(vii)
1) why is there noise in my data after the first simultaneous spike? nevermind theres noise at every spike
2) decrease noise by increasing spike magnitude.
