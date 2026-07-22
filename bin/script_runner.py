import subprocess
import time
import os
import sys
import datetime
import psutil

# Define the script name without extension
SCRIPT_NAME = os.path.splitext(os.path.basename(sys.argv[0]))[0]
# Define the log file path
LOG_FILE = f'/home/auto/{SCRIPT_NAME}.log'

# Function to log messages with timestamp
def log_message(message_source, message_text):
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open(LOG_FILE, 'a') as log_file:
        log_file.write(f"{message_source}:{timestamp}:{message_text}\n")
        log_file.flush()


# Function to run a script
def run_script(script):
    backoff_time = 1  # Initial backoff time in seconds
    log_message(SCRIPT_NAME, f"Running script {script}, I am PID {os.getpid()}.")
    # Check if the script is already running, if yes then kill it and let it's parent restart it as usual
    existing_processes = [p for p in psutil.process_iter() if p.name() == 'python3' and script in p.cmdline()]
    if existing_processes:
        for process in existing_processes:
            log_message(SCRIPT_NAME, f"Killing existing process with PID {process.pid} under supervisor pid {process.parent().pid} for script {script}")
            process.terminate()
            process.wait()
            log_message(SCRIPT_NAME, f"wait finished for PID {process.pid}.")
    else:
        while True:
            start_time = time.time()
            # Run the script and capture its output with line buffering
            command = ['python3', '-u', script]  # Use -u flag for unbuffered output
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
            log_message(SCRIPT_NAME, f"Launched {script} with pid {process.pid} under supervisor PID {os.getpid()}.")
            # Monitor the output line by line
            for line in process.stdout:
                output = line.strip()
                log_message(os.path.splitext(os.path.basename(script))[0], output)

            # Wait for the process to finish
            process.wait()

            end_time = time.time()
            elapsed_time = end_time - start_time
            log_message(SCRIPT_NAME, f"Script {script} exited in {elapsed_time} seconds. Backoff is {backoff_time}.")
            if elapsed_time < 60:
                time.sleep(backoff_time)
                backoff_time *= 2  # Exponential backoff
            else:
                backoff_time = 1  # Reset backoff time

