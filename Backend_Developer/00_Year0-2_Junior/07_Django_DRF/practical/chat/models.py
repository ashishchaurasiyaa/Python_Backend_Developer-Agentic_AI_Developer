"""Chat App Models — Room + Message."""
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Room(models.Model):
    """
    Chat room — many users can join.
    Types:
      public:  anyone can join (URL: /ws/chat/general/)
      private: invite-only (DMs between 2 users)
    """
    class RoomType(models.TextChoices):
        PUBLIC  = "public",  "Public"
        PRIVATE = "private", "Private"

    name        = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    room_type   = models.CharField(max_length=10, choices=RoomType.choices,
                                   default=RoomType.PUBLIC)
    members     = models.ManyToManyField(User, related_name="chat_rooms", blank=True)
    created_by  = models.ForeignKey(User, on_delete=models.CASCADE, related_name="owned_rooms")
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "chat_rooms"

    def __str__(self):
        return f"{self.room_type}:{self.name}"


class Message(models.Model):
    """Individual chat message in a room."""
    room       = models.ForeignKey(Room, on_delete=models.CASCADE, related_name="messages")
    author     = models.ForeignKey(User, on_delete=models.CASCADE, related_name="chat_messages")
    content    = models.TextField(max_length=4000)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "chat_messages"
        ordering = ["created_at"]
        indexes  = [models.Index(fields=["room", "created_at"])]

    def __str__(self):
        return f"{self.author.email}: {self.content[:50]}"
