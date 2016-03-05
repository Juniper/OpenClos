'''
Created on Sep 2, 2014

@author: moloyc
'''

import os
import bottle
from sqlalchemy.orm import exc
import sqlalchemy
import traceback
import json
import util
import signal
import sys
import logging
import importlib
from bottle import error, request, response, PluginError, ServerAdapter, parse_auth
import subprocess
from threading import Thread, Event
from urlparse import SplitResult

from error import EC_PLATFORM_ERROR
from exception import BaseError, isOpenClosException, InvalidConfiguration, PlatformError
from jnpr.openclos.dao import Dao
from loader import OpenClosProperty, loadLoggingConfig
import underlayRestRoutes
from crypt import Cryptic
from deviceConnector import CachedConnectionFactory

moduleName = 'rest'
loadLoggingConfig(appName=moduleName)
logger = logging.getLogger(moduleName)

restServer = None

def restServerStop():
    restServer.stop()
    
def rest_server_signal_handler(signal, frame):
    logger.debug("received signal %d", signal)
    # REVISIT: The main thread hangs if we just call restServer.stop from the signal handler. 
    # We have to spawn a thread to call restServer.stop
    Thread(target=restServerStop, args=()).start()
    sys.exit(0)
    
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

class BasicAuthPlugin(object):
    name = 'BasicAuthPlugin'

    def __init__(self, username, cleartextPassword):
        self.username = username
        self.cleartextPassword = cleartextPassword

    def setup(self, app):
        ''' Make sure that other installed plugins don't affect the same keyword argument.'''
        for plugin in app.plugins:
            if not isinstance(plugin, BasicAuthPlugin): 
                continue
            else:
                raise PluginError("Found another BasicAuthPlugin already installed")

    def checkPass(self):
        if self.username is not None:
            auth = request.headers.get('Authorization')
            if auth:
                (user, passwd) = parse_auth(auth)
                if user != self.username:
                    logger.error("Basic Auth: user '%s' not found", user)
                    return False
                if passwd != self.cleartextPassword:
                    logger.error("Basic Auth: password mismatch for user '%s'", user)
                    return False
                logger.debug("Basic Auth: user '%s' authenticated", user)
                return True
            else:
                logger.error("Basic Auth: Authorization header not found")
                return False
        else:
            # user doesn't configure username/password in http mode so let it pass
            return True
            
    def apply(self, callback, context):
        def wrapper(*args, **kwargs):
            if not self.checkPass():
                raise bottle.HTTPError(401)

            responseBody = callback(*args, **kwargs)
            return responseBody

        # Replace the route callback with the wrapped one.
        return wrapper

class StoppableServer(ServerAdapter):
    server = None

    def stop(self):
        if self.server is not None:
            # self.server.server_close() <--- alternative but causes bad fd exception
            self.server.shutdown()

class PlainWSGIRefServer(StoppableServer):
    def run(self, handler):
        from wsgiref.simple_server import make_server, WSGIRequestHandler
        if self.quiet:
            class QuietHandler(WSGIRequestHandler):
                def log_request(*args, **kw): pass
            self.options['handler_class'] = QuietHandler
        self.server = make_server(self.host, self.port, handler, **self.options)
        self.server.serve_forever()

class PlainPasteServer(StoppableServer):
    def run(self, handler): # pragma: no cover
        from paste import httpserver
        from paste.translogger import TransLogger
        handler = TransLogger(handler, setup_console_handler=(not self.quiet))
        self.server = httpserver.serve(handler, host=self.host, port=str(self.port),
                         **self.options)
                         
