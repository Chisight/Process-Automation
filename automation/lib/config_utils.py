# config_utils.py
import os

CONFIG_PATH = '/home/auto/config/automation.conf'
PRIVATE_CONFIG_PATH = '/home/auto/config/automation_private.conf'

def get_next_line(config_lines):
    # Static variable to track the current line index
#    if not hasattr(get_next_line, 'current_index'):
#        get_next_line.current_index = 0
    
    if get_next_line.current_index >= len(config_lines):
        return None  # No more lines to read
    
    line = config_lines[get_next_line.current_index].strip()
    get_next_line.current_index += 1
    
    if not line or line.startswith('#'):  # Skip empty lines and comments
        return get_next_line(config_lines)  # Recursively call to get the next valid line
    
    # Remove inline comments
    if '#' in line:
        line = line.split('#', 1)[0].strip()
    
    return line

def get_config(option):
    config_lines = []
    
    # Read and store lines from private and main config files
    if os.path.exists(PRIVATE_CONFIG_PATH):
        with open(PRIVATE_CONFIG_PATH, 'r') as private_config_file:
            config_lines.extend(private_config_file.readlines())
    
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'r') as config_file:
            config_lines.extend(config_file.readlines())
    
    
    # Reset index to start reading lines from the beginning
    get_next_line.current_index = 0

    collected_value = ""
    while True:
        line = get_next_line(config_lines)
        if line is None:
            break
        
        # Check for key-value pair
        if '=' in line:
            key, value = line.split('=', 1)
            key, value = key.strip(), value.strip()

            if key == option:
                # Handle multi-line value
                while value.endswith('\\'):
                    next_line = get_next_line(config_lines)
                    if next_line is None:
                        break
                    value = value[:-1].strip() + ' ' + next_line.strip()

                # Return as list if space-separated array values are detected
                if ' ' in value:
                    return value.split()
                return value
            
    # If option is not found in either file
    raise ValueError(f'Configuration not found for {option}')

