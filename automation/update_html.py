import os
import shutil
import pyinotify
from lib.config_utils import get_config

# Define the watched folders and destination files
INDEX_HTML_FILE = get_config('INDEX_HTML_FILE')
WEB_DIRECTORY = get_config('WEB_DIRECTORY')
WEB_STATIC_DIRECTORY = get_config('WEB_STATIC_DIRECTORY')
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
    first_tab = True # Track the first tab
    
    for folder in folder_names:
        folder_path = os.path.join(directory, folder)
        tab_name = folder.split('-', 1)[-1] # Extract the tab name from the folder name
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
        first_tab = False # Only the first tab should be active
    
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

# Function to sync files from WEB_STATIC_DIRECTORY to WEB_DIRECTORY
def sync_static_files(src_path, dest_dir):
    """
    Sync a file or directory from WEB_STATIC_DIRECTORY to WEB_DIRECTORY.
    If src_path is a file, copy it to dest_dir.
    If src_path is a directory, copy the entire directory structure.
    """
    try:
        # Get the relative path from WEB_STATIC_DIRECTORY
        rel_path = os.path.relpath(src_path, WEB_STATIC_DIRECTORY)
        dest_path = os.path.join(dest_dir, rel_path)
        
        # Ensure destination directory exists
        dest_parent = os.path.dirname(dest_path)
        if not os.path.exists(dest_parent):
            os.makedirs(dest_parent, exist_ok=True)
        
        if os.path.isdir(src_path):
            # If source is a directory, copy the entire tree
            if os.path.exists(dest_path):
                shutil.rmtree(dest_path)
            shutil.copytree(src_path, dest_path)
            print(f"Synced directory: {src_path} -> {dest_path}")
        else:
            # If source is a file, copy the file
            shutil.copy2(src_path, dest_path)
            print(f"Synced file: {src_path} -> {dest_path}")
    except Exception as e:
        print(f"Error syncing {src_path}: {e}")

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
        
        # Handle changes in WEB_DIRECTORY
        if event.pathname.startswith(WEB_DIRECTORY):
            # Update the index.html file only if it's closed for writing
            if event.mask & pyinotify.IN_CLOSE_WRITE:
                update_index_html(WEB_DIRECTORY, INDEX_HTML_FILE)
            # Update the index.html file if a file is created, moved, or deleted
            elif event.mask & (pyinotify.IN_CREATE | pyinotify.IN_MOVED_TO):
                update_index_html(WEB_DIRECTORY, INDEX_HTML_FILE)
            # Update the index.html file if a file is deleted or moved away
            elif event.mask & (pyinotify.IN_DELETE | pyinotify.IN_MOVED_FROM):
                update_index_html(WEB_DIRECTORY, INDEX_HTML_FILE)
        
        # Handle changes in WEB_STATIC_DIRECTORY
        elif event.pathname.startswith(WEB_STATIC_DIRECTORY):
            # Sync file if it's closed for writing (completed)
            if event.mask & pyinotify.IN_CLOSE_WRITE:
                sync_static_files(event.pathname, WEB_DIRECTORY)
            # Sync file if it's created
            elif event.mask & pyinotify.IN_CREATE:
                if os.path.isdir(event.pathname):
                    sync_static_files(event.pathname, WEB_DIRECTORY)
            # Sync file if it's moved to the directory
            elif event.mask & pyinotify.IN_MOVED_TO:
                sync_static_files(event.pathname, WEB_DIRECTORY)
            # Remove file from destination if deleted or moved away
            elif event.mask & (pyinotify.IN_DELETE | pyinotify.IN_MOVED_FROM):
                try:
                    rel_path = os.path.relpath(event.pathname, WEB_STATIC_DIRECTORY)
                    dest_path = os.path.join(WEB_DIRECTORY, rel_path)
                    if os.path.exists(dest_path):
                        if os.path.isdir(dest_path):
                            shutil.rmtree(dest_path)
                        else:
                            os.remove(dest_path)
                        print(f"Removed from destination: {dest_path}")
                except Exception as e:
                    print(f"Error removing {dest_path}: {e}")

# Main function to start monitoring
def main():
    # Create a new watch manager
    wm = pyinotify.WatchManager()
    # Associate the watch manager with a notifier
    notifier = pyinotify.Notifier(wm, EventHandler())
    
    # Recursively add watches on both directories
    print(f"Monitoring directory: {WEB_DIRECTORY} and its subdirectories")
    add_watch_recursive(wm, WEB_DIRECTORY)
    
    print(f"Monitoring directory: {WEB_STATIC_DIRECTORY} and its subdirectories")
    add_watch_recursive(wm, WEB_STATIC_DIRECTORY)
    
    # Loop forever and handle events
    notifier.loop()

if __name__ == "__main__":
    main()

