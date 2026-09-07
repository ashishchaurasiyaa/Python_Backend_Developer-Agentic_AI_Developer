"""
Create a class Movie with the following:
Attributes:
movie_name →> name of the movie
total_seats →> total seats available in the theatre ticket_price → price per ticket booked_seats → starts at o
Methods:
book_ticket(num_tickets) - books the given number of tickets. If enough seats are available, confirm the booking and show the total amount to pay. If not, show "Sorry, not enough seats available"
show_status() - displays movie name, seats available, and seats booked so far
"""

class Movie:
    def __init__(self,movie_name: str, total_seats: int, ticket_price: int):
        self.movie_name = movie_name
        self.total_seats = total_seats
        self.ticket_price = ticket_price
        self.booked_seats = 0


    def show_status(self):
        print(f"Movie Name: {self.movie_name}")
        print(f"Total Seats available: {self.total_seats}")

