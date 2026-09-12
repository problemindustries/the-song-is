import json
import os
import platform
import subprocess
import sys

# Resource directory — works both in dev and when frozen by PyInstaller
if getattr(sys, "frozen", False):
    RESOURCES_DIR = sys._MEIPASS
else:
    RESOURCES_DIR = os.path.dirname(os.path.abspath(__file__))

# User data directory — persists across app updates
_system = platform.system()
if _system == "Darwin":
    _data_base = os.path.expanduser("~/Library/Application Support")
elif _system == "Windows":
    _data_base = os.environ.get("APPDATA", os.path.expanduser("~"))
else:
    _data_base = os.path.expanduser("~/.config")

DATA_DIR = os.path.join(_data_base, "The Song Is")
os.makedirs(DATA_DIR, exist_ok=True)
DATA_FILE = os.path.join(DATA_DIR, "data.json")

DAW_CONFIGS = {
    "fl_studio": {
        "label": "FL Studio",
        "extensions": (".flp",),
        "skip": {"Backup", "Templates"},
        "default_dir": os.path.expanduser("~/Documents/Image-Line/FL Studio/Projects"),
    },
    "ableton": {
        "label": "Ableton Live",
        "extensions": (".als",),
        "skip": {"Backup", "Templates", "Samples"},
        "default_dir": os.path.expanduser(
            "~/Music/Ableton/Projects" if _system == "Darwin"
            else "~/Documents/Ableton/Projects"
        ),
    },
    "bitwig": {
        "label": "Bitwig Studio",
        "extensions": (".bwproject",),
        "skip": {"backup", "auto-backups"},
        "default_dir": os.path.expanduser("~/Documents/Bitwig Studio/Projects"),
    },
    "reaper": {
        "label": "REAPER",
        "extensions": (".rpp",),
        "skip": {"Backup", "Backups"},
        "default_dir": "",
    },
    "mixcraft": {
        "label": "Mixcraft Pro Studio",
        "extensions": (".mx10", ".mx9", ".mx8", ".mx7", ".mx6", ".mx5", ".mxc"),
        "skip": {"Backup", "Templates"},
        "default_dir": os.path.expanduser("~/Documents/Mixcraft Projects"),
    },
    "luna": {
        "label": "LUNA",
        "extensions": (),
        "skip": {"Backups", "Templates"},
        "folder_projects": True,
        "default_dir": os.path.expanduser(
            "~/Music/LUNA Sessions" if _system == "Darwin"
            else "~/Documents/LUNA Sessions"
        ),
    },
    "logic": {
        "label": "Logic Pro",
        "extensions": (".logicx",),
        "skip": {"Templates"},
        "default_dir": os.path.expanduser("~/Music/Logic"),
    },
    "garageband": {
        "label": "GarageBand",
        "extensions": (".band",),
        "skip": set(),
        "default_dir": os.path.expanduser("~/Music/GarageBand"),
    },
    "studio_one": {
        "label": "Studio One",
        "extensions": (".song",),
        "skip": {"Templates"},
        "default_dir": os.path.expanduser("~/Documents/Studio One/Songs"),
    },
    "cubase": {
        "label": "Cubase",
        "extensions": (".cpr",),
        "skip": {"Backup", "Templates"},
        "default_dir": "",
    },
    "nuendo": {
        "label": "Nuendo",
        "extensions": (".npr",),
        "skip": {"Backup", "Templates"},
        "default_dir": "",
    },
    "pro_tools": {
        "label": "Pro Tools",
        "extensions": (".ptx", ".ptf"),
        "skip": {"Session File Backups", "Video Files", "WaveCache.wfm"},
        "default_dir": os.path.expanduser("~/Documents/Pro Tools"),
    },
    "reason": {
        "label": "Reason",
        "extensions": (".reason",),
        "skip": {"Backups", "Templates"},
        "default_dir": "",
    },
    "cakewalk": {
        "label": "Cakewalk",
        "extensions": (".cwp",),
        "skip": {"Audio Data", "Picture Cache", "Templates"},
        "default_dir": os.path.expanduser("~/Documents/Cakewalk Projects"),
    },
    "waveform": {
        "label": "Waveform",
        "extensions": (".tracktionedit",),
        "skip": {"Backups", "Templates"},
        "default_dir": "",
    },
    "ardour": {
        "label": "Ardour",
        "extensions": (".ardour",),
        "skip": {"dead_sounds", "export", "interchange", "peaks"},
        "default_dir": "",
    },
    "lmms": {
        "label": "LMMS",
        "extensions": (".mmpz", ".mmp"),
        "skip": {"templates"},
        "default_dir": os.path.expanduser("~/Documents/lmms/projects"),
    },
    "renoise": {
        "label": "Renoise",
        "extensions": (".xrns",),
        "skip": {"Backups", "Templates"},
        "default_dir": "",
    },
    "adobe_audition": {
        "label": "Adobe Audition",
        "extensions": (".sesx",),
        "skip": {"Backup", "Templates"},
        "default_dir": "",
    },
}


