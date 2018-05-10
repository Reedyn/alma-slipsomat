# encoding=utf8
from __future__ import print_function
import os
import sys
import argparse
import readline
import shlex
from textwrap import dedent
from glob import glob
from cmd import Cmd
import traceback

from . import __version__
from .slipsomat import Worker, StatusFile, LocalStorage, TemplateConfigurationTable, TestPage
from .slipsomat import pull, pull_defaults, push, test

try:
    import inquirer
except ImportError:
    inquirer = None

histfile = '.slipsomat_history'
try:
    import readline
    # Remove some standard delimiters like "/".
    readline.set_completer_delims(' \'"')
except ImportError:
    # Windows?
    readline = None


class Shell(Cmd):
    """
    Interactive shell for parsing commands
    """
    intro = 'Welcome to slipsomat. Type help or ? to list commands.\n'
    prompt = "\001\033[1;36m\002slipsomat>\001\033[0m\002 "
    file = None

    def __init__(self):
        """
        Construct a new Shell object
        Params:
            browser: Browser object for command dispatch
        """
        super(Shell, self).__init__()
        print('Starting slipsomat {}'.format(__version__))

        self.worker = Worker('slipsomat.cfg')
        self.worker.connect()
        self.status_file = StatusFile()
        self.local_storage = LocalStorage(self.status_file)
        sys.stdout.write('Reading table... ')
        sys.stdout.flush()
        self.table = TemplateConfigurationTable(self.worker)
        self.testpage = TestPage(self.worker)
        sys.stdout.write('\rReading table... DONE\n')

    @staticmethod
    def completion_helper(basedir, word):
        candidates = []
        for root, dirs, files in os.walk(basedir):
            for file in files:
                candidates.append(os.path.join(root[len(basedir):], file))
        return [c for c in candidates if c.lower().startswith(word.lower())]

    def emptyline(self):
        "handle empty lines"
        pass

    def do_exit(self, arg):
        "Exit the program"
        self.worker.close()
        sys.exit()

    def do_pull(self, arg):
        "Pull in letters modified directly in Alma"
        self.execute(pull, self.table, self.local_storage, self.status_file)

    def do_defaults(self, arg):
        "Pull in updates to default letters"
        self.execute(pull_defaults, self.table, self.local_storage, self.status_file)

    def help_push(self):
        print(dedent("""
        push

            Push locally modified files to Alma. With no arguments specified, the
            command will look for locally modified files and ask if you want to
            push these.

        push <filename>

            Specify a filename relative to xsl/letters to only push a specific file.
        """))

    def do_push(self, arg):
        files = ['xsl/letters/%s' % filename for filename in shlex.split(arg)]
        self.execute(push, self.table, self.local_storage, self.status_file, files)

    def complete_push(self, word, line, begin_idx, end_idx):
        "Complete push arguments"
        return self.completion_helper('xsl/letters/', word)

    def help_test(self):
        print(dedent("""
        test <filename>@<lang>

            Test letter output by uploading XML files in the 'test-data' folder to
            the Alma Notification Template and storing screenshots of the resulting
            output.

        Parameters:
            - <filename> can be either a single filename in the 'test-data' folder
              or a glob pattern like '*.xml'
            - <lang> can be either a single language code or multiple language codes
              separated by comma. Defaults to "en" if not specified.
        """))

    def do_test(self, arg):
        languages = 'en'
        if '@' in arg:
            files, languages = arg.split('@')
        else:
            files = arg
        languages = languages.split(',')
        files = glob(os.path.abspath(os.path.join('test-data', files)))

        if len(files) == 0:
            print('Error: No such file')
            return

        self.execute(test, self.testpage, files, languages)

    def complete_test(self, word, line, begin_idx, end_idx):
        "Complete test arguments"
        return self.completion_helper('test-data/', word)

    # Aliases
    do_EOF = do_exit  # ctrl-d
    do_eof = do_EOF
    do_quit = do_exit

    def handle_exception(self, e):
        print("\nException:", e)
        traceback.print_exc(file=sys.stdout)

        if inquirer is None or not hasattr(inquirer, 'List'):
            print('Please "pip install inquirer" if you would like more debug options')
        else:
            q = inquirer.List('goto',
                              message='Now what?',
                              choices=['Restart browser', 'Debug with ipdb', 'Debug with pdb', 'Exit'],
                              )
            answers = inquirer.prompt([q])
            if answers['goto'] == 'Debug with ipdb':
                try:
                    import ipdb
                except ImportError:
                    print('Please run "pip install ipdb" to install ipdb')
                    sys.exit(1)
                ipdb.post_mortem()
            elif answers['goto'] == 'Debug with pdb':
                import pdb
                pdb.post_mortem()
            elif answers['goto'] == 'Restart browser':
                self.worker.restart()
                return

        self.worker.close()
        sys.exit()

    def preloop(self):
        if readline is not None and os.path.exists(histfile):
            readline.read_history_file(histfile)

    def execute(self, fn, *args, **kwargs):
        "Executes the function, and handle exceptions"

        if readline is not None:
            readline.set_history_length(10000)
            readline.write_history_file(histfile)
        try:
            fn(*args, **kwargs)
        except Exception as e:
            self.handle_exception(e)

    def precmd(self, line):
        "hook that is executed  when input is received"
        return line.strip()


def main():
    parser = argparse.ArgumentParser()
    options = parser.parse_args()
    if not os.path.exists('slipsomat.cfg'):
        print('No slipsomat.cfg file found in this directory. Exiting.')
        return

    shell = Shell()
    shell.cmdloop()
