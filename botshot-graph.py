from graphviz import Digraph
import importlib, importlib.util, os.path
import re
import yaml
import random
import inspect
import argparse
import django
import sys
import json


def module_from_file(module_name, filepath):
    """
	Gets certain module from given file.

	Args:
		module_name: Name of wanted module.
		filepath: Path to the file of module.

	Returns:
		Module.
	"""

    spec = importlib.util.spec_from_file_location(module_name, filepath)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    return module


def generate_colors(n):
    """
	Generates n colors.

	Args:
		n: Count of colors to generate.

	Returns:
		Generated colors in hexadecimal form.
	"""

    colors = []
    r = int(random.random() * 256)
    g = int(random.random() * 256)
    b = int(random.random() * 256)
    step = 256 / n

    for i in range(n):
        r += step
        g += step
        b += step
        r = int(r) % 256
        g = int(g) % 256
        b = int(b) % 256
        colors.append('#%02x%02x%02x' % (r, g, b))

    return colors


def remove_comments(source_code):
    """
	Removes comments from provided Python source code.

	Args:
		source_code: Python source code to remove comments from.

	Returns:
		Source code without comments.
	"""

    # Remove multi-line comments (''' COMMENT ''')
    to_return = re.sub(re.compile("'''.*?'''", re.DOTALL), "", source_code)
    # Remove multi-line comments (""" COMMENT """)
    to_return = re.sub(re.compile("\"\"\".*?\"\"\"", re.DOTALL), "", to_return)
    # Remove single-line comments (# COMMENT)
    to_return = re.sub(re.compile("#.*?\n"), "", to_return)

    return to_return