def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE) as f:
            return json.load(f)
    return {}


def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)


def daw_config(daw):
    return DAW_CONFIGS.get(daw, DAW_CONFIGS["fl_studio"])


def is_project_path(path, config):
    name = os.path.basename(path).casefold()
    return any(name.endswith(ext.casefold()) for ext in config["extensions"])


def project_name(path, config):
    name = os.path.basename(path)
    for ext in config["extensions"]:
        if name.casefold().endswith(ext.casefold()):
            return name[:-len(ext)]
    return name


def get_project_files(folder, daw):
    config = daw_config(daw)
    files = [
        entry.path for entry in os.scandir(folder)
        if not entry.name.startswith(".") and is_project_path(entry.path, config)
    ]
    files.sort(key=os.path.getmtime, reverse=True)
    return files


class Api:
    def get_config(self):
        data = load_data()
        daw = data.get("_daw", None)
        projects_dir = data.get("_projects_dir", None)
        return {
            "daw": daw,
            "projects_dir": projects_dir,
            "is_configured": daw is not None and projects_dir is not None,
            "default_dirs": {k: v["default_dir"] for k, v in DAW_CONFIGS.items()},
            "daws": {
                key: {
                    "label": config["label"],
                    "extensions": list(config["extensions"]),
                    "folder_projects": config.get("folder_projects", False),
                }
                for key, config in DAW_CONFIGS.items()
            },
        }

    def set_config(self, daw, projects_dir):
        daw = (daw or "").strip()
        projects_dir = (projects_dir or "").strip()
        if daw not in DAW_CONFIGS:
            return {"error": "Invalid DAW selection"}
        if not projects_dir or not os.path.isdir(projects_dir):
            return {"error": "Invalid or missing folder path"}
        data = load_data()
        data["_daw"] = daw
        data["_projects_dir"] = projects_dir
        save_data(data)
        return {"ok": True}

    def browse_folder(self):
        system = platform.system()
        try:
            if system == "Darwin":
                result = subprocess.run(
                    ["osascript", "-e",
                     'POSIX path of (choose folder with prompt "Select your DAW Projects folder")'],
                    capture_output=True, text=True, timeout=60,
                )
                path = result.stdout.strip().rstrip("/")
            elif system == "Windows":
                ps = (
                    "Add-Type -AssemblyName System.Windows.Forms;"
                    "$d = New-Object System.Windows.Forms.FolderBrowserDialog;"
                    "$d.Description = 'Select your DAW Projects folder';"
                    "if ($d.ShowDialog() -eq 'OK') { Write-Output $d.SelectedPath }"
                )
                result = subprocess.run(
                    ["powershell", "-Command", ps],
                    capture_output=True, text=True, timeout=60,
                )
                path = result.stdout.strip()
            else:
                return {"error": "Unsupported platform for native picker"}

            if path and os.path.isdir(path):
                return {"path": path}
            return {"error": "No folder selected"}

        except subprocess.TimeoutExpired:
            return {"error": "Picker timed out"}
        except Exception as e:
            return {"error": str(e)}

    def get_projects(self):
        store = load_data()
        projects_dir = store.get("_projects_dir")
        daw = store.get("_daw", "fl_studio")
        if not projects_dir or not os.path.exists(projects_dir):
            return []

        config = daw_config(daw)
        skip = {name.casefold() for name in config["skip"]}
        projects = []
        seen_names = set()
        entries = sorted(os.scandir(projects_dir), key=lambda entry: entry.name.casefold())

        # Preserve the original behavior first: each immediate subfolder is a
        # project, and its newest matching file is the one opened by default.
        for entry in entries:
            if entry.name.casefold() in skip or entry.name.startswith("."):
                continue
            if not entry.is_dir() or is_project_path(entry.path, config):
                continue

            files = get_project_files(entry.path, daw)
            if not files and config.get("folder_projects"):
                files = [entry.path]
            main_file = files[0] if files else None
            mtime = os.path.getmtime(main_file) if main_file else None

            projects.append({
                "name": entry.name,
                "main_file": main_file,
                "project_files": files,
                "main_flp": main_file,
                "flps": files,
                "mtime": mtime,
            })
            seen_names.add(entry.name.casefold())

        # Some DAWs store project files or macOS packages directly in one
        # library folder instead of creating a containing folder per project.
        for entry in entries:
            if entry.name.startswith(".") or not is_project_path(entry.path, config):
                continue
            name = project_name(entry.path, config)
            if name.casefold() in seen_names:
                continue
            projects.append({
                "name": name,
                "main_file": entry.path,
                "project_files": [entry.path],
                "main_flp": entry.path,
                "flps": [entry.path],
                "mtime": os.path.getmtime(entry.path),
            })
            seen_names.add(name.casefold())

        projects.sort(key=lambda project: project["name"].casefold())

        return projects

    def get_metadata(self):
        return load_data()

    def set_metadata(self, data):
        save_data(data)
        return {"ok": True}

    def load_data_file(self):
        system = platform.system()
        try:
            if system == "Darwin":
                result = subprocess.run(
                    ["osascript", "-e",
                     'POSIX path of (choose file with prompt "Select your data.json backup")'],
                    capture_output=True, text=True, timeout=60,
                )
                path = result.stdout.strip()
            elif system == "Windows":
                ps = (
                    "Add-Type -AssemblyName System.Windows.Forms;"
                    "$d = New-Object System.Windows.Forms.OpenFileDialog;"
                    "$d.Filter = 'JSON files (*.json)|*.json|All files (*.*)|*.*';"
                    "$d.Title = 'Select your data.json backup';"
                    "if ($d.ShowDialog() -eq 'OK') { Write-Output $d.FileName }"
                )
                result = subprocess.run(
                    ["powershell", "-Command", ps],
                    capture_output=True, text=True, timeout=60,
                )
                path = result.stdout.strip()
            else:
                return {"error": "Unsupported platform for native picker"}

            if not path or not os.path.isfile(path):
                return {"error": "No file selected"}

            with open(path) as f:
                data = json.load(f)

            save_data(data)
            return {"ok": True, "data": data}

        except json.JSONDecodeError:
            return {"error": "Selected file is not valid JSON"}
        except subprocess.TimeoutExpired:
            return {"error": "Picker timed out"}
        except Exception as e:
            return {"error": str(e)}

    def export_data(self, filename):
        system = platform.system()
        desktop = os.path.expanduser("~/Desktop")
        try:
            if system == "Darwin":
                result = subprocess.run(
                    ["osascript", "-e",
                     f'POSIX path of (choose file name with prompt "Export data as:" default name "{filename}" default location POSIX file "{desktop}")'],
                    capture_output=True, text=True, timeout=60,
                )
                path = result.stdout.strip()
            elif system == "Windows":
                ps = (
                    "Add-Type -AssemblyName System.Windows.Forms;"
                    "$d = New-Object System.Windows.Forms.SaveFileDialog;"
                    "$d.Filter = 'JSON files (*.json)|*.json';"
                    f"$d.FileName = '{filename}';"
                    "$d.InitialDirectory = [Environment]::GetFolderPath('Desktop');"
                    "if ($d.ShowDialog() -eq 'OK') { Write-Output $d.FileName }"
                )
                result = subprocess.run(
                    ["powershell", "-Command", ps],
                    capture_output=True, text=True, timeout=60,
                )
                path = result.stdout.strip()
            else:
                return {"error": "Unsupported platform"}

            if not path:
                return {"error": "No file selected"}

            with open(path, "w") as f:
                json.dump(load_data(), f, indent=2)
            return {"ok": True, "path": path}

        except subprocess.TimeoutExpired:
            return {"error": "Dialog timed out"}
        except Exception as e:
            return {"error": str(e)}

    def open_file(self, path, daw=None):
        if not path or not os.path.exists(path):
            return {"error": "File not found"}
        system = platform.system()
        if system == "Darwin":
            command = ["open", path]
            if daw == "luna" and os.path.isdir(path):
                command = ["open", "-a", "LUNA", path]
            subprocess.Popen(command)
        elif system == "Windows":
            if daw == "luna" and os.path.isdir(path):
                shortcut = os.path.join(path, "Open Session.lnk")
                if os.path.exists(shortcut):
                    path = shortcut
            os.startfile(path)
        else:
            subprocess.Popen(["xdg-open", path])
        return {"ok": True}


if __name__ == "__main__":
    import webview

    if _system == "Darwin":
        try:
            from AppKit import NSApplication, NSBundle, NSImage
            NSBundle.mainBundle().infoDictionary()["CFBundleName"] = "The Song Is"
            icon_path = os.path.join(RESOURCES_DIR, "static", "favicon.svg")
            if os.path.exists(icon_path):
                ns_app = NSApplication.sharedApplication()
                icon = NSImage.alloc().initWithContentsOfFile_(icon_path)
                if icon:
                    ns_app.setApplicationIconImage_(icon)
        except Exception:
            pass
    elif _system == "Windows":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "com.thesongis.app"
            )
        except Exception:
            pass

    html_path = os.path.join(RESOURCES_DIR, "templates", "index.html")
    api = Api()

    version_file = os.path.join(RESOURCES_DIR, "static", "version.txt")
    if os.path.exists(version_file):
        with open(version_file) as f:
            app_title = f"The Song Is {f.read().strip()}"
    else:
        app_title = "The Song Is"

    window = webview.create_window(
        app_title,
        url=f"file://{html_path}",
        js_api=api,
        width=1400,
        height=900,
        min_size=(900, 600),
    )
    webview.start()
