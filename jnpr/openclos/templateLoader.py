'''
Created on Nov 10, 2015

@author: moloyc
'''
import os
from jinja2 import Environment, PackageLoader, FileSystemLoader, exceptions

junosTemplateLocation = os.path.join('conf', 'junosTemplates')

currentWorkingDir = os.getcwd()
homeDir = os.path.expanduser('~')

class TemplateLoader(object):
    '''
    Loads junos template from DEFAULT location - 
    <openclos install dir>/jnpr/openclos/conf/junosTemplates 
    
    OVERRIDE template location search path - 
    1. current working directory
    2. HOME directory
    
    '''

    def __init__(self, junosTemplatePackage="jnpr.openclos", override=True):
        
        self._defaultTemplateEnv = Environment(loader=PackageLoader(junosTemplatePackage, junosTemplateLocation))
        self._defaultTemplateEnv.keep_trailing_newline = True
        
        self._overrideTemplateEnv = None
        if override:
            self._overrideTemplateEnv = Environment(loader=FileSystemLoader([currentWorkingDir, homeDir]))
            self._overrideTemplateEnv.keep_trailing_newline = True
        
    def getTemplate(self, name, parent=None, globals=None):
        if self._overrideTemplateEnv:
            try:
                return self._overrideTemplateEnv.get_template(name, parent, globals)
            except exceptions.TemplateNotFound:
                return self._defaultTemplateEnv.get_template(name, parent, globals)


