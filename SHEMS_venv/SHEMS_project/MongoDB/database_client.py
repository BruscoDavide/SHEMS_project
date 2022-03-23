import pymongo as pm
import logging

class databaseClient():
    def __init__(self, name, ip, port = None):
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
            self.client = pm.MongoClient(ip)
            self.db = self.client.name
            self.name = name
            self.collections = []
        except:
            logging.info('MongoDB client creation failed')
        
    def myCollection(self, collection_name):
        """Get or create a collection

        Args:
            collection (string): collection name
        Returns:
                db: the collection get or created
        """
        try:
            if collection_name in self.collections:
                return self.db.collection_name
            else:
                self.collections.append(collection_name)           
        except:
            logging.info(f'Collection {collection_name} does not created or found')

    def write_myDocument(self, document, collection):
        """Insert one or more documents in a specific database collection

        Args:
            document (list): list of dictionaries or documents
            collection (string): collection name
        """
        try:
            pointer = self.myCollection(collection)
            pointer.insert_many(document)
        except:
            logging.info('Write document failed')

    def count_myDocuments(self, collection):
        """Count the number of documents in a specific collection

        Args:
            collection (string): collection name
        Returns:
                int: number of documents in the collection
        """
        try:
            pointer = self.myCollection(collection)
            return list(pointer.count())
        except:
            logging.info('Count document failed')

    def read_myDocuments(self, collection):
        """Read documents from a specific collection

        Args:
            collection (string): collection name

        Returns:
            _type_: _description_
        """
        try:
            pointer = self.myCollection(collection)
            return list(pointer.find({}))
        except:
            logging.info('Read document failed')

    def update_myDocuments(self, collection, ID, object):
        """Update a field of the documents of a collection

        Args:
            collection (string): _description_
            ID (dict): dictionary compose like {document_identificator:document_indetificator_value}
            object: dictionary with the field update
        Returns:
            _type_: _description_
        """
        try:
            pointer = self.myCollection(collection)
            return list(pointer.update_one(ID, {'$set': object}))
        except:
            logging.info('Update document failed')

    def delete_myDocuments(self, collection, ID):
        """delete a documents from a collection

        Args:
            collection (string): _description_
            ID (dict): dictionary compose like {document_identificator:document_indetificator_value}
        Returns:
            _type_: _description_
        """
        try:
            pointer = self.myCollection(collection)
            return list(pointer.delete_one(ID))
        except:
            logging.info('Delete document failed')

    #TODO: da testare e aggiungere funzoinalità
    def myQuery(self, collection, object, operator= None):
        """Build your own query, see help function to know all the operators

        Args:
            collection (string): collection name
            object (dict): {field:value} in order to select all the documents in which 'field' has the 'value' value
                                field can be also in the form 'field1.field2', it means: {field1:{field2: ... }}
                            {field:value} in order to select all the documents in which 'field' 'operator' 'value'
            operator (string): query operator
        Returns:
            _type_: _description_
        """
        if operator == None or operator == '$eq':
            try:
                pointer = self.myCollection(collection)
                return list(pointer.find(object))
            except:
                logging.info()
        elif operator == '$gt':
            try:
                pointer = self.myCollection(collection)
                return list(pointer.find({object.key()[0]:{'$gt':object[object.key()[0]]} } ) )
            except:
                logging.info()
        else:
            logging.info(f'Operator {operator} does not recognized')

    def help(self):
        info = {'$eq':'Matches values that are equal to a specified value.',
                '$gt':'Matches values that are greater than a specified value.',
                '$gte':'Matches values that are greater than a specified value.',
                '$in':'Matches any of the values specified in an array.',
                '$lt':'Matches values that are less than a specified value.',
                '$lte':'Matches values that are less than or equal to a specified value.',
                '$ne':'Matches all values that are not equal to a specified value.',
                '$nin':'Matches none of the values specified in an array.',
                '$and':'Joins query clauses with a logical AND returns all documents that match the conditions of both clauses.',
                '$not':'Inverts the effect of a query expression and returns documents that do not match the query expression.',
                '$nor':'Joins query clauses with a logical NOR returns all documents that fail to match both clauses.',
                '$or':'Joins query clauses with a logical OR returns all documents that match the conditions of either clause.',
                '$expr':'Allows use of aggregation expressions within the query language.',
                'More':'https://docs.mongodb.com/manual/reference/operator/query/'}
        return info

    def server_info(self):
        #server_info = self.client.server_info() 
        #keys = server_info.keys(), 
        #db_names = self.client.list_database_names()
        #return server_info, keys, db_names, self.collections
        return self.collections



