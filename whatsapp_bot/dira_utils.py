import requests
import re
from django.conf import settings
from django.utils import timezone
from .models import UserSession, ConversationLog, QuizSession


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


def send_interactive_message(phone_number, header_text, body_text, buttons):
    """Send an interactive message with list buttons via WhatsApp API"""
    try:
        # Create list rows
        rows = []
        for i, button in enumerate(buttons):
            rows.append({
                "id": f"option_{i+1}",
                "title": button[:24],  # WhatsApp limit
                "description": f"Chagua {button}"
            })
        
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": phone_number,
            "type": "interactive",
            "interactive": {
                "type": "list",
                "header": {
                    "type": "text",
                    "text": header_text
                },
                "body": {
                    "text": body_text
                },
                "action": {
                    "button": "Chagua",
                    "sections": [
                        {
                            "title": "Chaguzi",
                            "rows": rows
                        }
                    ]
                }
            }
        }
        
        # Send via WhatsApp API
        response = whatsapp_api_call(payload)
        if not response or response.get('error'):
            print(f"Failed to send interactive message: {response.get('error', {}).get('message', 'Unknown error')}")
        return response
    except Exception as e:
        print(f"Error in send_interactive_message: {str(e)}")
        return None


def send_interactive_response(phone_number, user_session, response_text):
    """Send interactive response with list buttons based on current state"""
    try:
        if user_session.current_state == 'gender_disability':
            header = "Jinsia na Ulemavu"
            body = "Je, wewe ni mwanamke au mwenye ulemavu?\n(Hii itatusaidia kukupa maelezo maalum)"
            buttons = ["Mwanaume", "Mwanamke", "Mwanaume + Ulemavu", "Mwanamke + Ulemavu", "Sipendi kusema"]
            
            send_interactive_message(phone_number, header, body, buttons)
        else:
            # Fallback to text message
            send_text_message(phone_number, response_text)
            
    except Exception as e:
        print(f"Error in send_interactive_response: {str(e)}")
        # Fallback to text message
        send_text_message(phone_number, response_text)


def log_conversation(user_session, message_type, content):
    """Log conversation for analytics"""
    try:
        ConversationLog.objects.create(
            user_session=user_session,
            message_type=message_type,
            message_content=content
        )
    except Exception as e:
        print(f"Error logging conversation: {str(e)}")


def get_or_create_user_session(phone_number, contact_name=None):
    """Get or create user session"""
    try:
        session, created = UserSession.objects.get_or_create(
            phone_number=phone_number,
            defaults={
                'name': contact_name,
                'current_state': 'welcome',
                'is_active': True
            }
        )
        if created:
            print(f"Created new session for {phone_number}")
        return session
    except Exception as e:
        print(f"Error getting/creating user session: {str(e)}")
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
            elif message_type == 'interactive':
                # Handle interactive interactions (buttons and lists)
                interactive = message.get('interactive', {})
                if interactive.get('type') == 'button_reply':
                    button_id = interactive.get('button_reply', {}).get('id', '')
                    button_text = interactive.get('button_reply', {}).get('title', '')
                    # Convert button ID to number for processing
                    if button_id == 'btn_1':
                        text_body = '1'
                    elif button_id == 'btn_2':
                        text_body = '2'
                    elif button_id == 'btn_3':
                        text_body = '3'
                    else:
                        text_body = button_text.lower()
                    handle_text_message(from_number, text_body, contact_name)
                else:
                    # Handle list interactions
                    list_id = interactive.get('list_reply', {}).get('id', '')
                    list_text = interactive.get('list_reply', {}).get('title', '')
                    # Use the ID for list responses to match our option_1, option_2, etc.
                    text_body = list_id if list_id else list_text.lower()
                    handle_text_message(from_number, text_body, contact_name)
            elif message_type == 'image':
                handle_image_message(from_number, message)
            elif message_type == 'document':
                handle_document_message(from_number, message)
            else:
                # Send acknowledgment for other message types
                send_text_message(from_number, "Nimepokea ujumbe wako. Kwa sasa naweza kushughulika na ujumbe wa maandishi tu.")
                
    except Exception as e:
        print(f"Error processing message: {str(e)}")


