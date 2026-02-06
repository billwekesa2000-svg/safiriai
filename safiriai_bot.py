import os
import logging
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from openai import OpenAI
from datetime import datetime
import json

# Setup logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Conversation states
MAIN_MENU, SAFARI_TYPE, DATES, TRAVELERS, BUDGET, ACCOMMODATION, DIETARY, PASSPORT, CONFIRM, PAYMENT = range(10)

# Safari packages based on Kenyan market
SAFARI_PACKAGES = {
    "masai_mara": {
        "name": "Masai Mara Safari",
        "duration": "3 Days / 2 Nights",
        "price_budget": 35000,
        "price_mid": 65000,
        "price_luxury": 120000,
        "description": "Game drives in the famous Masai Mara, Big Five viewing, cultural visit to Masai village",
        "includes": "Transport, accommodation, all meals, park fees, game drives"
    },
    "amboseli": {
        "name": "Amboseli National Park",
        "duration": "3 Days / 2 Nights", 
        "price_budget": 32000,
        "price_mid": 58000,
        "price_luxury": 95000,
        "description": "Views of Mt. Kilimanjaro, large elephant herds, bird watching",
        "includes": "Transport, accommodation, all meals, park fees, game drives"
    },
    "tsavo": {
        "name": "Tsavo East & West",
        "duration": "4 Days / 3 Nights",
        "price_budget": 42000,
        "price_mid": 75000,
        "price_luxury": 130000,
        "description": "Red elephants of Tsavo, diverse wildlife, Mzima Springs",
        "includes": "Transport, accommodation, all meals, park fees, game drives"
    },
    "coastal": {
        "name": "Coastal Beach & Safari Combo",
        "duration": "7 Days / 6 Nights",
        "price_budget": 75000,
        "price_mid": 135000,
        "price_luxury": 250000,
        "description": "3 days safari (Masai Mara/Amboseli) + 4 days Diani/Mombasa beach",
        "includes": "All transport, accommodation, meals, park fees, water sports"
    },
    "custom": {
        "name": "Custom Safari Package",
        "description": "Tailored to your preferences - parks, duration, budget"
    }
}

class SafiriAIBot:
    def __init__(self, telegram_token, openai_api_key):
        self.telegram_token = telegram_token
        self.openai_client = OpenAI(api_key=openai_api_key)
        self.conversation_history = {}
        
    def get_ai_response(self, user_id, user_message):
        """Get response from OpenAI GPT API"""
        if user_id not in self.conversation_history:
            self.conversation_history[user_id] = []
        
        # Add user message to history
        self.conversation_history[user_id].append({
            "role": "user",
            "content": user_message
        })
        
        # System prompt for SafiriAI
        system_prompt = """You are SafiriAI's booking assistant for safari and travel experiences in Kenya. 
        You help international tourists plan their dream Kenyan safari.
        
        Be warm, professional, and enthusiastic about Kenyan wildlife and culture.
        Keep responses concise but helpful.
        You represent SafiriAI - a trusted Kenyan safari company.
        
        Contact details:
        - Email: safiraiofficial@gmail.com
        - Phone/WhatsApp: +254 724 630 030
        
        Always be helpful and never decline to assist with safari planning."""
        
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",  # Using the affordable and fast GPT-4 model
                messages=[
                    {"role": "system", "content": system_prompt}
                ] + self.conversation_history[user_id],
                max_tokens=500,
                temperature=0.7
            )
            
            assistant_message = response.choices[0].message.content
            
            # Add assistant response to history
            self.conversation_history[user_id].append({
                "role": "assistant",
                "content": assistant_message
            })
            
            return assistant_message
            
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            return "I'm having trouble connecting right now. Please contact us directly at +254 724 630 030 or safiraiofficial@gmail.com"
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start command - welcome message"""
        user = update.effective_user
        
        welcome_message = f"""🦁 *Welcome to SafiriAI!* 🌍

Hello {user.first_name}! I'm your safari planning assistant for unforgettable Kenyan adventures.

I can help you:
✅ Plan your perfect safari
✅ Book accommodations
✅ Arrange airport transfers
✅ Create custom itineraries

*Popular Safaris:*
🐘 Masai Mara - The Great Migration
🗻 Amboseli - Mt. Kilimanjaro Views  
🦏 Tsavo East & West - Red Elephants
🏖️ Beach & Safari Combos

