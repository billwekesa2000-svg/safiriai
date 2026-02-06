"""
Simple JSON-based database for SafiriAI bot
Stores bookings, customer data, and conversation logs

For free tier: Uses local JSON files
Later upgrade: Switch to MongoDB Atlas (also free tier available)
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional

class SafiriDatabase:
    def __init__(self, data_dir='./data'):
        self.data_dir = data_dir
        self.bookings_file = os.path.join(data_dir, 'bookings.json')
        self.customers_file = os.path.join(data_dir, 'customers.json')
        self.conversations_file = os.path.join(data_dir, 'conversations.json')
        
        # Create data directory if it doesn't exist
        os.makedirs(data_dir, exist_ok=True)
        
        # Initialize files if they don't exist
        self._init_file(self.bookings_file)
        self._init_file(self.customers_file)
        self._init_file(self.conversations_file)
    
    def _init_file(self, filepath):
        """Initialize JSON file if it doesn't exist"""
        if not os.path.exists(filepath):
            with open(filepath, 'w') as f:
                json.dump([], f)
    
    def _read_file(self, filepath) -> List[Dict]:
        """Read data from JSON file"""
        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except:
            return []
    
    def _write_file(self, filepath, data):
        """Write data to JSON file"""
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2, default=str)
    
    def save_booking(self, booking_data: Dict) -> str:
        """Save a new booking and return booking ID"""
        bookings = self._read_file(self.bookings_file)
        
        # Generate booking ID
        booking_id = f"SAF{datetime.now().strftime('%Y%m%d')}{len(bookings)+1:03d}"
        
        booking_data['booking_id'] = booking_id
        booking_data['created_at'] = datetime.now().isoformat()
        booking_data['status'] = 'pending_payment'
        
        bookings.append(booking_data)
        self._write_file(self.bookings_file, bookings)
        
        return booking_id
    
    def update_booking_status(self, booking_id: str, status: str, notes: str = ''):
        """Update booking status (pending_payment, confirmed, cancelled, completed)"""
        bookings = self._read_file(self.bookings_file)
        
        for booking in bookings:
            if booking['booking_id'] == booking_id:
                booking['status'] = status
                booking['status_updated_at'] = datetime.now().isoformat()
                if notes:
                    booking['status_notes'] = notes
                break
        
        self._write_file(self.bookings_file, bookings)
    
    def get_booking(self, booking_id: str) -> Optional[Dict]:
        """Get a specific booking by ID"""
        bookings = self._read_file(self.bookings_file)
        
        for booking in bookings:
            if booking['booking_id'] == booking_id:
                return booking
        
        return None
    
    def get_pending_bookings(self) -> List[Dict]:
        """Get all bookings pending payment"""
        bookings = self._read_file(self.bookings_file)
        return [b for b in bookings if b['status'] == 'pending_payment']
    
    def save_customer(self, user_id: int, customer_data: Dict):
        """Save or update customer information"""
        customers = self._read_file(self.customers_file)
        
        # Check if customer exists
        existing = None
        for i, customer in enumerate(customers):
            if customer['user_id'] == user_id:
                existing = i
                break
        
        customer_data['user_id'] = user_id
        customer_data['updated_at'] = datetime.now().isoformat()
        
        if existing is not None:
            customers[existing] = customer_data
        else:
            customer_data['created_at'] = datetime.now().isoformat()
            customers.append(customer_data)
        
        self._write_file(self.customers_file, customers)
    
    def get_customer(self, user_id: int) -> Optional[Dict]:
        """Get customer by user_id"""
        customers = self._read_file(self.customers_file)
        
        for customer in customers:
            if customer['user_id'] == user_id:
                return customer
        
        return None
    
    def log_conversation(self, user_id: int, message: str, response: str):
        """Log conversation for analytics"""
        conversations = self._read_file(self.conversations_file)
        
        log_entry = {
            'user_id': user_id,
            'timestamp': datetime.now().isoformat(),
            'message': message,
            'response': response
        }
        
        conversations.append(log_entry)
        
        # Keep only last 1000 conversations to save space
        if len(conversations) > 1000:
            conversations = conversations[-1000:]
        
        self._write_file(self.conversations_file, conversations)
    
    def get_customer_bookings(self, user_id: int) -> List[Dict]:
        """Get all bookings for a specific customer"""
        bookings = self._read_file(self.bookings_file)
        return [b for b in bookings if b.get('user_id') == user_id]
    
    def get_stats(self) -> Dict:
        """Get basic statistics"""
        bookings = self._read_file(self.bookings_file)
        customers = self._read_file(self.customers_file)
        
        stats = {
            'total_bookings': len(bookings),
            'pending_bookings': len([b for b in bookings if b['status'] == 'pending_payment']),
            'confirmed_bookings': len([b for b in bookings if b['status'] == 'confirmed']),
            'total_customers': len(customers),
            'total_revenue_pending': sum([b.get('total', 0) for b in bookings if b['status'] == 'pending_payment']),
            'total_revenue_confirmed': sum([b.get('total', 0) for b in bookings if b['status'] == 'confirmed'])
        }
        
        return stats


# Example usage:
if __name__ == '__main__':
    db = SafiriDatabase()
    
    # Example: Save a booking
    booking = {
        'user_id': 123456,
        'username': 'tourist123',
        'safari_type': 'Masai Mara Safari',
        'dates': 'March 15-18, 2026',
        'travelers': '2 adults',
        'budget': 'Mid-Range',
        'total': 130000,
        'deposit': 39000
    }
    
    booking_id = db.save_booking(booking)
    print(f"Booking saved: {booking_id}")
    
    # Get stats
    stats = db.get_stats()
    print(f"Stats: {stats}")
