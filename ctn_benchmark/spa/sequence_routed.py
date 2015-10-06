"""
Nengo Benchmark Model: SPA Sequence

Given no input, the model will cycle between cortical states using a
basal ganglia and thalamus.
"""

import split

'''
def gather_info(network, inputs, outputs, parents):
    for c in network.connections:
        if c.post_obj not in inputs:
            inputs[c.post_obj] = [c]
        else:
            inputs[c.post_obj].append(c)
        if c.pre_obj not in outputs:
            outputs[c.pre_obj] = [c]
        else:
            outputs[c.pre_obj].append(c)
        parents[c] = network
    for ens in network.ensembles:
        parents[ens] = network
    for n in network.nodes:
        parents[n] = network
    for net in network.networks:
        parents[net] = network
        gather_info(net, inputs, outputs, parents)

def split_passthrough(model, max_dim=16):
    inputs = {}
    outputs = {}
    parents = {}
    gather_info(model, inputs, outputs, parents)

    changed = True

    while changed:
      changed = False
      for node in model.all_nodes[:]:
        if node.output is None:
            if node.size_in > max_dim:
                changed = True
                nodes = []
                slices = []
                index = 0
                while index < node.size_in:
                    label = node.label
                    if label is not None:
                        label += ' (%d)' % len(nodes)
                    size = min(node.size_in - index, max_dim)
                    with parents[node]:
                        new_node = nengo.Node(None, size_in=size, label=label)
                        parents[new_node] = parents[node]
                        inputs[new_node] = []
                        outputs[new_node] = []
                    slices.append(slice(index, index + size))
                    nodes.append(new_node)
                    index += size

                for c in inputs[node][:]:
                    base_transform = c.transform
                    if len(base_transform.shape) == 0:
                        base_transform = np.eye(c.size_mid) * base_transform
                    transform = np.zeros((node.size_in, c.size_in))
                    transform[c.post_slice] = base_transform

                    for i, n in enumerate(nodes):
                        t = transform[slices[i]]
                        if np.count_nonzero(t) > 0:
                            with parents[c]:
                                new_c = nengo.Connection(c.pre, n,
                                                 transform=t,
                                                 synapse=c.synapse)
                                inputs[n].append(new_c)
                                outputs[c.pre_obj].append(new_c)
                                parents[new_c] = parents[c]
                    outputs[c.pre_obj].remove(c)
                    inputs[node].remove(c)
                    parents[c].connections.remove(c)

                for c in outputs[node][:]:
                    base_transform = c.transform
                    if len(base_transform.shape) == 0:
                        base_transform = np.eye(c.size_mid) * base_transform
                    transform = np.zeros((c.size_out, node.size_out))
                    transform[:, c.pre_slice] = base_transform

                    for i, n in enumerate(nodes):
                        t = transform[:, slices[i]]
                        if np.count_nonzero(t) > 0:
                            with parents[c]:
                                new_c = nengo.Connection(n, c.post,
                                                 transform=t,
                                                 synapse=c.synapse)
                                outputs[n].append(new_c)
                                inputs[c.post_obj].append(new_c)
                                parents[new_c] = parents[c]
                    inputs[c.post_obj].remove(c)
                    outputs[node].remove(c)
                    parents[c].connections.remove(c)

                parents[node].nodes.remove(node)

'''





import ctn_benchmark
import numpy as np
import nengo
import nengo.spa as spa

class SPASequenceRouted(ctn_benchmark.Benchmark):
    def params(self):
        self.default('dimensionality', D=32)
        self.default('number of actions', n_actions=5)
        self.default('time to simulate', T=1.0)
        self.default('starting action', start=0)

    def model(self, p):
        model = spa.SPA()
        with model:
            model.vision = spa.Buffer(dimensions=p.D)
            model.state = spa.Memory(dimensions=p.D)
            actions = ['dot(state, S%d) --> state=S%d' % (i,(i+1))
                       for i in range(p.n_actions - 1)]
            actions.append('dot(state, S%d) --> state=vision' %
                           (p.n_actions - 1))
            model.bg = spa.BasalGanglia(actions=spa.Actions(*actions))
            model.thal = spa.Thalamus(model.bg)

            model.input = spa.Input(vision='S%d' % p.start)

            self.probe = nengo.Probe(model.thal.actions.output, synapse=0.03)
        split.split_passthrough(model)

        return model

    def evaluate(self, p, sim, plt):
        sim.run(p.T)
        self.record_speed(p.T)

        index = int(0.05 / p.dt)  # ignore the first 50ms
        best = np.argmax(sim.data[self.probe][index:], axis=1)
        times = sim.trange()
        change = np.diff(best)
        change_points = np.where(change != 0)[0]
        intervals = np.diff(change_points * p.dt)

        best_index = best[change_points][1:]
        route_intervals = intervals[np.where(best_index == p.n_actions-1)[0]]
        seq_intervals = intervals[np.where(best_index != p.n_actions-1)[0]]

        data = sim.data[self.probe][index:]
        peaks = [np.max(data[change_points[i]:change_points[i+1]])
                 for i in range(len(change_points)-1)]

        if plt is not None:
            plt.plot(times, sim.data[self.probe])
            plt.plot(times[index + 1:], np.where(change!=0,1,0))

            for i, peak in enumerate(peaks):
                plt.hlines(peak, times[change_points[i] + index],
                                  times[change_points[i+1] + index])



        return dict(period=np.mean(seq_intervals),
                    period_sd=np.std(seq_intervals),
                    route_period=np.mean(route_intervals),
                    route_period_sp=np.std(route_intervals),
                    peak=np.mean(peaks), peak_sd=np.std(peaks))

if __name__ == '__main__':
    SPASequenceRouted().run()
