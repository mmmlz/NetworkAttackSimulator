import math
import random
import networkx as nx
import tkinter as Tk
from prettytable import PrettyTable

# import order important here
import matplotlib
matplotlib.use('TkAgg')
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg     # noqa E402
import matplotlib.pyplot as plt         # noqa E402
import matplotlib.patches as mpatches   # noqa E402

# Agent node in graph
AGENT = (0, 0)

# Colors and symbols for describing state of host
COLORS = ['yellow', 'orange', 'magenta', 'green', 'blue', 'red', 'black']
SYMBOLS = ['C', 'R', 'S', 'c', 'r', 'o', 'A']


class Viewer:
    """A class for visualizing the network state from NASimEnv"""

    def __init__(self, network):
        """
        Arguments
        ---------
        network : Network
            network of environment
        """
        self.network = network
        self.subnets = self._get_subnets(network)
        self.positions = self._get_host_positions(network)

    def render_graph(self, state, ax=None, show=False, width=5, height=6):
        """Render graph structure representing network that can be then be
        visualized

        Arguments
        ---------
        state : State
            state of network user wants to view (Typically will be initial state)
        ax : Axes
            matplotlib axis to plot graph on, or None to plot on new axis
        show : bool
            whether to display plot, or simply construct plot
        width : int
            width of GUI window
        height : int
            height of GUI window
        """
        G = self._construct_graph(state)
        colors = []
        labels = {}
        for n in list(G.nodes):
            colors.append(G.nodes[n]["color"])
            labels[n] = G.nodes[n]["label"]

        if ax is None:
            fig = plt.figure(figsize=(width, height))
            ax = fig.add_subplot(111)
        else:
            fig = ax.get_figure()

        nx.draw_networkx_nodes(G, self.positions, node_size=1000, node_color=colors, ax=ax)
        nx.draw_networkx_labels(G, self.positions, labels, font_size=10, font_weight="bold")
        nx.draw_networkx_edges(G, self.positions)
        ax.axis('off')
        ax.set_xlim(left=0.0, right=100.0)
        # ax.set_ylim(bottom=0.0, top=100.0)

        legend_entries = EpisodeViewer.legend(compromised=False)
        ax.legend(handles=legend_entries, fontsize=12, loc=2)

        if show:
            fig.tight_layout()
            plt.show()
            plt.close(fig)

    def render_episode(self, episode, width=7, height=5):
        """Display an episode from Cyber Attack Simulator Environment in a seperate
        window. Where an episode is a sequence of (state, action, reward, done)
        tuples generated from interactions with environment.

        Arguments
        ---------
        episode : list
            list of (State, Action, reward, done) tuples
        width : int
            width of GUI window
        height : int
            height of GUI window
        """
        init_ep_state = episode[0][0]
        G = self._construct_graph(init_ep_state)
        EpisodeViewer(episode, G, self.network.sensitive_hosts, width, height)

    def render_readable(self, obs):
        """Print a readable tabular version of observation to stdout

        Arguments
        ---------
        obs : Observation
            observation to view
        """
        host_obs = []
        for host_num, (host_addr, host) in enumerate(self.network.hosts.items()):
            host_obs_vector = obs.tensor[host_num]
            readable_dict = {"Host Address": host_addr}
            readable_dict.update(host.get_readable(host_obs_vector))
            host_obs.append(readable_dict)

        headers = list(host_obs[0].keys())
        table = PrettyTable(headers)
        for host in host_obs:
            row = [str(host[k]) for k in headers]
            table.add_row(row)
        print(table)

    def render_asci(self, obs):
        """Render observation in ASCI format to stdout

        Arguments
        ---------
        state : State
            state of network user wants to view (Typically will be initial state)
        """
        sensitive_hosts = self.network.sensitive_hosts
        subnets = [[] for x in range(len(self.subnets))]
        for m in self.network.address_space:
            subnets[m[0]].append(get_host_representation(obs, sensitive_hosts, m, SYMBOLS))

        max_row_size = max([len(x) for x in subnets])
        min_row_size = min([len(x) for x in subnets])

        output = "-----------------------------"
        for i, row in enumerate(subnets):
            output += "\nsubnet {0}: ".format(i)
            output += " " * ((max_row_size - len(row)) // 2)
            for col in row:
                output += col
            output += "\n"
            if i < len(subnets) - 1:
                n_spaces = (max_row_size - min_row_size) // 2
                output += " " * (len("subnet X: ") + n_spaces) + "|"
        output += "-----------------------------\n\n"

        print(output)

    def _construct_graph(self, state):
        """Create a network graph from the current state

        Arguments
        ---------
        state : State
            current state of network

        Returns
        -------
        G : Graph
            NetworkX Graph representing state of network
        """
        G = nx.Graph()
        sensitive_hosts = self.network.sensitive_hosts

        # Create a fully connected graph for each subnet
        for subnet in self.subnets:
            for m in subnet:
                node_color = get_host_representation(state, sensitive_hosts, m, COLORS)
                node_pos = self.positions[m]
                G.add_node(m, color=node_color, pos=node_pos, label=str(m))
            for x in subnet:
                for y in subnet:
                    if x == y:
                        continue
                    G.add_edge(x, y)

        # Retrieve first host in each subnet
        subnet_prime_nodes = []
        for subnet in self.subnets:
            subnet_prime_nodes.append(subnet[0])
        # Connect connected subnets by creating edge between first host from each subnet
        for x in subnet_prime_nodes:
            for y in subnet_prime_nodes:
                if x == y:
                    continue
                if self.network.subnets_connected(x[0], y[0]):
                    G.add_edge(x, y)

        return G

    def _get_host_positions(self, network):
        """Get list of positions for each host in episode

        Arguments
        ---------
        network : Network
            network object describing network configuration of environment
            episode was generated from
        """
        address_space = network.address_space
        depths = network.get_subnet_depths()
        max_depth = max(depths)
        # list of lists where each list contains subnet_id of subnets with same depth
        subnets_by_depth = [[] for i in range(max_depth + 1)]
        for subnet_id, subnet_depth in enumerate(depths):
            if subnet_id == 0:
                continue
            subnets_by_depth[subnet_depth].append(subnet_id)

        # max value of position in figure
        max_pos = 100
        # for spacing between rows and columns and spread of nodes within subnet
        margin = 10
        row_height = max_pos / (max_depth + 1)

        # positions are randomly assigned within regions of display based on subnet number
        positions = {}
        for m in address_space:
            m_subnet = m[0]
            m_depth = depths[m_subnet]
            # row is dependent on depth of subnet
            row_max = max_pos - (m_depth * row_height)
            row_min = max_pos - ((m_depth + 1) * row_height)
            # col width is dependent on number of subnets at same depth
            num_cols = len(subnets_by_depth[m_depth])
            col_width = max_pos / num_cols
            # col of host dependent on subnet_id relative to other subnets of same depth
            m_col = subnets_by_depth[m_depth].index(m_subnet)
            col_min = m_col * col_width
            col_max = (m_col + 1) * col_width
            # randomly sample position of host within row and column of subnet
            col_pos, row_pos = self._get_host_position(m, positions, address_space, row_min,
                                                       row_max, col_min, col_max, margin)
            positions[m] = (col_pos, row_pos)

        # get position of agent, which is just right of host first host in network
        first_m_pos = positions[address_space[0]]
        agent_row = first_m_pos[1]
        agent_col = min(first_m_pos[0] + margin * 4, max_pos - margin)
        positions[AGENT] = (agent_col, agent_row)

        return positions

    def _get_host_position(self, m, positions, address_space, row_min, row_max,
                           col_min, col_max, margin):
        """Get the position of m within the bounds of (row_min, row_max, col_min, col_max)
        while trying to make the distance between the positions of any two hosts in the
        same subnet greater than some threshold.
        """
        subnet_hosts = []
        for other_m in address_space:
            if other_m == m:
                continue
            if other_m[0] == m[0]:
                subnet_hosts.append(other_m)

        threshold = 8
        col_margin = (col_max - col_min) / 4
        col_mid = col_max - ((col_max - col_min) / 2)
        m_y = random.uniform(row_min + margin, row_max - margin)
        m_x = random.uniform(col_mid - col_margin, col_mid + col_margin)

        # only try 100 times
        good = False
        n = 0
        while n < 100 and not good:
            good = True
            m_x = random.uniform(col_mid - col_margin, col_mid + col_margin)
            m_y = random.uniform(row_min + margin, row_max - margin)
            for other_m in subnet_hosts:
                if other_m not in positions:
                    continue
                other_x, other_y = positions[other_m]
                dist = math.hypot(m_x - other_x, m_y - other_y)
                if dist < threshold:
                    good = False
                    break
            n += 1
        return m_x, m_y

    def _get_subnets(self, network):
        """Get list of hosts organized into subnets

        Arguments
        ---------
        network : Network
            the environment network

        Returns
        -------
        list[list[(int, int)]]
            addresses with each list containing hosts on same subnet
        """
        subnets = [[] for i in range(network.get_number_of_subnets())]
        for m in network.address_space:
            subnets[m[0]].append(m)
        # add internet host
        subnets[0].append(AGENT)
        return subnets


class EpisodeViewer:
    """Displays sequence of observations from NASimEnv in a seperate window"""

    def __init__(self, episode, G, sensitive_hosts, width=7, height=7):
        self.episode = episode
        self.G = G
        self.sensitive_hosts = sensitive_hosts
        # used for moving between timesteps in episode
        self.timestep = 0
        self._setup_GUI(width, height)
        # draw first observation
        self._next_graph()
        # Initialize GUI drawing loop
        Tk.mainloop()

    def _setup_GUI(self, width, height):
        """Setup all the elements for the GUI for displaying the network graphs.

        Initializes object variables:k
            Tk root : the root window for GUI
            FigureCanvasTkAgg canvas : the canvas object to draw figure onto
            Figure fig : the figure that holds axes
            Axes axes : the matplotlib figure axes to draw onto
        """
        # The GUI root window
        self.root = Tk.Tk()
        self.root.wm_title("Cyber Attack Simulator")
        self.root.wm_protocol("WM_DELETE_WINDOW", self._close)
        # matplotlib figure to house networkX graph
        self.fig = plt.figure(figsize=(width, height))
        self.axes = self.fig.add_subplot(111)
        self.fig.tight_layout()
        self.fig.subplots_adjust(top=0.8)
        # a tk.DrawingArea
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.root)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(side=Tk.TOP, fill=Tk.BOTH, expand=1)
        # buttons for moving between observations
        back = Tk.Button(self.root, text="back", command=self._previous_graph)
        back.pack()
        next = Tk.Button(self.root, text="next", command=self._next_graph)
        next.pack()

    def _close(self):
        plt.close('all')
        self.root.destroy()

    def _next_graph(self):
        if self.timestep < len(self.episode):
            t_state = self.episode[self.timestep][0]
            self.G = self._update_graph(self.G, t_state)
            self._draw_graph(self.G)
            self.timestep += 1

    def _previous_graph(self):
        if self.timestep > 1:
            self.timestep -= 2
            self._next_graph()

    def _update_graph(self, G, state):
        # update colour of each host in network as necessary
        for m in list(G.nodes):
            if m == AGENT:
                continue
            node_color = get_host_representation(state, self.sensitive_hosts, m, COLORS)
            G.nodes[m]["color"] = node_color
        return G

    def _draw_graph(self, G):
        pos = {}
        colors = []
        labels = {}
        for n in list(G.nodes):
            colors.append(G.nodes[n]["color"])
            labels[n] = G.nodes[n]["label"]
            pos[n] = G.nodes[n]["pos"]

        # clear window and redraw graph
        self.axes.cla()
        nx.draw_networkx_nodes(G, pos, node_color=colors, node_size=1500, ax=self.axes)
        nx.draw_networkx_labels(G, pos, labels, font_size=12, font_weight="bold")
        nx.draw_networkx_edges(G, pos)
        plt.axis('off')
        # generate and plot legend
        # legend_entries = self.legend()
        # plt.legend(handles=legend_entries, fontsize=16)
        # add title
        state, action, reward, done = self.episode[self.timestep]
        if done:
            title = "t = {0}\nGoal reached\ntotal reward = {1}".format(self.timestep, reward)
        else:
            title = "t = {0}\n{1}\nReward = {2}".format(self.timestep, action, reward)
        ax_title = self.axes.set_title(title, fontsize=16, pad=10)
        ax_title.set_y(1.05)

        xticks = self.axes.get_xticks()
        yticks = self.axes.get_yticks()
        # shift half a step to the left
        xmin = (3*xticks[0] - xticks[1])/2.
        ymin = (3*yticks[0] - yticks[1])/2.
        # shaft half a step to the right
        xmax = (3*xticks[-1] - xticks[-2])/2.
        ymax = (3*yticks[-1] - yticks[-2])/2.

        self.axes.set_xlim(left=xmin, right=xmax)
        self.axes.set_ylim(bottom=ymin, top=ymax)
        # self.fig.savefig("t_{}.png".format(self.timestep))
        self.canvas.draw()

    @staticmethod
    def legend(compromised=True):
        """
        Manually setup the display legend
        """
        a = mpatches.Patch(color='black', label='Agent')
        s = mpatches.Patch(color='magenta', label='Sensitive (S)')
        c = mpatches.Patch(color='green', label='Compromised (C)')
        r = mpatches.Patch(color='blue', label='Reachable (R)')
        legend_entries = [a, s, c, r]
        if compromised:
            sc = mpatches.Patch(color='yellow', label='S & C')
            sr = mpatches.Patch(color='orange', label='S & R')
            o = mpatches.Patch(color='red', label='not S, C or R')
            legend_entries.extend([sc, sr, o])
        return legend_entries


def get_host_representation(state, sensitive_hosts, m, representation):
    """Get the representation of a host based on current state

    Arguments
    ---------
    state : State
        current state
    sensitive_hosts : list
        list of addresses of sensitive hosts on network
    m : (int, int)
        host address
    representation : list
        list of different representations (e.g. color or symbol)

    Returns
    -------
    str
        host color
    """
    # agent not in state so return straight away
    if m == AGENT:
        return representation[6]
    compromised = state.compromised(m)
    reachable = state.reachable(m)
    sensitive = m in sensitive_hosts
    if sensitive:
        if compromised:
            output = representation[0]
        elif reachable:
            output = representation[1]
        else:
            output = representation[2]
    elif compromised:
        output = representation[3]
    elif reachable:
        output = representation[4]
    else:
        output = representation[5]
    return output
