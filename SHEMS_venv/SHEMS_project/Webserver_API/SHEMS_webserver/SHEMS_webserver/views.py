from django.http.response import HttpResponse
from django.shortcuts import render

import pymongo as pm

# Create your views here.

def home(request):
    #return HttpResponse("Ciao")
    return render(request, "home.html")

def getTest(request):
    #return render(request, "result.html", {"result":res})
    #calcolo un valore e torno quel valore
    #request.GET['']
    client = pm.MongoClient ('localhost')
    mydb = client['SHEMS_database']
    mycol = mydb['first_configuration']
    myquery = {'first_configuration'}
    mydoc = mycol.find() #""""""""""" lettura da DB
    return HttpResponse(f"the get request works: {list(mydoc)}")

def postTest(request):
    # request.POST['']
    return HttpResponse("the post request works")