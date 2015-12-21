'''
Created on Sep 2, 2014

@author: moloyc
'''

import os
import bottle
from sqlalchemy.orm import exc
import sqlalchemy
import StringIO
import zipfile
import traceback
import json
import util
import logging
import importlib

from bottle import error, request, response, PluginError, ServerAdapter
from error import EC_PLATFORM_ERROR
from exception import BaseError, isOpenClosException
from dao import Dao
from loader import OpenClosProperty, loadLoggingConfig
import underlayRestRoutes

moduleName = 'rest'
loadLoggingConfig(appName=moduleName)
logger = logging.getLogger(moduleName)

def loggingPlugin(callback):
    def wrapper(*args, **kwargs):
        msg = '"{} {} {}"'.format(request.method, 
                                  request.path,
                                  request.environ.get('SERVER_PROTOCOL', ''))
        
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug('%s REQUEST: %s', msg, request._get_body_string())
        else:
            logger.info('%s REQUEST:', msg)
        
        try:
            responseBody = callback(*args, **kwargs)
        except bottle.HTTPError as err:
            logger.error('HTTPError: status: %s, body: %s, exception: %s', err.status, err.body, err.exception)
            raise
        except Exception as exc:
            logger.error('Unknown error: %s', exc)
            logger.info('StackTrace: %s', traceback.format_exc())
            raise
       
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug('%s RESPONSE %s: %s', msg, response.status_code, responseBody)
        else:
            logger.info('%s RESPONSE %s:', msg, response.status_code)
            
        return responseBody
    return wrapper


class OpenclosDbSessionPlugin(object):
    name = 'OpenclosDbSessionPlugin'

    def __init__(self, daoClass=Dao):
        self.__dao = daoClass.getInstance()

    def setup(self, app):
        ''' Make sure that other installed plugins don't affect the same keyword argument.'''
        for plugin in app.plugins:
            if not isinstance(plugin, OpenclosDbSessionPlugin): 
                continue
            else:
                raise PluginError("Found another OpenclosDbSessionPlugin already installed")

    def apply(self, callback, context):
        def wrapper(*args, **kwargs):
            if request.method == 'POST' or request.method == 'PUT' or request.method == 'DELETE':
                with self.__dao.getReadWriteSession() as dbSession:
                    kwargs['dbSession'] = dbSession
                    responseBody = callback(*args, **kwargs)
            else:
                with self.__dao.getReadSession() as dbSession:
                    kwargs['dbSession'] = dbSession
                    responseBody = callback(*args, **kwargs)
            return responseBody

        # Replace the route callback with the wrapped one.
        return wrapper
    
