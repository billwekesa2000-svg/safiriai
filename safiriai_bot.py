import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from groq import Groq
from datetime import datetime
import json
from flask import Flask
from threading import Thread
import requests
import re

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

# Safari packages based on Kenyan market (prices in KES)
SAFARI_PACKAGES = {
    "masai_mara": {
        "name": "Masai Mara Safari",
        "duration": "3 Days / 2 Nights",
        "price_budget": 35000,
        "price_mid": 65000,
        "price_luxury": 120000,
        "description": "Game drives in the famous Masai Mara, Big Five viewing, cultural visit to Masai village"
    },
    "amboseli": {
        "name": "Amboseli National Park",
        "duration": "3 Days / 2 Nights", 
        "price_budget": 32000,
        "price_mid": 58000,
        "price_luxury": 95000,
        "description": "Views of Mt. Kilimanjaro, large elephant herds, bird watching"
    },
    "tsavo": {
        "name": "Tsavo East & West",
        "duration": "4 Days / 3 Nights",
        "price_budget": 42000,
        "price_mid": 75000,
        "price_luxury": 130000,
        "description": "Red elephants of Tsavo, diverse wildlife, Mzima Springs"
    },
    "watamu": {
        "name": "Watamu Beach Safari",
        "duration": "5 Days / 4 Nights",
        "price_budget": 55000,
        "price_mid": 95000,
        "price_luxury": 180000,
        "description": "Marine park, snorkeling, beach relaxation, water sports"
    },
    "coastal": {
        "name": "Coastal Beach & Safari Combo",
        "duration": "7 Days / 6 Nights",
        "price_budget": 75000,
        "price_mid": 135000,
        "price_luxury": 250000,
        "description": "3 days safari + 4 days beach"
    }
}

