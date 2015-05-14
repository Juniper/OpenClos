#------------------------------------------------------------------------------
#                             cli_handle_impl.py
#------------------------------------------------------------------------------
'''
@author : rgiyer
Date    : October 20th, 2014

This module implements all "handle" and "macro" specified in cliCommands.yaml.
Command context from the openclos CLI will invoke one or more functions (or handles) implemented in this module

'''

# Standard python libraries
import os
import re
import collections

# Python frameworks required for openclos
import yaml

# openclos classes
import util
from l3Clos import L3ClosMediation
from model import Pod
from ztp import ZtpServer
import dao
import rest
import propLoader
from report import ResourceAllocationReport

#------------------------------------------------------------------------------
#------------------------------------------------------------------------------
class CLIImplementor:

    pod_indentation = 8
    pod_attr_dict = collections.OrderedDict ()

#------------------------------------------------------------------------------
    def add_attr_to_pod_struct ( self, attr, attr_desc ):
        self.pod_attr_dict [ attr ] = attr_desc
        desc_len = len ( attr_desc )
        if ( self.pod_indentation < desc_len ):
            self.pod_indentation = desc_len 

#------------------------------------------------------------------------------
    def init_pod_attr ( self ):
        self.add_attr_to_pod_struct ( 'name', 'POD Name' )
        self.add_attr_to_pod_struct ( 'id', 'UUID' )
        self.add_attr_to_pod_struct ( 'spineCount', 'Spine Count' )
        self.add_attr_to_pod_struct ( 'spineDeviceType', 'Spine Device Type' )
        self.add_attr_to_pod_struct ( 'leafCount', 'Leaf Count' )
        self.add_attr_to_pod_struct ( 'leafDeviceType', 'Leaf Device Type' )
        self.add_attr_to_pod_struct ( 'hostOrVmCountPerLeaf', 'Host / VM Count Per Leaf' )
        self.add_attr_to_pod_struct ( 'interConnectPrefix', 'Inter-Connect Prefix' )
        self.add_attr_to_pod_struct ( 'vlanPrefix', 'VLAN Prefix' )
        self.add_attr_to_pod_struct ( 'loopbackPrefix', 'Loopback Prefix' )
        self.add_attr_to_pod_struct ( 'spineAS', 'Spine Autonomous Number' )
        self.add_attr_to_pod_struct ( 'leafAS', 'Leaf Automnomous Number' )
        self.add_attr_to_pod_struct ( 'topologyType', 'Topology Type' )
        self.add_attr_to_pod_struct ( 'outOfBandAddressList', 'Out-of-Band Address List' )
        self.add_attr_to_pod_struct ( 'spineJunosImage', 'Spine Junos Image' )
        self.add_attr_to_pod_struct ( 'leafJunosImage', 'Leaf Junos Image' )
        self.add_attr_to_pod_struct ( 'allocatedInterConnectBlock', 'Allocated Inter-Connect Block' )
        self.add_attr_to_pod_struct ( 'allocatedIrbBlock', 'Allocated IRB Block' )
        self.add_attr_to_pod_struct ( 'allocatedLoopbackBlock', 'Allocated Loopback Block' )
        self.add_attr_to_pod_struct ( 'allocatedSpineAS', 'Allocated Spine Autonomous Number' )
        self.add_attr_to_pod_struct ( 'allocatedLeafAS', 'Allocated Leaf Autonomous Number' )
        self.add_attr_to_pod_struct ( 'state', 'POD State' )

        self.rl_indent = "\t" + " " * ( self.pod_indentation + 4 )


#------------------------------------------------------------------------------
    def create_pods ( self, pod_definition_file ):
        ret_list = []
        pods_yaml_file = os.path.join ( propLoader.propertyFileLocation,
                                        pod_definition_file )

        try:
            pods_file_stream = open ( pods_yaml_file, 'r' )
            pods_template = yaml.load ( pods_file_stream )
            pods_definition = {}
            if ( pods_template.has_key ( "pods" ) ):
                pods_definition = pods_template [ "pods" ]
                l3ClosMediation = L3ClosMediation ()
                for pod in pods_definition:
                    l3ClosMediation.createPod ( pod, pods_definition [ pod ] )
            else:
                print "Could not find pods definition in " + pods_yaml_file
        except IOError as e:
            print "Could not open " + pods_yaml_file
            print e.strerror

        except ImportError:
            print "Could not load " + pods_yaml_file

        finally:
            pass


#------------------------------------------------------------------------------
    def handle_create_pods_from_file ( self, pod_definition_file, *args ):
        if ( len ( pod_definition_file ) > 0 ):
            self.create_pods ( pod_definition_file )
        else:
            print "Please provide a valid file YAML file containing POD definitions"

#------------------------------------------------------------------------------
    def handle_create_pods ( self, *args ):
        self.create_pods ( "closTemplate.yaml" )

#------------------------------------------------------------------------------
    def handle_show_pods_terse ( self, *args ):
        for item in self.list_all_pods_from_db ( "add_help" ):
            print item

#------------------------------------------------------------------------------
    def show_pod_detail ( self, pod_object ):
        self.init_pod_attr ()
        for attr in self.pod_attr_dict:
            try:
                value = getattr ( pod_object, attr )
                pod_desc = self.pod_attr_dict [ attr ]
                desc_indentation = self.pod_indentation + 2 - len ( pod_desc )
                pod_desc = pod_desc + " " * desc_indentation
                if ( attr != "name" ):
                    pod_desc = "\t" + pod_desc + ": "
                else:
                    pod_desc = "POD "
                str_value = str ( value )
                str_value.replace ( ',',self.rl_indent )
                print pod_desc + str_value
            except AttributeError:
                pass
    

