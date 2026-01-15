from .views import ( RegisterView, LoginView, VerifyView , Regenerate_codeView, 
                    ChangePasswordView, LogoutView , ChangeProfileView )
from rest_framework_simplejwt.views import TokenRefreshView 
from django.conf.urls.static import static
from django.urls import include, path 
from django.conf import settings
from django.contrib import admin  
from django.views import View 
from . import views     

urlpatterns = [
    path('' , views.login_page, name='login_page'), 
    path('page/register/' , views.register_page, name='register_page'), 
    path('page/verify_account/' , views.verify_account_page, name='verify_account_page'),  

    path('page/header/' , views.header, name='header'),
    path('page/footer/' , views.footer, name='footer'),

    ##############################     *******     << API's >>     *******        ##############################

    path('api/register/', RegisterView.as_view(), name='register'),
    path('api/login/', LoginView.as_view(), name='login'), 
    path('api/logout/', LogoutView.as_view(), name='logout'),
    path('api/verify_account/<str:authtoken>/', VerifyView.as_view(), name='verify_account'), 
    path('api/regenerate_code/<str:auth_token>/', Regenerate_codeView.as_view(), name="regenerate_code"),
    path('api/changePassword/<str:authtoken>/' , ChangePasswordView.as_view(), name='changePassword'),
    path('api/changeProfile/' , ChangeProfileView.as_view(), name='changeProfile'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT) 
 