def handle_text_message(phone_number, text, contact_name=None):
    """Handle incoming text messages with DIRA 2050 flow"""
    try:
        # Get or create user session
        user_session = get_or_create_user_session(phone_number, contact_name)
        if not user_session:
            send_text_message(phone_number, "Samahani, kuna tatizo la kiufundi. Jaribu tena baadaye.")
            return
        
        # Log incoming message
        log_conversation(user_session, 'incoming', text)
        
        # Process based on current state
        response = process_dira_flow(user_session, text)
        
        # Send response (use interactive buttons for 3-option selections)
        if user_session.current_state in ['gender_disability']:
            send_interactive_response(phone_number, user_session, response)
        else:
            send_text_message(phone_number, response)
        
        # Log outgoing message
        log_conversation(user_session, 'outgoing', response)
        
    except Exception as e:
        print(f"Error handling text message: {str(e)}")
        send_text_message(phone_number, "Samahani, kuna tatizo la kiufundi. Jaribu tena baadaye.")


def clear_user_session(phone_number):
    """Clear user session and start fresh"""
    try:
        # Delete existing session
        UserSession.objects.filter(phone_number=phone_number).delete()
        
        # Create new session
        user_session = UserSession.objects.create(
            phone_number=phone_number,
            current_state='welcome'
        )
        return user_session
    except Exception as e:
        print(f"Error clearing session: {str(e)}")
        return None


def process_dira_flow(user_session, text):
    """Process DIRA 2050 conversation flow"""
    text_lower = text.lower().strip()
    current_state = user_session.current_state
    
    # Handle special commands
    if text_lower == '#':
        # Clear session and restart
        user_session.current_state = 'welcome'
        user_session.economic_activity = ''
        user_session.gender = ''
        user_session.has_disability = False
        user_session.save()
        return get_welcome_message()
    
    if any(cmd in text_lower for cmd in ['restart', 'anza', 'anza upya']):
        user_session.current_state = 'welcome'
        user_session.save()
        return get_welcome_message()
    
    if any(cmd in text_lower for cmd in ['help', 'msaada']):
        return get_help_message()
    
    # State-based processing
    if current_state == 'welcome':
        return handle_welcome_state(user_session, text_lower)
    elif current_state == 'gender_disability':
        return handle_gender_disability_state(user_session, text_lower)
    elif current_state == 'personalized_overview':
        return handle_personalized_overview_state(user_session, text_lower)
    elif current_state == 'feedback':
        return handle_feedback_state(user_session, text_lower)
    else:
        return handle_default_response(user_session, text_lower)


def get_welcome_message():
    """Get welcome message for DIRA 2050"""
    return """🇹🇿 *Karibu kwa DIRA 2050 Chatbot!*

Hii ni dira ya Tanzania kuwa nchi yenye uchumi imara wa dola trilioni 1, elimu bora, na maisha bora kwa wote ifikapo 2050.

*Kama vijana, wewe unafanya nini kiuchumi?*

Chagua moja:
1️⃣ Mwanafunzi
2️⃣ Mkulima  
3️⃣ Mjasiriamali
4️⃣ Mfanyakazi
5️⃣ Bila ajira
6️⃣ Nyingine

*Andika nambari ya chaguo lako (1-6)*"""


def get_help_message():
    """Get help message"""
    return """🆘 *Msaada wa DIRA 2050 Chatbot*

*Amri za kawaida:*
• "#" - Futa session na anza upya
• "Rudi Menyu Kuu" - Anza mazungumzo upya
• "Maelezo" - Pata maelezo zaidi
• "Maoni" - Toa maoni yako
• "PDF" - Pata muhtasari wa kurasa

*Kuhusu DIRA 2050:*
DIRA ni Dira ya Maendeleo ya Tanzania 2050 inayolenga kuwa nchi yenye uchumi imara, elimu bora na maisha bora kwa wote.

*Kwa msaada zaidi:*
Tembelea: www.planning.go.tz"""


