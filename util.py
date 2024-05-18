import io
import subprocess
import os
import sys
import tempfile
from typing import Callable
from urllib import request

# Set the script path and define the Wine prefix for Windows compatibility
SCRIPT_PATH = os.path.dirname(os.path.realpath(__file__))
WINEPREFIX = os.path.join(os.getenv("STEAM_COMPAT_DATA_PATH"), "pfx")

# Function to check if dependencies are installed
def check_dependencies(requirements_file):

    ret = True
    # Check if dependencies have been installed
    with open(requirements_file) as f:
        for line in f:
            package = line.strip().split('==')[0]
            try:
                __import__(package)
            except ImportError:
                log(f"{package} is missing")
                ret = False
    return ret

# Function to install or execute pip commands
def pip(command: str,venv_path=None) -> int:
    pos_pip = None
    if venv_path:
        python_executable = os.path.join(venv_path,os.path.basename(sys.executable))
        pos_pip = os.path.join(venv_path,"bin","pip")
        if not os.path.isfile(pos_pip):
            pos_pip = None
    else:
        python_executable = sys.executable


    # Try to use pip directly if possible
    if pos_pip:
        process = subprocess.Popen(f"'{pos_pip}' {command}", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()
        #for line in stdout.splitlines():
        #    if line:
        #        log(line.decode("utf8"))
        #for line in stderr.splitlines():
        #    if line:
        #        log(line.decode("utf8"))

        process.wait()
        # Check if pip command was successful
        if process.returncode == 0:
            log("pip finished")
            return process.returncode


    # Try to use the built-in pip
    process = subprocess.Popen(f"'{python_executable}' -m pip {command}", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()
    #for line in stdout.splitlines():
    #    if line:
    #        log(line.decode("utf8"))
    #for line in stderr.splitlines():
    #    if line:
    #        log(line.decode("utf8"))

    # Check if -m pip command was successful
    if process.wait() == 0:
        log("pip finished")
        return process.returncode


    # If -m pip failed, fallback to using pip.pyz
    if venv_path:
        pip_pyz = os.path.join(venv_path, "bin", "pip.pyz")
    else:
        pip_pyz = os.path.join(SCRIPT_PATH, "pip.pyz")

    # Check and download pip.pyz if not present
    if not os.path.isfile(pip_pyz):
        log("pip not found. Downloading...")
        request.urlretrieve("https://bootstrap.pypa.io/pip/pip.pyz", pip_pyz)

        # Exit if pip.pyz still not present after download
        if not os.path.isfile(pip_pyz):
            log("CRITICAL: Failed to download pip. Exiting!")
            sys.exit(1)
    else:
        log("pip not installed. Using local pip.pyz")

    # Execute the pip command using pip.pyz
    process = subprocess.Popen(f"{python_executable} {pip_pyz} {command}", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()
    #for line in stdout.splitlines():
    #    if line:
    #        log(line.decode("utf8"))
    #for line in stderr.splitlines():
    #    if line:
    #        log(line.decode("utf8"))

    log("pip finished")
    # Return the exit code of the process
    return process.wait()

# Function for logging messages
def log(message: str):
    if "WEMOD_LOG" in os.environ:
        message = str(message)
        if message and message[-1] != "\n":
            message += "\n"
        with open(os.getenv("WEMOD_LOG"), "a") as f:
            f.write(message)

# Function to display a popup with options using FreeSimpleGUI
def popup_options(title: str, message: str, options: list[str]) -> str:
    import FreeSimpleGUI as sg
    layout = [
        [sg.Text(message, auto_size_text=True)],
        [list(map(lambda option: sg.Button(option), options))]
    ]
    window = sg.Window(title, layout, finalize=True)

    selected = None
    while selected is None:
        event, values = window.read()
        selected = event if options.index(event) > -1 else None

    window.close()
    return selected

# Function to execute a command and display output in a popup
def popup_execute(title: str, command: str, onwrite: Callable[[str], None] = None) -> int:
    import FreeSimpleGUI as sg
    import subprocess as sp

    sg.theme("systemdefault")

    text_str = [""]
    text = sg.Multiline("", disabled=True, autoscroll=True, size=(80, 30))
    layout = [[text]]
    window = sg.Window(title, layout, finalize=True)
    exitcode = [-1]

    def process_func():
        process = sp.Popen(command, stdout=subprocess.PIPE, shell=True)
        for line in iter(process.stdout.readline, ''):
            if line is None or line == b'':
                break
            s_line = line.decode("utf8")
            log(s_line)
            text_str[0] = text_str[0] + s_line + "\n"
            if onwrite is not None:
                onwrite(s_line)
        exitcode[0] = process.wait()

    window.perform_long_operation(process_func, "-PROCESS COMPLETE-")

    while True:
        event, values = window.read(timeout=1000)
        if event == "-PROCESS COMPLETE-":
            break
        elif event is None:
            sys.exit(0)
        else:
            if len(text_str[0]) < 1:
                continue
            text.update(text_str[0])

    window.close()
    return exitcode[0]

# Function to download a file with progress display
def popup_download(title: str, link: str, file_name: str):
    import FreeSimpleGUI as sg
    sg.theme("systemdefault")

    status = [0, 0]

    cache = os.path.join(SCRIPT_PATH, ".cache")
    if not os.path.isdir(cache):
        os.makedirs(cache)

    progress = sg.ProgressBar(100, orientation="h", s=(50, 10))
    text = sg.Text("0%")
    layout = [[progress], [text]]
    window = sg.Window(title, layout, finalize=True)

    def update_log(status: list[int], dl: int, total: int) -> None:
        status.clear()
        status.append(dl)
        status.append(total)

    file_path = os.path.join(cache, file_name)
    download_func = lambda: download_progress(link, file_path, lambda dl, total: update_log(status, dl, total))

    window.perform_long_operation(download_func, "-DL COMPLETE-")

    while True:
        event, values = window.read(timeout=1000)
        if event == "-DL COMPLETE-":
            break
        elif event is None:
            sys.exit(0)
        else:
            if len(status) < 2:
                continue
            dl, total = status
            perc = int(100 * (dl / total)) if total > 0 else 0
            text.update(f"{perc}% ({dl}/{total})")
            progress.update(perc)

    window.close()
    return file_path

# Function to handle download progress
def download_progress(link: str, file_name: str, set_progress):
    import requests

    with open(file_name, "wb") as f:
        response = requests.get(link, stream=True)
        total_length = response.headers.get('content-length')

        if total_length is None:  # no content length header
            f.write(response.content)
        else:
            dl = 0
            total_length = int(total_length)
            for data in response.iter_content(chunk_size=4096):
                dl += len(data)
                f.write(data)
                if set_progress is not None:
                    set_progress(dl, total_length)

# Function to execute winetricks commands
def winetricks(command: str, proton_bin: str) -> int:
    winetricks_sh = os.path.join(SCRIPT_PATH, "winetricks")

    # Download winetricks if not present
    if not os.path.isfile(winetricks_sh):
        log("winetricks not found. Downloading...")
        request.urlretrieve("https://github.com/Winetricks/winetricks/raw/master/src/winetricks", winetricks_sh)
        log(f"setting exec permissions on '{winetricks_sh}'")
        process = subprocess.Popen(f"sh -c 'chmod +x {winetricks_sh}'", shell=True)
        exit_code = process.wait()

        if exit_code != 0:
            message = f"failed to set exec permission on '{winetricks_sh}'"
            log(message)
            exit_with_message("ERROR", message)

    # Prepare the command with the correct environment
    command = f"export PATH='{proton_bin}' && export WINEPREFIX='{WINEPREFIX}' && {winetricks_sh} {command}"

    # Execute the command and return the response
    resp = popup_execute("winetricks", command)
    return resp

# Function to execute wine commands
def wine(command: str, proton_bin: str) -> int:
    # Prepare the command with the correct environment
    command = f"export PATH='{proton_bin}' && export WINEPREFIX='{WINEPREFIX}' && wine {command}"

    # Execute the command and return the response
    resp = popup_execute("wine", command)
    return resp

# Function to display a message and exit
def exit_with_message(title: str, exit_message: str, exit_code: int = 1) -> None:
    import FreeSimpleGUI as sg
    sg.theme("systemdefault")

    log(exit_message)
    sg.popup_ok(exit_message)
    sys.exit(exit_code)

# Function to handle caching of files
def cache(file_path: str, default: Callable[[str], None]) -> str:
    CACHE = os.path.join(SCRIPT_PATH, ".cache")
    if not os.path.isdir(CACHE):
        log("Cache dir not found. Creating...")
        os.mkdir(CACHE)

    FILE = os.path.join(CACHE, file_path)
    if os.path.isfile(FILE):
        log(f"Cached file found. Returning '{FILE}'")
        return FILE

    log(f"Cached file not found: '{FILE}'")

    default(FILE)
    return FILE

# Function to get or download .NET Framework 4.8
def get_dotnet48() -> str:
    # Newer if you like to test: "https://download.visualstudio.microsoft.com/download/pr/2d6bb6b2-226a-4baa-bdec-798822606ff1/8494001c276a4b96804cde7829c04d7f/ndp48-x86-x64-allos-enu.exe"
    LINK = "https://download.visualstudio.microsoft.com/download/pr/7afca223-55d2-470a-8edc-6a1739ae3252/abd170b4b0ec15ad0222a809b761a036/ndp48-x86-x64-allos-enu."
    cache_func = lambda FILE: popup_download("Downloading dotnet48", LINK, FILE)

    dotnet48 = cache("ndp48-x86-x64-allos-enu.exe", cache_func)
    return dotnet48

def deref(path):
    """
    Dereferences symbolic links in the specified directory and its subdirectories.

    Args:
        path (str): The root directory to search for symbolic links.

    Returns:
        None

    Steps:
        1. Finds symbolic links using the `find` command.
        2. Generates a shell script to replace links with their targets.
        3. Creates a temporary file and writes the script to it.
        4. Executes the temporary shell script to perform dereferencing.
        5. Displays progress as the script executes.

    Notes:
        - Uses a temporary file to avoid potential issues with complex shell commands.
        - Displays progress using echo statements within the script.
    """
    links = []

    command = f"find {path} -type l -ls"
    popup_execute("Dereference: Discovering", command, lambda x: links.append([f"{x.split()[10]}", f"{x.split()[12]}"]))
    
    script=""

    for i in range(len(links)):
        link = links[i]
        target = link[0]
        src = link[1]
        perc = round(((i+1) / len(links)) * 100, 2)

        script += "rm '{}' && cat '{}' > '{}' && echo 'Progress: {}%';".format(target, src, target, perc)
    
    with tempfile.NamedTemporaryFile() as tmp:
        tmp.write(script.encode())
        popup_execute("Dereference", f"sh {tmp.name}")

def copy_folder_with_progress(source: str, dest: str, ignore=None, include_override=None) -> None:
    import shutil
    import pathlib
    import FreeSimpleGUI as sg

    if ignore == {None}:
        ignore={'pfx/drive_c/users','pfx/dosdevices','pfx/drive_c/Program Files (x86)','pfx/drive_c/Program Files',
            'pfx/drive_c/ProgramData','drive_c/openxr','pfx/drive_c/vrclient','version','config_info'}

    if include_override == {None}:
        include_override={'pfx/drive_c/ProgramData/Microsoft','pfx/drive_c/Program Files (x86)/Microsoft.NET',
                      'pfx/drive_c/Program Files (x86)/Windows NT','pfx/drive_c/Program Files (x86)/Common Files',
                      'pfx/drive_c/Program Files/Common Files','pfx/drive_c/Program Files/Common Files',
                      'pfx/drive_c/Program Files/Windows NT'}

    if ignore is None:
        ignore = set()

    if include_override is None:
        include_override = set()

    log(f"ignoring: {ignore}\nincluding anyway: {include_override}")

    def traverse_folders(path):
        allf = []
        directory = pathlib.Path(path)
        for item in directory.rglob('*'): #sorted(, key=lambda x: str(x).count('/')):
            if item.is_file():
                allf.append(item)
        return allf

    def update_progress(copied, total):
        """ Update the GUI with the current progress. """
        percentage = int(100 * (copied / total)) if total > 0 else 0
        text.update(f"{percentage}% ({copied}/{total})")
        progress.update(percentage)
        window.refresh()

    sg.theme("systemdefault")

    progress = sg.ProgressBar(100, orientation="h", s=(50, 10))
    text = sg.Text("0%")
    extra = sg.Text("Reading prefix directory, please wait..")
    layout = [[extra] ,[progress], [text]]
    window = sg.Window('Copying Prefix', layout, finalize=True)
    window.refresh()

    files = traverse_folders(source)

    copy=[]
    for f in files:
        rfile = os.path.relpath(f, source)  # get file path relative to source
        use = True  # by default, use the file

        # Check if the file is in one of the dirs to ignore
        for i in ignore:
            if os.path.commonprefix([rfile, i]) == i:
                use = False  # don't use the file if it's in an ignore directory
                break  # break out of the ignore loop

        # If the file is not in any ignored directory, check if it's in one of the dirs to include
        if not use:
            for i in include_override:
                if os.path.commonprefix([rfile, i]) == i:
                    use = True  # use the file if it's in an include_override directory
                    break  # break out of the include_override loop
        if use:
            copy.append(rfile)

    extra.update("Copying prefix, please be patient...")
    window.refresh()

    total_files = len(files)
    copied_files = 0

    for f in copy:
        src_path = os.path.join(source, f)
        dest_path = os.path.join(dest, f)
        try:
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            shutil.copy2(src_path, dest_path, follow_symlinks=False)
        except:
            pass
        copied_files += 1
        update_progress(copied_files, total_files)


    window.close()



# Main execution block, example of using popup_execute
if __name__ == "__main__":
    popup_execute("HELLO", "sh -c \"echo hello && sleep 5 && echo bye\"")
