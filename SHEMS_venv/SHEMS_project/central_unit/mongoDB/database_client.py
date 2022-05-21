from pymongo import MongoClient
import logging

class databaseClient():
    def __init__(self, ip = None, port = None):
        """Definition of the database name

        Args:
            name (string): database name
            ip (int): database service ip. Can be also 'localhost', no ip is required in that case
            port (int, optional): database service port Defaults to None
        """
        #TODO: inserire poi una password
        """
        client = MongoClient(
        host = '987.65.4.3:27017', # <-- IP and port go here
        serverSelectionTimeoutMS = 3000, # 3 second timeout
        username="objectrocket",
        password="1234",
        )
        """
        try:
            client = MongoClient()
            self.db = client.SHEMS_database_local       
            self.collections = ['home_configuration', 'data_collected']
            self.name = 'SHEMS_database_local'
        except:
            logging.error('MongoDB client creation failed')
    
    def __collectionPointer(self, collection_name):
        """Get or create a collection pointer

        Args:
            collection (string): collection name
        Returns:
                db: the collection get or created
        """
        if collection_name == 'home_configuration':
            return self.db.home_configuration
        elif collection_name == 'data_collected':
            return self.db.data_collected
        else:
            logging.error(f'Collection {collection_name} does not created or found')

    def write_document(self, document, collection_name):
        """Insert one or more documents in a specific database collection

        Args:
            document (list): list of dictionaries or documents
            collection (string): collection name
        """
        try:
            pointer = self.__collectionPointer(collection_name)
            pointer.insert_one(document)
        except:
            logging.error('Writing document failed')

    def count_documents(self, collection_name):
        """Count the number of documents in a specific collection

        Args:
            collection (string): collection name
        Returns:
                int: number of documents in the collection
        """
        try:
            pointer = self.__collectionPointer(collection_name)
            return list(pointer.count())
        except:
            logging.error('Counting document failed')

    def read_documents(self, collection_name, document):
        """Read documents from a specific collection

        Args:
            collection (string): collection name

        Returns:
            mongoDB object:
        """
        try:
            pointer = self.__collectionPointer(collection_name)
            d = {}
            for i in pointer.find(document):
                d=i
            return d
        except:
            logging.error('Reading document failed')

    def update_documents(self, collection_name, document, object):
        """Update a field of the documents of a collection

        Args:
            collection (string): _description_
            ID (dict): dictionary compose like {document_identificator:document_indetificator_value}
            object: dictionary with the field update
        Returns:
            code (int): 1/0
        """
        try:
            pointer = self.__collectionPointer(collection_name)
            pointer.update_one(document, {'$set': object})
            return 1
        except:
            return 0

    def delete_documents(self, collection_name, document):
        """delete a documents from a collection

        Args:
            collection (string): _description_
            ID (dict): dictionary compose like {document_identificator:document_indetificator_value}
        Returns:
            _type_: _description_
        """
        try:
            pointer = self.__collectionPointer(collection_name)
            return list(pointer.delete_one(document))
        except:
            logging.error('Delete document failed')