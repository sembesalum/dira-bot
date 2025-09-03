from django.core.management.base import BaseCommand
from whatsapp_bot.dira_utils import send_text_message


class Command(BaseCommand):
    help = 'Test WhatsApp bot by sending a message'

    def add_arguments(self, parser):
        parser.add_argument('phone_number', type=str, help='Phone number to send test message to')
        parser.add_argument('message', type=str, help='Message to send')

    def handle(self, *args, **options):
        phone_number = options['phone_number']
        message = options['message']
        
        self.stdout.write(f'Sending message to {phone_number}: {message}')
        
        response = send_text_message(phone_number, message)
        
        if response:
            self.stdout.write(
                self.style.SUCCESS(f'Message sent successfully! Response: {response}')
            )
        else:
            self.stdout.write(
                self.style.ERROR('Failed to send message')
            )
