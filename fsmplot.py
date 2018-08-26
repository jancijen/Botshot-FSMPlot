from graphviz import Digraph
import yaml
import importlib, importlib.util, os.path
import inspect
import re
import argparse
import random

def module_from_file(module_name, filepath):
	spec = importlib.util.spec_from_file_location(module_name, filepath)
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module

def generate_colors(n):
	"""
	Generate n different colors.

	Args:
		n (int): count of colors to generate.
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

class FSMPlot:
	"""Class for plotting chatbot's finite state machine."""

	def __init__(self, bot_filepath, graph_filepath):
		self.bot_filepath = bot_filepath
		self.graph_filepath = graph_filepath
		self.fsm = None

		# Constants
		self.flow_keyword = 'BOTS'

	def state_indetifier(self, flow_name, state_name):
		"""
		Returns state title from provided flow and state names.

		Args:
			flow_name (string): name of the flow.
			state_name (string): name of the state.
		"""
		return flow_name + '.' + state_name

	def createFSM(self, colorful):
		"""
		Reads finite state machine from chatbot.
		"""

		# Get bot config
		bot_settings = module_from_file('BOT_CONFIG', os.path.join(self.bot_filepath, 'ExampleBot/bot_settings.py'))
		# Get filepath to the flow file
		flow_filepath = self.bot_filepath
		flow_filepath += bot_settings.BOT_CONFIG[self.flow_keyword].pop()

		# Read from flow file
		with open(flow_filepath, 'r') as flow_file:
			# TODO - JSON ?

			# YAML
			flow_data = yaml.load(flow_file)

		print('Graph drawing...')
		# FSM
		self.fsm = Digraph('finite_state_machine', filename=self.graph_filepath)
		# FSM attributes
		self.fsm.attr(rankdir='LR', size='8,5')

		# Get flow names
		flows = [flow for flow in flow_data]
		# Flow-color dictionary
		if colorful: # Generate colors
			colors = generate_colors(len(flows))
			flow_color = {flow:color for flow, color in zip(flows, colors)}
		else: # White colors
			flow_color = {flow:'#FFFFFF' for flow in flows}

		# Initial state
		self.fsm.attr('node', shape='doublecircle', fillcolor=flow_color['default'], style='filled')
		self.fsm.node(self.state_indetifier('default', 'root'))

		# Other states
		self.fsm.attr('node', shape='circle')
		for flow, value in flow_data.items():
			# Set flow's color
			self.fsm.attr('node', fillcolor=flow_color[flow])

			for state in value['states']:
				# Skip adding default:root node
				if flow != 'default' or state['name'] != 'root':
					# Node
					node_name = self.state_indetifier(flow, state['name'])
					# Add node
					self.fsm.node(node_name)
				else:
					node_name = self.state_indetifier('default', 'root')
		
		# Edges
		for flow, value in flow_data.items():
			for state in value['states']:
				node_name = self.state_indetifier(flow, state['name'])

				try:
					# Non-custom action
					next_state = state['action']['next']
					next_flow = None
					# Absolute state path
					for fl in flows:
						if next_state.startswith(fl + '.'):
							next_state = next_state[len(fl) + 1:]
							next_flow = fl
					# Relative state path
					if not next_flow:
						next_flow = flow

					next_node_name = self.state_indetifier(next_flow, next_state)

					print('Adding edge: ' + node_name + ' -> ' + next_node_name)
					# Add edge
					self.fsm.edge(node_name, next_node_name)
				except:
					# Custom action
					action_name = state['action'].split('.')[-1]
					action_filepath = state['action'][:-(len(action_name) + 1)].replace('.', '/') + '.py'
					
					print('Adding edges from custom action \'' + action_name + '\' from file \'' + action_filepath + '\':')
					action_file_module = module_from_file(action_name, os.path.join(self.bot_filepath, action_filepath))
					action_fn_text = inspect.getsource(getattr(action_file_module, action_name))
					return_indexes = [r.start() for r in re.finditer('(^|\W)return($|\W)', action_fn_text)]

					# Add edges
					for i in return_indexes:
						ret_val = action_fn_text[i + len('return') + 1:].split()[0]
						ret_val = ret_val.strip('\"\'')
						# Remove optional ':' from the end of action
						if ret_val.endswith(':'):
								ret_val = ret_val[:-len(':')]

          				# TODO!
						next_state = ret_val
						next_flow = None
						# Absolute state path
						for fl in flows:
							if next_state.startswith(fl + '.'):
								next_state = next_state[len(fl) + 1:]
								next_flow = fl
						# Relative state path
						if not next_flow:
							next_flow = flow

						next_node_name = self.state_indetifier(next_flow, next_state)

						# Add edge
						print(node_name + ' -> ' + next_node_name)
						self.fsm.edge(node_name, next_node_name)


	def save_and_show(self):
		"""
		Saves and shows finite state machine graph.
		"""

		if not self.fsm:
			print('There is no finite state machine to save/show.')
			return

		# Save and show FSM
		self.fsm.view()

	def save(self):
		"""
		Saves finite state machine graph.
		"""

		if not self.fsm:
			print('There is no finite state machine to show.')
			return

		# Save FSM 
		# DOT source
		self.fsm.save()
		# Render graph
		self.fsm.render()

if __name__ == '__main__':
	# Command line arguments
	parser = argparse.ArgumentParser(description='Script for plotting flow graph of Botshot chatbot.')
	parser.add_argument('--bot_dir', required=True, help='directory containing Botshot chatbot')
	parser.add_argument('--colorful', action='store_true', help='whether chatbot\'s flows should colored')
	parser.add_argument('--graph_path', default='fsm.gv', help='path where graph should be saved')
	parser.add_argument('--dont_show', action='store_true', help='whether graph should be displayed after saving')
	
	args = parser.parse_args()

	# Arguments processing
	bot_dir = os.path.join(os.path.dirname(__file__), args.bot_dir)

	# Plotting
	fsm_plot = FSMPlot(bot_dir, args.graph_path)
	fsm_plot.createFSM(args.colorful)
	
	# Save graph / save and show graph
	if args.dont_show:
		fsm_plot.save()
	else:
		fsm_plot.save_and_show()

