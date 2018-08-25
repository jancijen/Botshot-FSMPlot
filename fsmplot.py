from graphviz import Digraph
import yaml
import importlib, importlib.util, os.path

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
		self.fsm.node('default: root')
		del flow_data['default']['states'][0]

		# Other states
		self.fsm.attr('node', shape='circle')
		for flow, value in flow_data.items():
			for state in value['states']:
				# Skip default:root
				if flow == 'default' and state['name'] == 'root':
					continue
				self.fsm.node(flow + ': ' + state['name'])


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


