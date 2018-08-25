from graphviz import Digraph
import yaml
import importlib, importlib.util, os.path
import inspect
import re

# TMP
filepath = '../ExampleBot/'

def module_from_file(module_name, filepath):
	spec = importlib.util.spec_from_file_location(module_name, filepath)
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module

class FSMPlot:
	"""Class for plotting chatbot's finite state machine."""

	def __init__(self, bot_filepath):
		self.bot_filepath = bot_filepath
		self.fsm = None

		# Constants
		self.flow_keyword = 'BOTS'

	def create_state_title(self, flow_name, state_name):
		"""
		Creates state title from provided flow and state names.

		Args:
			flow_name (string): name of the flow.
			state_name (string): name of the state.
		"""
		return flow_name + '.' + state_name

	def createFSM(self):
		"""
		Reads finite state machine from chatbot.
		"""

		# Get bot config
		bot_settings = module_from_file('BOT_CONFIG', self.bot_filepath + 'ExampleBot/bot_settings.py')
		# Get filepath to the flow file
		flow_filepath = self.bot_filepath
		flow_filepath += bot_settings.BOT_CONFIG[self.flow_keyword].pop()

		# Read from flow file
		with open(flow_filepath, 'r') as flow_file:
			# TODO - JSON ?

			# YAML
			flow_data = yaml.load(flow_file)
			#print(flow_data)

		# FSM
		self.fsm = Digraph('finite_state_machine', filename='fsm.gv')
		# FSM attributes
		self.fsm.attr(rankdir='LR', size='8,5')

		# Initial state
		self.fsm.attr('node', shape='doublecircle')
		self.fsm.node(self.create_state_title('default', 'root'))

		# Get flow names
		flows = [flow for flow in flow_data]

		# Other states + edges
		self.fsm.attr('node', shape='circle')
		for flow, value in flow_data.items():
			for state in value['states']:
				# Skip adding default:root node
				if flow != 'default' or state['name'] != 'root':
					# Node
					node_name = self.create_state_title(flow, state['name'])
					# Add node
					self.fsm.node(node_name)
				else:
					node_name = self.create_state_title('default', 'root')

				# Edge
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

					next_node_name = self.create_state_title(next_flow, next_state)

					print('Adding edge:')
					print(node_name + ' ... ' + next_node_name)
					# Add edge
					self.fsm.edge(node_name, next_node_name)
				except:
					# Custom action
					action_name = state['action'].split('.')[-1]
					action_filepath = state['action'][:-(len(action_name) + 1)].replace('.', '/') + '.py'
					
					print('Adding edge (custom action) \'' + action_name + '\' from \'' + action_filepath + '\':')
					action_file_module = module_from_file(action_name, self.bot_filepath + action_filepath)
					action_fn_text = inspect.getsource(getattr(action_file_module, action_name))
					#print(action_fn_text)

					#print('---------------------')
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

						next_node_name = self.create_state_title(next_flow, next_state)

						# Add edge
						self.fsm.edge(node_name, next_node_name)

					#print('---------------------')
					#print(return_indexes)
					
					#print('Custom action is not supported yet.')


	def showFSM(self):
		"""
		Shows finite state machine.
		"""

		# TODO
		if not self.fsm:
			print('There is no FSM to show.')
			return
		# Show FSM
		self.fsm.view()


# TMP - TEST
fsm_plot = FSMPlot(filepath)
fsm_plot.createFSM()
fsm_plot.showFSM()

