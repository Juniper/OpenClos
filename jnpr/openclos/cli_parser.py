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
import subprocess
import inspect
import readline
# Packages required for openclos
import yaml
import collections
#import yamlordereddictloader

# openclos classes
import util
import propLoader

# cli related classes
from cli_handle_impl import CLIImplementor
global_needle = None
entered_macro = []
#------------------------------------------------------------------------------
#------------------------------------------------------------------------------
class CLICommand:

    def __init__ ( self, cmd_access, cmd_handle, cmd_macro, cmd_macroname, cmd_desc ):
        self.cmd_access = cmd_access
        self.cmd_handle = cmd_handle
        self.cmd_macro  = cmd_macro
	self.cmd_macroname = cmd_macroname
        self.cmd_desc   =  cmd_desc

# end class CLICommand

#------------------------------------------------------------------------------
#------------------------------------------------------------------------------
class CLIUtil:

    def __init__ ( self ):
	commandConfFile = os.path.join ( propLoader.propertyFileLocation, 
                                         'cliCommands.yaml' )
        self.yaml_file_stream = open ( commandConfFile, 'r' )
        raw_graph = yaml.load ( self.yaml_file_stream )
	#raw_graph = yaml.load(self.yaml_file_stream, Loader=yamlordereddictloader.Loader)
	#self.cmd_graph = {}
	self.cmd_graph=collections.OrderedDict()
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
		   cmd_macroname="",
                   cmd_desc="", *args ):
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
            elif ( cmd_handle != "" ):
                cmd_handle = ""

            # Get command macro
            if cmd_data.has_key ( "Macro" ):
                cmd_macro = cmd_data [ "Macro" ]
            elif ( cmd_macro != "" ):
                cmd_macro = ""
            
	    if cmd_data.has_key ( "MacroName" ):
		if "-" in cmd_data [ "MacroName" ]:
			print "Macro name cannot contain the character '-'"
			print "Excluding the handle"
			print cmd_compound + "_<" + cmd_data["MacroName"] +">"
			break 
		cmd_macroname = cmd_data [ "MacroName" ]
		cmd_compound = cmd_compound + "_<" + cmd_macroname + ">"
	    elif ( cmd_macroname != "" ):
		cmd_macroname = ""

            # Get command description
            if cmd_data.has_key ( "Desc" ):
                cmd_desc = cmd_data [ "Desc" ]
            elif ( cmd_desc != "" ):
                cmd_desc = ""
	
	    if cmd_data.has_key ( "Handle" ):
                #if cmd_data.has_key ( "MacroName" ):
		self.cmd_graph [ cmd_compound ] = CLICommand ( cmd_access, 
                                                               cmd_handle,
                                                               cmd_macro,
							       cmd_macroname,
                                                               cmd_desc )	
                
		if ( len ( cmd_compound ) > self.indentation ):
                    self.indentation = len ( cmd_compound )

            # Parse the arguments
            if cmd_data.has_key ( "Args" ):
                cmd_args = cmd_data [ "Args" ]
		self.dump_cmd ( cmd_args, 
                                cmd_compound, 
                                cmd_access,
                                cmd_handle,
                                cmd_macro,
				cmd_macroname,
                                cmd_desc )
	

#------------------------------------------------------------------------------
    def normalize_command ( self, cmd ):
        return cmd.replace ( " ", "_" )