def handle_welcome_state(user_session, text_lower):
    """Handle welcome state - economic activity selection"""
    activity_map = {
        '1': 'student',
        '2': 'farmer', 
        '3': 'entrepreneur',
        '4': 'worker',
        '5': 'unemployed',
        '6': 'other'
    }
    
    for key, value in activity_map.items():
        if key in text_lower:
            user_session.economic_activity = value
            user_session.current_state = 'gender_disability'
            user_session.save()
            return get_gender_disability_message()
    
    # If no clear activity, ask for clarification
    return """Samahani, sijaelewa. Tafadhali chagua moja ya chaguzi zifuatazo:

*Kama vijana, wewe unafanya nini kiuchumi?*

1️⃣ Mwanafunzi
2️⃣ Mkulima  
3️⃣ Mjasiriamali
4️⃣ Mfanyakazi
5️⃣ Bila ajira
6️⃣ Nyingine

*Andika nambari ya chaguo lako (1-6)*"""




def get_gender_disability_message():
    """Get gender and disability question"""
    return """*Je, wewe ni mwanamke au mwenye ulemavu?*

(Hii itatusaidia kukupa maelezo maalum)

1️⃣ Mwanaume
2️⃣ Mwanamke
3️⃣ Mwanaume mwenye ulemavu
4️⃣ Mwanamke mwenye ulemavu
5️⃣ Sipendi kusema

*Andika nambari ya chaguo lako (1-5)*"""


def handle_economic_activity_state(user_session, text_lower):
    """Handle economic activity state"""
    activity_map = {
        '1': 'student',
        '2': 'farmer', 
        '3': 'entrepreneur',
        '4': 'worker',
        '5': 'unemployed',
        '6': 'other'
    }
    
    for key, value in activity_map.items():
        if key in text_lower:
            user_session.economic_activity = value
            user_session.current_state = 'gender_disability'
            user_session.save()
            return get_gender_disability_message()
    
    # If no clear activity, ask for clarification
    return """Samahani, sijaelewa. Tafadhali chagua moja ya chaguzi zifuatazo:

*Kama vijana, wewe unafanya nini kiuchumi?*

1️⃣ Mwanafunzi
2️⃣ Mkulima  
3️⃣ Mjasiriamali
4️⃣ Mfanyakazi
5️⃣ Bila ajira
6️⃣ Nyingine

*Andika nambari ya chaguo lako (1-6)*"""


def handle_gender_disability_state(user_session, text_lower):
    """Handle gender and disability state"""
    # Handle interactive button responses
    if 'option_1' in text_lower or 'mwanaume' in text_lower:
        user_session.gender = 'male'
        user_session.has_disability = False
    elif 'option_2' in text_lower or 'mwanamke' in text_lower:
        user_session.gender = 'female'
        user_session.has_disability = False
    elif 'option_3' in text_lower or ('mwanaume' in text_lower and 'ulemavu' in text_lower):
        user_session.gender = 'male'
        user_session.has_disability = True
    elif 'option_4' in text_lower or ('mwanamke' in text_lower and 'ulemavu' in text_lower):
        user_session.gender = 'female'
        user_session.has_disability = True
    elif 'option_5' in text_lower or 'sipendi' in text_lower:
        # Prefer not to say - keep defaults
        pass
    # Handle numbered responses as fallback
    elif '1' in text_lower:
        user_session.gender = 'male'
        user_session.has_disability = False
    elif '2' in text_lower:
        user_session.gender = 'female'
        user_session.has_disability = False
    elif '3' in text_lower:
        user_session.gender = 'male'
        user_session.has_disability = True
    elif '4' in text_lower:
        user_session.gender = 'female'
        user_session.has_disability = True
    elif '5' in text_lower:
        # Prefer not to say - keep defaults
        pass
    else:
        return get_gender_disability_message()
    
    user_session.current_state = 'personalized_overview'
    user_session.save()
    
    return get_personalized_overview(user_session)