class SafiriAIBot:
    def __init__(self, telegram_token, groq_api_key, paystack_secret_key):
        self.telegram_token = telegram_token
        self.groq_client = Groq(api_key=groq_api_key)
        self.paystack_secret = paystack_secret_key
        self.conversation_history = {}
        self.user_booking_data = {}  # Store booking data per user
        self.exchange_rate = self.get_exchange_rate()
        
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
            return 0.0077  # Fallback rate
    
    def format_price_with_usd(self, kes_amount):
        """Format price showing both KES and USD"""
        usd_amount = kes_amount * self.exchange_rate
        return f"KES {kes_amount:,} (~USD {usd_amount:.0f})"
    
    def create_paystack_payment(self, email, amount, reference):
        """Create Paystack payment link"""
        url = "https://api.paystack.co/transaction/initialize"
        
        logger.info(f"Creating Paystack payment: email={email}, amount={amount}, reference={reference}")
        
        headers = {
            "Authorization": f"Bearer {self.paystack_secret}",
            "Content-Type": "application/json"
        }
        
        data = {
            "email": email,
            "amount": int(amount * 100),  # Paystack uses kobo/cents
            "reference": reference,
            "currency": "KES"
        }
        
        try:
            response = requests.post(url, headers=headers, json=data, timeout=10)
            result = response.json()
            
            logger.info(f"Paystack response: {result}")
            
            if result.get('status'):
                payment_url = result['data']['authorization_url']
                logger.info(f"Payment URL generated successfully: {payment_url}")
                return payment_url
            else:
                error_msg = result.get('message', 'Unknown error')
                logger.error(f"Paystack error: {error_msg}. Full response: {result}")
                return None
        except Exception as e:
            logger.error(f"Paystack error: {type(e).__name__} - {e}")
            return None
    
    def extract_booking_info(self, user_id):
        """Extract and validate booking information from conversation"""
        if user_id not in self.user_booking_data:
            return None
            
        data = self.user_booking_data[user_id]
        
        # Check if we have all required fields
        required = ['safari_type', 'travelers', 'budget_tier', 'email']
        if not all(field in data for field in required):
            return None
            
        return data
    
    def calculate_pricing(self, safari_type, num_travelers, budget_tier):
        """Calculate pricing based on safari and budget"""
        # Find matching safari package
        base_price = 65000  # Default mid-range
        
        safari_lower = safari_type.lower()
        if 'masai' in safari_lower or 'mara' in safari_lower:
            if budget_tier == 'budget':
                base_price = 35000
            elif budget_tier == 'luxury':
                base_price = 120000
            else:
                base_price = 65000
        elif 'amboseli' in safari_lower:
            if budget_tier == 'budget':
                base_price = 32000
            elif budget_tier == 'luxury':
                base_price = 95000
            else:
                base_price = 58000
        elif 'tsavo' in safari_lower:
            if budget_tier == 'budget':
                base_price = 42000
            elif budget_tier == 'luxury':
                base_price = 130000
            else:
                base_price = 75000
        elif 'watamu' in safari_lower or 'beach' in safari_lower:
            if budget_tier == 'budget':
                base_price = 55000
            elif budget_tier == 'luxury':
                base_price = 180000
            else:
                base_price = 95000
        elif 'coastal' in safari_lower or 'combo' in safari_lower:
            if budget_tier == 'budget':
                base_price = 75000
            elif budget_tier == 'luxury':
                base_price = 250000
            else:
                base_price = 135000
        
        safari_cost = base_price * num_travelers
        service_fee = int(safari_cost * 0.04)  # 4% service fee
        total = safari_cost + service_fee
        deposit = int(total * 0.5)  # 50% deposit
        balance = total - deposit
        
        return {
            'safari_cost': safari_cost,
            'service_fee': service_fee,
            'total': total,
            'deposit': deposit,
            'balance': balance
        }
    
    def get_ai_response(self, user_id, user_message):
        """Get AI response with function calling capability"""
        if user_id not in self.conversation_history:
            self.conversation_history[user_id] = []
        
        # Add user message to history
        self.conversation_history[user_id].append({
            "role": "user",
            "content": user_message
        })
        
        # Enhanced system prompt with booking instructions
        system_prompt = """You are SafiriAI's AI booking assistant for safari experiences in Kenya.

PERSONALITY:
- Warm, enthusiastic, and professional
- Target audience: International tourists
- Be conversational and helpful

YOUR ABILITIES:
You can help users book safaris through natural conversation. When a user wants to book or pay:

1. COLLECT REQUIRED INFORMATION (ask conversationally):
   - Safari type (Masai Mara, Amboseli, Tsavo, Watamu, Coastal Combo, or custom)
   - Number of travelers
   - Budget preference (budget/mid-range/luxury)
   - Email address (for payment receipt)
   - Optional: dates, dietary requirements, special requests

2. WHEN YOU HAVE ALL INFO, RESPOND WITH THIS EXACT FORMAT:
   [GENERATE_PAYMENT]
   Safari: [safari name]
   Travelers: [number]
   Budget: [budget/mid-range/luxury]
   Email: [email@example.com]
   [END_PAYMENT]

IMPORTANT RULES:
- Be natural - don't ask for all info at once, collect it through conversation
- If user says "I want to book/pay now", check what info you still need
- Only use [GENERATE_PAYMENT] format when you have: safari type, travelers, budget, and email
- Keep responses concise (2-4 sentences)
- Use minimal Swahili (Jambo for greetings, Hakuna matata for reassurance)
- NEVER mention contacting support team - YOU handle bookings directly
- If user seems ready to pay, collect any missing info and generate payment

PRICING REFERENCE (per person):
- Masai Mara: Budget KES 35k, Mid KES 65k, Luxury KES 120k
- Amboseli: Budget KES 32k, Mid KES 58k, Luxury KES 95k
- Tsavo: Budget KES 42k, Mid KES 75k, Luxury KES 130k
- Watamu Beach: Budget KES 55k, Mid KES 95k, Luxury KES 180k
- Coastal Combo: Budget KES 75k, Mid KES 135k, Luxury KES 250k

You represent SafiriAI - handle bookings confidently and professionally."""
        
        try:
            response = self.groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": system_prompt}
                ] + self.conversation_history[user_id],
                max_tokens=800,
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
            logger.error(f"Groq API error: {e}")
            return "I'm experiencing a technical issue. Let me try again - what safari were you interested in?"
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start command - welcome message"""
        user = update.effective_user
        user_id = user.id
        
        # Initialize user data
        if user_id not in self.user_booking_data:
            self.user_booking_data[user_id] = {}
        
        welcome_message = f"""Jambo {user.first_name}! Welcome to SafiriAI! 🦁🌍

I'm your AI safari assistant. I can help you:
- Explore safari options
- Plan your itinerary  
- Book and pay for your safari

Popular Safaris:
🐘 Masai Mara - The Great Migration
🗻 Amboseli - Mt. Kilimanjaro Views
🦏 Tsavo - Red Elephants
🏖️ Watamu & Coastal Beaches