class GraphPlot:
    """
	Class for plotting chatbot's graph.
	"""

    def __init__(self, bot_filepath, bot_name, graph_filepath, json_filepath):
        """
        :param bot_filepath:    django project root
        :param bot_name:        optional - name of django app containing bot (can differ from django project name)
        :param graph_filepath:  where to save generated graph
        """
        self.bot_filepath = bot_filepath
        # Add last backslash if needed
        if not self.bot_filepath.endswith('/'):
            self.bot_filepath += '/'

        self.graph_filepath = graph_filepath
        self.json_filepath = json_filepath
        self.bot_name = bot_name or self.bot_filepath.split('/')[-2]

        self.graph = None
        self.flows = None
        self.json = None

        # Django setup
        sys.path.append(self.bot_filepath)
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', self.bot_name + '.settings')
        django.setup()

        # Constants
        self.flow_keyword = 'BOTS'
        self.default_color = '#FFFFFF'
        self.initial_flow = 'default'
        self.initial_state = 'root'
        self.json_edge_value = 3

    def state_indetifier(self, flow_name, state_name):
        """
		Returns state identifier from provided flow and state names.

		Args:
			flow_name: Name of the flow.
			state_name: Name of the state.

		Returns:
			State identifier.
		"""

        return flow_name + '.' + state_name

    def flow_and_state(self, current_flow, state):
        """
		Returns flow and state from provided state.

		Args:
			current_flow: Current flow (used in case of relative state).
			state: Relative or absolute state.

		Returns:
			Flow and state.
		"""

        # Check flows
        assert self.flows, 'Flows has not been initialized.'

        flow = None

        # Absolute state
        for fl in self.flows:
            if state.startswith(fl + '.'):
                state = state[len(fl) + 1:]
                flow = fl

        # Relative state
        if not flow:
            flow = current_flow

        return flow, state

    def create_graph_nodes(self, colorful, flow_data):
        """
		Creates graph nodes from chatbot's flows.

		Args:
			colorful: Whether chatbot's flows should be colored in created graph.
			flow_data: Chatbot's flow dictionary.
		"""

        # Flow-color dictionary
        if colorful:  # Generate colors
            colors = generate_colors(len(self.flows))
            flow_color = {flow: color for flow, color in zip(self.flows, colors)}
        else:  # White colors
            flow_color = {flow: self.default_color for flow in self.flows}

        # Initial node
        self.graph.attr('node', shape='doublecircle', fillcolor=flow_color['default'], style='filled')
        self.graph.node(self.state_indetifier(self.initial_flow, self.initial_state))

        # Other nodes
        self.graph.attr('node', shape='circle')
        for flow_filepath, flow_dict in flow_data.items():
            for flow, value in flow_dict.items():
                # Set flow's color
                self.graph.attr('node', fillcolor=flow_color[flow])

                for state in value['states']:
                    # Add non-initial nodes
                    if flow != self.initial_flow or state['name'] != self.initial_state:
                        # Node
                        node_name = self.state_indetifier(flow, state['name'])
                        # Add node
                        self.graph.node(node_name)

    def create_graph_edges(self, flow_data):
        """
		Creates graph edges from chatbot's flows.

		Args:
			flow_data: Chatbot's flow dictionary.
		"""

        # Edges
        for flow_filepath, flow_dict in flow_data.items():
            for flow, value in flow_dict.items():
                for state in value['states']:
                    node_name = self.state_indetifier(flow, state['name'])

                    try:  # Non-custom action
                        # Get next (destination) state information

                        if 'action' not in state or not state['action']:
                            print("State {} has no action, skipping!".format(state['name']))
                            continue

                        elif isinstance(state['action'], dict):

                            if 'next' in state['action']:
                                next_flow, next_state = self.flow_and_state(flow, state['action']['next'])
                                next_node_name = self.state_indetifier(next_flow, next_state)

                                # Add edge
                                print('Adding edge: ' + node_name + ' -> ' + next_node_name)
                                self.graph.edge(node_name, next_node_name)
                            else:
                                print("State {} is terminal".format(state['name']))

                        else:  # action is a function

                            action_name = state['action'].split('.')[-1]
                            action_filepath = state['action'][:-(len(action_name) + 1)].replace('.', '/') + '.py'

                            print(
                                'Adding edges from custom action \'' + action_name + '\' from file \'' + action_filepath + '\':')
                            try:  # Absolute action path
                                action_file_module = module_from_file(action_name,
                                                                      os.path.join(self.bot_filepath, action_filepath))
                            except:  # Relative action path
                                flow_dir = os.path.dirname(flow_filepath)
                                action_filepath = os.path.join(flow_dir, action_filepath)
                                action_file_module = module_from_file(action_name,
                                                                      os.path.join(self.bot_filepath, action_filepath))
                            action_fn_text = remove_comments(inspect.getsource(getattr(action_file_module, action_name)))
                            return_indexes = [r.start() for r in re.finditer('(^|\W)return($|\W)', action_fn_text)]

                            # Add edge(s)
                            for i in return_indexes:
                                # Get return value(s)
                                ret_val = action_fn_text[i + len('return') + 1:].split()[0]
                                ret_val = ret_val.strip('\"\'')
                                # Remove optional ':' from the end of the action
                                if ret_val.endswith(':'):
                                    ret_val = ret_val[:-len(':')]

                                # Get next (destination) state information
                                next_flow, next_state = self.flow_and_state(flow, ret_val)
                                next_node_name = self.state_indetifier(next_flow, next_state)

                                # Add edge
                                print(node_name + ' -> ' + next_node_name)
                                self.graph.edge(node_name, next_node_name)
                    except Exception as ex:
                        print("Error processing state, skipping!")
                        print(ex)

    def get_flow_data(self):
        # Get bot config
        bot_settings = module_from_file('bot_settings',
                                        os.path.join(self.bot_filepath, self.bot_name + '/bot_settings.py'))

        # Get flow data
        flow_data = {}
        for flow_file in bot_settings.BOT_CONFIG[self.flow_keyword]:
            # Get filepath to the flow file
            flow_filepath = self.bot_filepath
            flow_filepath += flow_file

            # Read from flow file
            with open(flow_filepath, 'r') as flow_f:
                # YAML/JSON
                flow_data[flow_filepath] = yaml.load(flow_f)

        return flow_data

    def create_graph(self, colorful):
        """
        Creates graph from chatbot's flows.

        Args:
            colorful: Whether chatbot's flows should be colored in created graph.
        """

        # Get flow data
        flow_data = self.get_flow_data()

        # Get all flows names
        self.flows = [flow for flow_file in flow_data for flow in flow_data[flow_file]]

        print('Drawing graph...')
        # Graph
        self.graph = Digraph('bot_graph', filename=self.graph_filepath)
        # Graph attributes
        self.graph.attr(rankdir='LR', size='8,5')

        # Add nodes
        self.create_graph_nodes(colorful, flow_data)
        # Add edges
        self.create_graph_edges(flow_data)

    def generate_json(self):
        """
        Generates JSON file from chatbot's flows.
        """

        # Get flow data
        flow_data = self.get_flow_data()

        # Get all flows names
        self.flows = [flow for flow_file in flow_data for flow in flow_data[flow_file]]
        flow_indexes = {flow: index for index, flow in enumerate(self.flows, 1)}

        print('Generating JSON...')
        # Create JSON
        self.json = {}
        # Add nodes to JSON
        self.json['nodes'] = []
        self.allowed_states = set()

        for flow_filepath, flow_dict in flow_data.items():
            for flow, value in flow_dict.items():
                for state in value['states']:
                    # Node
                    node_name = self.state_indetifier(flow, state['name'])
                    # Add node to JSON
                    self.json['nodes'].append({
                        'id': node_name,
                        'group': flow_indexes[flow]
                    })
                    self.allowed_states.add(node_name)

        # Add edges to JSON
        self.json['links'] = []
        for flow_filepath, flow_dict in flow_data.items():
            for flow, value in flow_dict.items():
                for state in value['states']:
                    node_name = self.state_indetifier(flow, state['name'])

                    try:
                        if 'action' not in state or not state['action']:
                            print("State {} has no action, skipping!".format(state['name']))
                            continue

                        elif isinstance(state['action'], dict):

                            if 'next' in state['action']:
                                # Get next (destination) state information
                                next_flow, next_state = self.flow_and_state(flow, state['action']['next'])
                                next_node_name = self.state_indetifier(next_flow, next_state)

                                if next_node_name not in self.allowed_states:
                                    print("Next state {} not found in states, skipping!".format(next_node_name))
                                    continue

                                # Add edge to JSON
                                print('Adding edge: ' + node_name + ' -> ' + next_node_name)
                                self.json['links'].append({
                                    'source': node_name,
                                    'target': next_node_name,
                                    'value': self.json_edge_value
                                })
                            else:
                                print("State {} is terminal".format(state['name']))

                        else:  # action is a function
                            action_name = state['action'].split('.')[-1]
                            action_filepath = state['action'][:-(len(action_name) + 1)].replace('.', '/') + '.py'

                            print(
                                'Adding edges from custom action \'' + action_name + '\' from file \'' + action_filepath + '\':')
                            try:  # Absolute action path
                                action_file_module = module_from_file(action_name,
                                                                      os.path.join(self.bot_filepath, action_filepath))
                            except:  # Relative action path
                                flow_dir = os.path.dirname(flow_filepath)
                                action_filepath = os.path.join(flow_dir, action_filepath)
                                action_file_module = module_from_file(action_name,
                                                                      os.path.join(self.bot_filepath, action_filepath))
                            action_fn_text = remove_comments(
                                inspect.getsource(getattr(action_file_module, action_name)))
                            return_indexes = [r.start() for r in re.finditer('(^|\W)return($|\W)', action_fn_text)]

                            # Add edge(s)
                            for i in return_indexes:
                                # Get return value(s)
                                ret_val = action_fn_text[i + len('return') + 1:].split()[0]
                                ret_val = ret_val.strip('\"\'')
                                # Remove optional ':' from the end of the action
                                if ret_val.endswith(':'):
                                    ret_val = ret_val[:-len(':')]

                                # Get next (destination) state information
                                next_flow, next_state = self.flow_and_state(flow, ret_val)
                                next_node_name = self.state_indetifier(next_flow, next_state)

                                if next_node_name not in self.allowed_states:
                                    print("Next state {} not found in states, skipping!".format(next_node_name))
                                    continue

                                # Add edge to JSON
                                print(node_name + ' -> ' + next_node_name)
                                self.json['links'].append({
                                    'source': node_name,
                                    'target': next_node_name,
                                    'value': self.json_edge_value
                                })
                    except Exception as ex:
                        print("Error processing state, skipping!")
                        print(ex)

    def save_json(self):
        with open(self.json_filepath, 'w') as outfile:
            json.dump(self.json, outfile)

    def save_and_show(self):
        """
		Saves and shows graph.
		"""

        # Check for graph
        assert self.graph, 'There is no graph to save/show.'

        # Save and show graph
        self.graph.view()

    def save(self):
        """
		Saves graph.
		"""

        # Check for graph
        assert self.graph, 'There is no graph to show.'

        # Save graph
        # DOT source
        self.graph.save()
        # Render graph
        self.graph.render()


