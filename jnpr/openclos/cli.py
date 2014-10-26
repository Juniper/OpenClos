#------------------------------------------------------------------------------
#                            cli.py
#------------------------------------------------------------------------------
'''
@author : rgiyer
Date    : October 20th, 2014

This module is responsible for instantiating Python's standard CLI framework
"cmd". This CLI provides:
        - help functions showing all possible commands
        - tab complete for auto-completion / determining possible argument
          matches based on the command context

All CLI related configurations such as Introduction/Welcome message, 
exit message, command prompt text, command prompt terminal marker, etc. 
is defined in "cli" definition of openclos.yaml file.


For creating a new command:
1. Update cliCommands.yaml with the desired command. Existing tree may be
   used, or define a new tree structure starting from root.
2. Any macro (such as list defined pods, etc.) may be defined using "Macro" tag
3. Command has to define a "Handle", which will be used to execute the actual
   command.
4. Implement the handle in cli_handle_impl module

'''

# Standard python libraries
import cmd
import threading
import re
import os

# Python frameworks required for openclos
import yaml

# openclos classes
import util

# CLI related classes
from cli_parser import CLIUtil
from cli_parser import CLIImplementor

#------------------------------------------------------------------------------
#------------------------------------------------------------------------------
class ReadlineWrapper:


#------------------------------------------------------------------------------
    def get_completer ( self ):
        if util.isPlatformWindows ():
            import pyreadline
            return Readline ().get_completer ()
        else:
            import readline
            return readline.get_completer

#------------------------------------------------------------------------------
    def set_completer ( self, comp_func ):
        if util.isPlatformWindows ():
            import pyreadline
            Readline ().set_completer ( comp_func )
        else:
            import readline
            readline.set_completer ( comp_func )

#------------------------------------------------------------------------------
    def parse_and_bind ( self, complete_key ):
        if util.isPlatformWindows ():
            import pyreadline
            Readline ().parse_and_bind ( complete_key )
        else:
            import readline
            readline.parse_and_bind ( complete_key )

#------------------------------------------------------------------------------
    def get_line_buffer ( self ):
        if util.isPlatformWindows ():
            import pyreadline
            return Readline ().get_line_buffer ()
        else:
            import readline
            return readline.get_line_buffer ()

#------------------------------------------------------------------------------
    def get_begidx ( self ):
        if util.isPlatformWindows ():
            import pyreadline
            return Readline ().get_begidx ()
        else:
            import readline
            return readline.get_begidx ()

#------------------------------------------------------------------------------
    def get_endidx ( self ):
        if util.isPlatformWindows ():
            import pyreadline
            return Readline ().get_endidx ()
        else:
            import readline
            return readline.get_endidx ()

#------------------------------------------------------------------------------
    def insert_text ( self, line ):
        if util.isPlatformWindows ():
            import pyreadline
            Readline ().insert_text ( line )
        else:
            import readline
            readline.insert_text ( line )

#------------------------------------------------------------------------------
#------------------------------------------------------------------------------
class CLIShell ( cmd.Cmd ):

    cli_util = CLIUtil ()
    rl = ReadlineWrapper ()

#------------------------------------------------------------------------------
    def cmdloop ( self, intro=None ):
        self.preloop ()
        if self.use_rawinput and self.completekey:
            try:
                self.old_completer = self.rl.get_completer()
                self.rl.set_completer ( self.complete )
                self.rl.parse_and_bind ( self.completekey+": complete" )
            except ImportError:
                pass
        try:
            if intro is not None:
                self.intro = intro
            if self.intro:
                self.stdout.write ( str ( self.intro ) + "\n" )
            stop = None
            while not stop:
                if self.cmdqueue:
                    line = self.cmdqueue.pop ( 0 )
                else:
                    if self.use_rawinput:
                        try:
                            line = raw_input ( self.prompt )
                        except EOFError:
                            line = 'EOF'
                    else:
                        self.stdout.write ( self.prompt )
                        self.stdout.flush ()
                        line = self.stdin.readline ()
                        if not len ( line ):
                            line = 'EOF'
                        else:
                            line = line.rstrip ( '\r\n' )
                line = self.precmd ( line )
                stop = self.onecmd ( line )
                stop = self.postcmd ( stop, line )
            self.postloop ()
        finally:
            if self.use_rawinput and self.completekey:
                try:
                    self.rl.set_completer ( self.old_completer )
                except ImportError:
                    pass

