# -*- coding: utf-8 -*-
import os
import gi
import model.guiapi
import model.api
import model.log

from gui.gui_app import FaradayUi
from config.configuration import getInstanceConfiguration
from utils.logs import getLogger
from appwindow import AppWindow

from dialogs import PreferenceWindowDialog
from dialogs import NewWorkspaceDialog
from dialogs import PluginOptionsDialog
from dialogs import NotificationsDialog
from dialogs import aboutDialog

from mainwidgets import Sidebar
from mainwidgets import ConsoleLog
from mainwidgets import Terminal
from mainwidgets import Statusbar

from gui.loghandler import GUIHandler
from utils.logs import addHandler

gi.require_version('Gtk', '3.0')
gi.require_version('Vte', '2.91')

from gi.repository import Gio, Gtk, GdkPixbuf

CONF = getInstanceConfiguration()


class GuiApp(Gtk.Application, FaradayUi):
    """
    Creates the application and has the necesary callbacks to FaradayUi
    Right now handles by itself only the menu, everything is else is
    appWindow's resposibility as far as the initial UI goes.
    The dialogs are found inside the dialogs module
    """

    def __init__(self, model_controller, plugin_manager, workspace_manager):

        FaradayUi.__init__(self,
                           model_controller,
                           plugin_manager,
                           workspace_manager)

        Gtk.Application.__init__(self, application_id="org.infobyte.faraday",
                                 flags=Gio.ApplicationFlags.FLAGS_NONE)

        self.window = None

    def getMainWindow(self):
        """Returns the main window. This is none only at the
        the startup, the GUI will create one as soon as do_activate() is called
        """
        return self.window

    def createWorkspace(self, name, description="", w_type=""):
        """Pretty much copy/pasted from the QT3 GUI.
        Uses the instance of workspace manager passed into __init__ to
        get all the workspaces names and see if they don't clash with
        the one the user wrote. If everything's fine, it saves the new
        workspace"""

        if name in self.getWorkspaceManager().getWorkspacesNames():

            model.api.log("A workspace with name %s already exists"
                          % name, "ERROR")
        else:
            model.api.log("Creating workspace '%s'" % name)
            model.api.devlog("Looking for the delegation class")
            manager = self.getWorkspaceManager()
            try:
                w = manager.createWorkspace(name, description,
                                            manager.namedTypeToDbType(w_type))
                CONF.setLastWorkspace(w.name)
                CONF.saveConfig()
            except Exception as e:
                model.guiapi.notification_center.showDialog(str(e))

    def do_startup(self):
        """
        GTK calls this method after Gtk.Application.run()
        Sets up necesary acttions on menu and toolbar buttons
        Also reads the .xml file from menubar.xml
        """
        Gtk.Application.do_startup(self)  # deep GTK magic

        self.sidebar = Sidebar(self.workspace_manager,
                               self.changeWorkspace,
                               CONF.getLastWorkspace())

        self.terminal = Terminal(CONF)
        self.console_log = ConsoleLog()
        self.statusbar = Statusbar(self.on_click_notifications)
        self.notificationsModel = Gtk.ListStore(str)

        action = Gio.SimpleAction.new("about", None)
        action.connect("activate", self.on_about)
        self.add_action(action)

        action = Gio.SimpleAction.new("quit", None)
        action.connect("activate", self.on_quit)
        self.add_action(action)

        action = Gio.SimpleAction.new("preferences", None)
        action.connect("activate", self.on_preferences)
        self.add_action(action)

        action = Gio.SimpleAction.new("pluginOptions", None)
        action.connect("activate", self.on_pluginOptions)
        self.add_action(action)

        action = Gio.SimpleAction.new("new", None)
        action.connect("activate", self.on_new_button)
        self.add_action(action)

        action = Gio.SimpleAction.new("new_terminal")  # new terminal = new tab
        action.connect("activate", self.on_new_terminal_button)
        self.add_action(action)

        dirname = os.path.dirname(os.path.abspath(__file__))
        builder = Gtk.Builder.new_from_file(dirname + '/menubar.xml')
        builder.connect_signals(self)
        appmenu = builder.get_object('appmenu')
        self.set_app_menu(appmenu)
        helpMenu = builder.get_object('Help')
        self.set_menubar(helpMenu)

    def do_activate(self):
        """If there's no window, create one and present it (show it to user).
        If there's a window, just present it"""

        # We only allow a single window and raise any existing ones
        if not self.window:
            # Windows are associated with the application
            # when the last one is closed the application shuts down
            self.window = AppWindow(self.sidebar,
                                    self.terminal,
                                    self.console_log,
                                    self.statusbar,
                                    application=self,
                                    title="Faraday")
        self.window.present()

        self.loghandler = GUIHandler()
        model.guiapi.setMainApp(self)
        addHandler(self.loghandler)
        self.loghandler.registerGUIOutput(self.window)

        notifier = model.log.getNotifier()
        notifier.widget = self.window
        model.guiapi.notification_center.registerWidget(self.window)

    def postEvent(self, receiver, event):
        if receiver is None:
            receiver = self.getMainWindow()
        if event.type() == 3131:
            receiver.emit("new_log", event.text)
        if event.type() == 5100:
            self.notificationsModel.prepend([event.change.getMessage()])
            receiver.emit("new_notif")
        if event.type() == 3132:
            dialog_text = event.text
            dialog = Gtk.MessageDialog(self.window, 0,
                                       Gtk.MessageType.INFO,
                                       Gtk.ButtonsType.OK,
                                       dialog_text)
            dialog.run()
            dialog.destroy()

    def on_about(self, action, param):
        """ Defines what happens when you press 'about' on the menu"""

        about_dialog = aboutDialog(self.window)
        about_dialog.run()
        about_dialog.destroy()

    def on_preferences(self, action, param):
        """Defines what happens when you press 'preferences' on the menu"""

        preference_window = PreferenceWindowDialog()
        preference_window.show_all()

    def on_pluginOptions(self, action, param):
        """Defines what happens when you press "Plugins" on the menu"""
        pluginsOption_window = PluginOptionsDialog(self.plugin_manager)
        pluginsOption_window.show_all()

    def on_new_button(self, action, params):
        "Defines what happens when you press the 'new' button on the toolbar"
        new_workspace_dialog = NewWorkspaceDialog(self.createWorkspace,
                                                  self.workspace_manager,
                                                  self.sidebar)
        new_workspace_dialog.show_all()

    def on_new_terminal_button(self, action, params):
        """When the user clicks on the new_terminal button, creates a new
        instance of the Terminal and tells the window to add it as a new tab
        for the notebook"""
        new_terminal = Terminal(CONF)
        the_new_terminal = new_terminal.getTerminal()
        AppWindow.new_tab(self.window, the_new_terminal)

    def on_click_notifications(self, button):

        notifications_view = Gtk.TreeView(self.notificationsModel)
        renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn("Notifications", renderer, text=0)
        notifications_view.append_column(column)
        notifications_dialog = NotificationsDialog(notifications_view,
                                                   self.delete_notifications)
        notifications_dialog.show_all()

    def delete_notifications(self):
        self.notificationsModel.clear()
        self.window.emit("clear_notifications")

    def changeWorkspace(self, selection):
        """Pretty much copy/pasted from QT3 GUI.
        Selection is actually used nowhere, but the connect function is
        Sidebar passes it as an argument so well there it is"""

        tree_model, treeiter = selection.get_selected()
        workspaceName = tree_model[treeiter][0]

        try:
            ws = super(GuiApp, self).openWorkspace(workspaceName)
        except Exception as e:
            model.guiapi.notification_center.showDialog(str(e))
            ws = self.openDefaultWorkspace()
        workspace = ws.name
        CONF.setLastWorkspace(workspace)
        CONF.saveConfig()
        return ws

    def run(self, args):
        """First method to run, as defined by FaradayUi. This method is
        mandatory"""

        workspace = args.workspace
        try:
            ws = super(GuiApp, self).openWorkspace(workspace)
        except Exception as e:
            getLogger(self).error(
                ("Your last workspace %s is not accessible, "
                 "check configuration") % workspace)
            getLogger(self).error(str(e))
            ws = self.openDefaultWorkspace()
        workspace = ws.name

        CONF.setLastWorkspace(workspace)
        CONF.saveConfig()
        Gtk.Application.run(self)

    def on_quit(self, action, param):
        self.quit()
