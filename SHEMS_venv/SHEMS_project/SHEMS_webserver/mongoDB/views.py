from django.shortcuts import render

# Create your views here.
from utils import get_db_handle, get_collection_handle

"""
db_handle, mongo_client = get_db_handle(DATABASE_NAME, DATABASE_HOST, DATABASE_PORT, USERNAME, PASSWORD)
collection_handle = get_collection_handle(db_handle, REGIONS_COLLECTION)
collection_handle.find({...})
collection_handle.insert({...})
collection_handle.update({...})
"""