class SSLServer(StoppableServer):
    def __init__(self, host, port, certificate, **options):
        # https server won't start unless we have a real IP so we can bind the IP to the server cert
        if host == '0.0.0.0':
            raise InvalidConfiguration("Server cert cannot bind to 0.0.0.0. Please change ipAddr in openclos.yaml to real IP address")
            
        super(SSLServer, self).__init__(host, port, **options)
        self.certificate = certificate

    def createServerCert(self):
        # create server cert with default value populated
        cmd = "openssl req -new -x509 -subj '/C=US/ST=California/L=Sunnyvale/O=Juniper Networks/OU=Network Mgmt Switching/CN=" + self.host + "/emailAddress=openclos@juniper.net' -keyout " + self.certificate + " -out " + self.certificate + " -days 365 -nodes"
        try:
            logger.debug("Running command [" + cmd + "]:")
            output = subprocess.check_output(cmd, shell=True).strip()
            if output:
                logger.debug(output)
            logger.info("Server cert %s created successfully", self.certificate)
        except subprocess.CalledProcessError as exc:
            logger.error("Command [" + cmd + "] returned error code " + str(exc.returncode) + " and output " + exc.output)
            raise PlatformError(exc.output)
    
    def changeServerCertPermission(self):
        # change permission to 400
        cmd = "chmod 400 " + self.certificate
        try:
            logger.debug("Running command [" + cmd + "]:")
            output = subprocess.check_output(cmd, shell=True).strip()
            if output:
                logger.debug(output)
            logger.info("Server cert %s chmod successfully", self.certificate)
        except subprocess.CalledProcessError as exc:
            logger.error("Command [" + cmd + "] returned error code " + str(exc.returncode) + " and output " + exc.output)
            raise PlatformError(exc.output)
            
    def createServerCertImport(self):
        # create server cert with default value populated
        cmd = "openssl x509 -inform PEM -in " + self.certificate + " -outform DER -out " + self.certificate + ".cer"
        try:
            logger.debug("Running command [" + cmd + "]:")
            output = subprocess.check_output(cmd, shell=True).strip()
            if output:
                logger.debug(output)
            logger.info("Server cert import %s created successfully. Please import this file into your HTTPS client", self.certificate + ".cer")
        except subprocess.CalledProcessError as exc:
            logger.error("Command [" + cmd + "] returned error code " + str(exc.returncode) + " and output " + exc.output)
            raise PlatformError(exc.output)
            
    def checkServerCert(self):
        if not os.path.exists(self.certificate):
            logger.info("Server cert %s not found", self.certificate)
            self.createServerCert()
            self.changeServerCertPermission()
            self.createServerCertImport()
        else:
            logger.info("Server cert %s found", self.certificate)
    
class SSLWSGIRefServer(SSLServer):
    def __init__(self, host, port, certificate, **options):
        super(SSLWSGIRefServer, self).__init__(host, port, certificate, **options)
        
    def run(self, handler):
        self.checkServerCert()
        
        from wsgiref.simple_server import make_server, WSGIRequestHandler
        import ssl
        if self.quiet:
            class QuietHandler(WSGIRequestHandler):
                def log_request(*args, **kw): pass
            self.options['handler_class'] = QuietHandler
        self.server = make_server(self.host, self.port, handler, **self.options)
        self.server.socket = ssl.wrap_socket(self.server.socket,
                                     certfile=self.certificate,  # path to certificate
                                     server_side=True)
        self.server.serve_forever()
       
