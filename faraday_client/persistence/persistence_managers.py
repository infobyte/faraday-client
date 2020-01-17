'''
Faraday Penetration Test IDE
Copyright (C) 2013  Infobyte LLC (http://www.infobytesec.com/)
See the file 'doc/LICENSE' for the license information
'''
from __future__ import absolute_import
from __future__ import division

import os
import threading
import requests
import time
import logging
import socket

try:
    from urlparse import urlparse
except ImportError:
    from urllib.parse import urlparse
import traceback
from faraday.client.persistence.server import server

from faraday.utils.common import RestkitCookies
from faraday.client.managers.all import ViewsManager

from faraday.config.constant import CONST_BLACKDBS
from faraday.config.configuration import getInstanceConfiguration

CONF = getInstanceConfiguration()

logger = logging.getLogger(__name__)

class DBTYPE:
    """A simple enumeration of the databases types. CouchDB is the only
    valid DB right now.
    """
    COUCHDB = 1


class ConnectorContainer:
    def __init__(self, name, connector, type):
        self._connector = connector
        self.type = type
        self._name = name

    def getType(self):
        return self.type

    def connector(self):
        if self._connector.__class__.__name__ == 'function':
            self._connector = self._connector(self._name)
        return self._connector


class DbManager:

    def __init__(self, couch_exc_callback):
        self.couch_exc_callback = couch_exc_callback
        self.load()

    def load(self):
        self.couchmanager = CouchDbManager(CONF.getCouchURI(), self.couch_exc_callback)
        self.managers = {
                            DBTYPE.COUCHDB: self.couchmanager,
                        }
        self.dbs = {}
        self._loadDbs()

    def getAvailableDBs(self):
        return [typ for typ, manag in self.managers.items()
                if manag.isAvailable()]

    def _loadDbs(self):
        self.dbs = {}
        for dbname, connector in self.couchmanager.getDbs().items():
            self.dbs[dbname] = ConnectorContainer(dbname, connector, DBTYPE.COUCHDB)

    def _getManagerByType(self, dbtype):
        if dbtype == DBTYPE.COUCHDB:
            manager = self.couchmanager
        return manager

    def getConnector(self, name):
        # This returns a method that creates a connector
        # It's for lazy initalization in _loadDbs
        return self.dbs.get(name).connector()

    def connectorExists(self, name):
        return name in self.dbs.keys()

    def createDb(self, name, dbtype):
        if self.connectorExists(name):
            return False
        manager = self._getManagerByType(dbtype)
        self.addConnector(name, manager.createDb(name), dbtype)
        return self.getConnector(name)

    def addConnector(self, name, connector, dbtype):
        self.dbs[name] = ConnectorContainer(name, connector, dbtype)

    def getAllDbNames(self):
        self.refreshDbs()
        return list(self.dbs.keys())

    def refreshDbs(self):
        self.couchmanager.refreshDbs()
        for dbname, connector in self.couchmanager.getDbs().items():
            if dbname not in list(self.dbs.keys()):
                self.dbs[dbname] = ConnectorContainer(dbname, connector, DBTYPE.COUCHDB)

    def removeDb(self, name):
        connector = self.getConnector(name)
        self._getManagerByType(connector.getType()).deleteDb(name)
        del self.dbs[name]
        return True

    def getDbType(self, dbname):
        return self.dbs.get(dbname).getType()

    def reloadConfig(self):
        self.load()


class DbConnector:
    def __init__(self, type=None):
        self.changes_callback = None
        self.type = type

    def getType(self):
        return self.type

    def setChangesCallback(self, callback):
        self.changes_callback = callback

    def setNoWorkspacesCallback(self, callback):
        self.no_workspace_callback = callback

    def waitForDBChange(self):
        pass

    def forceUpdate(self):
        pass

    def saveDocument(self, document):
        raise NotImplementedError("DbConnector should not be used directly")

    def getDocument(self, documentId):
        raise NotImplementedError("DbConnector should not be used directly")

    def remove(self, documentId):
        raise NotImplementedError("DbConnector should not be used directly")

    def getDocsByFilter(self, parentId, type):
        raise NotImplementedError("DbConnector should not be used directly")

    def getChildren(self, document_id):
        raise NotImplementedError("DbConnector should not be used directly")


