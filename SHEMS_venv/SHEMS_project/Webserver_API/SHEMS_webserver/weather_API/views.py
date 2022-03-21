from django.http.response import HttpResponse
from django.shortcuts import render

import requests
import json


# Create your views here.

def home(request):
    #return HttpResponse("Ciao")
    return render(request, "home.html")

def weatherAPItest(request):
    #return render(request, "result.html", {"result":res})
    #calcolo un valore e torno quel valore
    #request.GET['']
    BASE_URL = "https://api.openweathermap.org/data/2.5/weather?"
    # City Name CITY = "Hyderabad"
    # API key API_KEY = "Your API Key"
    # upadting the URL
    CITY = 'Torino'
    API_KEY = '165605b60d026027b1e5d38b89469113'
    URL = BASE_URL + "appid=" + API_KEY + "&q=" + CITY
    # HTTP request
    response = requests.get(URL)
    # checking the status code of the request
    if response.status_code == 200:
    # getting data in the json format
        data = response.json()
        # getting the main dict block
        main = data['main']
        # getting temperature
        temperature = main['temp']
        # getting the humidity
        humidity = main['humidity']
        # getting the pressure
        pressure = main['pressure']
        # weather report
        report = data['weather']
        d = {}
        d['temp']=temperature
        d['hum']=humidity
        d['press']=pressure
        d['report']=report[0]['description']
        return HttpResponse(f"results of the get request:\n{d}")
    else:
        # showing the error message
        return HttpResponse(f"Error in the http request")

    