def get_personalized_overview(user_session):
    """Get personalized overview based on user's economic activity"""
    activity = user_session.economic_activity
    gender = user_session.gender
    has_disability = user_session.has_disability
    
    # Base message
    if activity == 'student':
        message = """📚 *Kama Mwanafunzi Vijana*

DIRA 2050 inakutegemea kujenga uwezo wa vijana (kama ulivyotajwa katika Nguzo ya Pili: Uwezo wa Watu na Maendeleo ya Jamii). Dira inalenga kuwapa vijana elimu na ujuzi stahiki ili kushiriki katika uchumi wa kisasa, kuondoa umaskini mkubwa, na kuunda ajira milioni. Lengo kuu: 25% ya Watanzania wafike elimu ya juu, na vijana kuwa nguzo ya uvumbuzi na ujasiriamali. Hii itaongeza kipato cha kila mtu hadi USD 7,000 na kukuza usawa wa kijinsia na ulemavu.

*Ili kufanikisha DIRA, hapa ni maeneo unayoweza kuzingatia kama mwanafunzi:*
1. Jenga ujuzi wa kidijitali na ujasiriamali (k.m. jiunge na programu za uvumbuzi ili kuchangia Vichocheo vya Sayansi na Teknolojia).
2. Shiriki katika shughuli za jamii kukuza umoja na mshikamano (kwa vijana kushiriki maamuzi, kama katika Utawala Bora).
3. Tumia elimu yako kuhifadhi mazingira (k.m. kujifunza kuhusu tabianchi ili kushiriki Nguzo ya Tatu: Uhifadhi wa Mazingira).
4. Pata mafunzo ya ziada ili kushindana sokoni (lenga wahitimu wenye ujuzi stahiki, kutoa mchango kwa sekta kama Viwanda au Huduma).
5. Thibiti uzalendo na vipaji vyako ili kujenga jamii inayowajibika.

Je, unataka maelezo zaidi kuhusu sekta fulani, au kutuma maoni yako? Au "Soma PDF" ili tupate muhtasari wa kurasa maalum."""

    elif activity == 'farmer':
        message = """🌾 *Kama Mkulima Vijana*

DIRA 2050 inakutambua kama nguzo ya Uchumi Imara, Jumuishi na Shindani (Nguzo ya Kwanza). Dira inalenga kufanya Tanzania kinara wa chakula Afrika na top 10 duniani kupitia sekta ya kilimo, kuongeza mauzo ya nje, na kuunda ajira kwa vijana. Hii itachangia ukuaji wa 8-10% wa uchumi, kupunguza umasikini, na kuwezesha vijana na wanawake katika sekta isiyo rasmi. Lengo: Universal access to clean water and 90% energy for productive farming.

*Ili kufanikisha DIRA, hapa ni maeneo unayoweza kuzingatia kama mkulima vijana:*
1. Tumia teknolojia bunifu kama bayoteknolojia kuongeza tija na kupunguza athari za tabianchi (kushiriki Vichocheo vya Nishati na Uhifadhi wa Mazingira).
2. Shiriki ushirikiano wa umma-binafsi (PPP) kwa miundombinu bora kama barabara na umwagiliaji (ili kufikia malengo ya Sekta za Mageuzi kama Kilimo).
3. Rasimisha shughuli zako ili kupata mikopo nafuu na kushiriki uchumi rasmi (kuwezesha vijana katika uwekezaji na ajira).
4. Lindeni ardhi na maji ili kutoa kilimo endelevu (kushiriki Nguzo ya Tatu na kukabiliana na mabadiliko ya tabianchi).
5. Jenga vipaji vyako katika ujasiriamali ili kuuza mazao kimataifa (kuongeza mapato na mshikamano wa jamii).

Je, unataka maelezo zaidi kuhusu sekta fulani, au kutuma maoni yako? Au "Soma PDF" ili tupate muhtasari wa kurasa maalum."""

    elif activity == 'entrepreneur':
        message = """💼 *Kama Mjasiriamali Vijana*

DIRA 2050 inakutegemea kujenga Sekta Binafsi Imara (katika Nguzo ya Kwanza: Uchumi Imara). Dira inalenga kuwawezesha vijana katika ujasiriamali na uvumbuzi ili kuchangia uchumi wa USD 1 trilioni, kuunda ajira, na kukuza ushirikiano kimataifa. Vijana ni sehemu kubwa ya idadi ya watu na nguzo muhimu katika maendeleo, na dira inasisitiza fursa sawa kwa vijana, wanawake, na wenye ulemavu katika biashara.

*Ili kufanikisha DIRA, hapa ni maeneo unayoweza kuzingatia kama mjasiriamali vijana:*
1. Vumbua bidhaa mpya na tumia kidijitali kama e-commerce kuuza nje (kushiriki Vichocheo vya Mageuzi ya Kidijitali na Uvumbuzi).
2. Shiriki PPP ili kupata mitaji na msaada wa serikali (kuimarisha mazingira ya biashara na uwekezaji).
3. Thibiti rushwa na kushiriki uongozi bora ili kukuza usawa wa kijinsia na ulemavu (kushiriki Msingi Mkuu: Utawala Bora).
4. Lindeni mazingira katika biashara yako (k.m. bidhaa endelevu ili kushiriki Uhifadhi wa Mazingira).
5. Jenga mtandao na vijana wengine ili kushiriki maamuzi na kuunda ajira (kuongeza mshikamano wa kitaifa).

Je, unataka maelezo zaidi kuhusu sekta fulani, au kutuma maoni yako? Au "Soma PDF" ili tupate muhtasari wa kurasa maalum."""

    elif activity == 'worker':
        message = """👷 *Kama Mfanyakazi Vijana*

DIRA 2050 inakutambua kama mchangiaji muhimu katika Uchumi Imara (Nguzo ya Kwanza). Dira inalenga kuunda ajira milioni na kuimarisha sekta mbalimbali ili kuchangia uchumi wa USD 1 trilioni.

*Ili kufanikisha DIRA, hapa ni maeneo unayoweza kuzingatia kama mfanyakazi vijana:*
1. Jenga ujuzi wa ziada katika sekta yako (kushiriki katika mafunzo ya ujuzi stahiki).
2. Shiriki katika mafunzo ya uongozi na maamuzi (kushiriki Utawala Bora).
3. Thibiti maadili ya kazi na uongozi bora (kuimarisha mazingira ya kazi).
4. Jenga mtandao na wafanyakazi wengine (kuongeza mshikamano wa sekta).
5. Shiriki katika maamuzi ya sekta na maendeleo (kuchangia maendeleo ya sekta).

Je, unataka maelezo zaidi kuhusu sekta fulani, au kutuma maoni yako? Au "Soma PDF" ili tupate muhtasari wa kurasa maalum."""

    elif activity == 'unemployed':
        message = """🤝 *Kama Vijana Bila Ajira*

DIRA 2050 inalenga kuunda ajira milioni kwa vijana na kuondoa umasikini. Dira inasisitiza fursa sawa kwa vijana, wanawake, na wenye ulemavu katika ajira na ujasiriamali.

*Ili kufanikisha DIRA, hapa ni maeneo unayoweza kuzingatia kama vijana bila ajira:*
1. Jifunze ujuzi mpya wa kidijitali na ujasiriamali (kushiriki katika mafunzo ya ujuzi).
2. Jiunge na mafunzo ya ujasiriamali na biashara (kujenga uwezo wa biashara).
3. Shiriki katika shughuli za jamii na maendeleo (kushiriki katika maamuzi ya jamii).
4. Tafuta fursa za ajira au biashara (kushiriki katika sekta mbalimbali).
5. Jenga mtandao na vijana wengine (kuongeza mshikamano na fursa).

Je, unataka maelezo zaidi kuhusu sekta fulani, au kutuma maoni yako? Au "Soma PDF" ili tupate muhtasari wa kurasa maalum."""

    else:
        message = """🌟 *Kama Vijana wa Tanzania*

DIRA 2050 inakutegemea kama mchangiaji muhimu katika maendeleo ya nchi. Dira inalenga kuwa nchi yenye uchumi imara wa dola trilioni 1, elimu bora, na maisha bora kwa wote.

*Ili kufanikisha DIRA, hapa ni maeneo unayoweza kuzingatia kama vijana wa Tanzania:*
1. Jenga ujuzi wa kidijitali na ujasiriamali (kushiriki katika mafunzo ya ujuzi).
2. Shiriki katika shughuli za jamii na maendeleo (kushiriki katika maamuzi ya jamii).
3. Thibiti maadili ya kitaifa na uzalendo (kuimarisha maadili ya kitaifa).
4. Jenga mtandao na vijana wengine (kuongeza mshikamano wa kitaifa).
5. Shiriki katika maamuzi ya jamii na maendeleo (kuchangia maendeleo ya nchi).

Je, unataka maelezo zaidi kuhusu sekta fulani, au kutuma maoni yako? Au "Soma PDF" ili tupate muhtasari wa kurasa maalum."""

    # Add gender/disability specific message
    if gender == 'female':
        message += "\n\n*Kama mwanamke vijana, DIRA inasisitiza usawa wa kijinsia katika ajira na umiliki wa ardhi.*"
    
    if has_disability:
        message += "\n\n*Kama mwenye ulemavu, DIRA inasisitiza uwezeshaji na fursa sawa katika maendeleo.*"

    user_session.current_state = 'personalized_overview'
    user_session.save()
    
    return message