class CouchDbConnector(DbConnector):
    # This ratio represents (db size / num of docs)
    # to compact the database when the size is too high
    MAXIMUM_RATIO_SIZE = 10000
    # This value represents the number of maximum saves
    # before we try to compact the db
    MAXIMUM_SAVES = 1000

    def __init__(self, db, seq_num=0):
        super(CouchDbConnector, self).__init__(type=DBTYPE.COUCHDB)
        self.db = db
        self.saves_counter = 0
        self.mutex = threading.Lock()
        self._docs = {}
        try:
            vmanager = ViewsManager()
            vmanager.addViews(self.db)
            self._compactDatabase()
        except restkit.Unauthorized:
            logger.warn(
                "You're not authorized to upload views to this database")
        self.seq_num = self.db.info()['update_seq']

    def getDocs(self):
        if len(list(self._docs.keys())) == 0:
            # TODO: change this.
            # backwards compatibility. ugly, but needed
            self._docs["orphan"] = {}
            self._docs["orphan"]["children"] = []
            for doc in self.getAllDocs():
                self.addDoc(doc)
        return self._docs

    def addDoc(self, doc):
        id = doc["_id"]
        doc["children"] = []
        if self._docs.get(id, None):
            doc["children"] = self._docs[id]["children"]
        self._docs[id] = doc

        parent_id = doc.get("parent", None)
        # TODO: change this.
        # backwards compatibility. ugly, but needed
        if not parent_id or parent_id == "None":
            parent_id = "orphan"
        if parent_id in self._docs.keys():
            self._docs[parent_id]["children"].append(
                self._docs[doc["_id"]])

    def delDoc(self, doc_id):
        doc = self._docs[doc_id]
        parent_id = doc.get("parent", None)
        # TODO: change this.
        # backwards compatibility. ugly, but needed
        if not parent_id or parent_id == "None":
            parent_id == "orphan"
        if parent_id in self._docs.keys():
            self._docs[parent_id]["children"].remove(doc)
        del self._docs[doc_id]

    def _ratio(self):
        return self.db.info()['disk_size'] / self.db.info()['doc_count']

    def saveDocument(self, document):
        self.incrementSeqNumber()
        logger.debug(
            "Saving document in couch db %s" % self.db)
        res = self.db.save_doc(document, use_uuids=True, force_update=True)
        if res:
            self.saves_counter += 1
            self.addDoc(document)
        if self.saves_counter > self.MAXIMUM_SAVES:
            self._compactDatabase()
            self.saves_counter = 0
        return res

    def forceUpdate(self):
        """It will try to update the information on the DB if it can.
        The except clause is necesary to catch the case where we've lost
        the connection to the DB.
        """

        doc = self.getDocument(self.db.dbname)
        try:
            return self.db.save_doc(doc, use_uuids=True, force_update=True)
        except:
            return False

    def getDocument(self, document_id):
        # logger.debug(
        #     "Getting document %s for couch db %s" % (document_id, self.db))
        doc = self.getDocs().get(document_id, None)
        if not doc:
            if self.db.doc_exist(document_id):
                doc = self.db.get(document_id)
                self.addDoc(doc)
        return doc

    def remove(self, document_id):
        """Remove a document from existence, both from the database
        and from the mappers."""
        if self.db.doc_exist(document_id):
            self.incrementSeqNumber()
            self.db.delete_doc(document_id)
        self.delDoc(document_id)

    def getChildren(self, document_id):
        return self._docs[document_id]["children"]

    def getDocsByFilter(self, parentId, type):
        if not type:
            key = None
            if parentId:
                key = '%s' % parentId
            view = 'mapper/byparent'
        else:
            key = ['%s' % parentId, '%s' % type]
            view = 'mapper/byparentandtype'

        values = [doc.get("value") for doc in self.db.view(view, key=key)]
        return values

    def getAllDocs(self):
        docs = [doc.get("value") for doc in self.db.view('utils/docs')]
        return docs

    def incrementSeqNumber(self):
        self.mutex.acquire()
        self.seq_num += 1
        self.mutex.release()

    def getSeqNumber(self):
        return self.seq_num

    def setSeqNumber(self, seq_num):
        self.seq_num = seq_num


    def waitForDBChange(self, since=0):
        """Listen to the stream of changes provided by CouchDbKit. Process
        these changes accordingly. If there's an exception while listening
        to the changes, return inmediatly."""

        # XXX: the while True found here shouldn't be necessary because
        # changesStream already keeps listening 'for ever'. In a few tests
        # I ran, this hypothesis was confirmed, but with our current setup
        # i'm afraid I may be missing something. In any case, it works
        # as it is, but this definitevely needs revision.

        logger.info(
            "Watching for changes")
        while True:
            last_seq = max(self.getSeqNumber(), since)
            self.stream = ChangesStream(
                self.db,
                feed="continuous",
                since=last_seq,
                heartbeat=1000)
            try:
                for change in self.stream:
                    if not self.changes_callback:
                        return
                    if not change.get('last_seq', None):
                        if change['seq'] > self.getSeqNumber():
                            self.setSeqNumber(change['seq'])
                            if not change['id'].startswith('_design'):
                                logger.info(
                                    "Changes from another instance")
                                deleted = bool(change.get('deleted', False))
                                revision = change.get("changes")[-1].get('rev')
                                obj_id = change.get('id')
                                if not deleted:
                                    # update cache
                                    doc = self.db.get(obj_id)
                                    self.addDoc(doc)
                                self.changes_callback(obj_id, revision, deleted)

            except ResourceNotFound as e:
                logger.info("The database couldn't be found")
                self.no_workspace_callback()
                return False

            except Exception as e:
                logger.info("Some exception happened while waiting for changes")
                logger.info("  The exception was: %s" % e)
                return False  # kill thread, it's failed... in reconnection
                              # another one will be created, don't worry

    def _compactDatabase(self):
        try:
            self.db.compact()
        except:
            logger.warn(
                "You're not authorized to compact this database")

    def find_in_server(self, resource, id):
        return server.get_object(self.db.dbname, resource, id)


