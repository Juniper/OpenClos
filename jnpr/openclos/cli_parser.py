#------------------------------------------------------------------------------
#                            cli_parser.py
#------------------------------------------------------------------------------
'''
@author : rgiyer
Date    : October 20th, 2014

This module is responsible for parsing command model defined in
cliCommands.yaml and providing functions for:
       - Validation of user-input
       - invoking execution handle for CLI commands or macro expansions
       - determine possible arg match for command auto-completion based 
         on context
'''

# Standard Python libraries
import os
import re
import inspect
import subprocess

# Packages required for openclos
import yaml

# openclos classes
import util

# cli related classes
from cli_handle_impl import CLIImplementor

#------------------------------------------------------------------------------
#------------------------------------------------------------------------------
class CLICommand:

    def __init__ ( self, cmd_access, cmd_handle, cmd_macro, cmd_desc ):
        self.cmd_access = cmd_access
        self.cmd_handle = cmd_handle
        self.cmd_macro  = cmd_macro
        self.cmd_desc   = cmd_desc

# end class CLICommand

#------------------------------------------------------------------------------
#------------------------------------------------------------------------------
class CLIUtil:

    def __init__ ( self ):
        commandConfFile = os.path.join ( util.configLocation, 
                                         'cliCommands.yaml' )
        self.yaml_file_stream = open ( commandConfFile, 'r' )
        raw_graph = yaml.load ( self.yaml_file_stream )
        self.cmd_graph = {}
        self.indentation = 8
        self.dump_cmd ( raw_graph )
        self.yaml_file_stream.close ()
        

#------------------------------------------------------------------------------
    def get_implementor_handle ( self, class_instance, handle_name ):
        handles = inspect.getmembers ( class_instance, 
                                       predicate = inspect.ismethod )
        for function_tuple in handles:
            if ( handle_name == function_tuple [ 0 ] ):
                return function_tuple [ 1 ]

        # no match found
        return 0

#------------------------------------------------------------------------------
    # Parse through the dictionary iteratively:
    def dump_cmd ( self,
                   cmds,
                   cmd_root="", 
                   cmd_access="READ",
                   cmd_handle="",
                   cmd_macro="",
                   cmd_desc="" ):

        for cmd in cmds:
            if ( cmd_root == "" ):
                cmd_compound = cmd
            else:
                cmd_compound = cmd_root + "_" + cmd

            cmd_data = cmds [ cmd ]

            # Get command access
            if cmd_data.has_key ( "Access" ):
                cmd_access = cmd_data [ "Access" ]

            # Get command handler
            if cmd_data.has_key ( "Handle" ):
                cmd_handle = cmd_data [ "Handle" ]

            # Get command macro
            if cmd_data.has_key ( "Macro" ):
                cmd_macro = cmd_data [ "Macro" ]

            # Get command description
            if cmd_data.has_key ( "Desc" ):
                cmd_desc = cmd_data [ "Desc" ]

            # Parse the arguments
            if cmd_data.has_key ( "Args" ):
                cmd_args = cmd_data [ "Args" ]
                self.dump_cmd ( cmd_args, 
                                cmd_compound, 
                                cmd_access,
                                cmd_handle,
                                cmd_macro,
                                cmd_desc )

            if cmd_data.has_key ( "Handle" ):
                self.cmd_graph [ cmd_compound ] = CLICommand ( cmd_access, 
                                                               cmd_handle,
                                                               cmd_macro,
                                                               cmd_desc )
                if ( len ( cmd_compound ) > self.indentation ):
                    self.indentation = len ( cmd_compound )

#------------------------------------------------------------------------------
    def normalize_command ( self, cmd ):
        return cmd.replace ( " ", "_" )

#------------------------------------------------------------------------------
    def get_indentation ( self, cmd ):
        return ( self.indentation + 8 - len ( cmd ) )

#------------------------------------------------------------------------------
    def suffix_macro_to_cmd ( self, macro_list, cmd ):
        ret_cmd = []
        for macro in macro_list:
            ret_cmd.append ( self.normalize_command ( cmd + "_" + macro ) )
        return ret_cmd

#------------------------------------------------------------------------------
    def get_macro_list ( self, class_instance, macro_txt, add_help=None ):
        fn_macro = self.get_implementor_handle ( class_instance, macro_txt )
        return fn_macro ( add_help )

#------------------------------------------------------------------------------
    def include_macro ( self, macro_list, ret_list ):
        for item in macro_list:
            ret_list.append ( item )