def handle_personalized_overview_state(user_session, text_lower):
    """Handle personalized overview state"""
    if any(word in text_lower for word in ['maelezo', 'details', 'zaidi']):
        return get_detailed_info(user_session)
    elif any(word in text_lower for word in ['maoni', 'feedback']):
        user_session.current_state = 'feedback'
        user_session.save()
        return get_feedback_message()
    elif any(word in text_lower for word in ['pdf', 'document', 'soma']):
        return get_pdf_info()
    elif any(word in text_lower for word in ['rudi', 'menyu', 'kuu', 'anza', 'restart']):
        user_session.current_state = 'welcome'
        user_session.save()
        return get_welcome_message()
    else:
        return """*Tafadhali chagua moja ya chaguzi zifuatazo:*

1️⃣ Maelezo zaidi
2️⃣ Toa maoni
3️⃣ Soma PDF
4️⃣ Rudi Menyu Kuu

*Andika nambari ya chaguo lako (1-4)*"""




def get_feedback_message():
    """Get feedback message"""
    return """💬 *Maoni yako ni muhimu!*

Tafadhali toa maoni yako kuhusu DIRA 2050 Chatbot:

• Je, maelezo yamekuwa muhimu?
• Je, unataka kuona kitu kingine?
• Je, una mapendekezo yoyote?

Andika maoni yako hapa chini. Tutayapeleka kwa Tume ya Mipango.

*Au andika "Rudi Menyu Kuu" kuanza upya mazungumzo.*"""


