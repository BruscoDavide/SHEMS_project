from django.contrib import admin
from django.urls import path
from . import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('SHEMS/home', views.home, name = 'SHEMS/home'),
    path('SHEMS/appliances', views.appliances, 'SHEMS/appliances'),
    path('SHEMS/scheduling', views.scheduling, name='SHEMS/scheduling'),
    path('SHEMS/changeScheduling', views.changeScheduling, name='SHEMS/changeScheduling'),
    path('SHEMS/summary', views.summary, name='SHEMS/summary'),
    path('SHEMS/settings',  views.settings, name='SHEMS/settings'),
    path('SHEMS/community', views.community, name='SHEMS/community'),
    path('SHEMS/registration', views.registration, name='SHEMS/registration')
]