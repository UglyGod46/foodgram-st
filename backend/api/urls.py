from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import IngredientViewSet, RecipeViewSet, UserViewSet

router = DefaultRouter()
router.register(r'recipes', RecipeViewSet)
router.register(r'ingredients', IngredientViewSet)
router.register(r'users', UserViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('auth/', include('djoser.urls')),
    path('auth/', include('djoser.urls.authtoken')),
    path('users/', include('djoser.urls')),
]
