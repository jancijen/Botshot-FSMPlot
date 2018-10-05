from graphviz import Digraph
import os.path
import yaml
import inspect
import argparse
import django
import sys
import json
import utility as ut


class GraphPlot:
    """
    Class for plotting chatbot's graph / generating JSON graph file.
    """

    def __init__(self, bot_filepath, bot_name, graph_filepath, json_filepath):
        """
        Args:
            bot_filepath:    Django project root.
            bot_name:        Optional - name of django app containing bot (can differ from django project name).
            graph_filepath:  Where to save generated graph.
            json_filepath:   Where to save generated JSON.
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

        # Constants
        self.flow_keyword = 'BOTS'
        self.default_color = '#FFFFFF'
        self.initial_flow = 'default'
        self.initial_state = 'root'
        self.json_edge_value = 3

        # Django setup
        sys.path.append(self.bot_filepath)
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', self.bot_name + '.settings')
        django.setup()

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

    def get_flow_data(self):
        """
        Returns flow data from bot's settings as a dictionary.

        Returns:
            Flow data dictionary.
        """

        # Get bot config
        bot_settings = ut.module_from_file('bot_settings', os.path.join(self.bot_filepath, self.bot_name + '/bot_settings.py'))
        
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


    # --------------------------------------------------------------------------
    # Graph - IR
    # --------------------------------------------------------------------------

    def create_ir_nodes(self, flow_data):
        """
        Creates nodes of intermediate representation of flow graph from flow data.

        Args:
            flow_data: Chatbot's flow data dictionary.

        Returns:
            List of nodes in format (node_name, flow).
        """

        # Nodes
        nodes = []
        for flow_filepath, flow_dict in flow_data.items():
            for flow, value in flow_dict.items():
                for state in value['states']:
                    # Node
                    node_name = ut.state_identifier(flow, state['name'])
                    # Add node to JSON
                    nodes.append((node_name, flow))

        return nodes

    def create_ir_edges(self, flow_data):
        """
        Creates edges of intermediate representation of flow graph from flow data.

        Args:
            flow_data: Chatbot's flow data dictionary.

        Returns:
            List of edges in format (from_vertex, to_vertex).
        """

        # Edges
        edges = []
        for flow_filepath, flow_dict in flow_data.items():
            for flow, value in flow_dict.items():
                for state in value['states']:
                    node_name = ut.state_identifier(flow, state['name'])

                    try:  # Non-custom action
                        # Get next (destination) state information

                        if 'action' not in state or not state['action']:
                            print("State {} has no action, skipping!".format(state['name']))
                            continue

                        elif isinstance(state['action'], dict):

                            if 'next' in state['action']:
                                next_flow, next_state = self.flow_and_state(flow, state['action']['next'])
                                next_node_name = ut.state_identifier(next_flow, next_state)

                                # Add edge
                                print('{} -> {}'.format(node_name, next_node_name))
                                edges.append((node_name, next_node_name))
                            else:
                                print("State {} is terminal".format(state['name']))

                        else:  # action is a function

                            action_name = state['action'].split('.')[-1]
                            action_filepath = state['action'][:-(len(action_name) + 1)].replace('.', '/') + '.py'

                            print('Adding edges from custom action \'{}\' from file \'{}\':'.format(action_name, action_filepath))
                            try:  # Absolute action path
                                action_file_module = ut.module_from_file(action_name,
                                                                      os.path.join(self.bot_filepath, action_filepath))
                            except:  # Relative action path
                                flow_dir = os.path.dirname(flow_filepath)
                                action_filepath = os.path.join(flow_dir, action_filepath)
                                action_file_module = ut.module_from_file(action_name,
                                                                      os.path.join(self.bot_filepath, action_filepath))
                            action_fn_text = ut.remove_comments(inspect.getsource(getattr(action_file_module, action_name)))
                            return_indexes = ut.return_indexes(action_fn_text)

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
                                next_node_name = ut.state_identifier(next_flow, next_state)

                                # Add edge
                                print('{} -> {}'.format(node_name, next_node_name))
                                edges.append((node_name, next_node_name))
                    except Exception as ex:
                        print("Error processing state, skipping!")
                        print(ex)

        return edges

    def create_ir(self):
        """
        Creates intermediate representation of flow graph from flow data.
        """

        # Get flow data
        flow_data = self.get_flow_data()

        # Flows
        self.flows = [flow for flow_file in flow_data for flow in flow_data[flow_file]]
        # Nodes
        self.nodes = self.create_ir_nodes(flow_data)
        # Edges
        self.edges = self.create_ir_edges(flow_data)


    # --------------------------------------------------------------------------
    # Graph - DOT, Image
    # --------------------------------------------------------------------------

    def create_graph_nodes(self, colorful, flow_data):
        """
        Creates graph nodes from chatbot's flows.

        Args:
            colorful: Whether chatbot's flows should be colored in created graph.
            flow_data: Chatbot's flow data dictionary.
        """

        # Flow-color dictionary
        if colorful: # Generate colors
            colors = ut.generate_colors(len(self.flows))
            flow_color = {flow: color for flow, color in zip(self.flows, colors)}
        else: # White colors
            flow_color = {flow: self.default_color for flow in self.flows}

        # Initial node
        self.graph.attr('node', shape='doublecircle', fillcolor=flow_color['default'], style='filled')
        self.graph.node(ut.state_identifier(self.initial_flow, self.initial_state))

        # Other nodes
        self.graph.attr('node', shape='circle')
        for name, flow in self.nodes:
            # Add non-initial nodes
            if flow != self.initial_flow or name != self.initial_state:
                # Set flow's color
                self.graph.attr('node', fillcolor=flow_color[flow])
                # Add node
                self.graph.node(name)

    def create_graph_edges(self, flow_data):
        """
        Creates graph edges from chatbot's flows.

        Args:
            flow_data: Chatbot's flow data dictionary.
        """

        # Edges
        for from_vertex, to_vertex in self.edges:
            self.graph.edge(from_vertex, to_vertex)
                        
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


    # --------------------------------------------------------------------------
    # Graph - JSON
    # --------------------------------------------------------------------------

    def generate_json_nodes(self, flow_data):
        """
        Generates graph nodes from chatbot's flows (to JSON).

        Args:
            flow_data: Chatbot's flow data dictionary.
        """

        flow_indexes = {flow: index for index, flow in enumerate(self.flows, 1)}

        # Add nodes to JSON
        self.json['nodes'] = []
        for name, flow in self.nodes:
            # Add node to JSON
            self.json['nodes'].append({
                'id': name,
                'group': flow_indexes[flow]
            })

    def generate_json_edges(self, flow_data):
        """
        Generates graph edges from chatbot's flows (to JSON).

        Args:
            flow_data: Chatbot's flow data dictionary.
        """

        # Add edges to JSON
        self.json['links'] = []
        for from_vertex, to_vertex in self.edges:
            self.json['links'].append({
                'source': from_vertex,
                'target': to_vertex,
                'value': self.json_edge_value
            })

    def generate_json(self):
        """
        Generates JSON file from chatbot's flows.
        """

        # Get flow data
        flow_data = self.get_flow_data()

        # Get all flows names
        self.flows = [flow for flow_file in flow_data for flow in flow_data[flow_file]]
        
        print('Generating JSON...')
        # Create JSON
        self.json = {}
        # Nodes
        self.generate_json_nodes(flow_data)
        # Edges
        self.generate_json_edges(flow_data)
        
    # --------------------------------------------------------------------------
    # Save/Load
    # --------------------------------------------------------------------------

    def save_json(self):
        # Check for JSON
        assert self.json, 'There is no JSON to save.'

        # Save JSON
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

# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

if __name__ == '__main__':
    # Command line arguments
    # Example: python3 ./botshot-graph.py --bot_dir . --bot_name chatbot
    parser = argparse.ArgumentParser(description='Script for plotting flow graph of Botshot chatbot and generating its JSON representation.')
    parser.add_argument('--bot_dir', required=True, help='root directory of Botshot chatbot')
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
    #bot_dir = os.path.abspath(bot_dir)

    # Plotting
    graph_plot = GraphPlot(bot_dir, args.bot_name, args.graph_path, args.json_path)
    # Create intermediate representation of flow graph
    graph_plot.create_ir()

    # JSON
    if args.json_output:
        graph_plot.generate_json()
        graph_plot.save_json()
    # Dot file and image
    else:
        graph_plot.create_graph(args.colorful)
    
        # Save graph/save and show graph
        if args.dont_show:
            graph_plot.save()
        else:
            graph_plot.save_and_show()
