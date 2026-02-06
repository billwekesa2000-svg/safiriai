"""
SafiriAI Admin Dashboard
View bookings, confirm payments, send updates to customers

Run this locally to manage your bookings
"""

import sys
from database import SafiriDatabase
from datetime import datetime
import json

class AdminDashboard:
    def __init__(self):
        self.db = SafiriDatabase()
    
    def display_menu(self):
        """Show admin menu"""
        print("\n" + "="*60)
        print("🦁 SAFIRIAI ADMIN DASHBOARD 🦁".center(60))
        print("="*60)
        print("\n1. View All Bookings")
        print("2. View Pending Bookings (Awaiting Payment)")
        print("3. View Confirmed Bookings")
        print("4. Search Booking by ID")
        print("5. Confirm Payment")
        print("6. View Statistics")
        print("7. Export Bookings to CSV")
        print("0. Exit")
        print("\n" + "="*60)
    
    def view_all_bookings(self):
        """Display all bookings"""
        bookings = self.db._read_file(self.db.bookings_file)
        
        if not bookings:
            print("\n📭 No bookings yet!")
            return
        
        print(f"\n📚 Total Bookings: {len(bookings)}\n")
        
        for booking in bookings:
            self._display_booking(booking)
    
    def view_pending_bookings(self):
        """Display pending bookings"""
        bookings = self.db.get_pending_bookings()
        
        if not bookings:
            print("\n✅ No pending bookings!")
            return
        
        print(f"\n⏳ Pending Bookings: {len(bookings)}\n")
        
        for booking in bookings:
            self._display_booking(booking)
    
    def view_confirmed_bookings(self):
        """Display confirmed bookings"""
        bookings = self.db._read_file(self.db.bookings_file)
        confirmed = [b for b in bookings if b['status'] == 'confirmed']
        
        if not confirmed:
            print("\n📭 No confirmed bookings yet!")
            return
        
        print(f"\n✅ Confirmed Bookings: {len(confirmed)}\n")
        
        for booking in confirmed:
            self._display_booking(booking)
    
    def _display_booking(self, booking):
        """Display a single booking"""
        print("─" * 60)
        print(f"🆔 Booking ID: {booking.get('booking_id', 'N/A')}")
        print(f"📅 Created: {booking.get('created_at', 'N/A')}")
        print(f"👤 Customer: @{booking.get('username', 'N/A')} (ID: {booking.get('user_id', 'N/A')})")
        print(f"🦁 Safari: {booking.get('data', {}).get('safari_type', 'N/A')}")
        print(f"📆 Dates: {booking.get('data', {}).get('dates', 'N/A')}")
        print(f"👥 Travelers: {booking.get('data', {}).get('travelers', 'N/A')}")
        print(f"💰 Total: KES {booking.get('total', 0):,}")
        print(f"💵 Deposit: KES {booking.get('deposit', 0):,}")
        print(f"📊 Status: {booking.get('status', 'N/A').upper()}")
        
        if booking.get('status_notes'):
            print(f"📝 Notes: {booking.get('status_notes')}")
        
        print()
    
    def search_booking(self):
        """Search for a specific booking"""
        booking_id = input("\nEnter Booking ID: ").strip().upper()
        booking = self.db.get_booking(booking_id)
        
        if booking:
            self._display_booking(booking)
        else:
            print(f"\n❌ Booking {booking_id} not found!")
    
    def confirm_payment(self):
        """Confirm payment for a booking"""
        booking_id = input("\nEnter Booking ID to confirm: ").strip().upper()
        booking = self.db.get_booking(booking_id)
        
        if not booking:
            print(f"\n❌ Booking {booking_id} not found!")
            return
        
        if booking['status'] != 'pending_payment':
            print(f"\n⚠️  Booking status is already: {booking['status']}")
            return
        
        self._display_booking(booking)
        
        confirm = input("\nConfirm this payment? (yes/no): ").strip().lower()
        
        if confirm == 'yes':
            notes = input("Add confirmation notes (optional): ").strip()
            self.db.update_booking_status(booking_id, 'confirmed', notes)
            print(f"\n✅ Booking {booking_id} confirmed!")
            print("\n📧 Remember to send confirmation email to customer!")
            print(f"   Customer Telegram: @{booking.get('username', 'N/A')}")
        else:
            print("\n❌ Confirmation cancelled")
    
    def view_stats(self):
        """Display statistics"""
        stats = self.db.get_stats()
        
        print("\n" + "="*60)
        print("📊 SAFIRIAI STATISTICS".center(60))
        print("="*60)
        print(f"\n📚 Total Bookings: {stats['total_bookings']}")
        print(f"⏳ Pending Payment: {stats['pending_bookings']}")
        print(f"✅ Confirmed: {stats['confirmed_bookings']}")
        print(f"👥 Total Customers: {stats['total_customers']}")
        print(f"\n💰 Revenue Pending: KES {stats['total_revenue_pending']:,}")
        print(f"💵 Revenue Confirmed: KES {stats['total_revenue_confirmed']:,}")
        print(f"💎 Total Revenue: KES {stats['total_revenue_pending'] + stats['total_revenue_confirmed']:,}")
        print()
    
    def export_to_csv(self):
        """Export bookings to CSV"""
        import csv
        
        bookings = self.db._read_file(self.db.bookings_file)
        
        if not bookings:
            print("\n📭 No bookings to export!")
            return
        
        filename = f"safiriai_bookings_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # Headers
            writer.writerow([
                'Booking ID', 'Date', 'Customer Username', 'User ID',
                'Safari Type', 'Travel Dates', 'Travelers', 'Budget',
                'Total (KES)', 'Deposit (KES)', 'Status'
            ])
            
            # Data
            for booking in bookings:
                data = booking.get('data', {})
                writer.writerow([
                    booking.get('booking_id', ''),
                    booking.get('created_at', ''),
                    booking.get('username', ''),
                    booking.get('user_id', ''),
                    data.get('safari_type', ''),
                    data.get('dates', ''),
                    data.get('travelers', ''),
                    data.get('budget', ''),
                    booking.get('total', 0),
                    booking.get('deposit', 0),
                    booking.get('status', '')
                ])
        
        print(f"\n✅ Exported to: {filename}")
    
    def run(self):
        """Run the admin dashboard"""
        while True:
            self.display_menu()
            choice = input("Enter your choice: ").strip()
            
            if choice == '1':
                self.view_all_bookings()
            elif choice == '2':
                self.view_pending_bookings()
            elif choice == '3':
                self.view_confirmed_bookings()
            elif choice == '4':
                self.search_booking()
            elif choice == '5':
                self.confirm_payment()
            elif choice == '6':
                self.view_stats()
            elif choice == '7':
                self.export_to_csv()
            elif choice == '0':
                print("\n👋 Goodbye!")
                break
            else:
                print("\n❌ Invalid choice!")
            
            input("\nPress Enter to continue...")

if __name__ == '__main__':
    dashboard = AdminDashboard()
    dashboard.run()
