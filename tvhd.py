import gi
import sys
import os
import subprocess
from datetime import datetime
import time
import gi.repository
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk
import mpv
import vlc

class DVBV5Player(Gtk.Window):

    def __init__(self):
        Gtk.Window.__init__(self, title="DVBV5 Player")

        # Sprawdzenie istnienia katalogu app_conf i utworzenie go w razie potrzeby
        self.create_app_conf_directory()

        self.playlist_files = []
        self.playlist_items = {}
        self.selected_playlist_file = None

        self.playlist_file_combo = Gtk.ComboBoxText()
        self.playlist_item_combo = Gtk.ComboBoxText()
        self.engine_combo = Gtk.ComboBoxText()

        self.play_button = Gtk.Button(label="Play")
        self.play_button.connect("clicked", self.play_channel)

        self.stop_button = Gtk.Button(label="Stop")
        self.stop_button.connect("clicked", self.stop_channel)

        self.drawing_area = Gtk.DrawingArea()
        self.drawing_area.set_size_request(1280, 720)  # Set video area size

        # HeaderBar to hold buttons
        self.header_bar = Gtk.HeaderBar()
        self.header_bar.set_show_close_button(True)
        self.header_bar.pack_start(self.playlist_file_combo)
        self.header_bar.pack_start(self.playlist_item_combo)
        self.header_bar.pack_end(self.engine_combo)
        self.header_bar.pack_end(self.play_button)
        self.header_bar.pack_end(self.stop_button)
        
        self.grid = Gtk.Grid()
        self.grid.attach(self.drawing_area, 0, 0, 1, 1)  # Add video area to grid

        self.add(self.grid)
        self.set_titlebar(self.header_bar)  # Set HeaderBar as title bar

        # Handle window state changes
        self.connect("window-state-event", self.on_window_state_event)

        self.player = None  # Initialize player attribute

        self.load_playlist_files()  # Load playlist files on startup

        # Connect the changed signal of playlist_file_combo to on_playlist_file_changed method
        self.playlist_file_combo.connect("changed", self.on_playlist_file_changed)

        self.playlist_files = []  # Lista przechowująca pełne ścieżki do plików playlisty
        self.load_playlist_files()  # Load playlist files on startup

        # Populate engine combo
        self.engine_combo.append_text("libVLC")
        self.engine_combo.append_text("mpv-python")
        self.engine_combo.set_active(0)  # Set "libVLC" as default engine

        # Auto wczytywanie playlist z katalogów app_conf/a0 do app_conf/a3
        for i in range(4):
            playlist_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), f'app_conf/a{i}')
            self.load_playlists_from_directory(playlist_dir)

    def create_app_conf_directory(self):
        app_conf_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app_conf")
        if not os.path.exists(app_conf_dir):
            os.makedirs(app_conf_dir)
            for i in range(4):
                subdir = os.path.join(app_conf_dir, f'a{i}')
                os.makedirs(subdir)
                for j in range(4):
                    os.makedirs(os.path.join(subdir, f'f{j}'))

    def on_window_state_event(self, widget, event):
        if event.new_window_state & Gdk.WindowState.MAXIMIZED:
            self.grid.set_row_homogeneous(True)
            self.grid.set_column_homogeneous(True)
        else:
            self.grid.set_row_homogeneous(False)
            self.grid.set_column_homogeneous(False)

    def load_playlist_files(self):
        playlist_dir = os.path.dirname(os.path.abspath(__file__))
        for file_name in os.listdir(playlist_dir):
            if file_name.endswith(".conf"):
                file_path = os.path.join(playlist_dir, file_name)
                self.playlist_files.append(file_path)  # Dodanie pełnej ścieżki do listy
                file_name_without_extension = os.path.splitext(file_name)[0]
                # Usunięcie rozszerzenia ".conf"
                file_name_without_extension = file_name_without_extension.replace(".conf", "")
                self.playlist_file_combo.append_text(file_name_without_extension)

    def load_playlists_from_directory(self, directory):
        for root, dirs, files in os.walk(directory):
            for file_name in files:
                if file_name.endswith(".conf"):
                    full_path = os.path.join(root, file_name)
                    self.playlist_files.append(full_path)
                    self.playlist_file_combo.append_text(file_name)

    def on_playlist_file_changed(self, combo):
        text = combo.get_active_text()
        if text:
            # Pobranie pełnej ścieżki do wybranego pliku z listy playlist_files
            file_index = combo.get_active()
            file_path = self.playlist_files[file_index]
            self.selected_playlist_file = file_path
            self.load_and_fill_playlist(self.selected_playlist_file)

            # Clear the current selection in playlist_item_combo
            self.playlist_item_combo.set_active(-1)
            
    def load_and_fill_playlist(self, path):
        self.playlist_items.clear()
        self.playlist_item_combo.remove_all()

        if os.path.exists(path):
            with open(path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("[") and line.endswith("]"):
                        channel_name = line[1:-1]
                        self.playlist_item_combo.append_text(channel_name)
                        self.playlist_items[channel_name] = None
        else:
            print(f"File not found: {path}")

    def play_channel(self, widget):
        selected_item = self.playlist_item_combo.get_active_text()
        if selected_item:
            now = datetime.now()
            file_name = now.strftime("%Y-%m-%d_%H:%M:%S") + ".ts"
            temp_file_path = f"/dev/shm/{file_name}"  # Temporary file in RAM
            command = ["dvbv5-zap", selected_item, "-c", self.selected_playlist_file, "-o", temp_file_path]
            # Pobranie parametrów -a i -f z nazwy katalogu playlisty
            params = os.path.dirname(self.selected_playlist_file).split(os.sep)
            a_param = params[-2][-1]  # Pobranie ostatniego znaku z przedostatniego elementu ścieżki
            f_param = params[-1][-1]  # Pobranie ostatniego znaku z ostatniego elementu ścieżki
            # Dodanie pobranych parametrów do polecenia dvbv5-zap
            command.extend(["-a", a_param, "-f", f_param])
            print(f"Starting dvbv5-zap with parameters: {command}")
            subprocess.Popen(command)
            time.sleep(5)  # Delay for 5 seconds
            selected_engine = self.engine_combo.get_active_text()
            if selected_engine == "libVLC":
                self.play_with_libvlc(temp_file_path)
            elif selected_engine == "mpv-python":
                self.play_with_mpv(temp_file_path)
        else:
            print("No selected item.")

    def play_with_libvlc(self, file_path):
        # Create a new libVLC instance
        self.player = vlc.Instance('--no-xlib', '--vout=gtk')
        
        # Create a new media player and set the video area
        self.media_player = self.player.media_player_new()
        self.media = self.player.media_new(f"file://{file_path}")
        self.media_player.set_media(self.media)

        # Set the video area to the window identifier for Gtk.DrawingArea
        self.video_window = self.drawing_area.get_window()
        if sys.platform == "win32":
            self.media_player.set_hwnd(self.video_window.get_handle())
        else:
            self.media_player.set_xwindow(self.video_window.get_xid())

        # Set black video background
        self.media_player.video_set_marquee_int(vlc.VideoMarqueeOption.Enable, 0)
        self.media_player.video_set_marquee_int(vlc.VideoMarqueeOption.Color, 0x000000)

        # Play the media player
        self.media_player.play()

    def play_with_mpv(self, file_path):
        # Utwórz odtwarzacz mpv
        self.mpv = mpv.MPV(wid=str(self.drawing_area.get_property("window").get_xid()))
        self.mpv.play(file_path)

    def stop_channel(self, widget):
        subprocess.run(["killall", "dvbv5-zap"])
        for file_name in os.listdir("/dev/shm"):
            if file_name.endswith(".ts"):
                os.remove(os.path.join("/dev/shm", file_name))
        if self.player:
            self.media_player.stop()
        if hasattr(self, 'mpv'):
            self.mpv.terminate()

win = DVBV5Player()
win.connect("destroy", Gtk.main_quit)
win.show_all()
Gtk.main()