#------------------------------------------------------------------------------
    def complete ( self, text, state ):
        if state == 0:
            origline = self.rl.get_line_buffer ()
            line = origline.lstrip ()
            stripped = len ( origline ) - len ( line )
            begidx = self.rl.get_begidx () - stripped
            endidx = self.rl.get_endidx () - stripped
            if begidx > 0 :
                cmd, args, foo = self.parseline ( line )
                if cmd == '':
                    compfunc = self.completedefault
                else:
                    try:
                        compfunc = getattr ( self, 'complete_' + cmd )
                    except AttributeError:
                        compfunc = self.completedefault
            else:
                compfunc = self.completenames
            self.completion_matches = compfunc ( text, line, begidx, endidx )
        try:
            return self.completion_matches [ state ]
        except IndexError:
            return None

#------------------------------------------------------------------------------
    def configure_cli_params ( self,
                               cli_prompt_text,
                               cli_prompt_style,
                               cli_header,
                               cli_on_exit ):
        self.prompt = "\n" + cli_prompt_text + cli_prompt_style + " "
        self.on_exit = cli_on_exit
        self.intro  = cli_header

#------------------------------------------------------------------------------
    def print_options ( self, header, results, current_line="" ):
        print "\n" + header + ":\n"
        for result in results:
            print "\t" + result
        self.rl.insert_text ( current_line )

#------------------------------------------------------------------------------
    def default ( self, line ):
        results = self.cli_util.get_match ( line )

        # Case 1: Invalid command. Print error
        if ( len ( results ) == 0 ):
            print "\nCommand not recognized\n"

        # Case 2: Valid command provided, or enter pressed half-way
        elif ( len ( results ) == 1 ):
            if ( self.cli_util.string_has_enter ( results [ 0 ] ) == 0 ):
                self.print_options ( "Command incomplete. Possible matches",
                                     results,
                                     line )
            else:
                # TODO - uncomment exception once testing is done
                # try:
                self.cli_util.validate_command_and_execute ( line )
                # except Exception as e:
                #     print "Encountered an exception of type:"
                #     print type ( e )
                #     print e

        # Case 3: Incomplete command. Provide possible matches
        else:
            self.print_options ( "Command incomplete. Possible options",
                                 results,
                                 line )

        return None

#------------------------------------------------------------------------------
    def exit_session ( self, *args ):
        print "\n" + self.on_exit + "\n"
        return "stop"

#------------------------------------------------------------------------------
    def do_exit ( self, *args ):
        return self.exit_session ()

#------------------------------------------------------------------------------
    def do_quit ( self, *args ):
        return self.exit_session ()

#------------------------------------------------------------------------------
    def do_bye ( self, *args ):
        return self.exit_session ()

#------------------------------------------------------------------------------
    def do_help ( self, *args ):
        for cmds in self.cli_util.get_all_cmds ():
            print cmds

#------------------------------------------------------------------------------
    def emptyline(self):
        return ""

#------------------------------------------------------------------------------
    def handle_hypenation ( self, result, cmd_line, hypen_index ):
        # Get the last token from command line
        cmd_line = cmd_line [ ::-1 ]
        match_object = re.search ( " ", cmd_line )
        if ( match_object != None ):
            cmd_line = cmd_line [ :match_object.end () ]
        cmd_line = cmd_line [ ::-1 ]

        # check if the last token has hypen
        match_object = re.search ( "-", cmd_line )
        if ( match_object != None ):
            # if command line has hypen too, we want to send
            # post hypenated portion to readline
            result = result [ hypen_index: ]

        return result

