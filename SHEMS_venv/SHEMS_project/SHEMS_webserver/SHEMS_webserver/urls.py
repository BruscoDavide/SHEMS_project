from django.contrib import admin
from django.urls import path
from . import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('home', views.home, name = 'home'),
    path('scheduling', views.scheduling, name='scheduling'),
    path('changeScheduling/listDevice', views.listDevice, name = 'changeScheduling/listDevice'),
    path('changeScheduling', views.changeScheduling, name='changeScheduling'),
    path('summary', views.summary, name='summary'),
    path('settings/oldParameters', views.oldParameters, name='settings/oldParameters'),
    path('settings',  views.settings, name='settings'),
    path('community/plots', views.communityPlots, name='community/plots'),
    path('community/prosumers', views.communityProsumers, name='community/prosumers'),
    path('registration', views.registration, name='registration')
    
]