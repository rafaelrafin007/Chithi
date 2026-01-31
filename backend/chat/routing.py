from django.urls import re_path
from .consumers import ChatConsumer

websocket_urlpatterns = [
    # ws://127.0.0.1:8000/ws/chat/<other_user_id>/?token=<JWT>
    re_path(r"^ws/chat/(?P<user_id>\d+)/$", ChatConsumer.as_asgi()),
]
