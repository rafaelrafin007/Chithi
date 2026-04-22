from chat.routing import websocket_urlpatterns as chat_ws
from users.social_routing import websocket_urlpatterns as social_ws

# Project-level websocket URL patterns
websocket_urlpatterns = []
websocket_urlpatterns += chat_ws
websocket_urlpatterns += social_ws