What kind of safari experience are you looking for?"""
        
        await update.message.reply_text(welcome_message)
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle all messages with AI + payment generation"""
        user_id = update.effective_user.id
        user_message = update.message.text
        
        # Refresh exchange rate periodically
        self.exchange_rate = self.get_exchange_rate()
        
        # Get AI response
        ai_response = self.get_ai_response(user_id, user_message)
        
        # Check if AI wants to generate payment
        if '[GENERATE_PAYMENT]' in ai_response and '[END_PAYMENT]' in ai_response:
            # Extract booking details from AI response
            payment_block = ai_response[ai_response.find('[GENERATE_PAYMENT]'):ai_response.find('[END_PAYMENT]')+13]
            
            # Parse the booking info
            safari_match = re.search(r'Safari: (.+)', payment_block)
            travelers_match = re.search(r'Travelers: (\d+)', payment_block)
            budget_match = re.search(r'Budget: (budget|mid-range|luxury)', payment_block, re.IGNORECASE)
            email_match = re.search(r'Email: ([\w\.-]+@[\w\.-]+\.\w+)', payment_block)
            
            if safari_match and travelers_match and budget_match and email_match:
                safari_type = safari_match.group(1).strip()
                num_travelers = int(travelers_match.group(1))
                budget_tier = budget_match.group(1).lower().replace('-', '_')
                if budget_tier == 'mid_range':
                    budget_tier = 'mid-range'
                email = email_match.group(1).strip()
                
                # Store booking data
                self.user_booking_data[user_id] = {
                    'safari_type': safari_type,
                    'travelers': num_travelers,
                    'budget_tier': budget_tier,
                    'email': email,
                    'timestamp': datetime.now().isoformat()
                }
                
                # Calculate pricing
                pricing = self.calculate_pricing(safari_type, num_travelers, budget_tier)
                
                # Generate payment reference
                reference = f"SAFARI-{user_id}-{int(datetime.now().timestamp())}"
                
                # Create Paystack payment link
                payment_url = self.create_paystack_payment(email, pricing['deposit'], reference)
                
                # Remove the [GENERATE_PAYMENT] block from response
                clean_response = ai_response.replace(payment_block, '').strip()
                
                # Send AI response first (if there's any text before the payment block)
                if clean_response:
                    await update.message.reply_text(clean_response)
                
                # Send payment breakdown
                payment_breakdown = f"""✅ Booking Confirmed!

💰 PAYMENT BREAKDOWN:

Safari Package: {self.format_price_with_usd(pricing['safari_cost'])}
Service Fee (4%): {self.format_price_with_usd(pricing['service_fee'])}
━━━━━━━━━━━━━━━━━━━━━━━━━━
Total Cost: {self.format_price_with_usd(pricing['total'])}

DEPOSIT REQUIRED (50%): {self.format_price_with_usd(pricing['deposit'])}
Balance Due (14 days before safari): {self.format_price_with_usd(pricing['balance'])}"""
                
                await update.message.reply_text(payment_breakdown)
                
                # Send payment link
                if payment_url:
                    payment_link_msg = f"""💳 PAY YOUR DEPOSIT NOW:

Click this link to pay securely with your card:

{payment_url}

Your payment receipt will be sent to:
{email}"""
                    
                    await update.message.reply_text(payment_link_msg)
                    
                    # Send M-Pesa alternative
                    mpesa_msg = f"""📱 OR Pay via M-Pesa (Kenya only):

1. Go to M-Pesa menu
2. Select "Lipa na M-Pesa"
3. Select "Buy Goods and Services"
4. Enter Till: 6339189
5. Enter Amount: {pricing['deposit']}

After payment, send your screenshot here!

Safari njema! 🦁🌍"""
                    
                    await update.message.reply_text(mpesa_msg)
                    
                    # Log booking
                    booking_data = {
                        'timestamp': datetime.now().isoformat(),
                        'user_id': user_id,
                        'username': update.effective_user.username,
                        'booking': self.user_booking_data[user_id],
                        'pricing': pricing,
                        'reference': reference,
                        'payment_url': payment_url,
                        'status': 'pending_payment'
                    }
                    logger.info(f"NEW BOOKING: {json.dumps(booking_data, indent=2)}")
                    
                else:
                    # Paystack failed
                    error_msg = """⚠️ Payment system temporarily unavailable.

Please contact us directly:
📧 safiriaiofficial@gmail.com
📞 +254 724 630 030

We'll process your booking immediately!"""
                    await update.message.reply_text(error_msg)
            else:
                # Parsing failed - send AI response normally
                await update.message.reply_text(ai_response)
        else:
            # Normal AI response
            await update.message.reply_text(ai_response)
    
    async def packages_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show safari packages"""
        self.exchange_rate = self.get_exchange_rate()
        
        packages_text = "🦁 SafiriAI Safari Packages\n\n"
        
        for key, pkg in SAFARI_PACKAGES.items():
            packages_text += f"📍 {pkg['name']}\n"
            packages_text += f"Duration: {pkg['duration']}\n"
            packages_text += f"From {self.format_price_with_usd(pkg['price_budget'])} per person\n"
            packages_text += f"{pkg['description']}\n\n"
        
        packages_text += "Just tell me which one interests you and I'll help you book it!"
        
        await update.message.reply_text(packages_text)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Help command"""
        help_text = """🆘 SafiriAI Help

I'm your AI safari assistant! Just chat with me naturally.

You can:
- Ask about safari options
- Get pricing information
- Book and pay for safaris directly in chat
- Ask questions about Kenya, wildlife, travel tips

Commands:
/start - Restart conversation
/packages - View all safari packages
/help - This message

Just tell me what you're looking for! 🦁"""
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
    
    def run(self):
        """Run the bot"""
        application = Application.builder().token(self.telegram_token).build()
        
        # Start Flask server in background
        Thread(target=run_flask, daemon=True).start()
        
        # Add handlers
        application.add_handler(CommandHandler('start', self.start))
        application.add_handler(CommandHandler('packages', self.packages_command))
        application.add_handler(CommandHandler('help', self.help_command))
        application.add_handler(CommandHandler('contact', self.contact_command))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        # Start bot
        logger.info("SafiriAI AI-Powered Bot starting...")
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
