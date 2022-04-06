import logging

from database_client import databaseClient


if __name__ == '__main__':

    log_name = './logs/mongoDB_cleint_simulator.log'
    logging.basicConfig(
        filename=log_name,
        format='%(asctime)s %(levelname)s: %(message)s',
        level=logging.INFO, datefmt="%H:%M:%S",
        filemode='w'
    )

    print('--\nClient creation')
    name = 'SHEMS_database'
    ip = 'localhost'
    myclient = databaseClient()

    #print('--\nCollection creation')
    collection_name='home_configuration'
    #mycollection = myclient.myCollection(collection_name)

    #print('--\nDocument writing')
    #document = [{'ID':1, 'name':'Davide', 'surname':'brusco', 'level':1}]
    #myclient.write_myDocument(document, collection_name )
    #print(f'In the collection  {collection_name} there are {myclient.count_myDocuments(collection_name)} documents')
    #print(myclient.read_myDocuments(collection_name))

    #print('--\nDocuments writing')
    #documents = [{'ID':2, 'name':'Da', 'surname':'br', 'level':2}, {'ID':3, 'name':'Dav', 'surname':'bru', 'level':1}] 
    #myclient.write_myDocument(documents, collection_name)
    #print(f'In the collection  {collection_name} there are {myclient.count_myDocuments(collection_name)} documents')
    print(myclient.read_documents(collection_name, {'_id':0}))
"""
    print('--\nDocument updating')
    ID = {'ID':3}
    object = {'level':2}
    print(myclient.update_myDocuments(collection_name, ID, object) )
    
    print('--\nDocument deleting')
    print(myclient.delete_myDocuments(collection_name, ID))
    print(myclient.read_myDocuments(collection_name))

    print(f'--\nSoft-skill\n{myclient.help()}')
    print(f'--\nSoft-skill\n{myclient.server_info()}')

    print('--\nError managing')
    print(myclient.read_myDocuments(collection='wrong_collection_name'))
    print('Check log file')
"""


