"""
Utility functions.
"""

import importlib
import random
import re


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

def return_indexes(source_code):
    """
    Returns indexes of 'return's (in given source code).

    Args:
        source_code: Python source code to get indexes from.

    Returns:
        Indexes of 'return's.
    """

    return [r.start() for r in re.finditer('(^|\W)return($|\W)', source_code)]

def state_identifier(flow_name, state_name):
    """
    Returns state identifier from provided flow and state names.

    Args:
        flow_name: Name of the flow.
        state_name: Name of the state.

    Returns:
        State identifier.
    """

    return flow_name + '.' + state_name
