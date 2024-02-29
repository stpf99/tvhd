import gi
import os
import subprocess
from datetime import datetime
import time
import gi.repository
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib, Pango 
import mpv

class DVBV5Player(Gtk.Window):

    def __init__(self):
        Gtk.Window.__init__(self, title="DVBV5 Player")

        self.create_app_conf_directory()

        self.playlist_files = []
        self.playlist_items = {}
        self.selected_playlist_file = None

        self.playlist_file_combo = Gtk.ComboBoxText()
        self.playlist_item_combo = Gtk.ComboBoxText()

        self.play_button = Gtk.Button(label="Play")
        self.play_button.connect("clicked", self.play_channel)

        self.stop_button = Gtk.Button(label="Stop")
        self.stop_button.connect("clicked", self.stop_channel)

        self.drawing_area = Gtk.DrawingArea()
        self.drawing_area.set_size_request(1280, 720)  # Set video area size
        self.drawing_area.set_vexpand(True)
        self.drawing_area.set_hexpand(True)
        self.signal_info_label = Gtk.Label(label="Signal Info: N/A")


        self.textview = Gtk.TextView()
        custom_font = Pango.FontDescription("Arial 18")
        self.textview.override_font(custom_font)
        self.textview.set_editable(False)
        self.textview.set_wrap_mode(Gtk.WrapMode.WORD)

        self.textbuffer = self.textview.get_buffer()
        self.scrolledwindow = Gtk.ScrolledWindow()
        self.scrolledwindow.set_size_request(-1, 5)  # -1 oznacza, że szerokość zostanie zachowana domyślna
        self.scrolledwindow.set_vexpand(False)
        self.scrolledwindow.set_hexpand(True)
        # Create a Gtk.Adjustment object
        adjustment = Gtk.Adjustment(value=1, lower=0, upper=100, step_increment=1, page_increment=10, page_size=0)

        # Set the vertical adjustment of the scrolled window
        self.scrolledwindow.set_vadjustment(adjustment)
        self.scrolledwindow.add(self.textview)

        self.header_bar = Gtk.HeaderBar()
        self.header_bar.set_show_close_button(True)
        self.header_bar.pack_start(self.playlist_file_combo)
        self.header_bar.pack_start(self.playlist_item_combo)
        self.header_bar.pack_end(self.play_button)
        self.header_bar.pack_end(self.stop_button)

        self.grid = Gtk.Grid()
        self.grid.attach(self.drawing_area, 0, 0, 1, 1)  
        self.grid.attach_next_to(self.scrolledwindow, self.drawing_area, Gtk.PositionType.BOTTOM, 1, 1)

        self.add(self.grid)
        self.set_titlebar(self.header_bar)  


        self.player = None  

        self.playlist_file_combo.connect("changed", self.on_playlist_file_changed)

        self.playlist_files = []  


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
            command = ["dvbv5-zap", selected_item, "-c", self.selected_playlist_file, "-o", "pipe:0"]
            params = os.path.dirname(self.selected_playlist_file).split(os.sep)
            a_param = params[-2][-1]  
            f_param = params[-1][-1]  
            command.extend(["-a", a_param, "-f", f_param])
            print(f"Starting dvbv5-zap with parameters: {command}")

            try:
                # Otwarcie potoku jako standardowe wejście dla procesu
                subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
                # Uruchomienie dvb-fe-tool i przechwycenie jego wyjścia
                fe_tool_command = ["dvb-fe-tool", "--femon"]
                fe_tool_command.extend(["-a", a_param, "-f", f_param])  # Dodanie parametrów adaptera i frontendu
                fe_tool_process = subprocess.Popen(fe_tool_command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

                # Aktualizacja etykiety informacji o sygnale w czasie rzeczywistym
                GLib.timeout_add(1000, self.update_signal_info, fe_tool_process.stdout)

                time.sleep(1)
                self.play_with_mpv()
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

    def play_with_mpv(self):
        self.mpv = mpv.MPV(input_default_bindings=True, input_vo_keyboard=True, wid=str(self.drawing_area.get_property("window").get_xid()))
        self.mpv.play("pipe:0")  # Potok jako źródło

    def stop_channel(self, widget):
        subprocess.run(["killall", "dvbv5-zap", "dvb-fe-tool"])
        if hasattr(self, 'mpv'):
            self.mpv.terminate()

win = DVBV5Player()
win.connect("destroy", Gtk.main_quit)
win.show_all()
Gtk.main()

