import json
import os
import platform
import re
import subprocess
import sys
from pathlib import Path
import zipfile

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
AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".aac"}

DAW_CONFIGS = {
    "fl_studio": {
        "label": "FL Studio",
        "extensions": (".flp", ".zip"),
        "zip_projects": True,
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


def project_dirs_from_data(data):
    """Read the multi-folder config, falling back to the pre-1.2 single folder."""
    configured = data.get("_projects_dirs")
    if not isinstance(configured, list):
        configured = [data.get("_projects_dir")]

    result = []
    seen = set()
    for path in configured:
        if not isinstance(path, str) or not path.strip():
            continue
        normalized = os.path.abspath(os.path.expanduser(path.strip()))
        key = os.path.normcase(normalized)
        if key not in seen:
            result.append(normalized)
            seen.add(key)
    return result


def is_valid_zipped_project(path):
    try:
        with zipfile.ZipFile(path) as archive:
            return any(name.casefold().endswith(".flp") for name in archive.namelist())
    except (OSError, zipfile.BadZipFile):
        return False


def project_timestamps(project_path, main_file=None):
    project_stat = os.stat(project_path)
    created_at = getattr(project_stat, "st_birthtime", None)
    if created_at is None and platform.system() == "Windows":
        created_at = project_stat.st_ctime
    modified_at = os.path.getmtime(main_file or project_path)
    return created_at, modified_at


def preview_audio_base(project_path):
    project_path = os.path.realpath(project_path)
    return project_path if os.path.isdir(project_path) else os.path.dirname(project_path)


def preview_audio_reference(audio_path, project_path):
    audio_path = os.path.realpath(audio_path)
    base = preview_audio_base(project_path)
    try:
        relative = os.path.relpath(audio_path, base)
        if relative != os.pardir and not relative.startswith(os.pardir + os.sep):
            return {"path": relative, "relative": True}
    except ValueError:
        pass
    return {"path": audio_path, "relative": False}


def resolve_preview_audio(project_path, reference):
    if isinstance(reference, str):
        reference = {"path": reference, "relative": False}
    if not isinstance(reference, dict) or not isinstance(reference.get("path"), str):
        return {"error": "No preview audio assigned"}

    stored_path = reference["path"]
    if reference.get("relative"):
        path = os.path.realpath(os.path.join(preview_audio_base(project_path), stored_path))
    else:
        path = os.path.realpath(os.path.expanduser(stored_path))
    if not os.path.isfile(path):
        return {"error": "Preview audio file not found"}
    if os.path.splitext(path)[1].casefold() not in AUDIO_EXTENSIONS:
        return {"error": "Unsupported preview audio format"}
    return {
        "ok": True,
        "name": os.path.basename(path),
        "path": path,
        "url": Path(path).as_uri(),
        "reference": reference,
    }


def assign_preview_audio(project_path, audio_path):
    if not isinstance(audio_path, str) or not audio_path.strip():
        return {"error": "No audio file dropped"}
    path = os.path.realpath(os.path.expanduser(audio_path.strip()))
    if not os.path.isfile(path):
        return {"error": "Audio file not found"}
    if os.path.splitext(path)[1].casefold() not in AUDIO_EXTENSIONS:
        return {"error": "Choose a WAV, MP3, M4A or AAC file"}
    return resolve_preview_audio(project_path, preview_audio_reference(path, project_path))


def applescript_string(value):
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'


def get_project_files(folder, daw):
    config = daw_config(daw)
    files = [
        entry.path for entry in os.scandir(folder)
        if not entry.name.startswith(".")
        and is_project_path(entry.path, config)
        and (
            not entry.name.casefold().endswith(".zip")
            or not config.get("zip_projects")
            or is_valid_zipped_project(entry.path)
        )
    ]
    files.sort(key=os.path.getmtime, reverse=True)
    return files


class Api:
    def get_config(self):
        data = load_data()
        daw = data.get("_daw", None)
        projects_dirs = project_dirs_from_data(data)
        projects_dir = projects_dirs[0] if projects_dirs else None
        return {
            "daw": daw,
            "projects_dir": projects_dir,
            "projects_dirs": projects_dirs,
            "is_configured": daw is not None and bool(projects_dirs),
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

    def set_config(self, daw, projects_dirs):
        daw = (daw or "").strip()
        if daw not in DAW_CONFIGS:
            return {"error": "Invalid DAW selection"}

        if isinstance(projects_dirs, str):
            projects_dirs = [projects_dirs]
        if not isinstance(projects_dirs, list):
            projects_dirs = []
        normalized = project_dirs_from_data({"_projects_dirs": projects_dirs})
        if not normalized:
            return {"error": "Add at least one projects folder"}
        invalid = [path for path in normalized if not os.path.isdir(path)]
        if invalid:
            return {"error": f"Folder not found: {invalid[0]}"}

        data = load_data()
        data["_daw"] = daw
        # Keep the first folder in the legacy key so v1.1 and older installs
        # still open the primary library if a user rolls back.
        data["_projects_dir"] = normalized[0]
        data["_projects_dirs"] = normalized
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

    def browse_audio_file(self, project_path):
        system = platform.system()
        initial_dir = preview_audio_base(project_path)
        try:
            if system == "Darwin":
                location = applescript_string(initial_dir)
                result = subprocess.run(
                    ["osascript", "-e",
                     'POSIX path of (choose file with prompt '
                     '"Choose preview audio (WAV, MP3, M4A or AAC)" '
                     f'default location POSIX file {location})'],
                    capture_output=True, text=True, timeout=60,
                )
                path = result.stdout.strip()
            elif system == "Windows":
                escaped_dir = initial_dir.replace("'", "''")
                ps = (
                    "Add-Type -AssemblyName System.Windows.Forms;"
                    "$d = New-Object System.Windows.Forms.OpenFileDialog;"
                    "$d.Filter = 'Audio files (*.wav;*.mp3;*.m4a;*.aac)|*.wav;*.mp3;*.m4a;*.aac';"
                    "$d.Title = 'Choose preview audio';"
                    f"$d.InitialDirectory = '{escaped_dir}';"
                    "if ($d.ShowDialog() -eq 'OK') { Write-Output $d.FileName }"
                )
                result = subprocess.run(
                    ["powershell", "-Command", ps],
                    capture_output=True, text=True, timeout=60,
                )
                path = result.stdout.strip()
            else:
                return {"error": "Unsupported platform for native picker"}

            if not path:
                return {"cancelled": True}
            return assign_preview_audio(project_path, path)
        except subprocess.TimeoutExpired:
            return {"error": "Picker timed out"}
        except Exception as e:
            return {"error": str(e)}

    def assign_audio_file(self, project_path, audio_path):
        try:
            return assign_preview_audio(project_path, audio_path)
        except Exception as e:
            return {"error": str(e)}

    def resolve_audio_file(self, project_path, reference):
        try:
            return resolve_preview_audio(project_path, reference)
        except Exception as e:
            return {"error": str(e)}

    def get_projects(self):
        store = load_data()
        projects_dirs = project_dirs_from_data(store)
        daw = store.get("_daw", "fl_studio")
        projects_dirs = [path for path in projects_dirs if os.path.isdir(path)]
        if not projects_dirs:
            return []

        config = daw_config(daw)
        skip = {name.casefold() for name in config["skip"]}
        discovered = []
        seen_paths = set()

        for projects_dir in projects_dirs:
            entries = sorted(os.scandir(projects_dir), key=lambda entry: entry.name.casefold())

            # Preserve the original behavior first: each immediate subfolder
            # is a project and its newest matching file opens by default.
            for entry in entries:
                if entry.name.casefold() in skip or entry.name.startswith("."):
                    continue
                if not entry.is_dir() or is_project_path(entry.path, config):
                    continue

                project_path = os.path.realpath(entry.path)
                path_key = os.path.normcase(project_path)
                if path_key in seen_paths:
                    continue
                files = get_project_files(entry.path, daw)
                if not files and config.get("folder_projects"):
                    files = [entry.path]
                main_file = files[0] if files else None
                created_at, modified_at = project_timestamps(project_path, main_file)
                discovered.append({
                    "base_name": entry.name,
                    "project_path": project_path,
                    "source_dir": projects_dir,
                    "main_file": main_file,
                    "project_files": files,
                    "main_flp": main_file,
                    "flps": files,
                    "created_at": created_at,
                    "modified_at": modified_at,
                    "mtime": modified_at,
                })
                seen_paths.add(path_key)

            # Some DAWs store project files or macOS packages directly in one
            # library folder instead of a containing folder per project.
            for entry in entries:
                if entry.name.startswith(".") or not is_project_path(entry.path, config):
                    continue
                if (
                    entry.name.casefold().endswith(".zip")
                    and config.get("zip_projects")
                    and not is_valid_zipped_project(entry.path)
                ):
                    continue
                project_path = os.path.realpath(entry.path)
                path_key = os.path.normcase(project_path)
                if path_key in seen_paths:
                    continue
                created_at, modified_at = project_timestamps(project_path, entry.path)
                discovered.append({
                    "base_name": project_name(entry.path, config),
                    "project_path": project_path,
                    "source_dir": projects_dir,
                    "main_file": entry.path,
                    "project_files": [entry.path],
                    "main_flp": entry.path,
                    "flps": [entry.path],
                    "created_at": created_at,
                    "modified_at": modified_at,
                    "mtime": modified_at,
                })
                seen_paths.add(path_key)

        # Metadata is keyed by project name, so remember stable display names
        # for same-named projects discovered in different library folders.
        saved_names = store.get("_project_names_by_path")
        if not isinstance(saved_names, dict):
            saved_names = {}
        used_names = set()
        projects = []
        names_changed = False
        for project in discovered:
            path_key = os.path.normcase(project["project_path"])
            name = saved_names.get(path_key)
            if not isinstance(name, str) or not name or name.casefold() in used_names:
                base_name = project["base_name"]
                name = base_name
                if name.casefold() in used_names:
                    source = os.path.basename(os.path.normpath(project["source_dir"])) or "Library"
                    name = f"{base_name} — {source}"
                    suffix = 2
                    while name.casefold() in used_names:
                        name = f"{base_name} — {source} ({suffix})"
                        suffix += 1
                saved_names[path_key] = name
                names_changed = True
            used_names.add(name.casefold())
            project["name"] = name
            project.pop("base_name", None)
            projects.append(project)

        if names_changed:
            store["_project_names_by_path"] = saved_names
            save_data(store)

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
            elif daw == "fl_studio" and path.casefold().endswith(".zip"):
                command = ["open", "-a", "FL Studio", path]
            subprocess.Popen(command)
        elif system == "Windows":
            if daw == "luna" and os.path.isdir(path):
                shortcut = os.path.join(path, "Open Session.lnk")
                if os.path.exists(shortcut):
                    path = shortcut
                os.startfile(path)
            elif daw == "fl_studio" and path.casefold().endswith(".zip"):
                executable = self._find_windows_fl_studio()
                if not executable:
                    return {"error": "Could not find FL Studio to open this ZIP project"}
                subprocess.Popen([executable, path])
            else:
                os.startfile(path)
        else:
            subprocess.Popen(["xdg-open", path])
        return {"ok": True}

    @staticmethod
    def _find_windows_fl_studio():
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, ".flp") as key:
                project_type = winreg.QueryValueEx(key, "")[0]
            with winreg.OpenKey(
                winreg.HKEY_CLASSES_ROOT, rf"{project_type}\shell\open\command"
            ) as key:
                command = winreg.QueryValueEx(key, "")[0]
            match = re.search(r'"([^"]+\.exe)"|([^"].*?\.exe)', command, re.IGNORECASE)
            if match:
                executable = (match.group(1) or match.group(2)).strip()
                if os.path.isfile(executable):
                    return executable
        except (ImportError, OSError):
            pass

        candidates = []
        for env_name in ("PROGRAMFILES", "PROGRAMFILES(X86)"):
            program_files = os.environ.get(env_name)
            image_line = os.path.join(program_files, "Image-Line") if program_files else ""
            if not os.path.isdir(image_line):
                continue
            for folder in os.listdir(image_line):
                executable = os.path.join(image_line, folder, "FL64.exe")
                if folder.casefold().startswith("fl studio") and os.path.isfile(executable):
                    candidates.append(executable)
        return sorted(candidates, reverse=True)[0] if candidates else None


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

    def enable_audio_file_drop(window):
        from webview.dom import DOMEventHandler

        def handle_drop(event):
            files = event.get("dataTransfer", {}).get("files", [])
            if not files:
                return
            path = files[0].get("pywebviewFullPath")
            if path:
                window.evaluate_js(
                    f"window.assignDroppedPreviewAudio({json.dumps(path)});"
                )

        window.dom.document.events.drop += DOMEventHandler(
            handle_drop,
            prevent_default=True,
        )

    window.events.loaded += enable_audio_file_drop
    webview.start()
