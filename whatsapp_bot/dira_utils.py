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
    """Send an interactive message with buttons via WhatsApp API"""
    try:
        # Create button list
        button_list = []
        for i, button in enumerate(buttons[:3]):  # WhatsApp allows max 3 buttons
            button_list.append({
                "type": "reply",
                "reply": {
                    "id": f"btn_{i+1}",
                    "title": button
                }
            })
        
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": phone_number,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "header": {
                    "type": "text",
                    "text": header_text
                },
                "body": {
                    "text": body_text
                },
                "action": {
                    "buttons": button_list
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
    """Send interactive response with buttons based on current state"""
    try:
        if user_session.current_state == 'economic_activity':
            if user_session.language == 'english':
                header = "Economic Activity"
                body = "What is your economic activity?"
                buttons = ["Student", "Farmer", "Entrepreneur"]
            else:
                header = "Shughuli za Kiuchumi"
                body = "Kama vijana, wewe unafanya nini kiuchumi?"
                buttons = ["Mwanafunzi", "Mkulima", "Mjasiriamali"]
            
            send_interactive_message(phone_number, header, body, buttons)
            
            # Send additional options as text
            if user_session.language == 'english':
                additional = "4️⃣ Worker\n5️⃣ Unemployed\n6️⃣ Other\n\n*Type the number (4-6) for other options*"
            else:
                additional = "4️⃣ Mfanyakazi\n5️⃣ Bila ajira\n6️⃣ Nyingine\n\n*Andika nambari (4-6) kwa chaguzi zingine*"
            
            send_text_message(phone_number, additional)
            
        elif user_session.current_state == 'gender_disability':
            if user_session.language == 'english':
                header = "Gender & Disability"
                body = "Please specify your gender and disability status:"
                buttons = ["Male", "Female", "Male + Disability"]
            else:
                header = "Jinsia na Ulemavu"
                body = "Je, wewe ni:"
                buttons = ["Mwanaume", "Mwanamke", "Mwanaume + Ulemavu"]
            
            send_interactive_message(phone_number, header, body, buttons)
            
            # Send additional options as text
            if user_session.language == 'english':
                additional = "4️⃣ Female + Disability\n5️⃣ Prefer not to say\n\n*Type the number (4-5) for other options*"
            else:
                additional = "4️⃣ Mwanamke + Ulemavu\n5️⃣ Sipendi kusema\n\n*Andika nambari (4-5) kwa chaguzi zingine*"
            
            send_text_message(phone_number, additional)
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
                # Handle button interactions
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
        
        # Send response (use interactive buttons for certain states)
        if user_session.current_state in ['economic_activity', 'gender_disability']:
            send_interactive_response(phone_number, user_session, response)
        else:
            send_text_message(phone_number, response)
        
        # Log outgoing message
        log_conversation(user_session, 'outgoing', response)
        
    except Exception as e:
        print(f"Error handling text message: {str(e)}")
        send_text_message(phone_number, "Samahani, kuna tatizo la kiufundi. Jaribu tena baadaye.")


def process_dira_flow(user_session, text):
    """Process DIRA 2050 conversation flow"""
    text_lower = text.lower().strip()
    current_state = user_session.current_state
    
    # Handle special commands
    if any(cmd in text_lower for cmd in ['restart', 'anza', 'anza upya']):
        user_session.current_state = 'welcome'
        user_session.save()
        return get_welcome_message()
    
    if any(cmd in text_lower for cmd in ['help', 'msaada']):
        return get_help_message()
    
    # State-based processing
    if current_state == 'welcome':
        return handle_welcome_state(user_session, text_lower)
    elif current_state == 'economic_activity':
        return handle_economic_activity_state(user_session, text_lower)
    elif current_state == 'gender_disability':
        return handle_gender_disability_state(user_session, text_lower)
    elif current_state == 'personalized_overview':
        return handle_personalized_overview_state(user_session, text_lower)
    elif current_state == 'quiz':
        return handle_quiz_state(user_session, text_lower)
    elif current_state == 'feedback':
        return handle_feedback_state(user_session, text_lower)
    else:
        return handle_default_response(user_session, text_lower)


def get_welcome_message():
    """Get welcome message for DIRA 2050"""
    return """🇹🇿 *Karibu kwa DIRA 2050 Chatbot!*

Hii ni dira ya Tanzania kuwa nchi yenye uchumi imara wa dola trilioni 1, elimu bora, na maisha bora kwa wote ifikapo 2050.

*Chagua lugha yako / Choose your language:*
1️⃣ Kiswahili
2️⃣ English

*Andika nambari ya chaguo lako (1 au 2)*"""


def get_help_message():
    """Get help message"""
    return """🆘 *Msaada wa DIRA 2050 Chatbot*

*Amri za kawaida:*
• "5" au "Anza" - Anza mazungumzo upya
• "1" au "Quiz" - Anza jaribio la maswali
• "2" au "Maelezo" - Pata maelezo zaidi
• "3" au "Maoni" - Toa maoni yako
• "4" au "PDF" - Pata muhtasari wa kurasa

*Kuhusu DIRA 2050:*
DIRA ni Dira ya Maendeleo ya Tanzania 2050 inayolenga kuwa nchi yenye uchumi imara, elimu bora na maisha bora kwa wote.

*Kwa msaada zaidi:*
Tembelea: www.planning.go.tz"""


def handle_welcome_state(user_session, text_lower):
    """Handle welcome state - language selection"""
    if '1' in text_lower or 'kiswahili' in text_lower:
        user_session.language = 'swahili'
        user_session.current_state = 'economic_activity'
        user_session.save()
        return get_economic_activity_message(user_session)
    elif '2' in text_lower or 'english' in text_lower:
        user_session.language = 'english'
        user_session.current_state = 'economic_activity'
        user_session.save()
        return get_economic_activity_message(user_session)
    else:
        return """Samahani, sijaelewa. Tafadhali chagua moja ya chaguzi zifuatazo:

*Chagua lugha yako / Choose your language:*
1️⃣ Kiswahili
2️⃣ English

*Andika nambari ya chaguo lako (1 au 2)*"""


def get_economic_activity_message(user_session):
    """Get economic activity selection message"""
    if user_session.language == 'english':
        return """*What is your economic activity?*

Choose one:
1️⃣ Student
2️⃣ Farmer
3️⃣ Entrepreneur
4️⃣ Worker
5️⃣ Unemployed
6️⃣ Other

*Type the number of your choice (1-6)*"""
    else:
        return """*Kama vijana, wewe unafanya nini kiuchumi?*

Chagua moja:
1️⃣ Mwanafunzi
2️⃣ Mkulima  
3️⃣ Mjasiriamali
4️⃣ Mfanyakazi
5️⃣ Bila ajira
6️⃣ Nyingine

*Andika nambari ya chaguo lako (1-6)*"""


def get_gender_disability_message(user_session):
    """Get gender and disability question"""
    if user_session.language == 'english':
        return """*Please specify:*

1️⃣ Male
2️⃣ Female
3️⃣ Male with disability
4️⃣ Female with disability
5️⃣ Prefer not to say

*Type the number of your choice (1-5)*"""
    else:
        return """*Je, wewe ni:*

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
            return get_gender_disability_message(user_session)
    
    # If no clear activity, ask for clarification
    return get_economic_activity_message(user_session)


def handle_gender_disability_state(user_session, text_lower):
    """Handle gender and disability state"""
    if '1' in text_lower:
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
        return get_gender_disability_message(user_session)
    
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

DIRA 2050 inakutegemea kujenga uwezo wa vijana (Nguzo ya Pili: Uwezo wa Watu na Maendeleo ya Jamii). Dira inalenga kuwapa vijana elimu na ujuzi stahiki ili kushiriki katika uchumi wa kisasa, kuondoa umaskini mkubwa, na kuunda ajira milioni.

*Lengo kuu:* 25% ya Watanzania wafike elimu ya juu, na vijana kuwa nguzo ya uvumbuzi na ujasiriamali. Hii itaongeza kipato cha kila mtu hadi USD 7,000 na kukuza usawa wa kijinsia na ulemavu.

*Maeneo unayoweza kuzingatia:*
1️⃣ Jenga ujuzi wa kidijitali na ujasiriamali
2️⃣ Shiriki katika shughuli za jamii kukuza umoja
3️⃣ Tumia elimu yako kuhifadhi mazingira
4️⃣ Pata mafunzo ya ziada ili kushindana sokoni
5️⃣ Thibiti uzalendo na vipaji vyako

Je, unataka maelezo zaidi, quiz, au kutuma maoni?"""

    elif activity == 'farmer':
        message = """🌾 *Kama Mkulima Vijana*

DIRA 2050 inakutambua kama nguzo ya Uchumi Imara, Jumuishi na Shindani (Nguzo ya Kwanza). Dira inalenga kufanya Tanzania kinara wa chakula Afrika na top 10 duniani kupitia sekta ya kilimo, kuongeza mauzo ya nje, na kuunda ajira kwa vijana.

*Lengo:* Universal access to clean water na 90% energy for productive farming. Hii itachangia ukuaji wa 8-10% wa uchumi na kupunguza umasikini.

*Maeneo unayoweza kuzingatia:*
1️⃣ Tumia teknolojia bunifu kama bayoteknolojia
2️⃣ Shiriki ushirikiano wa umma-binafsi (PPP)
3️⃣ Rasimisha shughuli zako ili kupata mikopo nafuu
4️⃣ Lindeni ardhi na maji ili kutoa kilimo endelevu
5️⃣ Jenga vipaji vyako katika ujasiriamali

Je, unataka maelezo zaidi, quiz, au kutuma maoni?"""

    elif activity == 'entrepreneur':
        message = """💼 *Kama Mjasiriamali Vijana*

DIRA 2050 inakutegemea kujenga Sekta Binafsi Imara (Nguzo ya Kwanza: Uchumi Imara). Dira inalenga kuwawezesha vijana katika ujasiriamali na uvumbuzi ili kuchangia uchumi wa USD 1 trilioni, kuunda ajira, na kukuza ushirikiano kimataifa.

*Vijana ni sehemu kubwa ya idadi ya watu na nguzo muhimu katika maendeleo.*

*Maeneo unayoweza kuzingatia:*
1️⃣ Vumbua bidhaa mpya na tumia kidijitali
2️⃣ Shiriki PPP ili kupata mitaji na msaada
3️⃣ Thibiti rushwa na kushiriki uongozi bora
4️⃣ Lindeni mazingira katika biashara yako
5️⃣ Jenga mtandao na vijana wengine

Je, unataka maelezo zaidi, quiz, au kutuma maoni?"""

    elif activity == 'worker':
        message = """👷 *Kama Mfanyakazi Vijana*

DIRA 2050 inakutambua kama mchangiaji muhimu katika Uchumi Imara (Nguzo ya Kwanza). Dira inalenga kuunda ajira milioni na kuimarisha sekta mbalimbali ili kuchangia uchumi wa USD 1 trilioni.

*Lengo:* Kuongeza ajira na kipato cha vijana, pamoja na usawa wa kijinsia na ulemavu.

*Maeneo unayoweza kuzingatia:*
1️⃣ Jenga ujuzi wa ziada katika sekta yako
2️⃣ Shiriki katika mafunzo ya uongozi
3️⃣ Thibiti maadili ya kazi na uongozi bora
4️⃣ Jenga mtandao na wafanyakazi wengine
5️⃣ Shiriki katika maamuzi ya sekta

Je, unataka maelezo zaidi, quiz, au kutuma maoni?"""

    elif activity == 'unemployed':
        message = """🤝 *Kama Vijana Bila Ajira*

DIRA 2050 inalenga kuunda ajira milioni kwa vijana na kuondoa umasikini. Dira inasisitiza fursa sawa kwa vijana, wanawake, na wenye ulemavu katika ajira na ujasiriamali.

*Lengo:* Kuongeza ajira na kipato cha vijana, pamoja na elimu na ujuzi stahiki.

*Maeneo unayoweza kuzingatia:*
1️⃣ Jifunze ujuzi mpya wa kidijitali
2️⃣ Jiunge na mafunzo ya ujasiriamali
3️⃣ Shiriki katika shughuli za jamii
4️⃣ Tafuta fursa za ajira au biashara
5️⃣ Jenga mtandao na vijana wengine

Je, unataka maelezo zaidi, quiz, au kutuma maoni?"""

    else:
        message = """🌟 *Kama Vijana wa Tanzania*

DIRA 2050 inakutegemea kama mchangiaji muhimu katika maendeleo ya nchi. Dira inalenga kuwa nchi yenye uchumi imara wa dola trilioni 1, elimu bora, na maisha bora kwa wote.

*Lengo kuu:* Kuongeza kipato cha kila mtu hadi USD 7,000 na kukuza usawa wa kijinsia na ulemavu.

*Maeneo unayoweza kuzingatia:*
1️⃣ Jenga ujuzi wa kidijitali na ujasiriamali
2️⃣ Shiriki katika shughuli za jamii
3️⃣ Thibiti maadili ya kitaifa
4️⃣ Jenga mtandao na vijana wengine
5️⃣ Shiriki katika maamuzi ya jamii

Je, unataka maelezo zaidi, quiz, au kutuma maoni?"""

    # Add gender/disability specific message
    if gender == 'female':
        if user_session.language == 'english':
            message += "\n\n*As a young woman, DIRA emphasizes gender equality in employment and land ownership.*"
        else:
            message += "\n\n*Kama mwanamke vijana, DIRA inasisitiza usawa wa kijinsia katika ajira na umiliki wa ardhi.*"
    
    if has_disability:
        if user_session.language == 'english':
            message += "\n\n*As a person with disability, DIRA emphasizes empowerment and equal opportunities in development.*"
        else:
            message += "\n\n*Kama mwenye ulemavu, DIRA inasisitiza uwezeshaji na fursa sawa katika maendeleo.*"

    # Add menu options
    if user_session.language == 'english':
        message += "\n\n*What would you like to do next?*\n\n1️⃣ Take Quiz\n2️⃣ Get Details\n3️⃣ Give Feedback\n4️⃣ View PDF Summary\n5️⃣ Restart\n\n*Type the number of your choice (1-5)*"
    else:
        message += "\n\n*Je, unataka kufanya nini baadaye?*\n\n1️⃣ Anza Quiz\n2️⃣ Pata Maelezo\n3️⃣ Toa Maoni\n4️⃣ Angalia PDF\n5️⃣ Anza Upya\n\n*Andika nambari ya chaguo lako (1-5)*"

    user_session.current_state = 'personalized_overview'
    user_session.save()
    
    return message


def handle_personalized_overview_state(user_session, text_lower):
    """Handle personalized overview state"""
    if '1' in text_lower or any(word in text_lower for word in ['quiz', 'jaribio', 'maswali']):
        return start_quiz(user_session)
    elif '2' in text_lower or any(word in text_lower for word in ['maelezo', 'details', 'zaidi']):
        return get_detailed_info(user_session)
    elif '3' in text_lower or any(word in text_lower for word in ['maoni', 'feedback']):
        user_session.current_state = 'feedback'
        user_session.save()
        return get_feedback_message()
    elif '4' in text_lower or any(word in text_lower for word in ['pdf', 'document']):
        return get_pdf_info()
    elif '5' in text_lower or any(word in text_lower for word in ['anza', 'restart']):
        user_session.current_state = 'welcome'
        user_session.save()
        return get_welcome_message()
    else:
        if user_session.language == 'english':
            return """*Please choose an option:*

1️⃣ Take Quiz
2️⃣ Get Details
3️⃣ Give Feedback
4️⃣ View PDF Summary
5️⃣ Restart

*Type the number of your choice (1-5)*"""
        else:
            return """*Tafadhali chagua moja ya chaguzi zifuatazo:*

1️⃣ Anza Quiz
2️⃣ Pata Maelezo
3️⃣ Toa Maoni
4️⃣ Angalia PDF
5️⃣ Anza Upya

*Andika nambari ya chaguo lako (1-5)*"""


def start_quiz(user_session):
    """Start quiz session"""
    try:
        quiz_session, created = QuizSession.objects.get_or_create(
            user_session=user_session,
            defaults={'current_question': 0, 'score': 0}
        )
        user_session.current_state = 'quiz'
        user_session.save()
        
        return get_quiz_question(quiz_session)
    except Exception as e:
        print(f"Error starting quiz: {str(e)}")
        return "Samahani, kuna tatizo la kiufundi. Jaribu tena baadaye."


def get_quiz_question(quiz_session):
    """Get quiz question"""
    questions = [
        {
            'question': 'Lengo la GDP la Tanzania ifikapo 2050 ni nini?',
            'options': ['A. USD 500 bilioni', 'B. USD 1 trilioni', 'C. USD 2 trilioni'],
            'correct': 'B'
        },
        {
            'question': 'Nguzo kuu za DIRA 2050 ni ngapi?',
            'options': ['A. 3', 'B. 5', 'C. 7'],
            'correct': 'A'
        },
        {
            'question': 'Kipato cha kila mtu kinatarajiwa kuongezeka hadi?',
            'options': ['A. USD 3,000', 'B. USD 5,000', 'C. USD 7,000'],
            'correct': 'C'
        },
        {
            'question': 'DIRA inalenga kuunda ajira ngapi?',
            'options': ['A. Milioni 5', 'B. Milioni 10', 'C. Milioni 15'],
            'correct': 'B'
        },
        {
            'question': 'Tanzania inalenga kuwa kinara wa chakula katika?',
            'options': ['A. Afrika Mashariki', 'B. Afrika', 'C. Dunia'],
            'correct': 'B'
        }
    ]
    
    if quiz_session.current_question >= len(questions):
        return finish_quiz(quiz_session)
    
    question_data = questions[quiz_session.current_question]
    return f"""📝 *Swali {quiz_session.current_question + 1}/5*

{question_data['question']}

{chr(10).join(question_data['options'])}

Andika herufi ya jibu lako (A, B, au C)"""


def handle_quiz_state(user_session, text_lower):
    """Handle quiz state"""
    try:
        quiz_session = QuizSession.objects.get(user_session=user_session)
        
        # Check answer
        answer = text_lower.strip().upper()
        questions = [
            {'correct': 'B'},
            {'correct': 'A'},
            {'correct': 'C'},
            {'correct': 'B'},
            {'correct': 'B'}
        ]
        
        if quiz_session.current_question < len(questions):
            correct_answer = questions[quiz_session.current_question]['correct']
            
            if answer == correct_answer:
                quiz_session.score += 1
                response = "✅ Sahihi! Jibu lako ni sahihi."
            else:
                response = f"❌ Sio sahihi. Jibu sahihi ni {correct_answer}."
            
            quiz_session.current_question += 1
            quiz_session.save()
            
            if quiz_session.current_question >= 5:
                return finish_quiz(quiz_session)
            else:
                response += f"\n\n{get_quiz_question(quiz_session)}"
                return response
        else:
            return finish_quiz(quiz_session)
            
    except Exception as e:
        print(f"Error handling quiz: {str(e)}")
        return "Samahani, kuna tatizo la kiufundi. Jaribu tena baadaye."


def finish_quiz(quiz_session):
    """Finish quiz and show results"""
    try:
        quiz_session.is_completed = True
        quiz_session.completed_at = timezone.now()
        quiz_session.save()
        
        user_session = quiz_session.user_session
        user_session.current_state = 'personalized_overview'
        user_session.save()
        
        score = quiz_session.score
        total = quiz_session.total_questions
        percentage = (score / total) * 100
        
        if percentage >= 80:
            message = f"""🎉 *Hongera!*

Umemaliza jaribio la maswali kwa ufanisi!
*Alama:* {score}/{total} ({percentage:.0f}%)

Umeonyesha uelewa mzuri wa DIRA 2050. Endelea kujifunza na kushiriki katika maendeleo ya nchi!

Je, unataka maelezo zaidi, kutuma maoni, au "Anza" kuanza upya?"""
        elif percentage >= 60:
            message = f"""👍 *Vizuri!*

Umemaliza jaribio la maswali!
*Alama:* {score}/{total} ({percentage:.0f}%)

Umeonyesha uelewa wa kati wa DIRA 2050. Endelea kujifunza zaidi!

Je, unataka maelezo zaidi, kutuma maoni, au "Anza" kuanza upya?"""
        else:
            message = f"""📚 *Jifunze zaidi!*

Umemaliza jaribio la maswali!
*Alama:* {score}/{total} ({percentage:.0f}%)

Hakuna shida! DIRA 2050 ni mada mpya. Endelea kujifunza zaidi kuhusu dira ya nchi.

Je, unataka maelezo zaidi, kutuma maoni, au "Anza" kuanza upya?"""
        
        return message
        
    except Exception as e:
        print(f"Error finishing quiz: {str(e)}")
        return "Samahani, kuna tatizo la kiufundi. Jaribu tena baadaye."


def get_feedback_message():
    """Get feedback message"""
    return """💬 *Maoni yako ni muhimu!*

Tafadhali toa maoni yako kuhusu DIRA 2050 Chatbot:

• Je, maelezo yamekuwa muhimu?
• Je, unataka kuona kitu kingine?
• Je, una mapendekezo yoyote?

Andika maoni yako hapa chini. Tutayapeleka kwa Tume ya Mipango.

*Au andika "Anza" kuanza upya mazungumzo.*"""


def handle_feedback_state(user_session, text_lower):
    """Handle feedback state"""
    if any(word in text_lower for word in ['anza', 'restart', 'anza upya']):
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

Je, unataka maelezo zaidi, quiz, au "Anza" kuanza upya?"""


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

Je, unataka quiz, maoni, au "Anza" kuanza upya?"""

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

Je, unataka quiz, maoni, au "Anza" kuanza upya?"""

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

Je, unataka quiz, maoni, au "Anza" kuanza upya?"""

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

Je, unataka quiz, maoni, au "Anza" kuanza upya?"""


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

Je, unataka quiz, maoni, au "Anza" kuanza upya?"""


def handle_default_response(user_session, text_lower):
    """Handle default response"""
    if user_session.language == 'english':
        return """Sorry, I didn't understand. Please choose one of the following options:

1️⃣ Take Quiz
2️⃣ Get Details  
3️⃣ Give Feedback
4️⃣ View PDF Summary
5️⃣ Restart
6️⃣ Help

*Type the number of your choice (1-6)*"""
    else:
        return """Samahani, sijaelewa. Tafadhali chagua moja ya chaguzi zifuatazo:

1️⃣ Anza Quiz
2️⃣ Pata Maelezo
3️⃣ Toa Maoni
4️⃣ Angalia PDF
5️⃣ Anza Upya
6️⃣ Msaada

*Andika nambari ya chaguo lako (1-6)*"""


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
