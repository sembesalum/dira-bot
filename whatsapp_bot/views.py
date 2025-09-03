import json
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.conf import settings
from .dira_utils import process_message


@csrf_exempt
def webhook(request):
    if request.method == 'GET':
        # Verification logic
        mode = request.GET.get('hub.mode')
        token = request.GET.get('hub.verify_token')
        challenge = request.GET.get('hub.challenge')
        
        if mode == 'subscribe' and token == settings.VERIFY_TOKEN:
            return HttpResponse(challenge, status=200)
        return HttpResponse('Verification failed', status=403)
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            entry_time = timezone.now()  # Using timezone.now() for timestamp
            print(f"Webhook received at {entry_time}")
            
            for entry in data.get('entry', []):
                for change in entry.get('changes', []):
                    value = change.get('value')
                    if value and 'messages' in value:
                        process_message(value)
            return HttpResponse('OK', status=200)
        except Exception as e:
            print(f"Webhook error at {timezone.now()}: {str(e)}")
            return HttpResponse('Error', status=500)