if __name__ == '__main__':
    # Command line arguments
    # Example: python3 ./graph.py --bot_dir . --bot_name chatbot
    parser = argparse.ArgumentParser(description='Script for plotting flow graph of Botshot chatbot.')
    parser.add_argument('--bot_dir', required=True, help='root directory of Botshot project')
    parser.add_argument('--bot_name', required=False, help='chatbot django app name (optional)')
    parser.add_argument('--colorful', action='store_true', help='whether chatbot\'s flows should colored')
    parser.add_argument('--graph_path', default='graph.gv', help='path where graph should be saved')
    parser.add_argument('--dont_show', action='store_true', help='whether graph should be displayed after saving')
    parser.add_argument('--json_output', action='store_true',
                        help='whether JSON should be produced instead of dot file and image')
    parser.add_argument('--json_path', default='graph.json', help='path where JSON should be saved')

    args = parser.parse_args()

    # Arguments processing
    bot_dir = os.path.join(os.path.dirname(__file__), args.bot_dir)
    bot_dir = os.path.abspath(bot_dir)


    # Plotting
    graph_plot = GraphPlot(bot_dir, args.bot_name, args.graph_path, args.json_path)

    # JSON
    if args.json_output:
        graph_plot.generate_json()
        graph_plot.save_json()
    else:  # Dot file and image
        graph_plot.create_graph(args.colorful)

        # Save graph/save and show graph
        if args.dont_show:
            graph_plot.save()
        else:
            graph_plot.save_and_show()