#------------------------------------------------------------------------------
    def string_has_enter ( self, string ):
        if ( re.search ( "<enter>", string ) != None ):
            return 1
        else:
            return 0

#------------------------------------------------------------------------------
    def add_enter_instruction ( self, result_list ):
        if ( len ( result_list ) ):
            string = result_list [ 0 ]
            if ( self.string_has_enter ( string ) == 1 ):
                return 0

        result_list.insert ( 0, " <enter>" + " " * self.get_indentation ( "<enter" ) + "Execute the current command" )
        

#------------------------------------------------------------------------------
    def match_macro ( self, macro_list, needle, ret_list ):
        for haystack in macro_list:
            if ( len ( needle ) == len ( haystack ) ):
                if ( re.match ( needle, haystack ) != None ):
                    self.add_enter_instruction ( ret_list )
            elif ( len ( needle ) < len ( haystack ) ):
                if ( re.match ( needle, haystack ) ):
                    ret_list.append ( haystack )
            else:
                print ""

#------------------------------------------------------------------------------
    def option_exists ( self, consider_option, ret_list ):
        for option in ret_list:
            if ( re.match ( option, consider_option ) != None ):
                return 1
        return 0

#------------------------------------------------------------------------------
    def complete_command ( self,
                           part_cmd, 
                           full_cmd, 
                           end_index, 
                           cmd_helper, 
                           ret_list ):
        unmatched_string = full_cmd [ end_index: ]

        # This is an adjustment for "<space>" before tab / ? keypress
        if ( part_cmd [ -1 ] == "_" ):
            part_cmd = part_cmd [ 0:-1 ]
            unmatched_string = "_" + unmatched_string
    
        if ( unmatched_string [ 0 ] == "_" ):
            # attach possible matches
            possible_option = unmatched_string.replace ( "_", " " ) + ( " " * self.get_indentation ( full_cmd ) )
            possible_option = possible_option + "<" + cmd_helper.cmd_desc + ">"
            ret_list.append ( possible_option )
        else:
            # Get part of the command from part_cmd
            match_object = re.search ( "_", part_cmd )
            while ( match_object != None ):
                part_cmd = part_cmd [ match_object.end (): ]
                match_object = re.search ( "_", part_cmd )
        
            # Get rest of the command from unmatched_string
            match_object = re.search ( "_", unmatched_string )
            if ( match_object != None ):
                unmatched_string = unmatched_string [ :(match_object.end()-1)]

            complete_word = part_cmd + unmatched_string
            if ( self.option_exists ( complete_word, ret_list ) == 0 ):
                 ret_list.append ( complete_word )

        return ret_list
        

#------------------------------------------------------------------------------
    def get_all_cmds ( self ):
        ret_list = []
        for cmd in self.cmd_graph:
            cmd_str = cmd.replace ( "_", " " )
            cmd_str = cmd_str + ( " " * self.get_indentation ( cmd ) ) + "<" + self.cmd_graph [ cmd ].cmd_desc + ">"
            ret_list.append ( cmd_str )
        return ret_list

#------------------------------------------------------------------------------
# Lot of reference here to needle and haystack, needle being the current
# command context of the CLI, and haystack being the command model dict
# created during CLIUtil instantiation
#------------------------------------------------------------------------------
    def get_match ( self, cmd ):
        if  ( len ( cmd ) == 0 or re.search ( "[a-z|A-Z|0-9]", cmd ) == None ):
            return self.get_all_cmds ()

        # chomp input string
        if ( cmd [ -1 ] == " " ):
            cmd = cmd [ 0:-1 ]

        needle = self.normalize_command ( cmd )
        ret_list = []

        for haystack in self.cmd_graph:
            len_haystack = len ( haystack )
            len_needle   = len ( needle )
            cmd_helper = self.cmd_graph [ haystack ]

            # Case 1: Full command is provided, without macro expansion
            if ( len_needle == len_haystack ):
                # check if we have a match
                if ( re.match ( needle, haystack ) != None ):
                    if ( cmd_helper.cmd_macro != "" ):
                        self.include_macro ( self.get_macro_list ( CLIImplementor (), cmd_helper.cmd_macro, "add help" ), ret_list )
                    else:
                        self.add_enter_instruction ( ret_list )

            # Case 2: Full command is provided with macro expansion
            elif ( len_needle > len_haystack ):
                match_object = re.match ( haystack, needle )
                if ( match_object != None ):
                    # Match exists - so get the macro
                    cmd_macro = needle [ match_object.end (): ]
                    if ( cmd_macro [ 0 ] == "_" and len ( cmd_macro ) > 1 ):
                        cmd_macro = cmd_macro [ 1: ]

                    if ( cmd_helper.cmd_macro != "" ):
                        cmd_macro_list = self.get_macro_list ( CLIImplementor(),
                                                          cmd_helper.cmd_macro )
                        self.match_macro ( cmd_macro_list, cmd_macro, ret_list )

            # Case 3: Part command is provided
            elif ( len_needle < len_haystack ):
                match_object = re.match ( needle, haystack )
                if ( match_object != None ):
                    # Match exists - get rest of the command
                    balance_cmd = haystack [ match_object.end (): ]
                    self.complete_command ( needle, 
                                            haystack, 
                                            match_object.end (), 
                                            self.cmd_graph [ haystack ],
                                            ret_list )
                

        return ret_list

