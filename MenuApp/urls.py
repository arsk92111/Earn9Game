from django.conf.urls.static import static 
from django.urls import include, path
from django.conf import settings
from django.contrib import admin
from django.views import View
from django.urls import path   
from . import views     

urlpatterns = [ 
    path('page/wallet_page/' , views.wallet_page, name='wallet_page'), 
    path('page/settings_page/' , views.settings_page, name='settings_page'),   

    ##############################     *******     << API's >>     *******        ##############################
 
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT) 
 