def handle_feedback_state(user_session, text_lower):
    """Handle feedback state"""
    if any(word in text_lower for word in ['rudi', 'menyu', 'kuu', 'anza', 'restart']):
        user_session.current_state = 'welcome'
        user_session.save()
        return get_welcome_message()
    else:
        # Log feedback
        log_conversation(user_session, 'feedback', text_lower)
        
        user_session.current_state = 'personalized_overview'
        user_session.save()
        
        return """Asante kwa maoni yako kuhusu DIRA 2050! 

Tutayapeleka kwa Tume ya Mipango ili kuboresha huduma.

Je, unataka maelezo zaidi, au "Rudi Menyu Kuu" kuanza upya?"""


def get_detailed_info(user_session):
    """Get detailed information"""
    activity = user_session.economic_activity
    
    if activity == 'student':
        return """📚 *Maelezo zaidi kwa Mwanafunzi*

*Nguzo ya Pili: Uwezo wa Watu na Maendeleo ya Jamii*
• Lengo: 25% ya Watanzania wafike elimu ya juu
• Vijana kuwa nguzo ya uvumbuzi na ujasiriamali
• Kuongeza kipato cha kila mtu hadi USD 7,000

*Vichocheo vya Sayansi na Teknolojia:*
• Jifunze teknolojia mpya
• Jiunge na programu za uvumbuzi
• Tumia kidijitali katika masomo yako

*Utawala Bora:*
• Shiriki katika shughuli za jamii
• Jenga uongozi bora
• Thibiti maadili ya kitaifa

*Uhifadhi wa Mazingira:*
• Jifunze kuhusu tabianchi
• Shiriki katika shughuli za mazingira
• Tumia teknolojia endelevu

Je, unataka maoni, au "Rudi Menyu Kuu" kuanza upya?"""

    elif activity == 'farmer':
        return """🌾 *Maelezo zaidi kwa Mkulima*

*Nguzo ya Kwanza: Uchumi Imara, Jumuishi na Shindani*
• Lengo: Tanzania kuwa kinara wa chakula Afrika
• Kuongeza mauzo ya nje
• Kuunda ajira kwa vijana

*Vichocheo vya Nishati na Uhifadhi wa Mazingira:*
• Tumia teknolojia bunifu
• Bayoteknolojia kuongeza tija
• Kupunguza athari za tabianchi

*Sekta za Mageuzi:*
• Kilimo endelevu
• Ushirikiano wa umma-binafsi (PPP)
• Miundombinu bora (barabara, umwagiliaji)

*Uwekezaji na Ajira:*
• Rasimisha shughuli zako
• Kupata mikopo nafuu
• Kushiriki uchumi rasmi

Je, unataka maoni, au "Rudi Menyu Kuu" kuanza upya?"""

    elif activity == 'entrepreneur':
        return """💼 *Maelezo zaidi kwa Mjasiriamali*

*Nguzo ya Kwanza: Uchumi Imara*
• Sekta Binafsi Imara
• Ujasiriamali na uvumbuzi
• Uchumi wa USD 1 trilioni

*Vichocheo vya Mageuzi ya Kidijitali na Uvumbuzi:*
• E-commerce kuuza nje
• Teknolojia mpya
• Bidhaa za uvumbuzi

*Ushirikiano wa Umma-Binafsi (PPP):*
• Kupata mitaji
• Msaada wa serikali
• Mazingira ya biashara

*Utawala Bora:*
• Thibiti rushwa
• Uongozi bora
• Usawa wa kijinsia na ulemavu

*Uhifadhi wa Mazingira:*
• Bidhaa endelevu
• Teknolojia ya kijani
• Mazingira ya biashara

Je, unataka maoni, au "Rudi Menyu Kuu" kuanza upya?"""

    else:
        return """🌟 *Maelezo zaidi kuhusu DIRA 2050*

*Lengo kuu:* Tanzania kuwa nchi yenye uchumi imara wa dola trilioni 1, elimu bora, na maisha bora kwa wote ifikapo 2050.

*Nguzo kuu 3:*
1. Uchumi Imara, Jumuishi na Shindani
2. Uwezo wa Watu na Maendeleo ya Jamii  
3. Uhifadhi wa Mazingira na Maendeleo Endelevu

*Msingi Mkuu:* Utawala Bora, Amani na Usalama

*Vichocheo vya Maendeleo:*
• Sayansi na Teknolojia
• Nishati na Uhifadhi wa Mazingira
• Mageuzi ya Kidijitali na Uvumbuzi

*Lengo la kipato:* USD 7,000 kwa kila mtu
*Lengo la ajira:* Milioni 10

Je, unataka maoni, au "Rudi Menyu Kuu" kuanza upya?"""


