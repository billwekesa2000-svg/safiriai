import os
import logging
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from groq import Groq
from datetime import datetime
import json
from flask import Flask
from threading import Thread
import requests

# Flask app for Render health check
app = Flask(__name__)

@app.route('/')
def home():
    return "SafiriAI Bot is running!", 200

@app.route('/health')
def health():
    return "OK", 200

def run_flask():
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)

# Setup logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Conversation states
MAIN_MENU, SAFARI_TYPE, DATES, TRAVELERS, BUDGET, ACCOMMODATION, DIETARY, PASSPORT, EMAIL, CONFIRM, PAYMENT = range(11)

# Safari packages based on Kenyan market (prices in KES)
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
    def __init__(self, telegram_token, groq_api_key, paystack_secret_key):
        self.telegram_token = telegram_token
        self.groq_client = Groq(api_key=groq_api_key)
        self.paystack_secret = paystack_secret_key
        self.conversation_history = {}
        self.exchange_rate = self.get_exchange_rate()  # Get initial rate
        
    def get_exchange_rate(self):
        """Get live KES to USD exchange rate"""
        try:
            response = requests.get("https://api.exchangerate-api.com/v4/latest/KES", timeout=5)
            data = response.json()
            usd_rate = data['rates']['USD']
            logger.info(f"Exchange rate fetched: 1 KES = {usd_rate} USD")
            return usd_rate
        except Exception as e:
            logger.error(f"Exchange rate API error: {e}")
            # Fallback to approximate rate if API fails
            return 0.0077  # Approximate rate as of early 2025
    
    def format_price_with_usd(self, kes_amount):
        """Format price showing both KES and USD"""
        usd_amount = kes_amount * self.exchange_rate
        return f"KES {kes_amount:,} (~USD {usd_amount:.0f})"
    
    def get_ai_response(self, user_id, user_message):
        """Get response from Groq AI API"""
        if user_id not in self.conversation_history:
            self.conversation_history[user_id] = []
        
        # Add user message to history
        self.conversation_history[user_id].append({
            "role": "user",
            "content": user_message
        })
        
        # Updated system prompt - minimal Swahili, no contact info by default
        system_prompt = """You are SafiriAI's booking assistant for safari and travel experiences in Kenya.

PERSONALITY:
- Warm, enthusiastic, and professional
- Target audience: International tourists visiting Kenya
- Be conversational and helpful, not robotic

IMPORTANT RULES:
- Keep responses concise (2-4 sentences max unless asked for details)
- Be helpful and friendly
- Focus on safari planning, wildlife, and Kenya's beauty
- NO Swahili phrases in regular conversation (only the bot uses them at specific moments)
- NEVER mention contact details (email/phone) unless user explicitly asks how to contact support
- If user seems stuck or there's a technical issue, THEN you may suggest they reach out for direct assistance

You represent SafiriAI - a trusted Kenyan safari company specializing in unforgettable wildlife experiences."""
        
        try:
            response = self.groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": system_prompt}
                ] + self.conversation_history[user_id],
                max_tokens=500,
                temperature=0.8
            )
            
            assistant_message = response.choices[0].message.content
            
            # Add assistant response to history
            self.conversation_history[user_id].append({
                "role": "assistant",
                "content": assistant_message
            })
            
            return assistant_message
            
        except Exception as e:
            logger.error(f"Groq API error: {e}")
            return "I'm experiencing a technical issue. Please contact our team at safiriaiofficial@gmail.com or +254 724 630 030 for immediate assistance."
    
    def create_paystack_payment(self, email, amount, reference):
        """Create Paystack payment link"""
        url = "https://api.paystack.co/transaction/initialize"
        
        headers = {
            "Authorization": f"Bearer {self.paystack_secret}",
            "Content-Type": "application/json"
        }
        
        data = {
            "email": email,
            "amount": int(amount * 100),  # Paystack uses kobo/cents
            "reference": reference,
            "currency": "KES",
            "callback_url": "https://safiriai.com/payment-success"
        }
        
        try:
            response = requests.post(url, headers=headers, json=data)
            result = response.json()
            
            if result.get('status'):
                return result['data']['authorization_url']
            else:
                logger.error(f"Paystack error: {result}")
                return None
        except Exception as e:
            logger.error(f"Paystack API error: {e}")
            return None
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start command - welcome message"""
        user = update.effective_user
        
        welcome_message = f"""Jambo {user.first_name}! Welcome to SafiriAI! 🦁🌍

I'm your safari planning assistant for unforgettable Kenyan adventures.

I can help you:
- Plan your perfect safari
- Book accommodations
- Arrange airport transfers
- Create custom itineraries