#------------------------------------------------------------------------------
    def handle_show_pod_detail ( self, pod_id, *args ):
        report = ResourceAllocationReport()
        with report._dao.getReadSession() as session:
            pod_object = report._dao.getObjectById(session, Pod, pod_id)
            self.show_pod_detail ( pod_object )

#------------------------------------------------------------------------------
    def handle_show_all_pods_detail ( self, *args ):
        print "---------------------------------------------------------------"
        report = ResourceAllocationReport()
        with report._dao.getReadSession() as session:
            pod_objects = report._dao.getAll(session, Pod)
            for pod in pod_objects:
                self.show_pod_detail ( pod )
                print "---------------------------------------------------------------"

#------------------------------------------------------------------------------
    def list_all_pods_from_db ( self, add_help=None, *args ):
        ret_list = []
        report = ResourceAllocationReport()
        with report._dao.getReadSession() as session:
            pod_objects = report._dao.getAll(session, Pod)
            for pod in pod_objects:
                pod_str = pod.id
                if ( add_help != None ):
                    pod_str = pod_str + "        <UUID of Pod [" + pod.name + "]>"
                ret_list.append ( pod_str )
    
            if ( len ( ret_list ) == 0 ):
                ret_list.insert ( 0, "Error:" )
                ret_list.append ( "No POD definitions found in the database" )
            return ret_list

#------------------------------------------------------------------------------
    def list_all_yaml_files ( self, *args ):
        ret_list = []
        for conf_file in os.listdir ( propLoader.propertyFileLocation ):
            if ( os.path.isfile ( os.path.join ( propLoader.propertyFileLocation, conf_file ) ) ):
                m = re.search ( ".yaml", conf_file )
                if ( m != None ):
                    ret_list.append ( conf_file )

        if ( len ( ret_list ) == 0 ):
            ret_list.insert ( 0, "Error:" )
            ret_list.append ( "No yaml files found at <[" + propLoader.propertyFileLocation + "]>" )

        return ret_list

#------------------------------------------------------------------------------
    def handle_create_cabling_plan ( self, pod_id ):
        l3ClosMediation = L3ClosMediation ()
        l3ClosMediation.createCablingPlan ( pod_id )
        

#------------------------------------------------------------------------------
    def handle_create_device_config ( self, pod_id ):
        l3ClosMediation = L3ClosMediation ()
        l3ClosMediation.createDeviceConfig ( pod_id )

#------------------------------------------------------------------------------
    def handle_create_ztp_config ( self, pod_name ):
        ztpServer = ZtpServer()
        ztpServer.createPodSpecificDhcpConfFile ( pod_name )

#------------------------------------------------------------------------------
    def handle_deploy_ztp_config ( self, pod_id ):
        
        ## Find the Pod Object
        report = ResourceAllocationReport()
        with report._dao.getReadSession() as session:
            pod_object = report._dao.getObjectById(session, Pod, pod_id)
            podDirectoryName = "%s-%s" % ( pod_id, pod_object.name )
        
        installedDhcpConf = "/etc/dhcp/dhcpd.conf"
        
        ## Generate the path to the dhcp conf
        generatedDhcpConf = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out', podDirectoryName, "dhcpd.conf" )
        
        if not os.path.isfile(generatedDhcpConf):
            print "DHCP configuration file has not been generated for Pod %s yet, will generate it first" % pod_id
            ztpServer = ZtpServer()
            ztpServer.createPodSpecificDhcpConfFile ( pod_id )

        if util.isPlatformUbuntu():
            os.system('sudo cp ' + generatedDhcpConf + ' ' + installedDhcpConf)
            print "New configuration file copied to %s " % installedDhcpConf
            os.system("/etc/init.d/isc-dhcp-server restart")

        elif util.isPlatformCentos():
            os.system('sudo cp ' + generatedDhcpConf + ' ' + installedDhcpConf)
            print "New configuration file copied to %s " % installedDhcpConf
            os.system("/etc/rc.d/init.d/dhcpd restart")
        
#------------------------------------------------------------------------------
    def handle_update_pods ( self, pod_id ):
        l3ClosMediation = L3ClosMediation ()
        
        ## Get Object for this Pod based on ID
        ## Get Data from config file
        report = ResourceAllocationReport()
        with report._dao.getReadSession() as session:
            pod_object = report._dao.getObjectById(session, Pod, pod_id)
            pod_name = pod_object.name
        pods_from_conf = l3ClosMediation.loadClosDefinition()
        
        l3ClosMediation.updatePod( pod_id, pods_from_conf[pod_name] )
        
        ## Regenerate devices configuration, cabling plan and ZTP configuration
        l3ClosMediation.createCablingPlan( pod_id )
        l3ClosMediation.createDeviceConfig( pod_id )
        
        ztpServer = ZtpServer()
        ztpServer.createPodSpecificDhcpConfFile ( pod_id )
    
#------------------------------------------------------------------------------
    def handle_update_password ( self, *args ):
        print "TODO: handle_update_password"

#------------------------------------------------------------------------------
    def handle_run_reports ( self, *args ):
        print "TODO: handle_run_reports"

#------------------------------------------------------------------------------
    def handle_run_rest_server ( self, *args ):
        print "TODO: handle_run_rest_server"

#------------------------------------------------------------------------------
#------------------------------------------------------------------------------