#------------------------------------------------------------------------------
    def return_graph (self):
	return self.cmd_graph

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
        prev_macro = self.get_previous_macro()
	return fn_macro ( prev_macro, add_help )
	
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
	global entered_macro
	for haystack in macro_list:
            if ( re.match ( needle, haystack ) != None ):
            	if ( len ( needle ) == len ( haystack ) ):
		    self.add_enter_instruction ( ret_list )
		    entered_macro.append(haystack)
                elif ( len ( needle ) < len ( haystack ) ):
		    if haystack not in ret_list:
                    	ret_list.append ( haystack )
			entered_macro.append(haystack)
            #else:
                #print ""

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

    def get_match (self, needle):
	global global_needle
	global_needle = needle
	macro_dict = {}
	ret_list = []
	# flag variable to denote if macro has been appended 
	flag=0

	if len(needle)==0 or re.search("[a-z|A-Z|0-9]", needle)==None:
	    return self.get_all_cmds()
	if needle[-1]==" ":
	    needle=needle[0:-1]
	needle = self.normalize_command(needle)
	while needle[-1]=="_":
	    needle=needle[0:-1]
	
	for haystack_orig in self.cmd_graph:
	    cmd_helper = self.cmd_graph [ haystack_orig ]		
	    
	    # Creating macro list for easy lookup and retrieval
	    if cmd_helper.cmd_macro!="":
		cmd_macro_list = self.get_macro_list(CLIImplementor(),cmd_helper.cmd_macro)
		macro_dict[cmd_helper.cmd_macroname]=cmd_macro_list
	    
	    # For regex operations
	    haystack = haystack_orig.replace("<","(?P<")
	    haystack = haystack.replace(">", ">.*)")
	    
	    # Matching using regex search and match
	    match_macros = re.search(haystack,needle)
	    if len(haystack_orig)<len(needle):	
		match_object = re.match(haystack_orig,needle)
	    else:
		match_object = re.match(needle,haystack_orig)
		
	    # Complete partially entered command
	    if match_object!=None:
		balance_haystack = haystack_orig[match_object.end():]
		if balance_haystack!="":
		    if balance_haystack[1]=="<" and cmd_helper.cmd_macro!="":
			# check to retrieve corresponding macro list
			if cmd_helper.cmd_macroname in haystack_orig.partition(">")[0]:
			    self.include_macro(macro_dict[cmd_helper.cmd_macroname],ret_list)
			    break
		    haystack_orig=haystack_orig.replace(" ","_")
		    self.complete_command(needle,haystack_orig,match_object.end(), cmd_helper, ret_list)
		else:
		    self.add_enter_instruction ( ret_list )
		
	    # Compare and complete macros 
	    elif match_macros!=None:
		for macro_name in macro_dict.keys():
		  if macro_name in cmd_helper.cmd_macroname:
		    # try-catch block to get all match groups
		    try:
			macro_needle = match_macros.group(macro_name)
			if "_" in macro_needle:
			    continue
			
			for each_macro in macro_dict[macro_name]:
			    if macro_needle in each_macro:
				self.match_macro(macro_dict[macro_name],macro_needle,ret_list)
				flag=1
				break
						
			if flag==0:
			    #print "Invalid macro. Possible options:"
			    self.include_macro(macro_dict[macro_name],ret_list)
						
					
		    except IndexError:
			break

	    # Find point of match and return remaining command
	    else:
		needle_temp = needle
		haystack_temp = haystack_orig
		
		# loop till all macros of commands are validated
		while True:
		    index_of_diff = 0
		    for char_a, char_b in zip(list(haystack_temp), list(needle_temp)):
			if char_a!=char_b:
			    break
			index_of_diff=index_of_diff+1
		    
		    if index_of_diff!=0:
			macro_needle = needle_temp[index_of_diff:]
			macro_needle = macro_needle.split("_",1)[-1]
			balance_haystack = haystack_temp[index_of_diff:]
				
			if balance_haystack[0]=="_":
			    balance_haystack=balance_haystack[1:]
			if balance_haystack[0]!="<":
			    match_object = re.match(macro_needle,balance_haystack)
			    if match_object!=None and flag==0:
				    end_pos = haystack_orig.find(balance_haystack)
				    self.complete_command(haystack_orig[:end_pos],haystack_orig,end_pos, cmd_helper, ret_list)
					
			if balance_haystack[0]=="<":
			    balance_haystack=balance_haystack.split("_",1)[-1]
			    match_object = re.match(macro_needle, balance_haystack)
			    for key in macro_dict:
				if macro_needle in macro_dict[key]:
				    end_pos = haystack_orig.find(balance_haystack)
				    self.complete_command(haystack_orig[:end_pos],haystack_orig,end_pos, cmd_helper, ret_list)

			   #  When needle ends with a macro
			    if match_object==None or macro_needle=="":
				#print "Incorrect command. Possible options:"
				if balance_haystack[0]=="<" and cmd_helper.cmd_macro!="":
				    self.include_macro(macro_dict[cmd_helper.cmd_macroname],ret_list)
				else:
				  if flag==0:
				    end_pos = haystack_orig.find(balance_haystack)
				    self.complete_command(haystack_orig[:end_pos],haystack_orig,end_pos, cmd_helper, ret_list)
				break

			    # When needle extends beyond current macro
			    else:
				haystack_temp = balance_haystack
		      		needle_temp = macro_needle
		        else:
			    break
		    else:
		    	break	
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
	    cmd_helper = self.cmd_graph[command]
	    
	    # For regex operations
	    command_temp = command.replace("<","(?P<")
	    command_temp = command_temp.replace(">", ">.*)")
            
	    match_object = re.match ( command_temp, 
                           self.normalize_command ( full_cmd_context ) )
	    
            if ( match_object != None ):
                # Okay - we found a match. Get macros if included
                command_args = ""		
		match_macros = re.search ( command_temp,self.normalize_command(full_cmd_context))
	    	if match_macros != None and cmd_helper.cmd_macroname!="":
		    macro_needle = match_macros.group(cmd_helper.cmd_macroname)
      		    command_args = macro_needle 
                
		#if ( len ( full_cmd_context ) > len ( command ) ):
                    #command_args = self.chomp ( full_cmd_context [ match_object.end (): ] )
		command_args = self.chomp (command_args)
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

#------------------------------------------------------------------------------

    def get_previous_macro(self):
	global global_needle
	global entered_macro
	if global_needle[-1]==" ":
	    global_needle=global_needle[0:-1]

	global_needle = cli_util.normalize_command(global_needle)
	prev_macro = None
	for each_macro in entered_macro:
		if each_macro in global_needle:
			prev_macro = each_macro
	return prev_macro

# end class CLIUtil
#------------------------------------------------------------------------------
#                              MAIN
#------------------------------------------------------------------------------
cli_util = CLIUtil ()
    

match_options = [ "create",
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
                  "update",
                  "deploy",
                  "run",
                  "" ]

if __name__ == '__main__':
    for match in match_options:
        print "Matching results for " + match + " is:"
        cli_util.print_results ( cli_util.get_match ( match ) )
        print "------------------------------------------------------"

