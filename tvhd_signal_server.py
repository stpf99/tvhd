import gi
import sys
import os
import subprocess
from datetime import datetime
import time
import gi.repository
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib, Pango 
import mpv
import vlc

class DVBV5Player(Gtk.Window):

    def __init__(self):
        Gtk.Window.__init__(self, title="DVBV5 Player")

        self.create_app_conf_directory()

        self.playlist_files = []
        self.playlist_items = {}
        self.selected_playlist_file = None

        self.playlist_file_combo = Gtk.ComboBoxText()
        self.playlist_item_combo = Gtk.ComboBoxText()
        self.engine_combo = Gtk.ComboBoxText()
        self.host_entry = Gtk.Entry()
        self.host_entry.set_text("")  # Set default host
        self.port_entry = Gtk.Entry()
        self.port_entry.set_text("")  # Set default port

        self.play_button = Gtk.Button(label="Play")
        self.play_button.connect("clicked", self.play_channel)

        self.stop_button = Gtk.Button(label="Stop")
        self.stop_button.connect("clicked", self.stop_channel)

        self.drawing_area = Gtk.DrawingArea()
        self.drawing_area.set_size_request(1280, 720)  # Set video area size

        self.signal_info_label = Gtk.Label(label="Signal Info: N/A")


        self.textview = Gtk.TextView()
        self.textview.set_editable(False)  # Ustawienie, że obszar tekstowy jest tylko do odczytu
        self.textview.set_wrap_mode(Gtk.WrapMode.WORD)  # Ustawienie trybu zawijania tekstu
        # Ustawienie większej czcionki
        font_desc = Pango.FontDescription("Sans 16")  # Ustawienie czcionki "Sans" o rozmiarze 16
        self.textview.override_font(font_desc)
        self.textbuffer = self.textview.get_buffer()
        self.scrolledwindow = Gtk.ScrolledWindow()
        self.scrolledwindow.set_vexpand(True)
        self.scrolledwindow.set_hexpand(True)
        self.scrolledwindow.add(self.textview)

        self.header_bar = Gtk.HeaderBar()
        self.header_bar.set_show_close_button(True)
        self.header_bar.pack_start(self.playlist_file_combo)
        self.header_bar.pack_start(self.playlist_item_combo)
        self.header_bar.pack_start(self.engine_combo)
        self.header_bar.pack_start(Gtk.Label(label="Host:"))
        self.header_bar.pack_start(self.host_entry)
        self.header_bar.pack_start(Gtk.Label(label="Port:"))
        self.header_bar.pack_start(self.port_entry)
        self.header_bar.pack_end(self.play_button)
        self.header_bar.pack_end(self.stop_button)

        self.grid = Gtk.Grid()
        self.grid.attach(self.drawing_area, 0, 0, 1, 1)  
        self.grid.attach_next_to(self.scrolledwindow, self.drawing_area, Gtk.PositionType.BOTTOM, 1, 1)

        self.add(self.grid)
        self.set_titlebar(self.header_bar)  

        self.connect("window-state-event", self.on_window_state_event)

        self.player = None  

        self.load_playlist_files()  

        self.playlist_file_combo.connect("changed", self.on_playlist_file_changed)

        self.playlist_files = []  
        self.load_playlist_files()  

        self.engine_combo.append_text("libVLC")
        self.engine_combo.append_text("mpv-python")
        self.engine_combo.set_active(0)  

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
                self.playlist_files.append(file_path)  
                file_name_without_extension = os.path.splitext(file_name)[0]
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
            file_index = combo.get_active()
            file_path = self.playlist_files[file_index]
            self.selected_playlist_file = file_path
            self.load_and_fill_playlist(self.selected_playlist_file)
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
            params = os.path.dirname(self.selected_playlist_file).split(os.sep)
            a_param = params[-2][-1]  
            f_param = params[-1][-1]  
            command.extend(["-a", a_param, "-f", f_param])
            command.extend(["-H", self.host_entry.get_text(), "-T", self.port_entry.get_text()])  
            print(f"Starting dvbv5-zap with parameters: {command}")
        try:
            subprocess.Popen(command, stderr=subprocess.PIPE)
            time.sleep(5)  

            # Uruchomienie dvb-fe-tool i przechwycenie jego wyjścia
            fe_tool_command = ["dvb-fe-tool", "--femon"]
            fe_tool_command.extend(["-a", a_param, "-f", f_param])  # Dodanie parametrów adaptera i frontendu
            fe_tool_process = subprocess.Popen(fe_tool_command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

            # Aktualizacja etykiety informacji o sygnale w czasie rzeczywistym
            GLib.timeout_add(1000, self.update_signal_info, fe_tool_process.stdout)
            
            selected_engine = self.engine_combo.get_active_text()
            if selected_engine == "libVLC":
                self.play_with_libvlc(temp_file_path)
            elif selected_engine == "mpv-python":
                self.play_with_mpv(temp_file_path)
        except Exception as e:
            print(f"Error: {e}")
        else:
            print("No selected item.")

    def update_signal_info(self, output):
        # Aktualizacja informacji o sygnale na podstawie otrzymanego outputu z dvb-fe-tool
        line = output.readline().strip()
        if line:
            # Wstawienie otrzymanego wiersza do obszaru tekstowego
            self.textbuffer.insert_at_cursor(line + "\n")
            # Automatyczne przewijanie obszaru tekstowego na dół
            adj = self.scrolledwindow.get_vadjustment()
            adj.set_value(adj.get_upper() - adj.get_page_size())
        return True  # Powrót wartości True, aby funkcja została wywołana ponownie

    def play_with_libvlc(self, file_path):
        self.player = vlc.Instance('--no-xlib', '--vout=gtk')
        self.media_player = self.player.media_player_new()
        self.media = self.player.media_new(f"file://{file_path}")
        self.media_player.set_media(self.media)
        self.video_window = self.drawing_area.get_window()
        if sys.platform == "win32":
            self.media_player.set_hwnd(self.video_window.get_handle())
        else:
            self.media_player.set_xwindow(self.video_window.get_xid())
        self.media_player.video_set_marquee_int(vlc.VideoMarqueeOption.Enable, 0)
        self.media_player.video_set_marquee_int(vlc.VideoMarqueeOption.Color, 0x000000)
        self.media_player.play()

    def play_with_mpv(self, file_path):
        self.mpv = mpv.MPV(wid=str(self.drawing_area.get_property("window").get_xid()))
        self.mpv.play(file_path)

    def stop_channel(self, widget):
        subprocess.run(["killall", "dvbv5-zap", "dvb-fe-tool"])
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

