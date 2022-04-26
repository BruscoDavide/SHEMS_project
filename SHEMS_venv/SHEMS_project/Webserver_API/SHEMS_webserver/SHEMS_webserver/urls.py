from django.contrib import admin
from django.urls import path
from . import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('SHEMS/home', views.home, name = 'SHEMS/home'),
    path('SHEMS/scheduling', views.scheduling, name='SHEMS/scheduling'),
    path('SHEMS/changeScheduling/listDevice', views.listDevice, name = 'SHEMS/changeScheduling/listDevice'),
    path('SHEMS/changeScheduling', views.changeScheduling, name='SHEMS/changeScheduling'),
    path('SHEMS/summary', views.summary, name='SHEMS/summary'),
    path('SHEMS/settings/oldParameters', views.oldParameters, name='SHEMS/settings/oldParameters'),
    path('SHEMS/settings',  views.settings, name='SHEMS/settings'),
    path('SHEMS/community/plots', views.communityPlots, name='SHEMS/community/plots'),
    path('SHEMS/community/prosumers', views.communityProsumers, name='SHEMS/community/prosumers'),
    path('SHEMS/registration', views.registration, name='SHEMS/registration')
    
]