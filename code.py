import datetime as dt
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import sqlite3
conn = sqlite3.connect("bookings.db")
cursor = conn.cursor()
cursor.execute("""
    CREATE TABLE IF NOT EXISTS bookings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guest TEXT,
        check_in TEXT,
        check_out TEXT,
        fee REAL
    )
""")
conn.commit()
bookings = []
def saveBooking(Pguest, Pcheck_in_date, Pcheck_out_date,Pfee):
    #check if there are clashes
    clashed = False
    for booking in bookings:
        if booking[1] <= Pcheck_in_date <= booking[2]: #if checkin is between an existing booking
            print ("dates taken (check in between existing booking)")
            clashed = True
        elif booking[1] <= Pcheck_out_date <= booking[2]: #if checkout is in between an existing booking
            print ("dates taken (checkout between existing booking)")
            clashed = True
        elif  Pcheck_in_date <= booking[1] and booking [2] <= Pcheck_out_date:
            # if check in is before the said existing booking
            # and the check out is after the existing booking
            # the existing booking lies between the new booking so the dates are taken
            print ("dates taken (existing booking lies between chosen dates)")
            clashed = True
    if clashed:
            Pcheck_in_date = inputDate()
            Pcheck_out_date = inputDate()
            saveBooking(Pguest, Pcheck_in_date, Pcheck_out_date, Pfee)
    else:
        newBooking = [Pguest, Pcheck_in_date, Pcheck_out_date,Pfee]
        bookings.append(newBooking)
def createBooking(pRate):
    guest = input("Enter your guest's name: ")
    check_in_date = inputDate()
    check_out_date = inputDate()
    while check_in_date > check_out_date:  # re-ask if checkout is before checkin
        print("invalid date, check out must be after check in")
        check_in_date = inputDate()
        check_out_date = inputDate()
    total_fee = (check_out_date - check_in_date).days*pRate
    saveBooking(guest,check_in_date,check_out_date,total_fee)
    createInvoice(guest,check_in_date,check_out_date,total_fee)
def inputDate():
    invalid = True
    while invalid:
        day = int(input("Enter day"))
        month = int(input ("Enter month"))
        year = int(input ("Enter year"))
        try:
            date = dt.date(year, month, day)
            invalid = False
        except ValueError:
            print ("Invalid date (Value error)")
    return date
def sortBookings(sortingby, reverse=False):
    if sortingby == 0:
        return bookings
    return sorted(bookings, key=lambda x: x[sortingby], reverse=reverse)

def showBookings(ask_sort=True):
    if ask_sort:
        invalid = True
        while invalid:
            raw = input("enter 1 to sort by check in date, 2 for check out date, 0 for no sorting: ")
            try:
                sortby = int(raw)
                if sortby in (0, 1, 2):
                    invalid = False
                else:
                    print("Please enter 0, 1, or 2")
            except ValueError:
                print("Invalid (Value error)")

        reverse = False
        if sortby != 0:
            direction = input("Enter 1 for earliest first, 2 for latest first: ")
            reverse = (direction == "2")

        display_list = sortBookings(sortby, reverse)
    else:
        display_list = bookings

    count = 1
    for booking in display_list:
        checkIn = booking[1].strftime("%d/%m/%Y")
        checkOut = booking[2].strftime("%d/%m/%Y")
        print(str(count) + ")" + booking[0] + "," + checkIn + "," + checkOut + "," + "£" + str(booking[3]))
        count += 1

def deleteBooking():
    showBookings(ask_sort=False)
    invalid = True
    while invalid:
        deleted = input("Enter your choice (0 to cancel): ")
        try:
            deleted = int(deleted)
            if deleted == 0:
                invalid = False
            elif 1 <= deleted <= len(bookings):
                del bookings[deleted - 1]
                invalid = False
            else:
                print("No booking with that number")
        except ValueError:
            print("Invalid (Value error)")
def searchByName():
    search = input("Enter name to search for: ")
    count = 1
    for booking in bookings:
        if search.lower() in booking[0].lower():
            checkIn = booking[1].strftime("%d/%m/%Y")
            checkOut = booking[2].strftime("%d/%m/%Y")
            print(str(count) + ")" + booking[0] + "," + checkIn + "," + checkOut + "," + "£" + str(booking[3]))
            count += 1
    if count == 1:  # NEW: count never incremented, so nothing matched
        print("No bookings found for that name")

def searchByDate():
    print("Enter the date to search for:")
    search_date = inputDate()
    count = 1
    for booking in bookings:
        if booking[1] <= search_date <= booking[2]:
            checkIn = booking[1].strftime("%d/%m/%Y")
            checkOut = booking[2].strftime("%d/%m/%Y")
            print(str(count) + ")" + booking[0] + "," + checkIn + "," + checkOut + "," + "£" + str(booking[3]))
            count += 1
    if count == 1:  # NEW: same idea
        print("No bookings found for that date")
def createInvoice(Pguest, Pcheck_in_date, Pcheck_out_date, Pfee):
    Pcheck_in_date = Pcheck_in_date.strftime("%d/%m/%Y")
    Pcheck_out_date = Pcheck_out_date.strftime("%d/%m/%Y")
    Pfee = str(Pfee)

    c = canvas.Canvas("test_invoice.pdf", pagesize=letter)
    width, height = letter

    # Title
    c.setFont("Helvetica-Bold", 24)
    c.drawString(50, height - 80, "Invoice")

    # horizontal line under the title
    c.setLineWidth(1)
    c.line(50, height - 90, width - 50, height - 90)

    # body text
    c.setFont("Helvetica", 12)
    y = height - 130  # tracks vertical position, so we can space lines evenly
    line_gap = 25

    c.drawString(50, y, "Guest: " + Pguest)
    y -= line_gap
    c.drawString(50, y, "Check-in: " + Pcheck_in_date)
    y -= line_gap
    c.drawString(50, y, "Check-out: " + Pcheck_out_date)
    y -= line_gap

    # a second line before the total, to set it apart
    c.line(50, y, width - 50, y)
    y -= line_gap

    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, "Total Fee: £" + Pfee)
    c.save()
def main(): # mainloop
    while True:
        print("1. Create Booking")
        print("2. See bookings")
        print("3. Remove booking")
        print("4. Search bookings")
        choice = input("Choose an option: ")

        if choice == "1":
            rate = int(input("Enter rate: "))
            createBooking(rate)
        elif choice == "2":
            showBookings()
        elif choice == "3":
            deleteBooking()
        elif choice == "4":
            searchFunction = input("for search by name enter 1, for search by date enter 2: ")
            if searchFunction == "1":
                searchByName()
            elif searchFunction == "2":
                searchByDate()
            else:
                print("Invalid option")
        else:
            print("Invalid choice, try again")


main()