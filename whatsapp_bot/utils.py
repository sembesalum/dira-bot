import requests
from django.conf import settings


def whatsapp_api_call(payload):
    """Make API call to WhatsApp Graph API"""
    headers = {
        'Authorization': f'Bearer {settings.WHATSAPP_ACCESS_TOKEN}',
        'Content-Type': 'application/json'
    }
    try:
        response = requests.post(
            f"https://graph.facebook.com/v18.0/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages",
            headers=headers,
            json=payload,
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"API Error: {str(e)}")
        return None


def send_text_message(phone_number, message):
    """Send a text message via WhatsApp API"""
    try:
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": phone_number,
            "type": "text",
            "text": {"body": message}
        }
        
        # Send via WhatsApp API
        response = whatsapp_api_call(payload)
        if not response or response.get('error'):
            print(f"Failed to send message: {response.get('error', {}).get('message', 'Unknown error')}")
        return response
    except Exception as e:
        print(f"Error in send_text_message: {str(e)}")
        return None


def process_message(value):
    """Process incoming WhatsApp messages"""
    try:
        messages = value.get('messages', [])
        contacts = value.get('contacts', [])
        
        for message in messages:
            # Extract message details
            message_id = message.get('id')
            from_number = message.get('from')
            timestamp = message.get('timestamp')
            message_type = message.get('type')
            
            # Get contact info
            contact_name = None
            for contact in contacts:
                if contact.get('wa_id') == from_number:
                    contact_name = contact.get('profile', {}).get('name')
                    break
            
            print(f"Message from {contact_name or from_number}: {message}")
            
            # Handle different message types
            if message_type == 'text':
                text_body = message.get('text', {}).get('body', '')
                handle_text_message(from_number, text_body, contact_name)
            elif message_type == 'image':
                handle_image_message(from_number, message)
            elif message_type == 'document':
                handle_document_message(from_number, message)
            else:
                # Send acknowledgment for other message types
                send_text_message(from_number, "I received your message. Currently, I can only process text messages.")
                
    except Exception as e:
        print(f"Error processing message: {str(e)}")


def handle_text_message(phone_number, text, contact_name=None):
    """Handle incoming text messages"""
    try:
        # Convert to lowercase for easier processing
        text_lower = text.lower().strip()
        
        # Simple bot responses
        if 'hello' in text_lower or 'hi' in text_lower:
            response = f"Hello {contact_name or 'there'}! 👋 How can I help you today?"
        elif 'help' in text_lower:
            response = """🤖 *Bot Commands:*
• Type 'hello' or 'hi' to greet
• Type 'help' to see this message
• Type 'info' to get bot information
• Type 'time' to get current time"""
        elif 'info' in text_lower:
            response = """ℹ️ *Bot Information:*
This is a WhatsApp bot built with Django and the WhatsApp Business API. I can help you with basic interactions and respond to your messages."""
        elif 'time' in text_lower:
            from django.utils import timezone
            current_time = timezone.now().strftime("%Y-%m-%d %H:%M:%S UTC")
            response = f"🕐 Current time: {current_time}"
        else:
            response = f"Thanks for your message: '{text}'\n\nType 'help' to see available commands."
        
        # Send response
        send_text_message(phone_number, response)
        
    except Exception as e:
        print(f"Error handling text message: {str(e)}")
        send_text_message(phone_number, "Sorry, I encountered an error processing your message.")


def handle_image_message(phone_number, message):
    """Handle incoming image messages"""
    try:
        image_data = message.get('image', {})
        image_id = image_data.get('id')
        caption = image_data.get('caption', '')
        
        response = f"📸 I received your image!"
        if caption:
            response += f"\nCaption: {caption}"
        response += "\n\nCurrently, I can only process text messages. Please send me a text message."
        
        send_text_message(phone_number, response)
    except Exception as e:
        print(f"Error handling image message: {str(e)}")


def handle_document_message(phone_number, message):
    """Handle incoming document messages"""
    try:
        document_data = message.get('document', {})
        filename = document_data.get('filename', 'Unknown file')
        
        response = f"📄 I received your document: {filename}\n\nCurrently, I can only process text messages. Please send me a text message."
        
        send_text_message(phone_number, response)
    except Exception as e:
        print(f"Error handling document message: {str(e)}")
