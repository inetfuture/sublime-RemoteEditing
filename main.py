import sublime
import sublime_plugin
import os
import os.path
import functools
import threading
import subprocess

TMP_DIR = '~/.sublime/RemoteEditing'


def main_thread(callback, *args, **kwargs):
    # sublime.set_timeout gets used to send things onto the main thread
    # most sublime.[something] calls need to be on the main thread
    sublime.set_timeout(functools.partial(callback, *args, **kwargs), 0)


class CommandThread(threading.Thread):
    def __init__(self, command, on_done, **kwargs):
        threading.Thread.__init__(self)
        self.command = command
        self.on_done = on_done

        if "stdin" in kwargs:
            self.stdin = kwargs["stdin"]
        else:
            self.stdin = None

        if "stdout" in kwargs:
            self.stdout = kwargs["stdout"]
        else:
            self.stdout = subprocess.PIPE

        self.kwargs = kwargs

    def run(self):
        try:
            proc = subprocess.Popen(str.join(' ', self.command),
                                    stdout=self.stdout,
                                    stderr=subprocess.STDOUT,
                                    stdin=subprocess.PIPE,
                                    shell=True,
                                    universal_newlines=True)
            # if sublime's python gets bumped to 2.7 we can just do:
            # output = subprocess.check_output(self.command)
            output = proc.communicate(self.stdin)[0]
            if not output:
                output = ''
            #print output
            main_thread(self.on_done, output, **self.kwargs)
        except subprocess.CalledProcessError, e:
            main_thread(self.on_done, e.returncode)
        except OSError, e:
            if e.errno == 2:
                main_thread(sublime.error_message, "Git binary could not be found in PATH\n\nConsider using the git_command setting for the Git plugin\n\nPATH is: %s" % os.environ['PATH'])
            else:
                raise e


class RemoteEditingCommand():
    def run_command(self, command, callback=None):
        if not callback:
            callback = self.generic_done
        thread = CommandThread(command, callback)
        thread.start()

    def generic_done(self, result):
        pass


class OpenRemoteFileCommand(RemoteEditingCommand, sublime_plugin.WindowCommand):
    def run(self):
        self.window.show_input_panel('Remote path', '', self.open_remote_file, None, None)

    def open_remote_file(self, remote_path):
        def on_scp_done(result):
            view = self.window.open_file(os.path.join(TMP_DIR, remote_path))
            view.set_name(remote_path)
            view.settings().set('RemoteEditing.remote_path', remote_path)

        def on_mkdir_done(result):
            self.run_command(['scp', remote_path, os.path.join(TMP_DIR, remote_path)], on_scp_done)

        self.run_command(['mkdir', '-p', TMP_DIR], on_mkdir_done)


class RemoteEditingEventListener(RemoteEditingCommand, sublime_plugin.EventListener):
    def on_post_save(self, view):
        remote_path = view.settings().get('RemoteEditing.remote_path')
        if remote_path:
            self.run_command(['scp', view.file_name(), remote_path])

    def on_close(self, view):
        remote_path = view.settings().get('RemoteEditing.remote_path')
        if remote_path:
            self.run_command(['rm', os.path.join(TMP_DIR, remote_path)])
