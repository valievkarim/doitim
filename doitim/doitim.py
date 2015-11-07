#!/usr/bin/python2

import os
import os.path
import ConfigParser
from gi.repository import Gtk
from urllib import quote
from getans import getans
import traceback
import uuid
import json

class SigninWindow(Gtk.Window):
    def __init__(self, config):
        Gtk.Window.__init__(self, title="doit.im")
        self.config = config
        self.box = Gtk.VBox()
        self.username_entry = Gtk.Entry()
        self.username_entry.set_text(self.config.username or "username")
        self.password_entry = Gtk.Entry()
        self.password_entry.set_text("password")
        self.password_entry.set_visibility(False)
        self.button = Gtk.Button(label="Sign In")
        self.statusbar = Gtk.Statusbar()
        self.context_id = self.statusbar.get_context_id("example")
        self.button.connect("clicked", self.on_button_clicked)
        self.username_entry.connect("activate", self.on_button_clicked)
        self.password_entry.connect("activate", self.on_button_clicked)
        self.box.pack_start(self.username_entry, True, True, 0)
        self.box.pack_start(self.password_entry, True, True, 0)
        self.box.pack_start(self.button, True, True, 0)
        self.box.pack_start(self.statusbar, True, True, 0)
        self.add(self.box)

    def on_button_clicked(self, widget):
        username = self.username_entry.get_text()
        password = self.password_entry.get_text()
        self.statusbar.remove_all(self.context_id)
        try:
            doit = Doit(username, password, None)
            doit.auth()
            self.config.username = username
            self.config.password = password
            self.config.cookie = doit.cookie
            self.config.write()
            print 'ok'
            win = AddWindow(self.config)
            self.hide()
            win.connect("delete-event", Gtk.main_quit)
            win.show_all()
        except DoitException:
            self.statusbar.push(self.context_id, "auth error")
        except:
            traceback.print_exc()
            Gtk.main_quit()      


class AddWindow(Gtk.Window):
    def __init__(self, config):
        Gtk.Window.__init__(self, title="doit.im")
        self.set_default_size(600, 300)
        self.config = config
        self.box = Gtk.VBox()
        self.text_entry = Gtk.Entry()
        self.text_entry.set_text("")
        self.statusbar = Gtk.Statusbar()
        self.context_id = self.statusbar.get_context_id("example")
        self.button = Gtk.Button(label="Add")
        self.button.connect("clicked", self.on_button_clicked)
        self.text_entry.connect("activate", self.on_button_clicked)
        self.box.pack_start(self.text_entry, True, True, 0)
        self.box.pack_start(self.button, True, True, 0)
        self.box.pack_start(self.statusbar, True, True, 0)
        self.add(self.box)


    def on_button_clicked(self, widget):
        text = self.text_entry.get_text()
        try:
            doit = Doit(self.config.username, self.config.password, self.config.cookie)
            doit.add(text)
            if self.config.cookie != doit.cookie:
                self.config.cookie = doit.cookie
                self.config.write()
            Gtk.main_quit()
        except DoitAuthException:
            self.config.cookie = ""
            self.config.write()
            self.statusbar.push(self.context_id, "auth failed, please restart")
        except Exception as e:
            traceback.print_exc()
            self.statusbar.push(self.context_id, "error: " + str(e))            


            
class ConfigException(Exception):
    pass

class Config(object):
    def __init__(self, filename):
        self.filename = filename
        self.username = None
        self.password = None
        self.cookie = None

    def read(self):
        if os.path.exists(self.filename):
            config = ConfigParser.RawConfigParser()
            config.read(self.filename)
            self.username = config.get("doit-light", "username")
            self.password = config.get("doit-light", "password")
            self.cookie = config.get("doit-light", "cookie")
        else:
            raise ConfigException("no config file '%s'" % self.filename)

    def write(self):
        assert self.username and self.password
        if not os.path.exists(self.filename):
            fname = os.path.realpath(self.filename)
            dr = os.path.dirname(fname)
            if not os.path.exists(dr):
                os.makedirs(dr)
            elif not os.path.isdir(dr):
                raise ConfigException("not a dir: '%s'" % dr)
        config = ConfigParser.RawConfigParser()
        config.add_section('doit-light')
        config.set('doit-light', 'username', self.username)
        config.set('doit-light', 'password', self.password)
        config.set('doit-light', 'cookie', self.cookie)
        with open(self.filename, "wb") as f:
            config.write(f)        

class DoitException(Exception):
    pass

class DoitAuthException(DoitException):
    pass

class Doit(object):
    def __init__(self, username, password, cookie):
        self.username = username
        self.password = password
        self.cookie = cookie

    def auth(self):
        ck = {}
        getans("http://i.doit.im/signin", "username=%s&password=%s&autologin=1" % (quote(self.username), quote(self.password)), ck=ck)
        if 'autologin' in ck:
            self.cookie = ck['autologin']
        else:
            raise DoitException("auth error")

    def add(self, text, noreauth=False):
        ck = {"autologin": self.cookie}
        task = {"all_day":True,"archived":0,"assignment":None,"attribute":"inbox","completed":0,"deleted":0,"end_at":0,"forwarded_by":None,"hidden":0,"uuid":str(uuid.uuid4()),"type":"task","notes":"","priority":0,"reminders":[],"repeat_no":None,"repeater":None,"start_at":None,"tags":[],"title":text,"trashed":0,"now":False,"project":None,"goal":None,"context":None,"pos":6834386}

        print json.dumps(task)
        res = str(getans("http://i.doit.im/api/tasks/create", json.dumps(task), ck=ck, headers=["Content-Type: application/json; charset=utf-8"]).body())
        print res
        r = json.loads(res)
        if r["message"] == "require login":
            if noreauth:
                raise DoitAuthException(res)
            try:
                self.auth()
                self.add(text, True)
            except DoitException:
                raise DoitAuthException(res)
        elif r["message"] != 'success':
            raise DoitException(res)

def main():
    config = Config(os.path.join(os.path.expanduser("~"), ".doit-light", "config"))
    try:
        config.read()
        if config.cookie:
            win = AddWindow(config)
        else:
            win = SigninWindow(config)
        win.connect("delete-event", Gtk.main_quit)
        win.show_all()
        Gtk.main()
    except ConfigException:
        win = SigninWindow(config)
        win.connect("delete-event", Gtk.main_quit)
        win.show_all()
        Gtk.main()
        

if __name__ == '__main__':
    main()

