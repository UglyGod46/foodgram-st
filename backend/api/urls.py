from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import IngredientViewSet, RecipeViewSet, UserViewSet

router = DefaultRouter()
router.register(r'recipes', RecipeViewSet)
router.register(r'ingredients', IngredientViewSet)
router.register(r'users', UserViewSet, basename='users')


urlpatterns = [
    path('', include(router.urls)),
    path('users/', include('djoser.urls')),
    path('auth/', include('djoser.urls.authtoken')),
    path('users/me/avatar/', UserViewSet.as_view({
        'put': 'avatar',
        'delete': 'delete_avatar'
    }), name='user-avatar'),
    path('users/subscriptions/', UserViewSet.as_view({
        'get': 'subscriptions'
    }), name='user-subscriptions'),
]