#------------------------------------------------------------------------------
    def chomp ( self, token ):
        match_object = re.search ( "[a-z|A-Z|0-9]", token )
        if ( match_object != None ):
            token = token [ ( match_object.end () - 1): ]

        token = token [ ::-1 ]
        match_object = re.search ( "[a-z|A-Z|0-9]", token )
        if ( match_object != None ):
            token = token [ ( match_object.end () - 1): ]

        token = token [ ::-1 ]

        return token

#------------------------------------------------------------------------------
    def validate_command_and_execute ( self, full_cmd_context ):
        # We will do the validation again in case this function is called
        # outside the CLI context
        best_cmd_match = ""
        best_cmd_args  = ""
        best_cmd_handle = None

        for command in self.cmd_graph:
            match_object = re.match ( command, 
                           self.normalize_command ( full_cmd_context ) )
            if ( match_object != None ):
                # Okay - we found a match. Get macros if included
                command_args = ""
                # TODO - different impl here for multiple args support
                if ( len ( full_cmd_context ) > len ( command ) ):
                    command_args = self.chomp ( full_cmd_context [ match_object.end (): ] )
                if ( len ( best_cmd_match ) < len ( command ) ):
                    best_cmd_match = command
                    best_cmd_args  = command_args
                    best_cmd_handle = self.get_implementor_handle ( CLIImplementor (), self.cmd_graph [ command ].cmd_handle )

        if ( best_cmd_handle != 0 ):
            return best_cmd_handle ( best_cmd_args )
        else:
            print self.cmd_graph [ best_cmd_match ].cmd_handle + " not implemented"

#------------------------------------------------------------------------------
    def print_results ( self, result_list ):
        for result in result_list:
            print "\t" + result

#------------------------------------------------------------------------------
    def print_command_graph ( self, cmd_dict ):
        for keys in cmd_dict:
            print keys + "=>"
            cmd = cmd_dict [ keys ]
            if ( cmd.cmd_desc != "" ):
                print "    " + cmd.cmd_desc
            print "    " + cmd.cmd_access
            if ( cmd.cmd_macro != "" ):
                fn_macro = self.get_implementor_handle ( CLIImplementor (), 
                                                        cmd.cmd_macro )
                if ( fn_macro != 0 ):
                    print fn_macro ()
                else:
                    print "    Macro not implemented"
            if ( cmd.cmd_handle != "" ):
                fn_handle = self.get_implementor_handle ( CLIImplementor (), 
                                                     cmd.cmd_handle )
                if ( fn_handle != 0 ):
                    fn_handle ()
                else:
                    print "    Handler not implemented"

# end class CLIUtil
#------------------------------------------------------------------------------
#------------------------------------------------------------------------------

#------------------------------------------------------------------------------
#                              MAIN
#------------------------------------------------------------------------------
cli_util = CLIUtil ()
    

match_options = [ "create cabling",
#                  "create cabling-plan",
#                  "create cabling-",
#                  "create cabling",
#                  "create cabling-plan pod",
#                  "create cabling-plan pod pod_2",
#                  "create",
#                  "create dev",
#                  "create device-config",
#                  "create device-config p",
#                  "create device-config pod",
#                  "create device-config pod pod_1",
#                  "run",
#                  "update password",
#                  "run r",
#                  "run RE",
#                  "create cab",
                  "create pods",
                  "create pods from",
                  "create pods from-file",
                  "" ]

if __name__ == '__main__':
    for match in match_options:
        print "Matching results for " + match + " is:"
        cli_util.print_results ( cli_util.get_match ( match ) )
        print "------------------------------------------------------"

