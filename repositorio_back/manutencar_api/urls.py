from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api-auth', include('rest_framework.urls')),
    path('', include('core.urls')),

    # Rota para obtenção de token JWT
    path('auth/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),

    # Rota para atualização de token JWT
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),


]