def get_pdf_info():
    """Get PDF information"""
    return """📄 *Muhtasari wa Kurasa za DIRA 2050*

*Kurasa muhimu:*
• Ukurasa 1-10: Utangulizi na malengo
• Ukurasa 11-30: Nguzo ya Kwanza (Uchumi)
• Ukurasa 31-50: Nguzo ya Pili (Uwezo wa Watu)
• Ukurasa 51-70: Nguzo ya Tatu (Mazingira)
• Ukurasa 71-90: Msingi Mkuu (Utawala)

*Kwa PDF kamili:*
Tembelea: www.planning.go.tz

*Au andika nambari ya ukurasa (k.m. "25") ili upate muhtasari wa ukurasa husika.*

Je, unataka maoni, au "Rudi Menyu Kuu" kuanza upya?"""


def handle_default_response(user_session, text_lower):
    """Handle default response"""
    return """Samahani, sijaelewa. Tafadhali chagua moja ya chaguzi zifuatazo:

1️⃣ Maelezo zaidi
2️⃣ Toa maoni
3️⃣ Soma PDF
4️⃣ Rudi Menyu Kuu

*Andika nambari ya chaguo lako (1-4)*"""


def handle_image_message(phone_number, message):
    """Handle incoming image messages"""
    try:
        image_data = message.get('image', {})
        image_id = image_data.get('id')
        caption = image_data.get('caption', '')
        
        response = f"📸 Nimepokea picha yako!"
        if caption:
            response += f"\nMaelezo: {caption}"
        response += "\n\nKwa sasa naweza kushughulika na ujumbe wa maandishi tu. Tafadhali tumia maandishi."
        
        send_text_message(phone_number, response)
    except Exception as e:
        print(f"Error handling image message: {str(e)}")


def handle_document_message(phone_number, message):
    """Handle incoming document messages"""
    try:
        document_data = message.get('document', {})
        filename = document_data.get('filename', 'Faili isiyojulikana')
        
        response = f"📄 Nimepokea faili yako: {filename}\n\nKwa sasa naweza kushughulika na ujumbe wa maandishi tu. Tafadhali tumia maandishi."
        
        send_text_message(phone_number, response)
    except Exception as e:
        print(f"Error handling document message: {str(e)}")
