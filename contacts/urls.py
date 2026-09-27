from django.urls import path

from .views import MessageHistoryListView, chat_message, user_contact

# `anonymous_contact` and `AdminContactView` were removed.
#
# anonymous_contact was entirely non-functional (UnboundLocalError on the
# anonymous path, a nonexistent Listing.object attribute, a TypeError
# concatenating a model instance to a str, and a filter on Contact.first_name
# which is not a model field) *and* it was the unauthenticated open email relay
# that mailed a client-supplied recipient. Requiring an account is also the
# right business model for a listings site: you want a verified lead.
#
# AdminContactView was hardcoded to `Contact.objects.get(id=5)` and was
# shadowed by the admin catch-all, so it was unreachable dead code.

urlpatterns = [
    path("user-contact", user_contact, name="user-contact"),
    path("chat", chat_message, name="chat"),
    path("history/<int:pk>", MessageHistoryListView.as_view(), name="chat-history"),
]
