from django.db import models
from django.utils import timezone


class UserSession(models.Model):
    """Model to track user sessions and conversation state"""
    phone_number = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100, blank=True, null=True)
    language = models.CharField(max_length=10, choices=[
        ('swahili', 'Kiswahili'),
        ('english', 'English')
    ], default='swahili')
    gender = models.CharField(max_length=10, choices=[
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
        ('', 'Not specified')
    ], blank=True, default='')
    has_disability = models.BooleanField(default=False)
    economic_activity = models.CharField(max_length=50, choices=[
        ('student', 'Mwanafunzi'),
        ('farmer', 'Mkulima'),
        ('entrepreneur', 'Mjasiriamali'),
        ('worker', 'Mfanyakazi'),
        ('unemployed', 'Bila ajira'),
        ('other', 'Other')
    ], blank=True, default='')
    current_state = models.CharField(max_length=50, default='welcome')
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.phone_number} - {self.economic_activity}"


class ConversationLog(models.Model):
    """Model to log all conversations for analytics"""
    user_session = models.ForeignKey(UserSession, on_delete=models.CASCADE)
    message_type = models.CharField(max_length=20, choices=[
        ('incoming', 'Incoming'),
        ('outgoing', 'Outgoing')
    ])
    message_content = models.TextField()
    timestamp = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.user_session.phone_number} - {self.message_type}"


class QuizSession(models.Model):
    """Model to track quiz sessions"""
    user_session = models.ForeignKey(UserSession, on_delete=models.CASCADE)
    current_question = models.IntegerField(default=0)
    score = models.IntegerField(default=0)
    total_questions = models.IntegerField(default=5)
    is_completed = models.BooleanField(default=False)
    started_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.user_session.phone_number} - Quiz {self.current_question}/{self.total_questions}"