class SSLPasteServer(SSLServer):
    def __init__(self, host, port, certificate, **options):
        super(SSLPasteServer, self).__init__(host, port, certificate, **options)
        
    def run(self, handler): # pragma: no cover
        self.checkServerCert()
        
        from paste import httpserver
        from paste.translogger import TransLogger
        handler = TransLogger(handler, setup_console_handler=(not self.quiet))
        self.options["ssl_pem"] = self.certificate  # path to certificate
        self.server = httpserver.serve(handler, host=self.host, port=str(self.port),
                         **self.options)
                         
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
        self.cryptic = Cryptic()
        
        # default values
        self.version = 1
        self.protocol = 'http'
        self.host = '0.0.0.0'
        self.port = 20080
        self.username = None
        self.cleartextPassword = None
        self.certificate = None
        if 'restServer' in self._conf:
            if 'version' in self._conf['restServer']:
                self.version = self._conf['restServer']['version']
            if 'protocol' in self._conf['restServer']:
                self.protocol = self._conf['restServer']['protocol']
            if 'ipAddr' in self._conf['restServer']:
                self.host = self._conf['restServer']['ipAddr']
            if 'port' in self._conf['restServer']:
                self.port = self._conf['restServer']['port']
            if 'username' in self._conf['restServer']:
                self.username = self._conf['restServer']['username']
            if 'password' in self._conf['restServer']:
                encryptedPassword = self._conf['restServer']['password']
                self.cleartextPassword = self.cryptic.decrypt(encryptedPassword)
            if 'certificate' in self._conf['restServer']:
                self.certificate = os.path.expanduser(self._conf['restServer']['certificate'])
        elif 'httpServer' in self._conf:
            # support legacy setting
            if 'ipAddr' in self._conf['httpServer']:
                self.host = self._conf['httpServer']['ipAddr']
            if 'port' in self._conf['httpServer']:
                self.port = self._conf['httpServer']['port']

        # basic validation
        if self.protocol == 'https':
            if self.certificate is None:
                raise InvalidConfiguration('Server cert is required in https mode. Please configure certificate in restServer in openclos.yaml')
            if self.username is None:
                raise InvalidConfiguration('Basic Authentication is required in https mode. Please configure username/password in restServer in openclos.yaml')
        elif self.protocol == 'http':
            if self.username is not None:
                logger.warning("Basic Authentication in http mode is supported but not recommended")

        # create base url
        self.baseUrl = '/openclos/v%d' % self.version
        self.indexLinks = []
        
        # basic authentication plugin
        self.basicAuthPlugin = BasicAuthPlugin(self.username, self.cleartextPassword)
        
        self.srv = None
        self.pluginModules = []
    
    def addIndexLink(self, indexLink):
        # index page should show all top level URLs
        # users whould be able to drill down through navigation
        self.indexLinks.append(indexLink)
        
    def populateContext(self, pluginDict = {}):
        context = {}
        context['pluginDict'] = pluginDict
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
    
    def setScheme(self):
        # REVISIT: this is a hack to set correct scheme in case of https
        env = str(request.environ) # this line is necessary to populate environ['bottle.request.urlparts']
        result = request.environ['bottle.request.urlparts']
        request.environ['bottle.request.urlparts'] = SplitResult(self.protocol, result.netloc, result.path, result.query, result.fragment)
        
    def initRest(self):
        self.app = bottle.app()
        self.app.install(loggingPlugin)
        self.app.install(self.basicAuthPlugin)
        self.app.install(self.openclosDbSessionPlugin)
        self.app.add_hook('before_request', self.setScheme)
        logger.info('RestServer initRest() done')

    def installRoutes(self):
        # install underlay routes. Note underlay is mandatory
        underlayRestRoutes.install(self.populateContext())
        
        # iterate 'plugin' section of openclos.yaml and install routes on all plugins
        if 'plugin' in self._conf:
            plugins = self._conf['plugin']
            for plugin in plugins:
                moduleName = plugin['package'] + '.' + plugin['name'] + 'RestRoutes'
                logger.info("loading plugin REST module '%s'", moduleName) 
                try:
                    pluginModule = importlib.import_module(moduleName)
                    self.pluginModules.append(pluginModule)
                    pluginInstall = getattr(pluginModule, 'install')
                    if pluginInstall is not None:
                        pluginInstall(self.populateContext(plugin))
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
        self.app.uninstall(BasicAuthPlugin)
        self.app.uninstall(OpenclosDbSessionPlugin)
        self.app.remove_hook('before_request', self.setScheme)

    def start(self):
        logger.info('REST server %s://%s:%d started', self.protocol, self.host, self.port)

        debugRest = False
        if logger.isEnabledFor(logging.DEBUG):
            debugRest = True

        if self.protocol == 'http':
            if self._openclosProperty.isSqliteUsed():
                self.srv = PlainWSGIRefServer(host=self.host, port=self.port)
            else:
                self.srv = PlainPasteServer(host=self.host, port=self.port)
            bottle.run(self.app, debug=debugRest, server=self.srv)
        elif self.protocol == 'https':
            if self._openclosProperty.isSqliteUsed():
                self.srv = SSLWSGIRefServer(host=self.host, port=self.port, certificate=self.certificate)
            else:
                self.srv = SSLPasteServer(host=self.host, port=self.port, certificate=self.certificate)
            bottle.run(self.app, debug=debugRest, server=self.srv)
        else:
            logger.error('REST server aborted: unknown protocol %s', self.protocol)

    def stop(self):
        # shutdown all live connections
        CachedConnectionFactory.getInstance()._stop()
        
        self._reset()
        
        # iterate 'plugin' section of openclos.yaml and uninstall on all plugins
        for pluginModule in self.pluginModules:
            try:
                pluginUninstall = getattr(pluginModule, 'uninstall')
                if pluginUninstall is not None:
                    pluginUninstall()
            except Exception as exc:
                logger.error("Error: %s", exc) 
                continue
        # stop rest server itself
        if self.srv is not None:
            self.srv.stop()
        
        logger.info('REST server %s://%s:%d stopped', self.protocol, self.host, self.port)

    @staticmethod
    def _populateErrorResponse(error):
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
    @error(400)
    def error400(error):
        return RestServer._populateErrorResponse(error)
        
    @staticmethod
    @error(404)
    def error404(error):
        return RestServer._populateErrorResponse(error)
        
    @staticmethod
    @error(500)
    def error500(error):
        return RestServer._populateErrorResponse(error)
        
def main():
    signal.signal(signal.SIGINT, rest_server_signal_handler)
    signal.signal(signal.SIGTERM, rest_server_signal_handler)
    global restServer
    restServer = RestServer()
    restServer.initRest()
    restServer.installRoutes()
    restServer.start()
    # Note we have to do this in order for signal to be properly caught by main thread
    # We need to do the similar thing when we integrate this into sampleApplication.py
    while True:
        signal.pause()
    
if __name__ == '__main__':
    main()
