from django.urls import re_path

from .social_consumers import SocialConsumer

websocket_urlpatterns = [
    re_path(r"^ws/social/$", SocialConsumer.as_asgi()),
]
