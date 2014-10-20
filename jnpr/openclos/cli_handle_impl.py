#------------------------------------------------------------------------------
#                             cli_handle_impl.py
#------------------------------------------------------------------------------
'''
@author : rgiyer
Date    : October 20th, 2014

This module implements all "handle" and "macro" specified in cliCommands.yaml.
Command context from the openclos CLI will invoke one or more functions (or handles) implemented in this module

'''

#------------------------------------------------------------------------------
#------------------------------------------------------------------------------
class CLIImplementor:

    def show_pods ( self ):
        ret_list = []
        ret_list.append ( "pod_1" )
        ret_list.append ( "pod_2" )
        return ret_list

#------------------------------------------------------------------------------
    def handle_create_cabling_plan ( self ):
        print "TODO: handle_create_cabling_plan"

#------------------------------------------------------------------------------
    def handle_create_device_config ( self ):
        print "TODO: handle_create_device_config"

#------------------------------------------------------------------------------
    def handle_create_ztp_config ( self ):
        print "TODO: handle_create_ztp_config"

#------------------------------------------------------------------------------
    def handle_update_password ( self ):
        print "TODO: handle_update_password"

#------------------------------------------------------------------------------
    def handle_run_reports ( self ):
        print "TODO: handle_run_reports"

#------------------------------------------------------------------------------
    def handle_run_rest_server ( self ):
        print "TODO: handle_run_rest_server"

#------------------------------------------------------------------------------
#------------------------------------------------------------------------------
