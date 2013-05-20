import sublime
import sublime_plugin
import os
import threading
import subprocess
import functools

def main_thread(callback, *args, **kwargs):
    # sublime.set_timeout gets used to send things onto the main thread
    # most sublime.[something] calls need to be on the main thread
    sublime.set_timeout(functools.partial(callback, *args, **kwargs), 0)

def _make_text_safeish(text, fallback_encoding, method='decode'):
    # The unicode decode here is because sublime converts to unicode inside
    # insert in such a way that unknown characters will cause errors, which is
    # distinctly non-ideal... and there's no way to tell what's coming out of
    # git in output. So...
    try:
        unitext = getattr(text, method)('utf-8')
    except (UnicodeEncodeError, UnicodeDecodeError):
        unitext = getattr(text, method)(fallback_encoding)
    return unitext

class CommandThread(threading.Thread):
    def __init__(self, command, on_done, working_dir="", fallback_encoding="", **kwargs):
        threading.Thread.__init__(self)
        self.command = command
        self.on_done = on_done
        self.working_dir = working_dir
        if "stdin" in kwargs:
            self.stdin = kwargs["stdin"]
        else:
            self.stdin = None
        if "stdout" in kwargs:
            self.stdout = kwargs["stdout"]
        else:
            self.stdout = subprocess.PIPE
        self.fallback_encoding = fallback_encoding
        self.kwargs = kwargs

    def run(self):
        try:
                shell = os.name == 'nt'

                proc = subprocess.Popen(self.command,
                    stdout=self.stdout, stderr=subprocess.STDOUT,
                    stdin=subprocess.PIPE,
                    shell=shell, universal_newlines=True)
                output = proc.communicate(self.stdin)[0]
                if not output:
                    output = ''
                # if sublime's python gets bumped to 2.7 we can just do:
                # output = subprocess.check_output(self.command)
                main_thread(self.on_done,
                    _make_text_safeish(output, self.fallback_encoding), **self.kwargs)

        except subprocess.CalledProcessError, e:
            main_thread(self.on_done, e.returncode)
        except OSError, e:
            if e.errno == 2:
                main_thread(sublime.error_message, "Git binary could not be found in PATH\n\nConsider using the git_command setting for the Git plugin\n\nPATH is: %s" % os.environ['PATH'])
            else:
                raise e

class RemoteEditingCommand():
    def run_command(self, command, callback=None):
        subprocess.Popen(command, stdout=subprocess.PIPE)
        thread = CommandThread(command, self.generic_done)
        thread.start()

    def generic_done(self, result):
        self.window.open_file('/home/aaron/workspace/nohup.out')

class OpenRemoteFileCommand(RemoteEditingCommand, sublime_plugin.WindowCommand):
    def run(self):
        self.run_command(['scp', 'test1:nohup.out', '/home/aaron/workspace'])