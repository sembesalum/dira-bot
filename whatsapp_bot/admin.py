from django.contrib import admin
from .models import UserSession, ConversationLog, QuizSession


@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    list_display = ['phone_number', 'name', 'economic_activity', 'gender', 'has_disability', 'current_state', 'created_at', 'is_active']
    list_filter = ['economic_activity', 'gender', 'has_disability', 'current_state', 'is_active', 'created_at']
    search_fields = ['phone_number', 'name']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(ConversationLog)
class ConversationLogAdmin(admin.ModelAdmin):
    list_display = ['user_session', 'message_type', 'timestamp', 'message_preview']
    list_filter = ['message_type', 'timestamp']
    search_fields = ['user_session__phone_number', 'message_content']
    readonly_fields = ['timestamp']
    
    def message_preview(self, obj):
        return obj.message_content[:50] + "..." if len(obj.message_content) > 50 else obj.message_content
    message_preview.short_description = 'Message Preview'


@admin.register(QuizSession)
class QuizSessionAdmin(admin.ModelAdmin):
    list_display = ['user_session', 'current_question', 'score', 'total_questions', 'is_completed', 'started_at']
    list_filter = ['is_completed', 'started_at']
    search_fields = ['user_session__phone_number']
    readonly_fields = ['started_at', 'completed_at']