#------------------------------------------------------------------------------
    def cli_command_complete ( self, current_line ):
        results = self.cli_util.get_match ( current_line )
        if ( len ( results ) == 1 ):
            if ( re.search ( "<", results [ 0 ] ) == None ):
                # word complete case
                results [ 0 ] = results [ 0 ]
                # GNU readline gets very confused with hypenated tokens
                # Compensate for any hypens in the command line
                # as readline library splits hypenated words
                # and tab-complete behavior might not be proper
                match_object = re.search ( "-", results [ 0 ] )
                if ( match_object != None ):
                   results [ 0 ] = self.handle_hypenation ( results [ 0 ],
                                                             current_line,
                                                     match_object.end () )
                results [ 0 ] = results [ 0 ] + " "
                return results
            else:
                # A single possible match. Optimize to return as word complete
                # But <enter> cases need not be handled
                # First remove any extra spaces we may encounter at start
                match_object = re.search ( "[a-z|A-Z|0-9|<]", results [ 0 ] )
                if ( match_object != None ):
                    results [ 0 ] = results [ 0 ] [ (match_object.end () - 1): ]
                match_object = re.search ( "<enter>", results [ 0 ] )
                if ( match_object == None ):
                    match_object = re.search ( " ", results [ 0 ] )
                    if ( match_object != None ):
                        results [ 0 ] = results [ 0 ] [ :match_object.end () ]
                        match_object = re.search ( "-", results [ 0 ] )
                        if ( match_object != None ):
                            results [ 0 ] = self.handle_hypenation ( results [0], current_line, match_object.end () )
                    return results
                else:
                    results.insert ( 0, "." )
                    return results
        elif ( len ( results ) > 1 ):
            results.insert ( 0, "." )
            return results
        else:
            return [ "No match found", "." ]

#------------------------------------------------------------------------------
    def completenames(self, text, *ignored):
        current_line = self.rl.get_line_buffer ()
        return self.cli_command_complete ( current_line )

#------------------------------------------------------------------------------
    def completedefault(self, text, *ignored):
        current_line = self.rl.get_line_buffer ()
        return self.cli_command_complete ( current_line )

#------------------------------------------------------------------------------
#------------------------------------------------------------------------------
class CLIShellWrapper:

    def __init__ ( self, 
                   cli_prompt_text,
                   cli_prompt_style,
                   cli_header,
                   cli_on_exit ):
        self.cli_prompt_text  = cli_prompt_text
        self.cli_prompt_style = cli_prompt_style
        self.cli_header       = cli_header
        self.cli_on_exit      = cli_on_exit

#------------------------------------------------------------------------------
    def run ( self ):
        cli_shell = CLIShell ()
        cli_shell.configure_cli_params ( self.cli_prompt_text,
                                         self.cli_prompt_style,
                                         self.cli_header,
                                         self.cli_on_exit )
        cli_shell.cmdloop ( "\n\n\t\t" + self.cli_header + "\t\t" )

#------------------------------------------------------------------------------
#------------------------------------------------------------------------------
#                           WORK IN PROGRESS CLASS
#                    OVERLOADING "?" KEY FOR AUTO-COMPLETE
#           RIGHT NOW MESSES THE WHOLE TERMINAL - AND WORKS ONLY IN LINUX


# class KeyLogging ( threading.Thread ):
#    import curses
#    import readline
# 
#     print "Getting the standard screen instance"
#     stdscr = curses.initscr ()
# 
#     def __init__ ( self ):
#         threading.Thread.__init__ ( self )
#         curses.noecho ()
#         curses.cbreak ()
#         self.stdscr.keypad ( 1 )
# 
#     def __del__ ( self ):
#         curses.nocbreak ()
#         self.stdscr.keypad ( 0 )
#         curses.echo ()
# 
#     def run ( self ):
#         print "Keylogger started"
#         key = ''
#         while ( key != ord ( '!' ) ):
#             key = self.stdscr.getch ()
#             if ( key == ord ( '?' ) ):
#                 curr_line = readline.get_line_buffer ()
#                 print "\n" + curr_line + "\tShow options\n"
#                 print "\r"
#                 readline.insert_text ( curr_line )
#                 readline.redisplay ()
#             else:
#                 self.stdscr.addch ( key )
#             self.stdscr.refresh ()
        
#------------------------------------------------------------------------------
#                             MAIN
#------------------------------------------------------------------------------
if __name__ == '__main__':

    # keylogger = KeyLogging ()
    # keylogger.start ()

    openclosConfFile = os.path.join ( util.configLocation,
                                      'openclos.yaml' )
    yaml_file_stream = open ( openclosConfFile, 'r' )
    cli_config = yaml.load ( yaml_file_stream )
    if ( cli_config.has_key ( "cli" ) ):
        cli_config = cli_config [ "cli" ]
        cli = CLIShellWrapper ( cli_config [ "prompt_text" ],
                                cli_config [ "prompt_style" ],
                                cli_config [ "header" ],
                                cli_config [ "on_exit" ] )
        cli.run ()
    else:
        print "CLI Configuration not present - cannot initialize"
