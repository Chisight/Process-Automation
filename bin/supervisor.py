"""
consider migrating to the approach in multiprocessingtest.py
"""


import os
import subprocess
import time
from multiprocessing import Process, Pool
import psutil  # Import the psutil module for process management
import datetime
import sys
import pyinotify  # Import the pyinotify module
from script_runner import run_script, log_message

# Define the directory to watch for changes
DIRECTORY_TO_WATCH = '/home/auto/automation'

# Function to find Python scripts in a folder
def find_python_scripts(folder_path):
    scripts = []
    for filename in os.listdir(folder_path):
        if filename.endswith(".py"):
            script_path = os.path.join(folder_path, filename)
            scripts.append(script_path)
    return scripts

# Define the script name without extension
SCRIPT_NAME = os.path.splitext(os.path.basename(sys.argv[0]))[0]

# Define a global pool for process management
pool = Pool()

# Event handler class to handle specific file modification events
class EventHandler(pyinotify.ProcessEvent):
    # Dictionary to store the last modification time of each file
    last_modification_times = {}

    # Function to update the last modification time of a file
    def update_last_modification_time(self, file_path):
        self.last_modification_times[file_path] = time.time()

    # Function to check if a file has been modified recently
    def is_recently_modified(self, file_path):
        return file_path in self.last_modification_times and \
               time.time() - self.last_modification_times[file_path] < 1

    def process_IN_CLOSE_WRITE(self, event):
        if event.pathname.endswith('.py') and not self.is_recently_modified(event.pathname):
            self.update_last_modification_time(event.pathname)
            log_message(SCRIPT_NAME, f"Change detected: {event.maskname} on {event.pathname}")
            written_script = event.pathname
            log_message(SCRIPT_NAME, f"New script {written_script} written. Starting it.")
            pool.apply_async(run_script, args=(written_script,))

    def process_IN_MOVED_TO(self, event):
        if event.pathname.endswith('.py') and not self.is_recently_modified(event.pathname):
            self.update_last_modification_time(event.pathname)
            log_message(SCRIPT_NAME, f"Change detected: {event.maskname} on {event.pathname}")
            moved_script = event.pathname
            log_message(SCRIPT_NAME, f"New script {moved_script} detected. Starting it.")
            pool.apply_async(run_script, args=(moved_script,))

    def process_IN_MOVED_FROM(self, event):
        if event.pathname.endswith('.py') and not self.is_recently_modified(event.pathname):
            self.update_last_modification_time(event.pathname)
            log_message(SCRIPT_NAME, f"Change detected: {event.maskname} on {event.pathname}")
            removed_script = event.pathname
            log_message(SCRIPT_NAME, f"Script {removed_script} moved out. Terminating its process.")
            # Find the process associated with the removed script and terminate it
            existing_processes = [p for p in psutil.process_iter() if p.name() == 'python3' and removed_script in p.cmdline()]
            for process in existing_processes:
                log_message(SCRIPT_NAME, f"Terminating process with PID {process.pid}.")
                parent_pid = process.ppid()
                process.terminate()
                process.wait()
                # Check if the parent process is still running and terminate it if needed
                parent_process = psutil.Process(parent_pid)
                if parent_process.is_running():
                    log_message(SCRIPT_NAME, f"Terminating parent process with PID {parent_pid}.")
                    parent_process.terminate()
                    parent_process.wait()

    def process_IN_DELETE(self, event):
        if event.pathname.endswith('.py') and not self.is_recently_modified(event.pathname):
            self.update_last_modification_time(event.pathname)
            log_message(SCRIPT_NAME, f"Change detected: {event.maskname} on {event.pathname}")
            deleted_script = event.pathname
            log_message(SCRIPT_NAME, f"Script {deleted_script} deleted. Terminating its process.")
            # Find the process associated with the deleted script and terminate it
            existing_processes = [p for p in psutil.process_iter() if p.name() == 'python3' and deleted_script in p.cmdline()]
            for process in existing_processes:
                log_message(SCRIPT_NAME, f"Terminating process with PID {process.pid}.")
                parent_pid = process.ppid()
                process.terminate()
                process.wait()
                # Check if the parent process is still running and terminate it if needed
                parent_process = psutil.Process(parent_pid)
                if parent_process.is_running():
                    log_message(SCRIPT_NAME, f"Terminating parent process with PID {parent_pid}.")
                    parent_process.terminate()
                    parent_process.wait()

    def process_IN_CLOSE_WRITE(self, event):
        if event.pathname.endswith('.py') and not self.is_recently_modified(event.pathname):
            self.update_last_modification_time(event.pathname)
            log_message(SCRIPT_NAME, f"Change detected: {event.maskname} on {event.pathname}")
            written_script = event.pathname
            log_message(SCRIPT_NAME, f"New script {written_script} written. Starting it.")
            pool.apply_async(run_script, args=(written_script,))

        def process_default(self, event):
            if event.pathname.endswith('.py'):
                log_message(SCRIPT_NAME, f"Change detected: {event.maskname} on {event.pathname}")

# Main function to start monitoring
def main():
    # Create a new watch manager
    wm = pyinotify.WatchManager()

    # Associate the watch manager with a notifier
    notifier = pyinotify.Notifier(wm, EventHandler())

    # Define the watch mask to monitor all events but handle only IN_MOVED_TO
    mask = pyinotify.ALL_EVENTS

    # Add a new watch on the directory for specific modification events
    wm.add_watch(DIRECTORY_TO_WATCH, mask)

    # Log the monitoring directory and found Python scripts
    log_message(SCRIPT_NAME, f"Monitoring directory: {DIRECTORY_TO_WATCH}")
    scripts = find_python_scripts(DIRECTORY_TO_WATCH)
    log_message(SCRIPT_NAME, f"Found Python scripts: {scripts}")

    # Start the initial set of scripts
    for script in scripts:
        process = Process(target=run_script, args=(script,))
        process.start()

    # Loop forever and handle events
    notifier.loop()

if __name__ == "__main__":
    main()

