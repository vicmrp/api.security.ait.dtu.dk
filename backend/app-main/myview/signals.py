# from django.db.models.signals import post_save, post_delete
# from django.dispatch import receiver
# from .models import UserProfile, Endpoint, EndpointPermission
# from django.core.cache import cache

# # Invalidate or update cache when a UserProfile is updated
# @receiver([post_save, post_delete], sender=UserProfile)
# def update_user_cache(sender, instance, **kwargs):
#     cache_key = f"user_{instance.user.id}_access"
#     cache.delete(cache_key)