class AbstractPersistenceManager:
    def __init__(self):
        self.dbs = {}

    def createDb(self, name):
        if not self.getDb(name):
            self.dbs[name] = self._create(name)
        return self.dbs[name]

    def _loadDbs(self):
        raise NotImplementedError("AbstractPersistenceManager should not be used directly")

    def refreshDbs(self):
        self._loadDbs()

    def _create(self, name):
        raise NotImplementedError("AbstractPersistenceManager should not be used directly")

    def deleteDb(self, name):
        if self.getDb(name):
            self._delete(name)
            del self.dbs[name]
            return True
        return False

    def _delete(self, name):
        raise NotImplementedError("AbstractPersistenceManager should not be used directly")

    def getDbNames(self):
        return list(self.dbs.keys())

    def getDbs(self):
        return self.dbs

    def getDb(self, name):
        return self.dbs.get(name, None)

    def isAvailable(self):
        return self._available


class CouchDbManager(AbstractPersistenceManager):
    """
    This is a couchdb manager for the workspace,
    it will load from the couchdb databases
    """
    def __init__(self, uri, couch_exception_callback):
        super(CouchDbManager, self).__init__()
        self._limitdbs = CONF.getLimits()[0]
        logger.debug(
            "Initializing CouchDBManager for url [%s]" % uri)
        self._lostConnection = False
        self.__uri = uri
        self._available = False
        self.couch_exception_callback = couch_exception_callback
        test_couch_thread = threading.Thread(target=self.continuosly_check_connection)
        test_couch_thread.daemon = True
        test_couch_thread.start()
        try:
            if uri is not None:
                self.testCouchUrl(uri)
                url = urlparse(uri)
                logger.debug(
                    "Setting user,pass %s %s" % (url.username, url.password))

                self.__serv = Server(uri=uri)
                cookies = CONF.getDBSessionCookies()
                if cookies:
                    auth_obj = RestkitCookies(cookies)
                    auth_resource = CouchdbResource(filters=[auth_obj])
                    self.__serv = Server(uri=uri, resource_instance=auth_resource)

                self._available = True
                self.pushReports()
                self._loadDbs()
        except:
            logger.warn("No route to couchdb server on: %s" % uri)
            logger.debug(traceback.format_exc())

    def continuosly_check_connection(self):
        """Intended to use on a separate thread. Call module-level
        function testCouch every second to see if response to the server_uri
        of the DB is still 200. Call the exception_callback if we can't access
        the server three times in a row.
        """
        tolerance = 0
        server_uri = self.__uri
        while True:
            time.sleep(1)
            test_was_successful = test_couch(server_uri)
            if test_was_successful:
                tolerance = 0
            else:
                tolerance += 1
                if tolerance == 3:
                    self.couch_exception_callback()
                    return False  # kill the thread if something went wrong

    def _create(self, name):
        if len(list(self.dbs.keys())) + 1 > self._limitdbs:
            raise Exception("You have reached the amount of workspaces allowed for your license")
        db = self.__serv.create_db(name.lower())
        return CouchDbConnector(db)

    def _delete(self, name):
        self.__serv.delete_db(name)

    def _loadDbs(self):

        def conditions(database):
            begins_with_underscore = database.startswith("_")
            is_blacklisted = database in CONST_BLACKDBS
            return not begins_with_underscore and not is_blacklisted

        try:
            for dbname in list(filter(conditions, self.__serv.all_dbs())):
                if dbname not in list(self.dbs.keys()):
                    if len(list(self.dbs.keys())) < self._limitdbs:
                        logger.debug(
                            "Asking for dbname[%s], registering for lazy initialization" % dbname)
                        self.dbs[dbname] = lambda x: self._loadDb(x) # pylint: disable=unnecessary-lambda
        except restkit.errors.RequestError as req_error:
            logger.error("Couldn't load databases. "
                                  "The connection to the CouchDB was probably lost. ")

    def _loadDb(self, dbname):
        db = self.__serv.get_db(dbname)
        seq = db.info()['update_seq']
        self.dbs[dbname] = CouchDbConnector(db, seq_num=seq)
        return self.dbs[dbname]

    def refreshDbs(self):
        """Refresh databases using inherited method. On exception, asume
        no databases are available.
        """
        try:
            return AbstractPersistenceManager.refreshDbs()
        except:
            return []

    def pushReports(self):
        vmanager = ViewsManager()
        reports = os.path.join(os.getcwd(), "views", "reports")
        try:
            workspace = self.__serv.get_or_create_db("reports")
            vmanager.addView(reports, workspace)
        except:
            logger.warn(
                "Reports database couldn't be uploaded. You need to be an admin to do it")
        return self.__uri + "/reports/_design/reports/index.html"

    @staticmethod
    def testCouchAuth(uri, uname, upass):
        """Will test logging in to the couchdb on uri with username uname
        and password upass. Return True on success, False on failure.
        """
        logging.getLogger("requests").setLevel(logging.WARNING)

        auth = {"name": uname, "password": upass}
        try:
            resp = requests.post(uri + "/_session", data=auth, timeout=1)
            return resp.ok
        except requests.adapters.ConnectionError:
            logging.error("Problem connecting to Couch "
                          "DB. Are you sure it is up?")
            return False
        except requests.adapters.ReadTimeout:
            return False

    @staticmethod
    def testCouch(uri):
        """Redirect to the module-level function of the name, which
        serves the same purpose and is used by other classes too."""
        return test_couch(uri)

    def testCouchUrl(self, uri):
        if uri is not None:
            url = urlparse(uri)
            host = url.hostname
            port = url.port
            self.test(host, int(port))

    def test(self, address, port):
        s = socket.socket()
        s.settimeout(1)
        s.connect((address, port))

    def replicate(self, workspace, *targets_dbs, **kwargs):
        logger.debug("Targets to replicate %s" % str(targets_dbs))
        for target_db in targets_dbs:
            src_db_path = "/".join([self.__uri, workspace])
            dst_db_path = "/".join([target_db, workspace])
            try:
                logger.info("workspace: %s, src_db_path: %s, dst_db_path: %s, **kwargs: %s" % (workspace, src_db_path, dst_db_path, kwargs))
                self.__peerReplication(workspace, src_db_path, dst_db_path, **kwargs)
            except ResourceNotFound as e:
                raise e
            except Exception as e:
                logger.error(e)
                raise

    def __peerReplication(self, workspace, src, dst, **kwargs):
        mutual = kwargs.get("mutual", True)
        continuous = kwargs.get("continuous", True)
        ct = kwargs.get("create_target", True)

        self.__serv.replicate(workspace, dst, mutual = mutual, continuous  = continuous, create_target = ct)
        if mutual:
            self.__serv.replicate(dst, src, continuous = continuous, **kwargs)


def test_couch(uri):
    """Return True if we could access uri/_api/info, which should happen
    if we have an Internet connection, the server is up and we have the correct
    permissions (response_code == 200)
    """
    try:
        response_code = requests.get(uri + '/_api/info', timeout=3).status_code
        return response_code == 200
    except:
        return False


# I'm Py3
