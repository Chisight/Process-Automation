import os
import pyinotify
from lib.config_utils import get_config

# Define the watched folder and destination file
DIRECTORY_TO_WATCH = get_config('DIRECTORY_TO_WATCH')
INDEX_HTML_FILE = get_config('INDEX_HTML_FILE')
WEB_DIRECTORY = get_config('WEB_DIRECTORY')
INDEX_TEMPLATE_FILE = eval(get_config('INDEX_TEMPLATE_FILE'))

# Function to read the contents of a file
def read_file_contents(file_path):
    with open(file_path, 'r') as file:
        return file.read()

# Function to update the index.html file with folders as tabs and filenames as content
def update_index_html(directory, index_file):
    # Get a list of folder names in the directory
    folder_names = sorted([f for f in os.listdir(directory) if os.path.isdir(os.path.join(directory, f)) and f[0].isdigit()])

    # Find the insertion point
    insertion_point = '<!-- Insertion Point -->'

    # Create the new tab structure
    tabs = []
    tab_content = []
    first_tab = True  # Track the first tab

    for folder in folder_names:
        folder_path = os.path.join(directory, folder)
        tab_name = folder.split('-', 1)[-1]  # Extract the tab name from the folder name
        tab_id = tab_name.lower().replace(' ', '-')

        # Mark the first tab as active
        active_class = " active" if first_tab else ""
        tabs.append(f'<button class="tab-link{active_class}" onclick="openTab(event, \'{tab_id}\')">{tab_name}</button>')

        # Get the HTML files in this folder
        filenames = sorted([f for f in os.listdir(folder_path) if f.endswith('.html') and f[0].isdigit()])
        content = []
        for filename in filenames:
            file_contents = read_file_contents(os.path.join(folder_path, filename))
            content.append(file_contents)

        # Add the tab content
        tab_content.append(f'<div id="{tab_id}" class="tab-content{active_class}">{"".join(content)}</div>')

        first_tab = False  # Only the first tab should be active

    # Write the updated content back to index.html
    with open(index_file, 'w') as f:
        # Insert the new content at the insertion point
        with open(INDEX_TEMPLATE_FILE, 'r') as template_file:
            for line in template_file:
                if insertion_point in line:
                    f.write(line)
                    f.write('<div class="tabs">\n')
                    f.write('\n'.join(tabs))
                    f.write('</div>\n')
                    f.write('\n'.join(tab_content))
                else:
                    f.write(line)

# Function to recursively add watches on all subdirectories
def add_watch_recursive(watch_manager, path):
    for root, dirs, files in os.walk(path):
        watch_manager.add_watch(root, pyinotify.ALL_EVENTS)
        print(f"Watching directory: {root}")
        for directory in dirs:
            watch_manager.add_watch(os.path.join(root, directory), pyinotify.ALL_EVENTS)
            print(f"Watching subdirectory: {os.path.join(root, directory)}")

# Event handler class to handle file modification events
class EventHandler(pyinotify.ProcessEvent):
    def process_default(self, event):
        print(f"Change detected: {event.pathname}")

        # Update the index.html file only if it's closed for writing
        if event.mask & pyinotify.IN_CLOSE_WRITE:
            update_index_html(DIRECTORY_TO_WATCH, INDEX_HTML_FILE)

        # Update the index.html file if a file is created, moved, or deleted
        elif event.mask & (pyinotify.IN_CREATE | pyinotify.IN_MOVED_TO):
            update_index_html(DIRECTORY_TO_WATCH, INDEX_HTML_FILE)

        # Update the index.html file if a file is deleted or moved away
        elif event.mask & (pyinotify.IN_DELETE | pyinotify.IN_MOVED_FROM):
            update_index_html(DIRECTORY_TO_WATCH, INDEX_HTML_FILE)

# Main function to start monitoring
def main():
    # Create a new watch manager
    wm = pyinotify.WatchManager()

    # Associate the watch manager with a notifier
    notifier = pyinotify.Notifier(wm, EventHandler())

    # Recursively add watches on the directory and its subdirectories
    add_watch_recursive(wm, DIRECTORY_TO_WATCH)

    print(f"Monitoring directory: {DIRECTORY_TO_WATCH} and its subdirectories")

    # Loop forever and handle events
    notifier.loop()

if __name__ == "__main__":
    main()