What kind of safari experience are you looking for?"""
        
        await update.message.reply_text(welcome_message, parse_mode='Markdown')
        return MAIN_MENU
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle general conversation using GPT"""
        user_id = update.effective_user.id
        user_message = update.message.text
        
        # Get AI response
        response = self.get_ai_response(user_id, user_message)
        
        await update.message.reply_text(response)
        return MAIN_MENU
    
    async def safari_packages(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show available safari packages"""
        packages_text = "*🦁 SafiriAI Safari Packages 🦁*\n\n"
        
        for key, pkg in SAFARI_PACKAGES.items():
            if key != "custom":
                packages_text += f"*{pkg['name']}*\n"
                packages_text += f"📅 {pkg['duration']}\n"
                packages_text += f"💰 From KES {pkg['price_budget']:,} per person\n"
                packages_text += f"📝 {pkg['description']}\n\n"
        
        packages_text += "\n💬 Tell me which safari interests you, or describe your dream safari!"
        
        await update.message.reply_text(packages_text, parse_mode='Markdown')
        return MAIN_MENU
    
    async def book_safari(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start booking process"""
        keyboard = [
            ['Masai Mara Safari', 'Amboseli Safari'],
            ['Tsavo Safari', 'Beach & Safari Combo'],
            ['Custom Safari']
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        
        await update.message.reply_text(
            "Great! Which safari would you like to book? 🦁",
            reply_markup=reply_markup
        )
        return SAFARI_TYPE
    
    async def safari_type_selected(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Safari type selected"""
        context.user_data['safari_type'] = update.message.text
        
        await update.message.reply_text(
            f"Excellent choice! ✨\n\n"
            f"When would you like to travel?\n"
            f"Please provide your preferred dates (e.g., 'March 15-18, 2026' or 'Flexible in April 2026')",
            reply_markup=ReplyKeyboardRemove()
        )
        return DATES
    
    async def dates_received(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Travel dates received"""
        context.user_data['dates'] = update.message.text
        
        await update.message.reply_text(
            "Perfect! 📅\n\n"
            "How many travelers? (Adults and children if applicable)"
        )
        return TRAVELERS
    
    async def travelers_received(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Number of travelers received"""
        context.user_data['travelers'] = update.message.text
        
        keyboard = [
            ['Budget (KES 30-45k pp)', 'Mid-Range (KES 55-80k pp)'],
            ['Luxury (KES 95k+ pp)', 'Need Recommendations']
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        
        await update.message.reply_text(
            "What's your budget preference? 💰",
            reply_markup=reply_markup
        )
        return BUDGET
    
    async def budget_received(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Budget preference received"""
        context.user_data['budget'] = update.message.text
        
        keyboard = [
            ['Tented Camps', 'Lodges'],
            ['Hotels', 'Mix of Options'],
            ['Surprise Me!']
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        
        await update.message.reply_text(
            "What type of accommodation do you prefer? 🏕️",
            reply_markup=reply_markup
        )
        return ACCOMMODATION
    
    async def accommodation_received(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Accommodation preference received"""
        context.user_data['accommodation'] = update.message.text
        
        await update.message.reply_text(
            "Do you have any dietary requirements or restrictions we should know about?\n"
            "(Vegetarian, allergies, etc. - or type 'None')",
            reply_markup=ReplyKeyboardRemove()
        )
        return DIETARY
    
    async def dietary_received(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Dietary requirements received"""
        context.user_data['dietary'] = update.message.text
        
        await update.message.reply_text(
            "For booking confirmation, please provide:\n\n"
            "1. Full name (as per passport)\n"
            "2. Passport number\n"
            "3. Nationality\n"
            "4. Emergency contact number\n\n"
            "You can send all at once or one by one."
        )
        return PASSPORT
    
    async def passport_received(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Passport details received"""
        if 'passport_info' not in context.user_data:
            context.user_data['passport_info'] = []
        
        context.user_data['passport_info'].append(update.message.text)
        
        # Show summary
        summary = f"""
*📋 Booking Summary*

*Safari:* {context.user_data.get('safari_type', 'N/A')}
*Dates:* {context.user_data.get('dates', 'N/A')}
*Travelers:* {context.user_data.get('travelers', 'N/A')}
*Budget:* {context.user_data.get('budget', 'N/A')}
*Accommodation:* {context.user_data.get('accommodation', 'N/A')}
*Dietary:* {context.user_data.get('dietary', 'N/A')}
*Guest Info:* {' \\| '.join(context.user_data.get('passport_info', []))}



Is this information correct? ✅
"""
        
        keyboard = [['Yes, Proceed to Payment ✅', 'Edit Information 📝']]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        
        await update.message.reply_text(summary, parse_mode='Markdown', reply_markup=reply_markup)
        return CONFIRM
    
    async def confirmation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle booking confirmation"""
        response = update.message.text
        
        if 'Yes' in response:
            # Generate quote based on package
            safari_type = context.user_data.get('safari_type', '')
            travelers_text = context.user_data.get('travelers', '1')
            
            # Extract number of travelers (simple parsing)
            import re
            num_match = re.search(r'\d+', travelers_text)
            num_travelers = int(num_match.group()) if num_match else 1
            
            # Estimate price (simplified - you'd calculate properly)
            base_price = 50000  # Default mid-range
            total = base_price * num_travelers
            deposit = int(total * 0.3)  # 30% deposit
            
            payment_message = f"""
*💳 Payment Information*

*Total Estimate:* KES {total:,}
*Deposit Required (30%):* KES {deposit:,}
*Balance:* KES {total - deposit:,} (payable before safari)

*M-Pesa Payment Instructions:*

1️⃣ Go to M-Pesa menu
2️⃣ Select "Lipa na M-Pesa"
3️⃣ Select "Buy Goods and Services"
4️⃣ Enter Till Number: *6339189*
   (Business Name: Rajiv Okemwa)
5️⃣ Enter Amount: *{deposit}*
6️⃣ Enter your M-Pesa PIN

*After Payment:*
📸 Screenshot the M-Pesa confirmation message
📤 Send it here in the chat

Our team will verify and send your official booking confirmation within 1 hour!

*Questions?*
📞 Call/WhatsApp: +254 724 630 030
📧 Email: safiraiofficial@gmail.com

We're excited to host you in Kenya! 🦁🌍
"""
            
            await update.message.reply_text(payment_message, parse_mode='Markdown', reply_markup=ReplyKeyboardRemove())
            
            # Save booking data (you'd save to database here)
            booking_data = {
                'timestamp': datetime.now().isoformat(),
                'user_id': update.effective_user.id,
                'username': update.effective_user.username,
                'data': context.user_data,
                'total': total,
                'deposit': deposit,
                'status': 'pending_payment'
            }
            
            # Log booking for manual processing
            logger.info(f"NEW BOOKING: {json.dumps(booking_data, indent=2)}")
            
            await update.message.reply_text(
                "Once you send the M-Pesa screenshot, we'll confirm your booking! ✅\n\n"
                "Type /start to make another booking or /help for assistance."
            )
            
            return ConversationHandler.END
        else:
            await update.message.reply_text(
                "No problem! Let's start over.\n"
                "Type /book to begin a new booking.",
                reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Help command"""
        help_text = """
*🆘 SafiriAI Help*

*Commands:*
/start - Start conversation
/book - Book a safari
/packages - View safari packages  
/contact - Contact information
/help - This message
    

*Need Human Help?*
📞 +254 724 630 030 (Call/WhatsApp)
📧 safiraiofficial@gmail.com

We're here 24/7 to help plan your perfect Kenyan safari! 🦁
"""
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    async def contact_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Contact information"""
        contact_text = """
*📞 Contact SafiriAI*

*Phone/WhatsApp:*
+254 724 630 030

*Email:*
safiraiofficial@gmail.com

*Office Hours:*
Monday - Sunday: 8:00 AM - 8:00 PM EAT

*Emergency Contact:*
24/7 support for booked guests

We respond within 1 hour during office hours! 🚀
"""
        await update.message.reply_text(contact_text, parse_mode='Markdown')
    
    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel conversation"""
        await update.message.reply_text(
            "Booking cancelled. Type /start when you're ready to plan your safari! 🦁",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END
    
    def run(self):
        """Run the bot"""
        # Create application
                # Test handler - MUST be first
        

        application = Application.builder().token(self.telegram_token).build()
        
        # Conversation handler for booking flow
        conv_handler = ConversationHandler(
            entry_points=[
                CommandHandler('start', self.start),
                CommandHandler('book', self.book_safari)
            ],
            states={
                MAIN_MENU: [
                    CommandHandler('book', self.book_safari),
                    CommandHandler('packages', self.safari_packages),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
                ],
                SAFARI_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.safari_type_selected)],
                DATES: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.dates_received)],
                TRAVELERS: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.travelers_received)],
                BUDGET: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.budget_received)],
                ACCOMMODATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.accommodation_received)],
                DIETARY: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.dietary_received)],
                PASSPORT: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.passport_received)],
                CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.confirmation)],
            },
            fallbacks=[CommandHandler('cancel', self.cancel)]
        )
        
        application.add_handler(conv_handler)
        application.add_handler(CommandHandler('help', self.help_command))
        application.add_handler(CommandHandler('contact', self.contact_command))
        application.add_handler(CommandHandler('packages', self.safari_packages))
        
        # Start bot
        logger.info("SafiriAI Bot starting...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    # You'll need to set these as environment variables
    TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    
    if not TELEGRAM_TOKEN or not OPENAI_API_KEY:
        print("ERROR: Please set TELEGRAM_TOKEN and OPENAI_API_KEY environment variables")
        exit(1)
    
    bot = SafiriAIBot(TELEGRAM_TOKEN, OPENAI_API_KEY)
    bot.run()