Popular Safaris:
🐘 Masai Mara - The Great Migration
🗻 Amboseli - Mt. Kilimanjaro Views  
🦏 Tsavo East & West - Red Elephants
🏖️ Diani & Watamu - Beautiful Beaches

What kind of safari experience are you looking for?"""
        
        await update.message.reply_text(welcome_message)
        return MAIN_MENU
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle general conversation using AI"""
        user_id = update.effective_user.id
        user_message = update.message.text
        
        # Get AI response
        response = self.get_ai_response(user_id, user_message)
        
        await update.message.reply_text(response)
        return MAIN_MENU
    
    async def safari_packages(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show available safari packages"""
        # Refresh exchange rate
        self.exchange_rate = self.get_exchange_rate()
        
        packages_text = "SafiriAI Safari Packages 🦁\n\n"
        
        for key, pkg in SAFARI_PACKAGES.items():
            if key != "custom":
                packages_text += f"📍 {pkg['name']}\n"
                packages_text += f"Duration: {pkg['duration']}\n"
                packages_text += f"From {self.format_price_with_usd(pkg['price_budget'])} per person\n"
                packages_text += f"{pkg['description']}\n\n"
        
        packages_text += "Which safari interests you? Or describe your dream safari and I'll help create it! 🌍"
        
        await update.message.reply_text(packages_text)
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
            "Wonderful! Which safari would you like to book? 🦁",
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
        
        # Refresh exchange rate for accurate pricing
        self.exchange_rate = self.get_exchange_rate()
        
        keyboard = [
            [f'Budget ({self.format_price_with_usd(35000)} pp)'],
            [f'Mid-Range ({self.format_price_with_usd(65000)} pp)'],
            [f'Luxury ({self.format_price_with_usd(120000)} pp)'],
            ['Need Recommendations']
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
        
        # Ask for email
        await update.message.reply_text(
            "Thank you! 📧\n\n"
            "Finally, what's your email address?\n"
            "(We'll send your payment receipt here)"
        )
        return EMAIL
    
    async def email_received(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Email received - show summary"""
        context.user_data['email'] = update.message.text
        
        # Show summary
        summary = (
            "📋 Booking Summary\n\n"
            f"Safari: {context.user_data.get('safari_type', 'N/A')}\n"
            f"Dates: {context.user_data.get('dates', 'N/A')}\n"
            f"Travelers: {context.user_data.get('travelers', 'N/A')}\n"
            f"Budget: {context.user_data.get('budget', 'N/A')}\n"
            f"Accommodation: {context.user_data.get('accommodation', 'N/A')}\n"
            f"Dietary: {context.user_data.get('dietary', 'N/A')}\n"
            f"Guest Info: {', '.join(context.user_data.get('passport_info', []))}\n"
            f"Email: {context.user_data.get('email', 'N/A')}\n\n"
            "Is this information correct? ✅"
        )
        
        keyboard = [['Yes, Proceed to Payment', 'Edit Information']]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        
        await update.message.reply_text(summary, reply_markup=reply_markup)
        return CONFIRM
    
    async def confirmation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle booking confirmation"""
        response = update.message.text
        
        if 'Yes' in response:
            # Refresh exchange rate for final pricing
            self.exchange_rate = self.get_exchange_rate()
            
            # Generate quote based on package
            safari_type = context.user_data.get('safari_type', '')
            travelers_text = context.user_data.get('travelers', '1')
            
            # Extract number of travelers (simple parsing)
            import re
            num_match = re.search(r'\d+', travelers_text)
            num_travelers = int(num_match.group()) if num_match else 1
            
            # Estimate price (simplified - you'd calculate properly based on budget tier)
            base_price_pp = 65000  # Default mid-range per person
            
            # Try to extract budget tier from user selection
            budget_text = context.user_data.get('budget', '').lower()
            if 'budget' in budget_text:
                base_price_pp = 35000
            elif 'luxury' in budget_text:
                base_price_pp = 120000
            
            # Calculate costs
            safari_cost = base_price_pp * num_travelers
            service_fee = int(safari_cost * 0.04)  # 4% service fee
            total = safari_cost + service_fee
            deposit = int(total * 0.5)  # 50% deposit
            balance = total - deposit
            
            user_email = context.user_data.get('email', 'guest@safiriai.com')
            
            # Generate unique reference
            reference = f"SAFARI-{update.effective_user.id}-{int(datetime.now().timestamp())}"
            
            # Create Paystack payment link
            payment_url = self.create_paystack_payment(user_email, deposit, reference)
            
            if payment_url:
                payment_message = f"""Thank you for choosing SafiriAI! 🎉

💰 PAYMENT BREAKDOWN:

Safari Package: {self.format_price_with_usd(safari_cost)}
Service Fee (4%): {self.format_price_with_usd(service_fee)}
━━━━━━━━━━━━━━━━━━━━━━━━━━
Total Cost: {self.format_price_with_usd(total)}

DEPOSIT REQUIRED (50%): {self.format_price_with_usd(deposit)}
Balance Due (14 days before safari): {self.format_price_with_usd(balance)}"""
                
                await update.message.reply_text(payment_message, reply_markup=ReplyKeyboardRemove())
                
                # Send payment link as separate message for better visibility
                payment_link_message = f"""💳 PAY YOUR DEPOSIT NOW:

Click this link to pay securely with your card:

{payment_url}

Your payment receipt will be sent to:
{user_email}"""
                
                await update.message.reply_text(payment_link_message)
                
                # Send M-Pesa alternative
                mpesa_message = f"""📱 OR Pay via M-Pesa (Kenya only):

1. Go to M-Pesa menu
2. Select "Lipa na M-Pesa"  
3. Select "Buy Goods and Services"
4. Enter Till: 6339189
5. Enter Amount: {deposit}

After payment, send your screenshot here for verification!

Safari njema! 🦁🌍"""
                
                await update.message.reply_text(mpesa_message)
            else:
                # Fallback if Paystack fails
                payment_message = f"""Thank you for choosing SafiriAI! 🎉

💰 PAYMENT BREAKDOWN:

Safari Package: {self.format_price_with_usd(safari_cost)}
Service Fee (4%): {self.format_price_with_usd(service_fee)}
━━━━━━━━━━━━━━━━━━━━━━━━━━
Total Cost: {self.format_price_with_usd(total)}

DEPOSIT REQUIRED (50%): {self.format_price_with_usd(deposit)}
Balance Due (14 days before safari): {self.format_price_with_usd(balance)}"""
            
                await update.message.reply_text(payment_message, reply_markup=ReplyKeyboardRemove())
                
                error_message = """⚠️ We're experiencing a temporary technical issue with our payment system.

Please contact us directly for payment instructions:

📧 safiriaiofficial@gmail.com
📞 +254 724 630 030

We'll process your booking immediately!"""
                
                await update.message.reply_text(error_message)
            
            # Save booking data
            booking_data = {
                'timestamp': datetime.now().isoformat(),
                'user_id': update.effective_user.id,
                'username': update.effective_user.username,
                'data': context.user_data,
                'pricing': {
                    'safari_cost': safari_cost,
                    'service_fee': service_fee,
                    'total': total,
                    'deposit': deposit,
                    'balance': balance,
                    'exchange_rate': self.exchange_rate
                },
                'reference': reference,
                'status': 'pending_payment'
            }
            
            # Log booking for manual processing
            logger.info(f"NEW BOOKING: {json.dumps(booking_data, indent=2)}")
            
            # Final confirmation message
            final_msg = """✅ Once payment is confirmed, we'll send your official booking details!

Type /start to make another booking."""
            
            await update.message.reply_text(final_msg)
            
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
        help_text = """🆘 SafiriAI Help

Commands:
/start - Start conversation
/book - Book a safari
/packages - View safari packages  
/contact - Contact information
/help - This message

I'm here to help plan your perfect Kenyan safari! 🦁"""
        await update.message.reply_text(help_text)
    
    async def contact_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Contact information"""
        contact_text = """📞 Contact SafiriAI

Email: safiriaiofficial@gmail.com
Phone/WhatsApp: +254 724 630 030

Office Hours:
Monday - Sunday: 8:00 AM - 8:00 PM EAT

We respond within 1 hour!"""
        await update.message.reply_text(contact_text)
    
    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel conversation"""
        await update.message.reply_text(
            "Booking cancelled. Hakuna matata! Type /start when ready to plan your safari! 🦁",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END
    
    def run(self):
        """Run the bot"""
        application = Application.builder().token(self.telegram_token).build()
        
        # Start Flask server in background thread
        Thread(target=run_flask, daemon=True).start()

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
                EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.email_received)],
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
    # Environment variables
    TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
    GROQ_API_KEY = os.getenv('GROQ_API_KEY')
    PAYSTACK_SECRET_KEY = os.getenv('PAYSTACK_SECRET_KEY')
    
    if not TELEGRAM_TOKEN or not GROQ_API_KEY or not PAYSTACK_SECRET_KEY:
        print("ERROR: Please set TELEGRAM_TOKEN, GROQ_API_KEY, and PAYSTACK_SECRET_KEY environment variables")
        exit(1)
    
    bot = SafiriAIBot(TELEGRAM_TOKEN, GROQ_API_KEY, PAYSTACK_SECRET_KEY)
    bot.run()