class RestServer():
    def __init__(self, conf={}, daoClass=Dao):
        if any(conf) == False:
            self._openclosProperty = OpenClosProperty(appName=moduleName)
            self._conf = self._openclosProperty.getProperties()
        else:
            self._conf = conf
        
        self.__daoClass = daoClass
        self.__dao = daoClass.getInstance()
        self.openclosDbSessionPlugin = OpenclosDbSessionPlugin(daoClass)
        
        # default values
        self.version = 1
        self.protocol = 'http'
        self.host = 'localhost'
        self.port = 20080
        if 'restServer' in self._conf:
            if 'version' in self._conf['restServer']:
                self.version = self._conf['restServer']['version']
            if 'protocol' in self._conf['restServer']:
                self.protocol = self._conf['restServer']['protocol']
            if 'ipAddr' in self._conf['restServer']:
                self.host = self._conf['restServer']['ipAddr']
            if 'port' in self._conf['restServer']:
                self.port = self._conf['restServer']['port']
        elif 'httpServer' in self._conf:
            # support legacy setting
            if 'ipAddr' in self._conf['httpServer']:
                self.host = self._conf['httpServer']['ipAddr']
            if 'port' in self._conf['httpServer']:
                self.port = self._conf['httpServer']['port']
            
        # create base url
        self.baseUrl = '/openclos/v%d' % self.version
        self.indexLinks = []
        
    def addIndexLink(self, indexLink):
        # index page should show all top level URLs
        # users whould be able to drill down through navigation
        self.indexLinks.append(indexLink)
        
    def populateContext(self):
        context = {}
        context['conf'] = self._conf
        context['daoClass'] = self.__daoClass
        context['dao'] = self.__dao
        context['baseUrl'] = self.baseUrl
        context['app'] = self.app
        context['logger'] = logger
        context['restServer'] = self
        return context

    def getIndex(self, dbSession=None):
        if 'openclos' not in bottle.request.url:
            bottle.redirect(str(bottle.request.url).translate(None, ',') + 'openclos')
            
        # Decide what index links to return based on the request URL.
        #
        # Following are some examples of index links. 
        # /openclos/v1/underlay/pods
        # /openclos/v1/underlay/conf
        # /openclos/v1/overlay/fabrics
        jsonLinks = []
        protocol = bottle.request.urlparts[0]
        host = bottle.request.urlparts[1]
        for link in self.indexLinks:
            # include this link only if *entire* request URL is prefix of the link
            # e.g if the request URL is /openclos/v1/underlay, then overlay links won't be included
            if link.startswith(bottle.request.path):
                jsonLinks.append({'link': {'href': '%s://%s%s' % (protocol, host, link)}})

        jsonBody = \
            {'href': str(bottle.request.url).translate(None, ','),
             'links': jsonLinks
             }

        return jsonBody
    
    def addIndexRoutes(self):
        # Register all prefixes with the same callback.
        #
        # Following are some examples of index links. 
        # /openclos/v1/underlay/pods
        # /openclos/v1/underlay/conf
        # /openclos/v1/overlay/fabrics
        #
        # prefixes shall include:
        # /
        # /openclos
        # /openclos/v1
        # /openclos/v1/underlay
        # /openclos/v1/overlay
        prefixes = set('/')
        for link in self.indexLinks:
            pos = 1
            while True:
                pos = link.find('/', pos)
                if pos == -1:
                    break
                prefixes.add(link[:pos])
                pos = pos + 1
                
        for prefix in prefixes:
            self.app.route(prefix, 'GET', self.getIndex)
    
    def initRest(self):
        self.app = bottle.app()
        self.app.install(loggingPlugin)
        self.app.install(self.openclosDbSessionPlugin)
        logger.info('RestServer initRest() done')

    def installRoutes(self):
        context = self.populateContext()
        
        # install underlay routes. Note underlay is mandatory
        underlayRestRoutes.install(context)
        
        # iterate 'plugin' section of openclos.yaml and install routes on all plugins
        if 'plugin' in self._conf:
            plugins = self._conf['plugin']
            for plugin in plugins:
                moduleName = plugin['package'] + '.' + plugin['name'] + 'RestRoutes'
                logger.info("loading plugin REST module '%s'", moduleName) 
                try:
                    pluginModule = importlib.import_module(moduleName)
                    pluginInstall = getattr(pluginModule, 'install')
                    if pluginInstall is not None:
                        pluginInstall(context)
                except (AttributeError, ImportError) as err:
                    logger.error("Failed to load plugin REST module '%s'. Error: %s", moduleName, err) 
                # XXX should we continue?
        
        # install index routes
        self.addIndexRoutes()
        
        logger.info('RestServer installRoutes() done')

    def _reset(self):
        """
        Resets the state of the rest server and application
        Used for Test only
        """
        self.app.uninstall(loggingPlugin)
        self.app.uninstall(OpenclosDbSessionPlugin)


    def start(self):
        logger.info('REST server starting at %s:%d', self.host, self.port)
        debugRest = False
        if logger.isEnabledFor(logging.DEBUG):
            debugRest = True

        if self._openclosProperty.isSqliteUsed():
            bottle.run(self.app, host=self.host, port=self.port, debug=debugRest)
        else:
            bottle.run(self.app, host=self.host, port=self.port, debug=debugRest, server='paste')

    @staticmethod
    @error(400)
    def error400(error):
        bottle.response.headers['Content-Type'] = 'application/json'
        if error.exception is not None:
            if isOpenClosException(error.exception):
                return json.dumps({'errorCode': error.exception.code, 'errorMessage' : error.exception.message})
            elif issubclass(error.exception.__class__, sqlalchemy.exc.SQLAlchemyError):
                return json.dumps({'errorCode': EC_PLATFORM_ERROR, 'errorMessage' : str(error.exception.message)})
            else:
                return json.dumps({'errorCode': EC_PLATFORM_ERROR, 'errorMessage' : str(error.exception)})
        else:
            return json.dumps({'errorCode': EC_PLATFORM_ERROR, 'errorMessage' : str(error)})
        
    @staticmethod
    @error(404)
    def error404(error):
        bottle.response.headers['Content-Type'] = 'application/json'
        if error.exception is not None:
            if isOpenClosException(error.exception):
                return json.dumps({'errorCode': error.exception.code, 'errorMessage' : error.exception.message})
            elif issubclass(error.exception.__class__, sqlalchemy.exc.SQLAlchemyError):
                return json.dumps({'errorCode': EC_PLATFORM_ERROR, 'errorMessage' : str(error.exception.message)})
            else:
                return json.dumps({'errorCode': EC_PLATFORM_ERROR, 'errorMessage' : str(error.exception)})
        else:
            return json.dumps({'errorCode': EC_PLATFORM_ERROR, 'errorMessage' : str(error)})
        
    @staticmethod
    @error(500)
    def error500(error):
        bottle.response.headers['Content-Type'] = 'application/json'
        if error.exception is not None:
            if isOpenClosException(error.exception):
                return json.dumps({'errorCode': error.exception.code, 'errorMessage' : error.exception.message})
            elif issubclass(error.exception.__class__, sqlalchemy.exc.SQLAlchemyError):
                return json.dumps({'errorCode': EC_PLATFORM_ERROR, 'errorMessage' : str(error.exception.message)})
            else:
                return json.dumps({'errorCode': EC_PLATFORM_ERROR, 'errorMessage' : str(error.exception)})
        else:
            return json.dumps({'errorCode': EC_PLATFORM_ERROR, 'errorMessage' : str(error)})
        
def main():
    restServer = RestServer()
    restServer.initRest()
    restServer.installRoutes()
    restServer.start()
    
if __name__ == '__main__':
    main()
